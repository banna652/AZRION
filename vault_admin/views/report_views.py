from .common_imports import *

def generate_excel_report(orders, stats):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"
    
    # Header styling
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="16213e", end_color="16213e", fill_type="solid")
    
    # Title
    ws.merge_cells('A1:H1')
    ws['A1'] = f'Sales Report - {stats["report_type"].title()}'
    ws['A1'].font = Font(bold=True, size=16)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    # Date range
    ws.merge_cells('A2:H2')
    ws['A2'] = f'Period: {stats["start_date"].strftime("%Y-%m-%d")} to {stats["end_date"].strftime("%Y-%m-%d")}'
    ws['A2'].alignment = Alignment(horizontal='center')
    
    # Summary statistics
    ws['A4'] = 'Summary Statistics'
    ws['A4'].font = Font(bold=True, size=14)
    
    ws['A5'] = 'Total Orders:'
    ws['B5'] = stats['total_orders']
    ws['A6'] = 'Total Revenue:'
    ws['B6'] = float(stats['total_revenue'])
    ws['A7'] = 'Total Discount:'
    ws['B7'] = float(stats['total_discount'])
    ws['A8'] = 'Total Shipping:'
    ws['B8'] = float(stats['total_shipping'])
    ws['A9'] = 'Subtotal:'
    ws['B9'] = float(stats['total_subtotal'])
    
    # Orders table header
    ws['A11'] = 'Order Details'
    ws['A11'].font = Font(bold=True, size=14)
    
    headers = ['Order Number', 'Customer', 'Date', 'Subtotal', 'Discount', 'Shipping', 'Total', 'Coupon']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=13, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    
    # Orders data
    for row, order in enumerate(orders, 14):
        ws.cell(row=row, column=1, value=order.order_number)
        ws.cell(row=row, column=2, value=order.user.full_name)
        ws.cell(row=row, column=3, value=order.created_at.strftime('%Y-%m-%d %H:%M'))
        ws.cell(row=row, column=4, value=float(order.subtotal))
        ws.cell(row=row, column=5, value=float(order.coupon_discount))
        ws.cell(row=row, column=6, value=float(order.shipping_charge))
        ws.cell(row=row, column=7, value=float(order.total_amount))
        ws.cell(row=row, column=8, value=order.coupon.code if order.coupon else 'None')
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'sales_report_{stats["report_type"]}_{stats["start_date"].strftime("%Y%m%d")}_to_{stats["end_date"].strftime("%Y%m%d")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

def generate_pdf_report(orders, stats):
    template_path = 'reports/sales_report_pdf.html'
    context = {
        'orders': orders,
        'stats': stats,
        'generated_at': timezone.now(),
    }
    
    template = get_template(template_path)
    html = template.render(context)
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f'sales_report_{stats["report_type"]}_{stats["start_date"].strftime("%Y%m%d")}_to_{stats["end_date"].strftime("%Y%m%d")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    return HttpResponse("Error generating PDF", status=500)

@never_cache
@login_required
@user_passes_test(lambda u: u.is_staff)
def sales_report(request):
    # Get filter parameters
    report_type = request.GET.get('report_type', 'daily')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Calculate date range based on report type
    now = timezone.now()
    
    if report_type == 'daily':
        start_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date_obj = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif report_type == 'weekly':
        start_date_obj = now - timedelta(days=7)
        end_date_obj = now
    elif report_type == 'monthly':
        start_date_obj = now - timedelta(days=30)
        end_date_obj = now
    elif report_type == 'yearly':
        start_date_obj = now - timedelta(days=365)
        end_date_obj = now
    elif report_type == 'custom' and start_date and end_date:
        try:
            start_date_obj = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
            end_date_obj = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except ValueError:
            messages.error(request, "Invalid date format")
            start_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date_obj = now
    else:
        start_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date_obj = now
    
    # Get orders within date range
    orders = Order.objects.filter(
        created_at__range=[start_date_obj, end_date_obj],
        status='delivered'  # Only count delivered orders
    ).select_related('user', 'coupon').prefetch_related('items')
    
    # Calculate statistics
    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_discount = orders.aggregate(total=Sum('coupon_discount'))['total'] or Decimal('0.00')
    total_shipping = orders.aggregate(total=Sum('shipping_charge'))['total'] or Decimal('0.00')
    
    # Calculate subtotal (revenue + discount - shipping)
    total_subtotal = total_revenue + total_discount - total_shipping
    
    # Get top products
    top_products = OrderItem.objects.filter(
        order__in=orders
    ).values(
        'product__product_name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('price')
    ).order_by('-total_quantity')[:5]
    
    # Get coupon usage statistics
    coupon_usage = orders.exclude(coupon__isnull=True).values(
        'coupon__code'
    ).annotate(
        usage_count=Count('id'),
        total_discount=Sum('coupon_discount')
    ).order_by('-usage_count')[:5]
    
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
    
    context = {
        'report_type': report_type,
        'start_date': start_date_obj.strftime('%Y-%m-%d'),
        'end_date': end_date_obj.strftime('%Y-%m-%d'),
        'start_date_input': start_date,
        'end_date_input': end_date,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_discount': total_discount,
        'total_shipping': total_shipping,
        'total_subtotal': total_subtotal,
        'orders': orders[:20],  # Show latest 20 orders
        'top_products': top_products,
        'coupon_usage': coupon_usage,
        'daily_sales': daily_sales,
    }
    
    return render(request, 'reports/sales_report.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def download_sales_report(request):
    format_type = request.GET.get('format', 'pdf')
    report_type = request.GET.get('report_type', 'daily')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Calculate date range (same logic as sales_report view)
    now = timezone.now()
    
    if report_type == 'daily':
        start_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date_obj = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif report_type == 'weekly':
        start_date_obj = now - timedelta(days=7)
        end_date_obj = now
    elif report_type == 'monthly':
        start_date_obj = now - timedelta(days=30)
        end_date_obj = now
    elif report_type == 'yearly':
        start_date_obj = now - timedelta(days=365)
        end_date_obj = now
    elif report_type == 'custom' and start_date and end_date:
        try:
            start_date_obj = timezone.make_aware(datetime.strptime(start_date, '%Y-%m-%d'))
            end_date_obj = timezone.make_aware(datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except ValueError:
            start_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date_obj = now
    else:
        start_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date_obj = now
    
    # Get data
    orders = Order.objects.filter(
        created_at__range=[start_date_obj, end_date_obj],
        status='delivered'
    ).select_related('user', 'coupon').prefetch_related('items')
    
    # Calculate statistics
    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_discount = orders.aggregate(total=Sum('coupon_discount'))['total'] or Decimal('0.00')
    total_shipping = orders.aggregate(total=Sum('shipping_charge'))['total'] or Decimal('0.00')
    total_subtotal = total_revenue + total_discount - total_shipping
    
    if format_type == 'excel':
        return generate_excel_report(orders, {
            'report_type': report_type,
            'start_date': start_date_obj,
            'end_date': end_date_obj,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'total_discount': total_discount,
            'total_shipping': total_shipping,
            'total_subtotal': total_subtotal,
        })
    else:
        return generate_pdf_report(orders, {
            'report_type': report_type,
            'start_date': start_date_obj,
            'end_date': end_date_obj,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'total_discount': total_discount,
            'total_shipping': total_shipping,
            'total_subtotal': total_subtotal,
        })