from .common_imports import *

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
    
    paginator = Paginator(orders_qs, 5)
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
            
            if order.payment_method == 'online' and order.status != 'delivered':
                wallet, created = Wallet.objects.get_or_create(user=request.user)
                if created:
                    wallet.refresh_from_db()
                
                # Add refund amount to wallet
                refund_amount = order.total_amount
                wallet.add_money(
                    amount=refund_amount,
                    description=f"Refund for cancelled order #{order.order_number}"
                )
                
                messages.success(request, f"Order {order.order_number} has been cancelled successfully. ₹{refund_amount} has been refunded to your wallet.")
            else:
                messages.success(request, f"Order {order.order_number} has been cancelled successfully.")
        else:
            messages.error(request, "This order cannot be cancelled.")
    
    return redirect('user_orders')

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
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        if payment_method == 'wallet':
            # Get or create wallet
            
            
            # Check if wallet has sufficient balance
            if wallet.balance < Decimal(str(total_amount)):
                return JsonResponse({
                    'success': False,
                    'message': f'Insufficient wallet balance. Available: ₹{wallet.balance}, Required: ₹{total_amount:.2f}'
                })
        
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
        
        if payment_method == 'wallet':
            # Deduct amount from wallet
            wallet = Wallet.objects.get(user=request.user)
            if wallet.deduct_money(total_amount, f"Payment for Order #{order_number}"):
                order.status = 'confirmed'  # Wallet payments are immediately confirmed
                order.save()
            else:
                # This shouldn't happen as we already checked balance, but just in case
                order.delete()  # Remove the order if wallet deduction fails
                return JsonResponse({
                    'success': False,
                    'message': 'Wallet payment failed. Please try again.'
                })
        
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
        
        if payment_method == 'wallet':
            success_message = f'Order placed successfully using wallet! Remaining balance: ₹{wallet.balance:.2f}'
        else:
            success_message = 'Order placed successfully!'
        
        return JsonResponse({
            'success': True,
            'message': success_message,
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
        
        if order_item.order.payment_method == 'online' and order_item.order.status != 'delivered':
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            if created:
                wallet.refresh_from_db()
            
            # Calculate refund amount for this item
            refund_amount = order_item.get_total_price()
            wallet.add_money(
                amount=refund_amount,
                description=f"Refund for cancelled item {order_item.product.product_name} from order #{order_item.order.order_number}"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'{order_item.product.product_name} has been cancelled successfully. ₹{refund_amount} has been refunded to your wallet.'
            })
        
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
@require_POST
def add_product_review(request, product_id):
    """Add or update a product review"""
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        rating = data.get('rating')
        review_text = data.get('review_text', '').strip()
        
        # Validate rating
        if not rating or rating not in [1, 2, 3, 4, 5]:
            return JsonResponse({
                'success': False,
                'message': 'Please select a valid rating (1-5 stars).'
            })
        
        # Validate review text
        if not review_text:
            return JsonResponse({
                'success': False,
                'message': 'Please write a review.'
            })
        
        if len(review_text) < 10:
            return JsonResponse({
                'success': False,
                'message': 'Review must be at least 10 characters long.'
            })
        
        if len(review_text) > 1000:
            return JsonResponse({
                'success': False,
                'message': 'Review cannot exceed 1000 characters.'
            })
        
        # Get the product
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Product not found.'
            })
        
        # Check if user has purchased this product and it's delivered
        has_delivered_order = OrderItem.objects.filter(
            product=product,
            order__user=request.user,
            order__status='delivered',
            status='active'
        ).exists()
        
        if not has_delivered_order:
            return JsonResponse({
                'success': False,
                'message': 'You can only review products from delivered orders.'
            })
        
        # Create or update review
        review, created = ProductReview.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={
                'rating': rating,
                'review_text': review_text,
                'is_verified_purchase': True
            }
        )
        
        action = 'added' if created else 'updated'
        
        return JsonResponse({
            'success': True,
            'message': f'Review {action} successfully!',
            'review': {
                'id': review.id,
                'rating': review.rating,
                'review_text': review.review_text,
                'created_at': review.created_at.strftime('%B %d, %Y')
            }
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        logger.error(f"Error adding review: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while adding your review.'
        })
        
@never_cache
@login_required
@require_GET
def get_review(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Product not found.'})
    
    try:
        review = ProductReview.objects.get(product=product, user=request.user)
        return JsonResponse({
            'success': True,
            'review': {
                'id': review.id,
                'rating': review.rating,
                'review_text': review.review_text,
                'created_at': review.created_at.strftime('%B %d, %Y')
            }
        })
    except ProductReview.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'No review found for this product.'})