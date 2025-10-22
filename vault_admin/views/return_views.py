from .common_imports import *

@login_required
@user_passes_test(lambda u: u.is_staff)
def return_requests_page(request):
    status_filter = request.GET.get('status', 'all')
    request_type = request.GET.get('type', 'all')  # New filter for request type
    
    # Get both individual item returns and full order returns
    item_returns = ItemReturnRequest.objects.select_related(
        'order_item__order__user', 
        'order_item__product', 
        'order_item__variant',
        'processed_by'
    ).order_by('-requested_at')
    
    full_order_returns = ReturnRequest.objects.select_related(
        'order__user', 
        'processed_by'
    ).order_by('-requested_at')
    
    # Apply status filter
    if status_filter != 'all':
        item_returns = item_returns.filter(status=status_filter)
        full_order_returns = full_order_returns.filter(status=status_filter)
    
    # Apply type filter
    if request_type == 'item':
        full_order_returns = full_order_returns.none()
    elif request_type == 'order':
        item_returns = item_returns.none()
    
    # Combine and sort the querysets
    all_returns = []
    
    # Add item returns
    for item_return in item_returns:
        all_returns.append({
            'type': 'item',
            'id': item_return.id,
            'order_number': item_return.order_item.order.order_number,
            'order_id': item_return.order_item.order.id,
            'customer_name': item_return.order_item.order.user.full_name,
            'customer_email': item_return.order_item.order.user.email,
            'product_name': item_return.order_item.product.product_name,
            'variant_color': item_return.order_item.variant.get_color_display(),
            'quantity': item_return.order_item.quantity,
            'item_total': item_return.order_item.get_total_price(),
            'reason': item_return.reason,
            'status': item_return.status,
            'requested_at': item_return.requested_at,
            'processed_at': item_return.processed_at,
            'processed_by': item_return.processed_by,
            'admin_notes': item_return.admin_notes,
            'object': item_return
        })
    
    # Add full order returns
    for order_return in full_order_returns:
        all_returns.append({
            'type': 'order',
            'id': order_return.id,
            'order_number': order_return.order.order_number,
            'order_id': order_return.order.id,
            'customer_name': order_return.order.user.full_name,
            'customer_email': order_return.order.user.email,
            'product_name': 'Full Order',
            'variant_color': '',
            'quantity': order_return.order.items.count(),
            'item_total': order_return.order.total_amount,
            'reason': order_return.reason,
            'status': order_return.status,
            'requested_at': order_return.requested_at,
            'processed_at': order_return.processed_at,
            'processed_by': order_return.processed_by,
            'admin_notes': order_return.admin_notes,
            'object': order_return
        })
    
    # Sort by requested_at descending
    all_returns.sort(key=lambda x: x['requested_at'], reverse=True)
    
    # Paginate
    paginator = Paginator(all_returns, 10)
    page = request.GET.get('page')
    try:
        return_requests = paginator.page(page)
    except PageNotAnInteger:
        return_requests = paginator.page(1)
    except EmptyPage:
        return_requests = paginator.page(paginator.num_pages)
    
    context = {
        'return_requests': return_requests,
        'status_filter': status_filter,
        'request_type': request_type,
    }
    return render(request, 'orders/return_request.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
@require_http_methods(["GET", "POST"])
def verify_return_request(request, return_request_id):
    return_request = get_object_or_404(ReturnRequest, id=return_request_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '').strip()
        
        try:
            if action == 'approve':
                if return_request.status != 'pending':
                    messages.error(request, "This return request has already been processed.")
                    return redirect('return_requests_page')

                return_request.status = 'approved'
                return_request.admin_notes = admin_notes
                return_request.processed_at = timezone.now()
                return_request.processed_by = request.user
                return_request.save()

                order = return_request.order
                order.status = 'returned'
                order.save()

                for item in order.items.all():
                    item.variant.stock_quantity += item.quantity
                    item.variant.save()

                wallet, created = Wallet.objects.get_or_create(user=order.user)
                wallet.add_money(
                    order.total_amount,
                    f"Refund for returned order {order.order_number}"
                )
                
                messages.success(
                    request, 
                    f"Return request approved successfully. ₹{order.total_amount} has been added to {order.user.full_name}'s wallet."
                )
                
            elif action == 'reject':
                
                if not admin_notes:
                    messages.error(request, "Admin notes are required when rejecting a return request.")
                    return redirect('return_requests_page')

                if return_request.status != 'pending':
                    messages.error(request, "This return request has already been processed.")
                    return redirect('return_requests_page')

                return_request.status = 'rejected'
                return_request.admin_notes = admin_notes
                return_request.processed_at = timezone.now()
                return_request.processed_by = request.user
                return_request.save()
                
                messages.success(
                    request, 
                    f"Return request for order {return_request.order.order_number} has been rejected."
                )
            
            else:
                messages.error(request, "Invalid action specified.")
                
        except Exception as e:
            messages.error(request, f"An error occurred while processing the return request: {str(e)}")
    
    return redirect('return_requests_page')

@login_required
@user_passes_test(lambda u: u.is_staff)
@require_http_methods(["GET", "POST"])
def verify_item_return_request(request, item_return_id):
    item_return = get_object_or_404(ItemReturnRequest, id=item_return_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '').strip()
        
        try:
            if action == 'approve':
                if item_return.status != 'pending':
                    messages.error(request, "This return request has already been processed.")
                    return redirect('return_requests_page')
                
                # Update return request
                item_return.status = 'approved'
                item_return.admin_notes = admin_notes
                item_return.processed_at = timezone.now()
                item_return.processed_by = request.user
                item_return.save()
                
                # Update order item status
                order_item = item_return.order_item
                order_item.status = 'returned'
                order_item.save()
                
                # Restore stock
                order_item.variant.stock_quantity += order_item.quantity
                order_item.variant.save()
                
                # Add refund to wallet
                wallet, created = Wallet.objects.get_or_create(user=order_item.order.user)
                refund_amount = order_item.get_total_price()
                wallet.add_money(
                    refund_amount,
                    f"Refund for returned item: {order_item.product.product_name} from order {order_item.order.order_number}"
                )
                
                messages.success(
                    request, 
                    f"Item return approved successfully. ₹{refund_amount} has been added to {order_item.order.user.full_name}'s wallet."
                )
                
            elif action == 'reject':
                if not admin_notes:
                    messages.error(request, "Admin notes are required when rejecting a return request.")
                    return redirect('return_requests_page')
                
                if item_return.status != 'pending':
                    messages.error(request, "This return request has already been processed.")
                    return redirect('return_requests_page')
                
                item_return.status = 'rejected'
                item_return.admin_notes = admin_notes
                item_return.processed_at = timezone.now()
                item_return.processed_by = request.user
                item_return.save()
                
                messages.success(
                    request, 
                    f"Item return request for {item_return.order_item.product.product_name} has been rejected."
                )
            else:
                messages.error(request, "Invalid action specified.")
                
        except Exception as e:
            messages.error(request, f"An error occurred while processing the return request: {str(e)}")
    
    return redirect('return_requests_page')