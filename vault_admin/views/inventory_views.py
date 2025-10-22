from .common_imports import *

@login_required
@user_passes_test(lambda u: u.is_staff)
def inventory_management(request):
    query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', 'all')
    stock_filter = request.GET.get('stock', 'all')
    
    variants = ProductVariant.objects.select_related('product__category').filter(product__is_deleted=False, is_active=True)
    
    if query:
        variants = variants.filter(Q(product__product_name__icontains=query) | Q(product__category__name__icontains=query) | Q(color__icontains=query))
        
    if category_filter != 'all':
        try:
            category_filter = int(category_filter)
            variants = variants.filter(product__category_id=category_filter)
        except (ValueError, TypeError):
            category_filter = 'all'
            
    if stock_filter == 'low':
        variants = variants.filter(stock_quantity__lte=5, stock_quantity__gt=0)
    elif stock_filter == 'out':
        variants = variants.filter(stock_quantity=0)
    elif stock_filter == 'available':
        variants = variants.filter(stock_quantity__gt=5)
        
    variants = variants.order_by('stock_quantity', 'product__product_name')
    
    categories = Category.objects.filter(is_deleted=False).order_by('name')
    
    paginator = Paginator(variants, 15)
    page = request.GET.get('page')
    try:
        variants = paginator.page(page)
    except PageNotAnInteger:
        variants = paginator.page(1)
    except EmptyPage:
        variants = paginator.page(paginator.num_pages)
        
    context = {
        'variants': variants, 'categories': categories, 'query': query,
        'category_filter': str(category_filter) if category_filter != 'all' else 'all',
        'stock_filter': stock_filter,
    } 
    return render(request, 'orders/inventory_management.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def update_stock(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    
    if request.method == 'POST':
        try:
            new_stock = int(request.POST.get('stock_quantity', 0))
            if new_stock >= 0:
                variant.stock_quantity = new_stock
                variant.save()
                messages.success(request, f"Stock updated for {variant.product.product_name} - {variant.get_color_display()}")
            else:
                messages.error(request, "Stock quantity cannot be negative")
        except ValueError:
            messages.error(request, "Invalid stock quantity")
    return redirect('inventory_management')