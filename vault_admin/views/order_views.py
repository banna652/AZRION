from .common_imports import *

@never_cache
@login_required
@user_passes_test(lambda u: u.is_staff)
def order_management_page(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    payment_filter = request.GET.get('payment', 'all')
    sort_order = request.GET.get('sort', 'desc')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    orders = Order.objects.select_related('user', 'shipping_address').prefetch_related('items__product', 'items__variant')
    
    if query:
        orders = orders.filter(Q(order_number__icontains=query) | Q(user__full_name__icontains=query) | Q(user__email__icontains=query) | Q(items__product__product_name__icontains=query)).distinct()
        
    if status_filter != 'all':
        orders = orders.filter(status=status_filter)
        
    if payment_filter != 'all':
        orders = orders.filter(payment_method=payment_filter)
        
    if date_from:
        try:
            from_date = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__gte=from_date)
        except ValueError:
            date_from = ''
            
    if date_to:
        try:
            to_date = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date__lte=to_date)
        except ValueError:
            date_to = ''
            
    if sort_order == 'asc':
        orders = orders.order_by('created_at')
    else:
        orders = orders.order_by('-created_at')
        
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    delivered_orders = Order.objects.filter(status='delivered').count()
    cancelled_orders = Order.objects.filter(status='cancelled').count()
    total_revenue = Order.objects.filter(status='delivered').aggregate(total=Sum('total_amount'))['total'] or 0
    
    paginator = Paginator(orders, 10)
    page = request.GET.get('page')
    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)
        
    context = {
        'orders':orders, 'query': query, 'status_filter': status_filter,
        'payment_filter': payment_filter, 'sort_order': sort_order, 'date_from': date_from,
        'date_to': date_to, 'total_orders': total_orders, 'pending_orders': pending_orders,
        'delivered_orders': delivered_orders, 'cancelled_orders': cancelled_orders, 'total_revenue': total_revenue,
        'order_status_choices': Order.ORDER_STATUS_CHOICES, 'payment_method_choices': Order.PAYMENT_METHOD_CHOICES,
    }
    
    return render(request, 'orders/order_management.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_items = order.items.all()
    
    # Calculate item statistics
    active_items_count = order_items.filter(status='active').count()
    cancelled_items_count = order_items.filter(status='cancelled').count()
    returned_items_count = order_items.filter(status='returned').count()
    
    # Get return request if exists (for backward compatibility)
    try:
        return_request = order.return_request
    except:
        return_request = None
    
    context = {
        'order': order,
        'order_items': order_items,
        'return_request': return_request,
        'active_items_count': active_items_count,
        'cancelled_items_count': cancelled_items_count,
        'returned_items_count': returned_items_count,
    }
    
    return render(request, 'orders/orders_details.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if new_status in dict(Order.ORDER_STATUS_CHOICES):
            old_status = order.status
            order.status = new_status
            order.save()
            
            if new_status == 'cancelled' and old_status != 'cancelled':
                for item in order.items.all():
                    item.variant.stock_quantity += item.quantity
                    item.variant.save()
                    
            messages.success(request, f"Order {order.order_number} status updated to {order.get_status_display()}")
        else:
            messages.error(request, "Invalid status selected")
            
    return redirect('order_detail_view', order_id=order.id)
