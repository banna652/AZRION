from .common_imports import *

@never_cache
@login_required
@user_passes_test(lambda u: u.is_staff)
def coupon_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    discount_type_filter = request.GET.get('discount_type', 'all')
    
    coupons = Coupon.objects.all()
    
    if query:
        coupons = coupons.filter(
            Q(code__icontains=query) |
            Q(description__icontains=query)
        )
    
    if status_filter == 'active':
        coupons = coupons.filter(is_active=True, valid_until__gte=timezone.now())
    elif status_filter == 'inactive':
        coupons = coupons.filter(is_active=False)
    elif status_filter == 'expired':
        coupons = coupons.filter(valid_until__lt=timezone.now())
    
    if discount_type_filter != 'all':
        coupons = coupons.filter(discount_type=discount_type_filter)
    
    coupons = coupons.order_by('-created_at')
    
    # Statistics
    total_coupons = Coupon.objects.count()
    active_coupons = Coupon.objects.filter(is_active=True, valid_until__gte=timezone.now()).count()
    expired_coupons = Coupon.objects.filter(valid_until__lt=timezone.now()).count()
    total_usage = CouponUsage.objects.count()
    
    paginator = Paginator(coupons, 10)
    page = request.GET.get('page')
    
    try:
        coupons = paginator.page(page)
    except PageNotAnInteger:
        coupons = paginator.page(1)
    except EmptyPage:
        coupons = paginator.page(paginator.num_pages)
    
    context = {
        'coupons': coupons,
        'query': query,
        'status_filter': status_filter,
        'discount_type_filter': discount_type_filter,
        'total_coupons': total_coupons,
        'active_coupons': active_coupons,
        'expired_coupons': expired_coupons,
        'total_usage': total_usage,
    }
    
    return render(request, 'coupons/coupon_list.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def add_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        discount_type = request.POST.get('discount_type', 'percentage')
        discount_value = request.POST.get('discount_value', '').strip()
        minimum_amount = request.POST.get('minimum_amount', '0').strip()
        maximum_discount = request.POST.get('maximum_discount', '').strip()
        usage_limit = request.POST.get('usage_limit', '').strip()
        valid_from = request.POST.get('valid_from', '').strip()
        valid_until = request.POST.get('valid_until', '').strip()
        
        errors = []
        
        # Validate coupon code
        if not code:
            errors.append("Coupon code is required")
        elif len(code) < 3:
            errors.append("Coupon code should be at least 3 characters long")
        elif len(code) > 50:
            errors.append("Coupon code should not exceed 50 characters")
        elif not re.match(r'^[A-Z0-9]+$', code):
            errors.append("Coupon code should only contain uppercase letters and numbers")
        elif Coupon.objects.filter(code=code).exists():
            errors.append("A coupon with this code already exists")
        
        # Validate discount value
        if not discount_value:
            errors.append("Discount value is required")
        else:
            try:
                discount_value = float(discount_value)
                if discount_value <= 0:
                    errors.append("Discount value must be greater than 0")
                if discount_type == 'percentage' and discount_value > 100:
                    errors.append("Percentage discount cannot exceed 100%")
            except ValueError:
                errors.append("Please enter a valid discount value")
        
        # Validate minimum amount
        try:
            minimum_amount = float(minimum_amount)
            if minimum_amount < 0:
                errors.append("Minimum amount cannot be negative")
        except ValueError:
            errors.append("Please enter a valid minimum amount")
        
        # Validate maximum discount
        if maximum_discount:
            try:
                maximum_discount = float(maximum_discount)
                if maximum_discount <= 0:
                    errors.append("Maximum discount must be greater than 0")
            except ValueError:
                errors.append("Please enter a valid maximum discount")
        else:
            maximum_discount = None
        
        # Validate usage limit
        if usage_limit:
            try:
                usage_limit = int(usage_limit)
                if usage_limit <= 0:
                    errors.append("Usage limit must be greater than 0")
            except ValueError:
                errors.append("Please enter a valid usage limit")
        else:
            usage_limit = None
        
        # Validate dates
        if not valid_from:
            errors.append("Valid from date is required")
        if not valid_until:
            errors.append("Valid until date is required")
        
        if valid_from and valid_until:
            try:
                from_date = timezone.make_aware(datetime.strptime(valid_from, '%Y-%m-%dT%H:%M'))
                until_date = timezone.make_aware(datetime.strptime(valid_until, '%Y-%m-%dT%H:%M'))
                
                if from_date >= until_date:
                    errors.append("Valid from date must be before valid until date")
                
                if until_date <= timezone.now():
                    errors.append("Valid until date must be in the future")
                    
            except ValueError:
                errors.append("Please enter valid dates")
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'coupons/add_coupon.html', {
                'code': request.POST.get('code', ''),
                'description': description,
                'discount_type': discount_type,
                'discount_value': request.POST.get('discount_value', ''),
                'minimum_amount': request.POST.get('minimum_amount', ''),
                'maximum_discount': request.POST.get('maximum_discount', ''),
                'usage_limit': request.POST.get('usage_limit', ''),
                'valid_from': valid_from,
                'valid_until': valid_until,
            })
        
        try:
            Coupon.objects.create(
                code=code,
                description=description,
                discount_type=discount_type,
                discount_value=discount_value,
                minimum_amount=minimum_amount,
                maximum_discount=maximum_discount,
                usage_limit=usage_limit,
                valid_from=from_date,
                valid_until=until_date,
                is_active=True
            )
            messages.success(request, f"Coupon '{code}' created successfully")
            return redirect('coupon_list')
        except Exception as e:
            messages.error(request, "An error occurred while creating the coupon")
            return render(request, 'coupons/add_coupon.html', {
                'code': request.POST.get('code', ''),
                'description': description,
                'discount_type': discount_type,
                'discount_value': request.POST.get('discount_value', ''),
                'minimum_amount': request.POST.get('minimum_amount', ''),
                'maximum_discount': request.POST.get('maximum_discount', ''),
                'usage_limit': request.POST.get('usage_limit', ''),
                'valid_from': valid_from,
                'valid_until': valid_until,
            })
    
    return render(request, 'coupons/add_coupon.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)
    
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        description = request.POST.get('description', '').strip()
        discount_type = request.POST.get('discount_type', 'percentage')
        discount_value = request.POST.get('discount_value', '').strip()
        minimum_amount = request.POST.get('minimum_amount', '0').strip()
        maximum_discount = request.POST.get('maximum_discount', '').strip()
        usage_limit = request.POST.get('usage_limit', '').strip()
        valid_from = request.POST.get('valid_from', '').strip()
        valid_until = request.POST.get('valid_until', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        errors = []
        
        # Validate coupon code
        if not code:
            errors.append("Coupon code is required")
        elif len(code) < 3:
            errors.append("Coupon code should be at least 3 characters long")
        elif len(code) > 50:
            errors.append("Coupon code should not exceed 50 characters")
        elif not re.match(r'^[A-Z0-9]+$', code):
            errors.append("Coupon code should only contain uppercase letters and numbers")
        elif Coupon.objects.filter(code=code).exclude(id=coupon.id).exists():
            errors.append("A coupon with this code already exists")
        
        # Validate discount value
        if not discount_value:
            errors.append("Discount value is required")
        else:
            try:
                discount_value = float(discount_value)
                if discount_value <= 0:
                    errors.append("Discount value must be greater than 0")
                if discount_type == 'percentage' and discount_value > 100:
                    errors.append("Percentage discount cannot exceed 100%")
            except ValueError:
                errors.append("Please enter a valid discount value")
        
        # Validate minimum amount
        try:
            minimum_amount = float(minimum_amount)
            if minimum_amount < 0:
                errors.append("Minimum amount cannot be negative")
        except ValueError:
            errors.append("Please enter a valid minimum amount")
        
        # Validate maximum discount
        if maximum_discount:
            try:
                maximum_discount = float(maximum_discount)
                if maximum_discount <= 0:
                    errors.append("Maximum discount must be greater than 0")
            except ValueError:
                errors.append("Please enter a valid maximum discount")
        else:
            maximum_discount = None
        
        # Validate usage limit
        if usage_limit:
            try:
                usage_limit = int(usage_limit)
                if usage_limit <= 0:
                    errors.append("Usage limit must be greater than 0")
            except ValueError:
                errors.append("Please enter a valid usage limit")
        else:
            usage_limit = None
        
        # Validate dates
        if not valid_from:
            errors.append("Valid from date is required")
        if not valid_until:
            errors.append("Valid until date is required")
        
        if valid_from and valid_until:
            try:
                from_date = timezone.make_aware(datetime.strptime(valid_from, '%Y-%m-%dT%H:%M'))
                until_date = timezone.make_aware(datetime.strptime(valid_until, '%Y-%m-%dT%H:%M'))
                
                if from_date >= until_date:
                    errors.append("Valid from date must be before valid until date")
                    
            except ValueError:
                errors.append("Please enter valid dates")
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                coupon.code = code
                coupon.description = description
                coupon.discount_type = discount_type
                coupon.discount_value = discount_value
                coupon.minimum_amount = minimum_amount
                coupon.maximum_discount = maximum_discount
                coupon.usage_limit = usage_limit
                coupon.valid_from = from_date
                coupon.valid_until = until_date
                coupon.is_active = is_active
                coupon.save()
                
                messages.success(request, f"Coupon '{code}' updated successfully")
                return redirect('coupon_list')
            except Exception as e:
                messages.error(request, "An error occurred while updating the coupon")
    
    # Get usage statistics
    usage_count = CouponUsage.objects.filter(coupon=coupon).count()
    
    context = {
        'coupon': coupon,
        'usage_count': usage_count,
    }
    
    return render(request, 'coupons/edit_coupon.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def toggle_coupon_status(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'activate':
            coupon.is_active = True
            coupon.save()
            messages.success(request, f"Coupon '{coupon.code}' has been activated successfully")
        elif action == 'deactivate':
            coupon.is_active = False
            coupon.save()
            messages.success(request, f"Coupon '{coupon.code}' has been deactivated successfully")
        
        return redirect('coupon_list')
    
    # Get usage statistics for confirmation
    usage_count = CouponUsage.objects.filter(coupon=coupon).count()
    
    return render(request, 'coupons/toggle_coupon_status.html', {
        'coupon': coupon,
        'usage_count': usage_count,
    })