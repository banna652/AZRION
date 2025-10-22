from .common_imports import *

@never_cache
@login_required
def wishlist_view(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    wishlist_items = wishlist.items.select_related('product', 'variant').prefetch_related('variant__images')
    
    for item in wishlist_items:
        item.display_image = item.product.get_main_image()
        item.discounted_price = item.product.get_discounted_price()
    
    context = {
        'wishlist_items': wishlist_items,
        'total_items': wishlist_items.count(),
    }
    
    return render(request, 'wishlist/wishlist.html', context)

@login_required
@require_POST
def add_to_wishlist(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        
        if not product_id or not variant_id:
            return JsonResponse({
                'success': False,
                'message': 'Product and variant are required.'
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
        
        wishlist, created = Wishlist.objects.get_or_create(user=request.user)
        
        wishlist_item, item_created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            product=product,
            variant=variant
        )
        
        if item_created:
            message = f'{product.product_name} added to wishlist!'
        else:
            message = f'{product.product_name} is already in your wishlist.'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'item_created': item_created,
            'wishlist_count': wishlist.items.count(),
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        print(e)
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while adding to wishlist.'
        })

@login_required
@require_POST
def remove_from_wishlist(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        data = json.loads(request.body)
        wishlist_item_id = data.get('wishlist_item_id')
        
        if not wishlist_item_id:
            return JsonResponse({
                'success': False,
                'message': 'Wishlist item ID is required.'
            })
        
        try:
            wishlist_item = WishlistItem.objects.get(id=wishlist_item_id, wishlist__user=request.user)
            product_name = wishlist_item.product.product_name
            wishlist_item.delete()
            
            wishlist = Wishlist.objects.get(user=request.user)
            
            return JsonResponse({
                'success': True,
                'message': f'{product_name} removed from wishlist.',
                'wishlist_count': wishlist.items.count(),
            })
        except WishlistItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Wishlist item not found.'
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data.'
        })
    except Exception as e:
        print(e)
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while removing item.'
        })

@login_required
@require_POST
def clear_wishlist(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        wishlist = Wishlist.objects.get(user=request.user)
        wishlist.items.all().delete()
        return JsonResponse({
            'success': True,
            'message': 'Wishlist cleared successfully.',
            'wishlist_count': 0,
        })
    except Wishlist.DoesNotExist:
        return JsonResponse({
            'success': True,
            'message': 'Wishlist is already empty.',
            'wishlist_count': 0,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while clearing wishlist.'
        })