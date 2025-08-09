from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from .models import User, Category, Product, Address, Order, Cart, CartItem, Wishlist, WishlistItem, OrderItem, ProductVariant, ReturnRequest, ItemReturnRequest, CouponUsage, Coupon, ReferralReward, ReferralOffer, Wallet, WalletTransaction
from django.db.models import Q
from django.db import models
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
from django.contrib.auth.hashers import check_password
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import random
import re
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.template.loader import get_template
from io import BytesIO
from xhtml2pdf import pisa
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
import razorpay
import hmac
import hashlib
import logging
from decimal import Decimal
from datetime import timedelta
from zoneinfo import ZoneInfo 

logger = logging.getLogger(__name__)

try:
    if hasattr(settings, 'RAZORPAY_KEY_ID') and hasattr(settings, 'RAZORPAY_KEY_SECRET'):
        if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            logger.info("Razorpay client initialized successfully")
        else:
            razorpay_client = None
            logger.error("Razorpay keys are empty")
    else:
        razorpay_client = None
        logger.error("Razorpay keys not found in settings")
except Exception as e:
    razorpay_client = None
    logger.error(f"Failed to initialize Razorpay client: {e}")

def generate_otp():
    return str(random.randint(100000, 999999))

def check_user_blocked(user):
    if user.is_authenticated and not user.is_active and not user.is_staff:
        return True
    return False

@never_cache
def front_page(request):
    if request.user.is_authenticated:
        if check_user_blocked(request.user):
            logout(request)
            request.session.flush()
            messages.error(request, "Your account has been temporarily blocked. Please contact support if you believe this is an error.")
            return render(request, 'front.html')
        return redirect('home')
    return render(request, 'front.html')

@never_cache
def sign_up_page(request, token=None):
    """
    Unified signup page that handles both regular signup and referral signup
    """
    if request.user.is_authenticated:
        if check_user_blocked(request.user):
            logout(request)
            request.session.flush()
            messages.error(request, "Your account has been temporarily blocked. Please contact support if you believe this is an error.")
            return render(request, 'signup.html')
        return redirect('home')
    
    # Handle referral token if provided
    referrer = None
    referral_code = ''
    
    if token:
        try:
            referrer = User.objects.get(referral_token=token, is_active=True)
            referral_code = referrer.referral_code
        except User.DoesNotExist:
            messages.error(request, "Invalid referral link.")
            return redirect('sign_up')
    
    if request.method == 'POST':
        full_name = request.POST.get('fullname', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirmPassword', '')
        ph_number = request.POST.get('ph_number', '').strip()
        referral_code_input = request.POST.get('referral_code', '').strip().upper()
        terms_accepted = request.POST.get('terms') == 'on'
        
        errors = {}
        
        # Validation
        if not re.fullmatch(r'[A-Za-z ]+', full_name):
            errors['full_name'] = "Name must contain only letters and spaces."
        
        if not email:
            errors['email'] = "Enter your email."
        elif User.objects.filter(email=email).exists():
            errors['email'] = "Email is already registered."
        
        if not re.fullmatch(r'^[0-9]{10,15}$', ph_number):
            errors['ph_number'] = "Enter a valid 10-digit number."
        
        if len(password) < 8 or not re.search(r'[^A-Za-z0-9]', password):
            errors['password'] = "Password must be at least 8 characters long and include a special character."
        
        if password != confirm_password:
            errors['confirm_password'] = "Passwords do not match."
        
        if not terms_accepted:
            errors['terms'] = "You must accept the terms and conditions."
        
        # Validate referral code if provided
        referrer_user = None
        if referral_code_input:
            try:
                referrer_user = User.objects.get(referral_code=referral_code_input, is_active=True)
            except User.DoesNotExist:
                errors['referral_code'] = "Invalid referral code."
        elif referrer:  # If came through referral link
            referrer_user = referrer
        
        if errors:
            return render(request, 'signup.html', {
                'errors': errors,
                'form_data': {
                    'fullname': full_name,
                    'email': email,
                    'ph_number': ph_number,
                    'referral_code': referral_code_input or referral_code,
                    'terms': terms_accepted,
                },
                'referrer': referrer
            })
        else:
            try:
                # Create user
                otp = generate_otp()
                hashed_password = make_password(password)
                user = User.objects.create(
                    full_name=full_name,
                    email=email,
                    password=hashed_password,
                    ph_number=ph_number,
                    otp_code=otp,
                    referred_by=referrer_user,
                    is_verified=True if referrer_user else False  # Auto-verify referred users
                )
                
                # Process referral reward if referrer exists
                if referrer_user:
                    active_referral_offer = ReferralOffer.objects.filter(is_active=True).first()
                    if active_referral_offer:
                        # Check if referrer hasn't exceeded max referrals
                        if not active_referral_offer.max_referrals or \
                           ReferralReward.objects.filter(referrer=referrer_user).count() < active_referral_offer.max_referrals:
                            
                            # Generate coupon for referrer
                            coupon = active_referral_offer.generate_referral_coupon(referrer_user)
                            
                            # Create referral reward record
                            ReferralReward.objects.create(
                                referrer=referrer_user,
                                referred_user=user,
                                referral_offer=active_referral_offer,
                                coupon=coupon,
                                reward_amount=active_referral_offer.reward_value
                            )
                            
                            messages.success(request, f"Account created successfully! {referrer_user.full_name} has received a referral reward.")
                        else:
                            messages.success(request, "Account created successfully!")
                    else:
                        messages.success(request, "Account created successfully!")
                
                # Send OTP email
                send_mail(
                    subject='Your OTP Verification Code',
                    message=f'Your OTP code is: {otp}',
                    from_email='muhammaduhasanulbanna652@gmail.com',
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                request.session['email'] = email
                request.session['otp_verified'] = False
                request.session['otp_sent_time'] = timezone.now().timestamp()
                
                if referrer_user:
                    # Auto-login referred users after OTP verification
                    request.session['auto_login_after_otp'] = True
                
                return redirect('verify')
                
            except Exception as e:
                logger.error(f"Error creating user: {e}")
                messages.error(request, "An error occurred while creating your account. Please try again.")
                return render(request, 'signup.html', {
                    'form_data': {
                        'fullname': full_name,
                        'email': email,
                        'ph_number': ph_number,
                        'referral_code': referral_code_input or referral_code,
                        'terms': terms_accepted,
                    },
                    'referrer': referrer
                })
    
    # GET request - show form
    context = {
        'referrer': referrer,
        'form_data': {
            'referral_code': referral_code
        }
    }
    return render(request, 'signup.html', context)

def otp_verify(request):
    if request.user.is_authenticated:
        if check_user_blocked(request.user):
            logout(request)
            request.session.flush()
            messages.error(request, "Your account has been temporarily blocked. Please contact support if you believe this is an error.")
            return redirect('front')
        return redirect('home')
    
    email = request.session.get('email')
    if not email:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('sign_up')
    
    if request.method == "POST":
        otp_input = ''.join([
            request.POST.get('otp1', ''),
            request.POST.get('otp2', ''),
            request.POST.get('otp3', ''),
            request.POST.get('otp4', ''),
            request.POST.get('otp5', ''),
            request.POST.get('otp6', ''),
        ])
        
        try:
            user = User.objects.get(email=email)
            if user.otp_code == otp_input:
                user.is_verified = True
                user.otp_code = ''
                user.save()
                request.session['otp_verified'] = True
                request.session.pop('otp_sent_time', None)
                
                # Check if should auto-login (for referred users)
                if request.session.get('auto_login_after_otp'):
                    request.session.pop('auto_login_after_otp', None)
                    request.session.pop('email', None)
                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                    login(request, user)
                    messages.success(request, "Email verified successfully! Welcome to AZRION!")
                    return redirect('home')
                else:
                    messages.success(request, "Email verified successfully!")
                    return redirect('login')
            else:
                messages.error(request, "Invalid OTP. Please check your email and try again.")
                return render(request, 'verification.html', {'email': email})
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('sign_up')
    
    return render(request, 'verification.html', {'email': email})

def resend_otp(request):
    if request.method == 'POST':
        email = request.session.get('email')
        otp_verified = request.session.get('otp_verified', False)
        
        if otp_verified:
            messages.info(request, 'You are already verified.')
            return redirect('home')
        
        if not email:
            messages.error(request, 'Session expired. Please sign up again.')
            return redirect('sign_up')
        
        try:
            user = User.objects.get(email=email)
            new_otp = generate_otp()
            user.otp_code = new_otp
            user.save()
            
            send_mail(
                subject='Your New OTP Code',
                message=f'Your new OTP is: {new_otp}',
                from_email='muhammaduhasanulbanna652@gmail.com',
                recipient_list=[email],
                fail_silently=False,
            )
            
            request.session['otp_sent_time'] = timezone.now().timestamp()
            messages.success(request, 'New OTP has been sent to your email.')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
    
    return redirect('verify')

@never_cache
def login_page(request):
    if request.user.is_authenticated:
        if check_user_blocked(request.user):
            logout(request)
            request.session.flush()
            messages.error(request, "Your account has been temporarily blocked. Please contact support if you believe this is an error.")
            return render(request, 'login.html')
        return redirect('home')
    
    errors = {}
    form_data = {}
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        form_data = {'email': email}
        
        user = None
        if not email:
            errors['email'] = "Email is required."
        elif not User.objects.filter(email=email).exists():
            errors['email'] = "No account found with this email."
        else:
            user = User.objects.get(email=email)
        
        if not password:
            errors['password'] = "Password is required."
        elif user and not check_password(password, user.password):
            errors['password'] = "Incorrect password."
        
        if user and not user.is_active and not user.is_staff:
            errors['email'] = "Your account has been temporarily blocked. Please contact support."
        
        if errors:
            return render(request, 'login.html', {
                'errors': errors,
                'form_data': form_data
            })
        
        user.last_login = timezone.now()
        user.save()
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        
        if user.is_staff:
            return redirect('user_management')
        else:
            return redirect('home')
    
    return render(request, 'login.html')

@never_cache
def forgot_password(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, "Email is required.")
            return render(request, 'forgot_password.html', {'form_data': {'email': email}})
        
        try:
            user = User.objects.get(email=email)
            reset_otp = generate_otp()
            user.otp_code = reset_otp
            user.save()
            
            send_mail(
                subject='Password Reset OTP',
                message=f'Your password reset OTP is: {reset_otp}. This OTP is valid for 10 minutes.',
                from_email='muhammaduhasanulbanna652@gmail.com',
                recipient_list=[email],
                fail_silently=False,
            )
            
            request.session['reset_email'] = email
            request.session['reset_otp_sent_time'] = timezone.now().timestamp()
            messages.success(request, "Password reset OTP has been sent to your email.")
            return redirect('verify_reset_otp')
        except User.DoesNotExist:
            messages.error(request, "No account found with this email address.")
            return render(request, 'forgot_password.html', {'form_data': {'email': email}})
    
    return render(request, 'forgot_password.html')

@never_cache
def verify_reset_otp(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    email = request.session.get('reset_email')
    if not email:
        messages.error(request, "Session expired. Please start the password reset process again.")
        return redirect('forgot_password')
    
    if request.method == 'POST':
        otp_input = ''.join([
            request.POST.get('otp1', ''),
            request.POST.get('otp2', ''),
            request.POST.get('otp3', ''),
            request.POST.get('otp4', ''),
            request.POST.get('otp5', ''),
            request.POST.get('otp6', ''),
        ])
        
        try:
            user = User.objects.get(email=email)
            if user.otp_code == otp_input:
                request.session['otp_verified_for_reset'] = True
                request.session.pop('reset_otp_sent_time', None)
                messages.success(request, "OTP verified successfully!")
                return redirect('reset_password')
            else:
                messages.error(request, "Invalid OTP. Please check your email and try again.")
                return render(request, 'verify_reset_otp.html', {'email': email})
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('forgot_password')
    
    return render(request, 'verify_reset_otp.html', {'email': email})

@never_cache
def reset_password(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    email = request.session.get('reset_email')
    otp_verified = request.session.get('otp_verified_for_reset', False)
    
    if not email or not otp_verified:
        messages.error(request, "Unauthorized access. Please start the password reset process again.")
        return redirect('forgot_password')
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        errors = {}
        
        if len(new_password) < 8 or not re.search(r'[^A-Za-z0-9]', new_password):
            errors['new_password'] = "Password must be at least 8 characters long and include a special character."
        
        if new_password != confirm_password:
            errors['confirm_password'] = "Passwords do not match."
        
        if errors:
            return render(request, 'reset_password.html', {'errors': errors})
        
        try:
            user = User.objects.get(email=email)
            user.password = make_password(new_password)
            user.otp_code = ''
            user.save()
            
            request.session.pop('reset_email', None)
            request.session.pop('otp_verified_for_reset', None)
            messages.success(request, "Password reset successfully! You can now login with your new password.")
            return redirect('login')
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('forgot_password')
    
    return render(request, 'reset_password.html')

def resend_reset_otp(request):
    if request.method == 'POST':
        email = request.session.get('reset_email')
        if not email:
            messages.error(request, "Session expired. Please start the password reset process again.")
            return redirect('forgot_password')
        
        try:
            user = User.objects.get(email=email)
            new_otp = generate_otp()
            user.otp_code = new_otp
            user.save()
            
            send_mail(
                subject='New Password Reset OTP',
                message=f'Your new password reset OTP is: {new_otp}. This OTP is valid for 10 minutes.',
                from_email='muhammaduhasanulbanna652@gmail.com',
                recipient_list=[email],
                fail_silently=False,
            )
            
            request.session['reset_otp_sent_time'] = timezone.now().timestamp()
            messages.success(request, "New OTP has been sent to your email.")
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
    
    return redirect('verify_reset_otp')

def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('front')

def t_o_s_page(request):
    return render(request, 'terms_of_service.html')

def privacy_policy_page(request):
    return render(request, 'privacy_policy.html')

@never_cache
@login_required
def home_page(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked. Please contact support if you believe this is an error.")
        return redirect('front')
    
    if request.user.is_staff:
        return redirect('user_management')
    
    now_utc = timezone.now()
    now = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))
    
    featured_products = Product.objects.filter(is_deleted=False).select_related('category').prefetch_related('variants__images')[:6]
    
    for product in featured_products:
        original_product_offer = product.product_offer or 0
        
        # Get highest valid category offer (if exists)
        category_offers = product.category.category_offers.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        ).order_by('-discount_percentage')
        
        category_offer = category_offers.first().discount_percentage if category_offers.exists() else 0
        best_offer = max(original_product_offer, category_offer)
        product.product_offer = best_offer
        
        if best_offer > 0:
            discount_amount = (product.price * best_offer) / 100
            product.discounted_price = product.price - discount_amount
        else:
            product.discounted_price = product.price
        
        product.display_image = product.get_main_image()
    
    categories = Category.objects.filter(is_deleted=False)[:3]
    
    return render(request, 'home.html', {
        'featured_products': featured_products,
        'categories': categories
    })

@never_cache
@login_required
def product_list(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    sort_by = request.GET.get('sort', 'newest')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    
    now = timezone.now()
    
    # Base queryset
    products = Product.objects.filter(is_deleted=False).select_related('category').prefetch_related('variants__images')
    
    # Prepare product list for in-memory manipulation
    products_list = list(products)
    
    # Apply category offers if higher than product offers
    for product in products_list:
        product_offer = product.product_offer or 0
        
        # Get valid category offer (if any)
        category_offers = product.category.category_offers.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        ).order_by('-discount_percentage')
        
        category_offer = category_offers.first().discount_percentage if category_offers.exists() else 0
        
        # Decide final offer
        best_offer = max(product_offer, category_offer)
        product.product_offer = best_offer
        
        if best_offer > 0:
            discount_amount = (product.price * best_offer) / 100
            product.discounted_price = product.price - discount_amount
        else:
            product.discounted_price = product.price
        
        product.display_image = product.get_main_image()
    
    # Filtering
    if query:
        products_list = [p for p in products_list if
            query.lower() in p.product_name.lower() or
            query.lower() in p.product_description.lower() or
            query.lower() in p.category.name.lower()
        ]
    
    if category_id:
        try:
            category_id_int = int(category_id)
            products_list = [p for p in products_list if p.category.id == category_id_int]
        except (ValueError, TypeError):
            category_id = ''
    
    if min_price:
        try:
            min_price_val = float(min_price)
            products_list = [p for p in products_list if p.discounted_price >= min_price_val]
        except (ValueError, TypeError):
            min_price = ''
    
    if max_price:
        try:
            max_price_val = float(max_price)
            products_list = [p for p in products_list if p.discounted_price <= max_price_val]
        except (ValueError, TypeError):
            max_price = ''
    
    # Sorting
    if sort_by == 'price_low':
        products_list.sort(key=lambda p: p.discounted_price)
    elif sort_by == 'price_high':
        products_list.sort(key=lambda p: p.discounted_price, reverse=True)
    elif sort_by == 'name_asc':
        products_list.sort(key=lambda p: p.product_name)
    elif sort_by == 'name_desc':
        products_list.sort(key=lambda p: p.product_name, reverse=True)
    elif sort_by == 'oldest':
        products_list.sort(key=lambda p: p.created_at)
    else:
        products_list.sort(key=lambda p: p.created_at, reverse=True)
    
    # Paginator
    paginator = Paginator(products_list, 12)
    page = request.GET.get('page')
    try:
        products_page = paginator.page(page)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)
    
    # For price slider range
    all_prices = [p.discounted_price for p in products_list]
    if all_prices:
        min_range = min(all_prices)
        max_range = max(all_prices)
    else:
        min_range = 0
        max_range = 10000
    
    categories = Category.objects.filter(is_deleted=False).order_by('name')
    
    context = {
        'products': products_page,
        'categories': categories,
        'query': query,
        'selected_category': str(category_id) if category_id else '',
        'sort_by': sort_by,
        'min_price': min_price,
        'max_price': max_price,
        'price_range': {'min_price': min_range, 'max_price': max_range},
        'total_products': paginator.count,
    }
    
    return render(request, 'product_list.html', context)

@never_cache
@login_required
def product_detail_page(request, product_id):
    try:
        product = get_object_or_404(Product, id=product_id)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect('product_list')
    now =timezone.now()
    product_offer = product.product_offer or 0
    # Get valid category offer (if any)
    category_offers = product.category.category_offers.filter(
        is_active=True,
        valid_from__lte=now,
        valid_until__gte=now
    ).order_by('-discount_percentage')
    
    category_offer = category_offers.first().discount_percentage if category_offers.exists() else 0
    
    # Decide final offer
    best_offer = max(product_offer, category_offer)
    product.product_offer = best_offer
    if best_offer > 0:
        discount_amount = (product.price * best_offer) / 100
        product.discounted_price = product.price - discount_amount
    else:
        product.discounted_price = product.price
        
    if product.product_offer > 0:
        discount_amount = (product.price * product.product_offer) / 100
        product.discounted_price = product.price - discount_amount
        product.savings = discount_amount
    else:
        product.discounted_price = product.price
        product.savings = 0
    
    variants = product.variants.prefetch_related('images').filter(is_active=True)
    available_variants = variants.filter(stock_quantity__gt=0)
    
    reviews = product.reviews.select_related('user').order_by('-created_at')
    rating_stats = {
        'average': product.get_average_rating(),
        'total': product.get_total_reviews(),
        'distribution': product.get_rating_distribution()
    }
    
    related_products = Product.objects.filter(
        category=product.category,
        is_deleted=False
    ).exclude(id=product_id).select_related('category').prefetch_related('variants__images')[:4]
    
    for related_product in related_products:
        if related_product.product_offer > 0:
            discount_amount = (related_product.price * related_product.product_offer) / 100
            related_product.discounted_price = related_product.price - discount_amount
        else:
            related_product.discounted_price = related_product.price
        related_product.display_image = related_product.get_main_image()
    
    specifications = {
        'Category': product.category.name,
        'Total Stock': product.get_total_stock(),
        'Available Colors': variants.count(),
    }
    
    if product.product_offer > 0:
        specifications['Discount'] = f"{product.product_offer}% OFF"
    
    context = {
        'product': product,
        'variants': variants,
        'available_variants': available_variants,
        'reviews': reviews,
        'rating_stats': rating_stats,
        'related_products': related_products,
        'specifications': specifications,
    }
    
    return render(request, 'product_details.html', context)

def check_product_availability(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        return JsonResponse({
            'available': product.is_available(),
            'total_stock': product.get_total_stock(),
            'is_deleted': product.is_deleted
        })
    except Product.DoesNotExist:
        return JsonResponse({
            'available': False,
            'total_stock': 0,
            'is_deleted': True
        })

@never_cache
@login_required
def cart_view(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.items.select_related('product', 'variant').prefetch_related('variant__images')
    
    total_price = 0
    available_items = []
    unavailable_items = []
    
    for item in cart_items:
        item.unit_price = item.get_unit_price()
        item.total_price = item.get_total_price()
        if item.is_available():
            available_items.append(item)
            total_price += item.total_price
        else:
            unavailable_items.append(item)
    
    context = {
        'cart': cart,
        'available_items': available_items,
        'unavailable_items': unavailable_items,
        'total_price': total_price,
        'total_items': len(available_items),
    }
    
    return render(request, 'cart/cart.html', context)

@login_required
@require_POST
def add_to_cart(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        quantity = int(data.get('quantity', 1))
        
        if not product_id or not variant_id:
            return JsonResponse({
                'success': False,
                'message': 'Product and variant are required.'
            })
        
        if quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Invalid quantity.'
            })
        
        try:
            product = Product.objects.get(id=product_id)
            variant = ProductVariant.objects.get(id=variant_id, product=product)
        except (Product.DoesNotExist, ProductVariant.DoesNotExist):
            return JsonResponse({
                'success': False,
                'message': 'Product or variant not found.'
            })
        
        if product.is_deleted or product.category.is_deleted or not variant.is_active:
            return JsonResponse({
                'success': False,
                'message': 'This product is no longer available.'
            })
        
        if variant.stock_quantity < quantity:
            return JsonResponse({
                'success': False,
                'message': f'Only {variant.stock_quantity} items available in stock.'
            })
        
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={'quantity': quantity}
        )
        
        if not item_created:
            new_quantity = cart_item.quantity + quantity
            if new_quantity > variant.stock_quantity:
                return JsonResponse({
                    'success': False,
                    'message': f'Cannot add more items. Only {variant.stock_quantity} available, {cart_item.quantity} already in cart.'
                })
            if new_quantity > 10:
                return JsonResponse({
                    'success': False,
                    'message': 'Maximum 10 items allowed per product.'
                })
            cart_item.quantity = new_quantity
            cart_item.save()
        else:
            if quantity > 10:
                return JsonResponse({
                    'success': False,
                    'message': 'Maximum 10 items allowed per product.'
                })
        
        try:
            wishlist = Wishlist.objects.get(user=request.user)
            wishlist.items.filter(product=product, variant=variant).delete()
        except Wishlist.DoesNotExist:
            pass
        
        cart_total = cart.get_total_items()
        
        return JsonResponse({
            'success': True,
            'message': f'{product.product_name} added to cart successfully!',
            'cart_total': cart_total,
            'item_quantity': cart_item.quantity,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        print(e,'ddddddddddddddddddddd')
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while adding to cart.'
        })

@login_required
@require_POST
def update_cart_quantity(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        cart_item_id = data.get('cart_item_id')
        action = data.get('action')
        
        if not cart_item_id or action not in ['increase', 'decrease']:
            return JsonResponse({
                'success': False,
                'message': 'Invalid request parameters.'
            })
        
        try:
            cart_item = CartItem.objects.get(
                id=cart_item_id,
                cart__user=request.user
            )
        except CartItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cart item not found.'
            })
        
        if not cart_item.is_available():
            return JsonResponse({
                'success': False,
                'message': 'This item is no longer available.'
            })
        
        if action == 'increase':
            new_quantity = cart_item.quantity + 1
        else:
            new_quantity = cart_item.quantity - 1
        
        if new_quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Quantity must be at least 1.'
            })
        
        if new_quantity > cart_item.variant.stock_quantity:
            return JsonResponse({
                'success': False,
                'message': f'Only {cart_item.variant.stock_quantity} items available in stock.'
            })
        
        if new_quantity > 10:
            return JsonResponse({
                'success': False,
                'message': 'Maximum 10 items allowed per product.'
            })
        
        cart_item.quantity = new_quantity
        cart_item.save()
        
        item_total = cart_item.get_total_price()
        cart_total = cart_item.cart.get_total_price()
        cart_items_count = cart_item.cart.get_total_items()
        
        return JsonResponse({
            'success': True,
            'quantity': new_quantity,
            'item_total': float(item_total),
            'cart_total': float(cart_total),
            'cart_items_count': cart_items_count,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while updating quantity.'
        })

@login_required
@require_POST
def remove_from_cart(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        cart_item_id = data.get('cart_item_id')
        
        if not cart_item_id:
            return JsonResponse({
                'success': False,
                'message': 'Cart item ID is required.'
            })
        
        try:
            cart_item = CartItem.objects.get(
                id=cart_item_id,
                cart__user=request.user
            )
            product_name = cart_item.product.product_name
            cart_item.delete()
            
            cart = Cart.objects.get(user=request.user)
            cart_total = cart.get_total_price()
            cart_items_count = cart.get_total_items()
            
            return JsonResponse({
                'success': True,
                'message': f'{product_name} removed from cart.',
                'cart_total': float(cart_total),
                'cart_items_count': cart_items_count,
            })
        except CartItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cart item not found.'
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while removing item.'
        })

@login_required
@require_POST
def clear_cart(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        cart = Cart.objects.get(user=request.user)
        cart.items.all().delete()
        return JsonResponse({
            'success': True,
            'message': 'Cart cleared successfully.',
            'cart_total': 0,
            'cart_items_count': 0,
        })
    except Cart.DoesNotExist:
        return JsonResponse({
            'success': True,
            'message': 'Cart is already empty.',
            'cart_total': 0,
            'cart_items_count': 0,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while clearing cart.'
        })

@never_cache
@login_required
def checkout(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    try:
        cart = Cart.objects.get(user=request.user)
        cart_items = cart.items.select_related('product', 'variant').prefetch_related('variant__images')
        available_items = [item for item in cart_items if item.is_available()]
        
        if not available_items:
            messages.warning(request, "Your cart is empty or contains unavailable items.")
            return redirect('cart_view')
        
        subtotal = sum(item.get_total_price() for item in available_items)
        
        # Calculate coupon discount
        coupon_discount = Decimal('0.00')
        applied_coupon = None
        if cart.applied_coupon:
            applied_coupon = cart.applied_coupon
            is_valid, message = applied_coupon.is_valid(request.user, subtotal)
            if is_valid:
                coupon_discount = applied_coupon.calculate_discount(subtotal)
            else:
                # Remove invalid coupon
                cart.applied_coupon = None
                cart.save()
                messages.warning(request, f"Coupon removed: {message}")
        
        # Calculate shipping and total
        discounted_subtotal = float(subtotal) - float(coupon_discount)
        shipping_charge = Decimal('50.00') if discounted_subtotal < 500 else Decimal('0.00')
        total_amount = float(discounted_subtotal) + float(shipping_charge)
        
        addresses = request.user.addresses.all()
        default_address = addresses.filter(is_default=True).first()
        
        # Check if Razorpay is properly configured
        razorpay_enabled = razorpay_client is not None
        
        # Get available coupons for the user
        available_coupons = get_available_coupons(request.user, subtotal)
        
        context = {
            'cart_items': available_items,
            'addresses': addresses,
            'default_address': default_address,
            'subtotal': subtotal,
            'coupon_discount': coupon_discount,
            'applied_coupon': applied_coupon,
            'shipping_charge': shipping_charge,
            'total_amount': total_amount,
            'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
            'razorpay_enabled': razorpay_enabled,
            'available_coupons': available_coupons,
        }
        
        return render(request, 'cart/checkout.html', context)
    except Cart.DoesNotExist:
        messages.warning(request, "Your cart is empty.")
        return redirect('cart_view')
    
def get_available_coupons(user, cart_total):
    """Get all available coupons for the user"""
    now = timezone.now()
    available_coupons = []

    # Get regular active coupons (public coupons available to all users)
    regular_coupons = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_until__gte=now,
        minimum_amount__lte=cart_total
    ).exclude(
        # Exclude coupons that are tied to referral rewards
        referralreward__isnull=False
    )

    for coupon in regular_coupons:
        # Check if coupon has usage limit
        if coupon.usage_limit:
            current_usage = CouponUsage.objects.filter(coupon=coupon).count()
            if current_usage >= coupon.usage_limit:
                continue
        
        # Check if user has already used this coupon (assuming one use per user)
        if CouponUsage.objects.filter(coupon=coupon, user=user).exists():
            continue
        
        # Calculate discount for display
        discount_amount = coupon.calculate_discount(cart_total)
        
        available_coupons.append({
            'coupon': coupon,
            'discount_amount': discount_amount,
            'type': 'regular'
        })

    # Get referral reward coupons ONLY for the current user
    referral_rewards = ReferralReward.objects.filter(
        referrer=user,  # Only for the current user
        is_claimed=False,
        coupon__isnull=False,
        coupon__is_active=True,
        coupon__valid_from__lte=now,
        coupon__valid_until__gte=now,
        coupon__minimum_amount__lte=cart_total
    ).select_related('coupon')

    for reward in referral_rewards:
        coupon = reward.coupon
        
        # Double check that this referral reward belongs to the current user
        if reward.referrer != user:
            continue
            
        # Check if already used by this user
        if CouponUsage.objects.filter(coupon=coupon, user=user).exists():
            continue
            
        discount_amount = coupon.calculate_discount(cart_total)
        
        available_coupons.append({
            'coupon': coupon,
            'discount_amount': discount_amount,
            'type': 'referral',
            'referral_reward': reward
        })

    # Sort by discount amount (highest first)
    available_coupons.sort(key=lambda x: x['discount_amount'], reverse=True)

    return available_coupons

@login_required
@require_POST
def remove_coupon(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        cart = Cart.objects.get(user=request.user)
        
        if not cart.applied_coupon:
            return JsonResponse({
                'success': False,
                'message': 'No coupon is currently applied.'
            })
        
        coupon_code = cart.applied_coupon.code
        cart.applied_coupon = None
        cart.save()
        
        # Recalculate totals
        cart_items = cart.items.select_related('product', 'variant')
        available_items = [item for item in cart_items if item.is_available()]
        subtotal = sum(item.get_total_price() for item in available_items)
        shipping_charge = Decimal('50.00') if subtotal < 500 else Decimal('0.00')
        total_amount = subtotal + shipping_charge
        
        return JsonResponse({
            'success': True,
            'message': f'Coupon "{coupon_code}" removed successfully.',
            'subtotal': float(subtotal),
            'coupon_discount': 0,
            'shipping_charge': float(shipping_charge),
            'total_amount': float(total_amount)
        })
        
    except Cart.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Cart not found.'
        })
    except Exception as e:
        logger.error(f"Error removing coupon: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while removing the coupon.'
        })

@login_required
@require_POST
def apply_coupon(request):
    from decimal import Decimal
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        coupon_code = data.get('coupon_code', '').strip().upper()
        
        if not coupon_code:
            return JsonResponse({
                'success': False,
                'message': 'Please enter a coupon code.'
            })
        
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cart not found.'
            })
        
        # Check if coupon already applied
        if cart.applied_coupon and cart.applied_coupon.code == coupon_code:
            return JsonResponse({
                'success': False,
                'message': 'This coupon is already applied.'
            })
        
        try:
            coupon = Coupon.objects.get(code=coupon_code)
        except Coupon.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Invalid coupon code.'
            })
        
        # Calculate current cart total
        cart_items = cart.items.select_related('product', 'variant')
        available_items = [item for item in cart_items if item.is_available()]
        subtotal = sum(Decimal(item.get_total_price()) for item in available_items)
        
        # Validate coupon
        is_valid, message = coupon.is_valid(request.user, subtotal)
        if not is_valid:
            return JsonResponse({
                'success': False,
                'message': message
            })
        
        # Apply coupon
        cart.applied_coupon = coupon
        cart.save()
        
        # Calculate new totals
        coupon_discount = coupon.calculate_discount(subtotal)
        discounted_subtotal = subtotal - coupon_discount
        shipping_charge = Decimal('50.00') if subtotal < Decimal('500') else Decimal('0.00')
        total_amount = subtotal + shipping_charge
        
        return JsonResponse({
            'success': True,
            'message': f'Coupon "{coupon_code}" applied successfully!',
            'coupon_code': coupon.code,
            'coupon_description': coupon.description or '',
            'discount_type': coupon.discount_type,
            'discount_value': float(coupon.discount_value),
            'subtotal': float(subtotal),
            'coupon_discount': float(coupon_discount),
            'shipping_charge': float(shipping_charge),
            'total_amount': float(total_amount)
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        logger.error(f"Error applying coupon: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while applying the coupon.'
        })

@login_required
@require_POST
def remove_coupon(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        cart = Cart.objects.get(user=request.user)
        
        if not cart.applied_coupon:
            return JsonResponse({
                'success': False,
                'message': 'No coupon is currently applied.'
            })
        
        coupon_code = cart.applied_coupon.code
        cart.applied_coupon = None
        cart.save()
        
        # Recalculate totals
        cart_items = cart.items.select_related('product', 'variant')
        available_items = [item for item in cart_items if item.is_available()]
        subtotal = sum(item.get_total_price() for item in available_items)
        shipping_charge = Decimal('50.00') if subtotal < 500 else Decimal('0.00')
        total_amount = subtotal + shipping_charge
        
        return JsonResponse({
            'success': True,
            'message': f'Coupon "{coupon_code}" removed successfully.',
            'subtotal': float(subtotal),
            'coupon_discount': 0,
            'shipping_charge': float(shipping_charge),
            'total_amount': float(total_amount)
        })
        
    except Cart.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Cart not found.'
        })
    except Exception as e:
        logger.error(f"Error removing coupon: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while removing the coupon.'
        })

@login_required
@require_POST
def create_razorpay_order(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    if not razorpay_client:
        return JsonResponse({
            'success': False,
            'message': 'Payment gateway is not properly configured. Please contact support.'
        })
    
    try:
        data = json.loads(request.body)
        address_id = data.get('address_id')
        
        if not address_id:
            return JsonResponse({
                'success': False,
                'message': 'Please select a delivery address.'
            })
        
        try:
            address = Address.objects.get(id=address_id, user=request.user)
        except Address.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Invalid delivery address.'
            })
        
        try:
            cart = Cart.objects.get(user=request.user)
            cart_items = cart.items.select_related('product', 'variant')
        except Cart.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cart is empty.'
            })
        
        available_items = [item for item in cart_items if item.is_available()]
        if not available_items:
            return JsonResponse({
                'success': False,
                'message': 'No available items in cart.'
            })
        
        subtotal = sum(item.get_total_price() for item in available_items)
        
        # Handle coupon discount
        coupon_discount = Decimal('0.00')
        applied_coupon = None
        if cart.applied_coupon:
            applied_coupon = cart.applied_coupon
            is_valid, message = applied_coupon.is_valid(request.user, subtotal)
            if is_valid:
                coupon_discount = applied_coupon.calculate_discount(subtotal)
            else:
                cart.applied_coupon = None
                cart.save()
        
        discounted_subtotal = float(subtotal) - float(coupon_discount)
        shipping_charge = Decimal('50.00') if discounted_subtotal < 500 else Decimal('0.00')
        total_amount = float(discounted_subtotal) + float(shipping_charge)
        
        # Create Razorpay order with error handling
        try:
            razorpay_order = razorpay_client.order.create({
                'amount': int(total_amount * 100),  # Amount in paise
                'currency': 'INR',
                'payment_capture': 1
            })
            logger.info(f"Razorpay order created: {razorpay_order['id']}")
        except Exception as e:
            logger.error(f"Failed to create Razorpay order: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to create payment order. Please try again or contact support.'
            })
        
        # Create order in database
        order_number = f"ORD{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
        order = Order.objects.create(
            user=request.user,
            order_number=order_number,
            subtotal=subtotal,
            coupon=applied_coupon,
            coupon_discount=coupon_discount,
            shipping_charge=shipping_charge,
            total_amount=total_amount,
            payment_method='online',
            shipping_address=address,
            status='pending',
            razorpay_order_id=razorpay_order['id']
        )
        
        # Create order items
        for cart_item in available_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                quantity=cart_item.quantity,
                price=cart_item.get_unit_price()
            )
        
        return JsonResponse({
            'success': True,
            'razorpay_order_id': razorpay_order['id'],
            'order_id': order.id,
            'amount': int(total_amount * 100),
            'currency': 'INR',
            'name': 'AZRION',
            'description': f'Order #{order_number}',
            'prefill': {
                'name': request.user.full_name,
                'email': request.user.email,
                'contact': request.user.ph_number
            }
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while creating payment order.'
        })

@csrf_exempt
@login_required
@require_POST
def verify_payment(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    if not razorpay_client:
        return JsonResponse({
            'success': False,
            'message': 'Payment gateway is not properly configured.'
        })
    
    try:
        data = json.loads(request.body)
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')
        order_id = data.get('order_id')
        
        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature, order_id]):
            return JsonResponse({
                'success': False,
                'message': 'Missing payment verification data.'
            })
        
        # Verify signature
        try:
            generated_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode(),
                f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
                hashlib.sha256
            ).hexdigest()
            
            if generated_signature != razorpay_signature:
                logger.error("Payment signature verification failed")
                return JsonResponse({
                    'success': False,
                    'message': 'Payment verification failed.'
                })
        except Exception as e:
            logger.error(f"Error verifying payment signature: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Payment verification failed.'
            })
        
        # Update order
        try:
            order = Order.objects.get(id=order_id, user=request.user)
            order.razorpay_payment_id = razorpay_payment_id
            order.status = 'confirmed'
            order.save()
            
            # Mark coupon as used if applied
            if order.coupon:
                order.coupon.used_count += 1
                order.coupon.save()
                
                # Create coupon usage record
                CouponUsage.objects.create(
                    user=request.user,
                    coupon=order.coupon,
                    order=order
                )
            
            # Update stock and clear cart
            cart = Cart.objects.get(user=request.user)
            for item in order.items.all():
                item.variant.stock_quantity -= item.quantity
                item.variant.save()
            
            cart.items.all().delete()
            cart.applied_coupon = None
            cart.save()
            
            logger.info(f"Payment verified successfully for order {order.order_number}")
            
            return JsonResponse({
                'success': True,
                'message': 'Payment verified successfully!',
                'redirect_url': f'/order-success/{order.id}/'
            })
        
        except Order.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Order not found.'
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        logger.error(f"Error verifying payment: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while verifying payment.'
        })

@login_required
@require_POST
def place_order(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        address_id = data.get('address_id')
        payment_method = data.get('payment_method', 'cod')
        
        if not address_id:
            return JsonResponse({
                'success': False,
                'message': 'Please select a delivery address.'
            })
        
        try:
            address = Address.objects.get(id=address_id, user=request.user)
        except Address.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Invalid delivery address.'
            })
        
        try:
            cart = Cart.objects.get(user=request.user)
            cart_items = cart.items.select_related('product', 'variant')
        except Cart.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cart is empty.'
            })
        
        available_items = [item for item in cart_items if item.is_available()]
        if not available_items:
            return JsonResponse({
                'success': False,
                'message': 'No available items in cart.'
            })
        
        subtotal = sum(item.get_total_price() for item in available_items)
        
        # Handle coupon discount
        coupon_discount = Decimal('0.00')
        applied_coupon = None
        if cart.applied_coupon:
            applied_coupon = cart.applied_coupon
            is_valid, message = applied_coupon.is_valid(request.user, subtotal)
            if is_valid:
                coupon_discount = applied_coupon.calculate_discount(subtotal)
            else:
                cart.applied_coupon = None
                cart.save()
        
        discounted_subtotal = float(subtotal) - float(coupon_discount)
        shipping_charge = Decimal('50.00') if discounted_subtotal < 500 else Decimal('0.00')
        total_amount = float(discounted_subtotal) + float(shipping_charge)
        
        order_number = f"ORD{timezone.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
        order = Order.objects.create(
            user=request.user,
            order_number=order_number,
            subtotal=subtotal,
            coupon=applied_coupon,
            coupon_discount=coupon_discount,
            shipping_charge=shipping_charge,
            total_amount=total_amount,
            payment_method=payment_method,
            shipping_address=address,
            status='pending'
        )
        
        for cart_item in available_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                quantity=cart_item.quantity,
                price=cart_item.get_unit_price()
            )
            cart_item.variant.stock_quantity -= cart_item.quantity
            cart_item.variant.save()
        
        # Mark coupon as used if applied
        if applied_coupon:
            applied_coupon.used_count += 1
            applied_coupon.save()
            
            # Create coupon usage record
            CouponUsage.objects.create(
                user=request.user,
                coupon=applied_coupon,
                order=order
            )
        
        cart.items.all().delete()
        cart.applied_coupon = None
        cart.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Order placed successfully!',
            'order_number': order_number,
            'order_id': order.id,
            'redirect_url': f'/order-success/{order.id}/'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while placing order.'
        })

@never_cache
@login_required
def payment_failure(request, order_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        context = {
            'order': order,
            'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        }
        return render(request, 'cart/payment_failure.html', context)
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('home')

@login_required
@require_POST
def retry_payment(request, order_id):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    if not razorpay_client:
        return JsonResponse({
            'success': False,
            'message': 'Payment gateway is not properly configured.'
        })
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        
        if order.status != 'pending':
            return JsonResponse({
                'success': False,
                'message': 'This order cannot be retried.'
            })
        
        # Create new Razorpay order
        try:
            razorpay_order = razorpay_client.order.create({
                'amount': int(order.total_amount * 100),
                'currency': 'INR',
                'payment_capture': 1
            })
        except Exception as e:
            logger.error(f"Failed to create Razorpay order for retry: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to create payment order. Please try again.'
            })
        
        # Update order with new Razorpay order ID
        order.razorpay_order_id = razorpay_order['id']
        order.save()
        
        return JsonResponse({
            'success': True,
            'razorpay_order_id': razorpay_order['id'],
            'order_id': order.id,
            'amount': int(order.total_amount * 100),
            'currency': 'INR',
            'name': 'AZRION',
            'description': f'Order #{order.order_number}',
            'prefill': {
                'name': request.user.full_name,
                'email': request.user.email,
                'contact': request.user.ph_number
            }
        })
    
    except Order.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Order not found.'
        })
    except Exception as e:
        logger.error(f"Error retrying payment: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while retrying payment.'
        })

@never_cache
@login_required
def order_success(request, order_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        return render(request, 'cart/order_success.html', {'order': order})
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('home')

@never_cache
@login_required
def order_detail(request, order_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        order_items = order.items.select_related('product', 'variant')
        context = {
            'order': order,
            'order_items': order_items,
        }
        return render(request, 'cart/order_detail.html', context)
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('user_orders')

@never_cache
@login_required
def user_profile(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    user = request.user
    addresses = user.addresses.all()
    recent_orders = user.orders.all()[:3]
    
    wishlist_count = 0
    try:
        wishlist = Wishlist.objects.get(user=user)
        wishlist_count = wishlist.items.count()
    except Wishlist.DoesNotExist:
        pass
    
    context = {
        'user': user,
        'addresses': addresses,
        'recent_orders': recent_orders,
        'total_orders': user.orders.count(),
        'wishlist_count': wishlist_count,
    }
    
    return render(request, 'profile/user_profile.html', context)

@never_cache
@login_required
def edit_profile(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    user = request.user
    errors = {}
    form_data = {}
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        ph_number = request.POST.get('ph_number', '').strip()
        profile_image = request.FILES.get('profile_image')
        
        form_data = {
            'full_name': full_name,
            'email': email,
            'ph_number': ph_number,
        }
        
        if not re.fullmatch(r'[A-Za-z ]+', full_name):
            errors['full_name'] = "Name must contain only letters and spaces."
        
        if not email:
            errors['email'] = "Email is required."
        elif email != user.email and User.objects.filter(email=email).exists():
            errors['email'] = "Email is already registered."
        
        if not re.fullmatch(r'^[0-9]{10,15}$', ph_number):
            errors['ph_number'] = "Enter a valid 10-15 digit phone number."
        
        if errors:
            return render(request, 'profile/edit_profile.html', {
                'errors': errors,
                'form_data': form_data,
                'user': user
            })
        
        email_changed = email != user.email
        if email_changed:
            otp = generate_otp()
            request.session['profile_update_data'] = {
                'full_name': full_name,
                'email': email,
                'ph_number': ph_number,
                'otp': otp,
            }
            
            if profile_image:
                image_name = f"temp_profile_{user.id}_{timezone.now().timestamp()}.{profile_image.name.split('.')[-1]}"
                image_path = default_storage.save(f"temp_profiles/{image_name}", ContentFile(profile_image.read()))
                request.session['profile_update_data']['temp_image_path'] = image_path
            
            send_mail(
                subject='Email Verification for Profile Update',
                message=f'Your OTP for email verification is: {otp}',
                from_email='muhammaduhasanulbanna652@gmail.com',
                recipient_list=[email],
                fail_silently=False,
            )
            
            request.session['profile_otp_sent_time'] = timezone.now().timestamp()
            messages.success(request, f"OTP has been sent to {email}. Please verify to complete profile update.")
            return redirect('verify_profile_email')
        else:
            user.full_name = full_name
            user.ph_number = ph_number
            if profile_image:
                if user.pro_image:
                    if default_storage.exists(user.pro_image.name):
                        default_storage.delete(user.pro_image.name)
                user.pro_image = profile_image
            user.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('user_profile')
    
    return render(request, 'profile/edit_profile.html', {'user': user})

@never_cache
@login_required
def verify_profile_email(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    profile_data = request.session.get('profile_update_data')
    if not profile_data:
        messages.error(request, "Session expired. Please try updating your profile again.")
        return redirect('edit_profile')
    
    if request.method == 'POST':
        otp_input = ''.join([
            request.POST.get('otp1', ''),
            request.POST.get('otp2', ''),
            request.POST.get('otp3', ''),
            request.POST.get('otp4', ''),
            request.POST.get('otp5', ''),
            request.POST.get('otp6', ''),
        ])
        
        if profile_data['otp'] == otp_input:
            user = request.user
            user.full_name = profile_data['full_name']
            user.email = profile_data['email']
            user.ph_number = profile_data['ph_number']
            
            if 'temp_image_path' in profile_data:
                if user.pro_image:
                    if default_storage.exists(user.pro_image.name):
                        default_storage.delete(user.pro_image.name)
                
                temp_path = profile_data['temp_image_path']
                if default_storage.exists(temp_path):
                    with default_storage.open(temp_path, 'rb') as temp_file:
                        permanent_name = f"profile_images/user_{user.id}_{timezone.now().timestamp()}.{temp_path.split('.')[-1]}"
                        user.pro_image.save(permanent_name, ContentFile(temp_file.read()), save=False)
                    default_storage.delete(temp_path)
            
            user.save()
            request.session.pop('profile_update_data', None)
            request.session.pop('profile_otp_sent_time', None)
            messages.success(request, "Profile updated successfully with new email!")
            return redirect('user_profile')
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'profile/verify_profile_email.html', {
                'email': profile_data['email']
            })

@never_cache
@login_required
def change_password(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    errors = {}
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if not current_password:
            errors['current_password'] = "Current password is required."
        elif not check_password(current_password, request.user.password):
            errors['current_password'] = "Current password is incorrect."
        
        if len(new_password) < 8 or not re.search(r'[^A-Za-z0-9]', new_password):
            errors['new_password'] = "Password must be at least 8 characters long and include a special character."
        
        if new_password != confirm_password:
            errors['confirm_password'] = "New passwords do not match."
        
        if current_password == new_password:
            errors['new_password'] = "New password must be different from current password."
        
        if errors:
            return render(request, 'profile/change_password.html', {'errors': errors})
        
        request.user.password = make_password(new_password)
        request.user.save()
        messages.success(request, "Password changed successfully!")
        return redirect('user_profile')
    
    return render(request, 'profile/change_password.html')

@never_cache
@login_required
def manage_addresses(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    addresses = request.user.addresses.all()
    return render(request, 'profile/manage_addresses.html', {'addresses': addresses})

@never_cache
@login_required
def add_address(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    errors = {}
    form_data = {}
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        address_line_1 = request.POST.get('address_line_1', '').strip()
        address_line_2 = request.POST.get('address_line_2', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        postal_code = request.POST.get('postal_code', '').strip()
        country = request.POST.get('country', '').strip()
        address_type = request.POST.get('address_type', 'home')
        is_default = request.POST.get('is_default') == 'on'
        
        form_data = {
            'full_name': full_name,
            'phone_number': phone_number,
            'address_line_1': address_line_1,
            'address_line_2': address_line_2,
            'city': city,
            'state': state,
            'postal_code': postal_code,
            'country': country,
            'address_type': address_type,
            'is_default': is_default,
        }
        
        if not re.fullmatch(r'[A-Za-z ]+', full_name):
            errors['full_name'] = "Name must contain only letters and spaces."
        
        if not re.fullmatch(r'^[0-9]{10,15}$', phone_number):
            errors['phone_number'] = "Enter a valid 10-15 digit phone number."
        
        if not address_line_1:
            errors['address_line_1'] = "Address line 1 is required."
        
        if not city:
            errors['city'] = "City is required."
        
        if not state:
            errors['state'] = "State is required."
        
        if not re.fullmatch(r'^[0-9]{6}$', postal_code):
            errors['postal_code'] = "Enter a valid 6-digit postal code."
        
        if not country:
            errors['country'] = "Country is required."
        
        if errors:
            return render(request, 'profile/add_address.html', {
                'errors': errors,
                'form_data': form_data
            })
        
        Address.objects.create(
            user=request.user,
            full_name=full_name,
            phone_number=phone_number,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            address_type=address_type,
            is_default=is_default,
        )
        
        messages.success(request, "Address added successfully!")
        return redirect('manage_addresses')
    
    return render(request, 'profile/add_address.html')

@never_cache
@login_required
def edit_address(request, address_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    address = get_object_or_404(Address, id=address_id, user=request.user)
    errors = {}
    form_data = {}
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        address_line_1 = request.POST.get('address_line_1', '').strip()
        address_line_2 = request.POST.get('address_line_2', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        postal_code = request.POST.get('postal_code', '').strip()
        country = request.POST.get('country', '').strip()
        address_type = request.POST.get('address_type', 'home')
        is_default = request.POST.get('is_default') == 'on'
        
        form_data = {
            'full_name': full_name,
            'phone_number': phone_number,
            'address_line_1': address_line_1,
            'address_line_2': address_line_2,
            'city': city,
            'state': state,
            'postal_code': postal_code,
            'country': country,
            'address_type': address_type,
            'is_default': is_default,
        }
        
        if not re.fullmatch(r'[A-Za-z ]+', full_name):
            errors['full_name'] = "Name must contain only letters and spaces."
        
        if not re.fullmatch(r'^[0-9]{10,15}$', phone_number):
            errors['phone_number'] = "Enter a valid 10-15 digit phone number."
        
        if not address_line_1:
            errors['address_line_1'] = "Address line 1 is required."
        
        if not city:
            errors['city'] = "City is required."
        
        if not state:
            errors['state'] = "State is required."
        
        if not re.fullmatch(r'^[0-9]{6}$', postal_code):
            errors['postal_code'] = "Enter a valid 6-digit postal code."
        
        if not country:
            errors['country'] = "Country is required."
        
        if errors:
            return render(request, 'profile/edit_address.html', {
                'errors': errors,
                'form_data': form_data,
                'address': address
            })
        
        address.full_name = full_name
        address.phone_number = phone_number
        address.address_line_1 = address_line_1
        address.address_line_2 = address_line_2
        address.city = city
        address.state = state
        address.postal_code = postal_code
        address.country = country
        address.address_type = address_type
        address.is_default = is_default
        address.save()
        
        messages.success(request, "Address updated successfully!")
        return redirect('manage_addresses')
    
    form_data = {
        'full_name': address.full_name,
        'phone_number': address.phone_number,
        'address_line_1': address.address_line_1,
        'address_line_2': address.address_line_2,
        'city': address.city,
        'state': address.state,
        'postal_code': address.postal_code,
        'country': address.country,
        'address_type': address.address_type,
        'is_default': address.is_default,
    }
    
    return render(request, 'profile/edit_address.html', {
        'form_data': form_data,
        'address': address
    })

@never_cache
@login_required
def set_default_address(request, address_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    if request.method == 'POST':
        try:
            address = get_object_or_404(Address, id=address_id, user=request.user)
            address.is_default = True
            address.save()
            messages.success(request, "Default address updated successfully!")
        except Exception as e:
            messages.error(request, f"Error setting default address: {e}")
    else:
        messages.error(request, "Invalid request method.")
    
    return redirect('manage_addresses')

@never_cache
@login_required
def delete_address(request, address_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        try:
            address.delete()
            messages.success(request, "Address deleted successfully!")
        except Exception as e:
            messages.error(request, f"Error deleting address: {e}")
    else:
        messages.error(request, "Invalid request method.")
    
    return redirect('manage_addresses')

@never_cache
@login_required
def user_orders(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    user = request.user
    orders_qs = (
        user.orders
            .all()
            .prefetch_related('items__product', 'items__variant')
    )
    
    query = request.GET.get('q', '').strip()
    if query:
        orders_qs = orders_qs.filter(
            Q(order_number__icontains=query) |
            Q(items__product__product_name__icontains=query)
        ).distinct()
    
    orders_qs = orders_qs.order_by('-created_at')
    
    paginator = Paginator(orders_qs, 3)
    page_number = request.GET.get('page', 1)
    try:
        orders = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        orders = paginator.page(1)
    
    context = {
        'orders': orders,
        'query': query,
    }
    
    return render(request, 'profile/user_orders.html', context)

@never_cache
@login_required
def cancel_order(request, order_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if request.method == 'POST':
        if order.can_be_cancelled():
            order.status = 'cancelled'
            order.save()
            messages.success(request, f"Order {order.order_number} has been cancelled successfully.")
        else:
            messages.error(request, "This order cannot be cancelled.")
    
    return redirect('user_orders')

def resend_profile_otp(request):
    if request.method == 'POST':
        profile_data = request.session.get('profile_update_data')
        if not profile_data:
            messages.error(request, "Session expired. Please try updating your profile again.")
            return redirect('edit_profile')
        
        new_otp = generate_otp()
        profile_data['otp'] = new_otp
        request.session['profile_update_data'] = profile_data
        
        send_mail(
            subject='New Email Verification OTP',
            message=f'Your new OTP for email verification is: {new_otp}',
            from_email='muhammaduhasanulbanna652@gmail.com',
            recipient_list=[profile_data['email']],
            fail_silently=False,
        )
        
        request.session['profile_otp_sent_time'] = timezone.now().timestamp()
        messages.success(request, "New OTP has been sent to your email.")
    
    return redirect('verify_profile_email')

@never_cache
@login_required
def wishlist_view(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    wishlist_items = wishlist.items.select_related('product', 'variant').prefetch_related('variant__images')
    
    for item in wishlist_items:
        item.display_image = item.product.get_main_image()
        item.discounted_price = item.product.get_discounted_price()
    
    context = {
        'wishlist_items': wishlist_items,
        'total_items': wishlist_items.count(),
    }
    
    return render(request, 'wishlist/wishlist.html', context)

@login_required
@require_POST
def add_to_wishlist(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        
        if not product_id or not variant_id:
            return JsonResponse({
                'success': False,
                'message': 'Product and variant are required.'
            })
        
        try:
            product = Product.objects.get(id=product_id)
            variant = ProductVariant.objects.get(id=variant_id, product=product)
        except (Product.DoesNotExist, ProductVariant.DoesNotExist):
            return JsonResponse({
                'success': False,
                'message': 'Product or variant not found.'
            })
        
        if product.is_deleted or product.category.is_deleted or not variant.is_active:
            return JsonResponse({
                'success': False,
                'message': 'This product is no longer available.'
            })
        
        wishlist, created = Wishlist.objects.get_or_create(user=request.user)
        
        wishlist_item, item_created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            product=product,
            variant=variant
        )
        
        if item_created:
            message = f'{product.product_name} added to wishlist!'
        else:
            message = f'{product.product_name} is already in your wishlist.'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'item_created': item_created,
            'wishlist_count': wishlist.items.count(),
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        print(e)
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while adding to wishlist.'
        })

@login_required
@require_POST
def remove_from_wishlist(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        wishlist_item_id = data.get('wishlist_item_id')
        
        if not wishlist_item_id:
            return JsonResponse({
                'success': False,
                'message': 'Wishlist item ID is required.'
            })
        
        try:
            wishlist_item = WishlistItem.objects.get(id=wishlist_item_id, wishlist__user=request.user)
            product_name = wishlist_item.product.product_name
            wishlist_item.delete()
            
            wishlist = Wishlist.objects.get(user=request.user)
            
            return JsonResponse({
                'success': True,
                'message': f'{product_name} removed from wishlist.',
                'wishlist_count': wishlist.items.count(),
            })
        except WishlistItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Wishlist item not found.'
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        print(e)
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while removing item.'
        })

@login_required
@require_POST
def clear_wishlist(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        wishlist = Wishlist.objects.get(user=request.user)
        wishlist.items.all().delete()
        return JsonResponse({
            'success': True,
            'message': 'Wishlist cleared successfully.',
            'wishlist_count': 0,
        })
    except Wishlist.DoesNotExist:
        return JsonResponse({
            'success': True,
            'message': 'Wishlist is already empty.',
            'wishlist_count': 0,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while clearing wishlist.'
        })

@login_required
def download_invoice(request, order_id):
    if check_user_blocked(request.user):
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.select_related('product', 'variant')
    
    template_path = 'invoices/invoice_template.html'
    context = {'order': order, 'order_items': order_items}
    template = get_template(template_path)
    html = template.render(context)
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{order.order_number}.pdf"'
        return response
    return HttpResponse("Error generating PDF", status=500)

@login_required
@require_POST
def request_return(request, order_id):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
        
        if not reason:
            return JsonResponse({
                'success': False,
                'message': 'Return reason is required.'
            })
        
        if len(reason) < 10:
            return JsonResponse({
                'success': False,
                'message': 'Please provide a detailed reason (at least 10 characters).'
            })
        
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        if order.status != 'delivered':
            return JsonResponse({
                'success': False,
                'message': 'Only delivered orders can be returned.'
            })
        
        if hasattr(order, 'return_request'):
            return JsonResponse({
                'success': False,
                'message': 'Return request already exists for this order.'
            })
        
        return_deadline = order.created_at + timedelta(days=7)
        
        if timezone.now() > return_deadline:
            return JsonResponse({
                'success': False,
                'message': 'Return period has expired. Orders can only be returned within 7 days of delivery.'
            })
        
        ReturnRequest.objects.create(order=order, reason=reason, status='pending')
        
        return JsonResponse({
            'success': True,
            'message': 'Return request submitted successfully. We will review request and get back to you soon.'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while submitting return request.'
        })

@login_required
@require_POST
def cancel_order_item(request, item_id):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
        
        if not reason:
            return JsonResponse({
                'success': False,
                'message': 'Cancellation reason is required.'
            })
        
        try:
            order_item = OrderItem.objects.get(
                id=item_id,
                order__user=request.user
            )
        except OrderItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Order item not found.'
            })
        
        if not order_item.can_be_cancelled():
            return JsonResponse({
                'success': False,
                'message': 'This item cannot be cancelled.'
            })
        
        # Cancel the item
        order_item.status = 'cancelled'
        order_item.save()
        
        # Restore stock
        order_item.variant.stock_quantity += order_item.quantity
        order_item.variant.save()
        
        return JsonResponse({
            'success': True,
            'message': f'{order_item.product.product_name} has been cancelled successfully.'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while cancelling the item.'
        })

@login_required
@require_POST
def request_item_return(request, item_id):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
        
        if not reason:
            return JsonResponse({
                'success': False,
                'message': 'Return reason is required.'
            })
        
        if len(reason) < 10:
            return JsonResponse({
                'success': False,
                'message': 'Please provide a detailed reason (at least 10 characters).'
            })
        
        try:
            order_item = OrderItem.objects.get(
                id=item_id,
                order__user=request.user
            )
        except OrderItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Order item not found.'
            })
        
        if not order_item.can_be_returned():
            return JsonResponse({
                'success': False,
                'message': 'This item cannot be returned.'
            })
        
        if hasattr(order_item, 'return_request'):
            return JsonResponse({
                'success': False,
                'message': 'Return request already exists for this item.'
            })
        
        # Create return request
        ItemReturnRequest.objects.create(
            order_item=order_item,
            reason=reason,
            status='pending'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Return request submitted successfully. We will review your request and get back to you soon.'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while submitting return request.'
        })

@never_cache
@login_required
def wallet_view(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    # Get or create wallet
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    # Get transactions with pagination
    transactions = wallet.transactions.all().order_by('-created_at')
    paginator = Paginator(transactions, 10)
    page = request.GET.get('page')
    
    try:
        transactions_page = paginator.page(page)
    except PageNotAnInteger:
        transactions_page = paginator.page(1)
    except EmptyPage:
        transactions_page = paginator.page(paginator.num_pages)
    
    # Get referral statistics
    referral_rewards = ReferralReward.objects.filter(referrer=request.user)
    total_referrals = referral_rewards.count()
    total_referral_earnings = referral_rewards.aggregate(
        total=models.Sum('reward_amount')
    )['total'] or 0
    
    # Get referred users - Fixed the field name from date_joined to created_at
    referred_users = User.objects.filter(referred_by=request.user).order_by('-created_at')[:5]
    
    # Generate referral link
    current_site = get_current_site(request)
    referral_link = f"http://{current_site.domain}{reverse('sign_up_with_referral', kwargs={'token': request.user.referral_token})}"
    
    # Get active referral offer
    active_referral_offer = ReferralOffer.objects.filter(is_active=True).first()
    
    context = {
        'wallet': wallet,
        'transactions': transactions_page,
        'total_referrals': total_referrals,
        'total_referral_earnings': total_referral_earnings,
        'referred_users': referred_users,
        'referral_link': referral_link,
        'referral_code': request.user.referral_code,
        'active_referral_offer': active_referral_offer,
    }
    
    return render(request, 'wallet/wallet.html', context)

@login_required
@require_POST
def generate_referral_link(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        current_site = get_current_site(request)
        referral_link = f"http://{current_site.domain}{reverse('sign_up_with_referral', kwargs={'token': request.user.referral_token})}"
        
        return JsonResponse({
            'success': True,
            'referral_link': referral_link,
            'referral_code': request.user.referral_code
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error generating referral link.'
        })
