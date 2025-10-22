from .common_imports import *

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

def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('front')

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