from .common_imports import *

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
    products = Product.objects.filter(
        is_deleted=False,
        category__is_deleted=False,
        category__is_blocked=False
    ).select_related('category').prefetch_related('variants__images')
    
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