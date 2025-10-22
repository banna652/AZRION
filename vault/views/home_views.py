from .common_imports import *

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
    
def t_o_s_page(request):
    return render(request, 'terms_of_service.html')

def privacy_policy_page(request):
    return render(request, 'privacy_policy.html')