from .common_imports import *

@never_cache
@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard(request):
    # Get current date and time
    now = timezone.now()
    today = now.date()
    
    # Calculate date ranges
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Basic counts
    total_users = User.objects.count()
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_orders = Order.objects.count()
    
    # Sales statistics
    today_orders = Order.objects.filter(created_at__date=today, status='delivered')
    weekly_orders = Order.objects.filter(created_at__gte=week_ago, status='delivered')
    monthly_orders = Order.objects.filter(created_at__gte=month_ago, status='delivered')
    
    # Revenue calculations
    today_revenue = today_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    weekly_revenue = weekly_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    monthly_revenue = monthly_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_revenue = Order.objects.filter(status='delivered').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Order counts
    today_order_count = today_orders.count()
    weekly_order_count = weekly_orders.count()
    monthly_order_count = monthly_orders.count()
    
    # Recent orders
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:5]
    
    # Top selling products (last 30 days)
    top_products = OrderItem.objects.filter(
        order__created_at__gte=month_ago,
        order__status='delivered'
    ).values(
        'product__product_name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('price')
    ).order_by('-total_quantity')[:5]
    
    # Coupon statistics
    total_coupons = Coupon.objects.count()
    active_coupons = Coupon.objects.filter(is_active=True, valid_until__gte=now).count()
    coupon_usage_today = CouponUsage.objects.filter(used_at__date=today).count()
    total_discount_given = Order.objects.filter(status='delivered').aggregate(
        total=Sum('coupon_discount')
    )['total'] or Decimal('0.00')
    
    # Daily sales data for chart (last 7 days)
    daily_sales = []
    for i in range(7):
        date = (now - timedelta(days=i)).date()
        day_orders = Order.objects.filter(created_at__date=date, status='delivered')
        daily_revenue = day_orders.aggregate(total=Sum('total_amount'))['total'] or 0
        daily_sales.append({
            'date': date.strftime('%Y-%m-%d'),
            'revenue': float(daily_revenue),
            'orders': day_orders.count()
        })
    
    daily_sales.reverse()  # Show oldest to newest
    
    # Order status distribution
    order_status_counts = Order.objects.values('status').annotate(count=Count('id'))
    
    context = {
        'total_users': total_users,
        'total_products': total_products,
        'total_categories': total_categories,
        'total_orders': total_orders,
        'today_revenue': today_revenue,
        'weekly_revenue': weekly_revenue,
        'monthly_revenue': monthly_revenue,
        'total_revenue': total_revenue,
        'today_order_count': today_order_count,
        'weekly_order_count': weekly_order_count,
        'monthly_order_count': monthly_order_count,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'total_coupons': total_coupons,
        'active_coupons': active_coupons,
        'coupon_usage_today': coupon_usage_today,
        'total_discount_given': total_discount_given,
        'daily_sales': daily_sales,
        'order_status_counts': order_status_counts,
    }
    
    return render(request, 'dashboard.html', context)