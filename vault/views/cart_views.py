from .common_imports import *

@never_cache
@login_required
def cart_view(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.items.select_related('product', 'variant').prefetch_related('variant__images')
    
    total_price = 0
    available_items = []
    unavailable_items = []
    
    for item in cart_items:
        item.unit_price = item.get_unit_price()
        item.total_price = item.get_total_price()
        if item.is_available():
            available_items.append(item)
            total_price += item.total_price
        else:
            unavailable_items.append(item)
    
    context = {
        'cart': cart,
        'available_items': available_items,
        'unavailable_items': unavailable_items,
        'total_price': total_price,
        'total_items': len(available_items),
    }
    
    return render(request, 'cart/cart.html', context)

@login_required
@require_POST
def add_to_cart(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        quantity = int(data.get('quantity', 1))
        
        if not product_id or not variant_id:
            return JsonResponse({
                'success': False,
                'message': 'Product and variant are required.'
            })
        
        if quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Invalid quantity.'
            })
        
        try:
            product = Product.objects.get(id=product_id)
            variant = ProductVariant.objects.get(id=variant_id, product=product)
        except (Product.DoesNotExist, ProductVariant.DoesNotExist):
            return JsonResponse({
                'success': False,
                'message': 'Product or variant not found.'
            })
        
        if product.is_deleted or product.category.is_deleted or not variant.is_active:
            return JsonResponse({
                'success': False,
                'message': 'This product is no longer available.'
            })
        
        if variant.stock_quantity < quantity:
            return JsonResponse({
                'success': False,
                'message': f'Only {variant.stock_quantity} items available in stock.'
            })
        
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={'quantity': quantity}
        )
        
        if not item_created:
            new_quantity = cart_item.quantity + quantity
            if new_quantity > variant.stock_quantity:
                return JsonResponse({
                    'success': False,
                    'message': f'Cannot add more items. Only {variant.stock_quantity} available, {cart_item.quantity} already in cart.'
                })
            if new_quantity > 10:
                return JsonResponse({
                    'success': False,
                    'message': 'Maximum 10 items allowed per product.'
                })
            cart_item.quantity = new_quantity
            cart_item.save()
        else:
            if quantity > 10:
                return JsonResponse({
                    'success': False,
                    'message': 'Maximum 10 items allowed per product.'
                })
        
        try:
            wishlist = Wishlist.objects.get(user=request.user)
            wishlist.items.filter(product=product, variant=variant).delete()
        except Wishlist.DoesNotExist:
            pass
        
        cart_total = cart.get_total_items()
        
        return JsonResponse({
            'success': True,
            'message': f'{product.product_name} added to cart successfully!',
            'cart_total': cart_total,
            'item_quantity': cart_item.quantity,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        print(e,'ddddddddddddddddddddd')
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while adding to cart.'
        })
        
@login_required
@require_POST
def update_cart_quantity(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        cart_item_id = data.get('cart_item_id')
        action = data.get('action')
        
        if not cart_item_id or action not in ['increase', 'decrease']:
            return JsonResponse({
                'success': False,
                'message': 'Invalid request parameters.'
            })
        
        try:
            cart_item = CartItem.objects.get(
                id=cart_item_id,
                cart__user=request.user
            )
        except CartItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cart item not found.'
            })
        
        if not cart_item.is_available():
            return JsonResponse({
                'success': False,
                'message': 'This item is no longer available.'
            })
        
        if action == 'increase':
            new_quantity = cart_item.quantity + 1
        else:
            new_quantity = cart_item.quantity - 1
        
        if new_quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Quantity must be at least 1.'
            })
        
        if new_quantity > cart_item.variant.stock_quantity:
            return JsonResponse({
                'success': False,
                'message': f'Only {cart_item.variant.stock_quantity} items available in stock.'
            })
        
        if new_quantity > 10:
            return JsonResponse({
                'success': False,
                'message': 'Maximum 10 items allowed per product.'
            })
        
        cart_item.quantity = new_quantity
        cart_item.save()
        
        item_total = cart_item.get_total_price()
        cart_total = cart_item.cart.get_total_price()
        cart_items_count = cart_item.cart.get_total_items()
        
        return JsonResponse({
            'success': True,
            'quantity': new_quantity,
            'item_total': float(item_total),
            'cart_total': float(cart_total),
            'cart_items_count': cart_items_count,
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while updating quantity.'
        })
        
@login_required
@require_POST
def remove_from_cart(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        cart_item_id = data.get('cart_item_id')
        
        if not cart_item_id:
            return JsonResponse({
                'success': False,
                'message': 'Cart item ID is required.'
            })
        
        try:
            cart_item = CartItem.objects.get(
                id=cart_item_id,
                cart__user=request.user
            )
            product_name = cart_item.product.product_name
            cart_item.delete()
            
            cart = Cart.objects.get(user=request.user)
            cart_total = cart.get_total_price()
            cart_items_count = cart.get_total_items()
            
            return JsonResponse({
                'success': True,
                'message': f'{product_name} removed from cart.',
                'cart_total': float(cart_total),
                'cart_items_count': cart_items_count,
            })
        except CartItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Cart item not found.'
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while removing item.'
        })

@login_required
@require_POST
def clear_cart(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        cart = Cart.objects.get(user=request.user)
        cart.items.all().delete()
        return JsonResponse({
            'success': True,
            'message': 'Cart cleared successfully.',
            'cart_total': 0,
            'cart_items_count': 0,
        })
    except Cart.DoesNotExist:
        return JsonResponse({
            'success': True,
            'message': 'Cart is already empty.',
            'cart_total': 0,
            'cart_items_count': 0,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while clearing cart.'
        })