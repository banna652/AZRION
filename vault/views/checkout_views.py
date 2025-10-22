from .common_imports import *

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