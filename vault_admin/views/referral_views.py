from .common_imports import *

@never_cache
@login_required
@user_passes_test(lambda u: u.is_staff)
def category_offer_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    category_filter = request.GET.get('category', 'all')
    
    offers = CategoryOffer.objects.select_related('category').all()
    now_utc = timezone.now()  # timezone-aware UTC
    now = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))
    
    if query:
        offers = offers.filter(
            Q(offer_name__icontains=query) |
            Q(category__name__icontains=query) |
            Q(description__icontains=query)
        )
    
    if status_filter == 'active':
        offers = offers.filter(is_active=True)
    elif status_filter == 'inactive':
        offers = offers.filter(is_active=False)
    elif status_filter == 'expired':
        offers = offers.filter(valid_until__lt=timezone.now())
    elif status_filter == 'upcoming':
        offers = offers.filter(valid_from__gt=timezone.now())
    
    if category_filter != 'all':
        try:
            category_filter = int(category_filter)
            offers = offers.filter(category_id=category_filter)
        except (ValueError, TypeError):
            category_filter = 'all'
    
    offers = offers.order_by('-created_at')
    
    categories = Category.objects.filter(is_deleted=False).order_by('name')
    
    paginator = Paginator(offers, 10)
    page = request.GET.get('page')
    
    try:
        offers = paginator.page(page)
    except PageNotAnInteger:
        offers = paginator.page(1)
    except EmptyPage:
        offers = paginator.page(paginator.num_pages)
    
    # Statistics
    total_offers = CategoryOffer.objects.count()
    active_offers = CategoryOffer.objects.filter(is_active=True).count()
    expired_offers = CategoryOffer.objects.filter(valid_until__lt=timezone.now()).count()
    
    context = {
        'offers': offers,
        'categories': categories,
        'query': query,
        'status_filter': status_filter,
        'category_filter': str(category_filter) if category_filter != 'all' else 'all',
        'total_offers': total_offers,
        'active_offers': active_offers,
        'expired_offers': expired_offers,
        'now':now
    }
    
    return render(request, 'offers/category_offer_list.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def add_category_offer(request):
    if request.method == 'POST':
        offer_name = request.POST.get('offer_name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        discount_percentage = request.POST.get('discount_percentage', '').strip()
        valid_from = request.POST.get('valid_from', '').strip()
        valid_until = request.POST.get('valid_until', '').strip()
        
        errors = []
        now_utc = timezone.now()  # timezone-aware UTC
        now = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))
        
        # Validate offer name
        if not offer_name:
            errors.append("Offer name is required")
        elif len(offer_name) < 3:
            errors.append("Offer name should be at least 3 characters long")
        elif len(offer_name) > 100:
            errors.append("Offer name should not exceed 100 characters")
        
        # Validate category
        if not category_id:
            errors.append("Please select a category")
        else:
            try:
                category = Category.objects.get(id=category_id, is_deleted=False)
            except Category.DoesNotExist:
                errors.append("Selected category does not exist")
        
        # Validate discount percentage
        if not discount_percentage:
            errors.append("Discount percentage is required")
        else:
            try:
                discount_percentage = float(discount_percentage)
                if discount_percentage <= 0 or discount_percentage > 100:
                    errors.append("Discount percentage must be between 0.01 and 100")
            except ValueError:
                errors.append("Please enter a valid discount percentage")
        
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
            categories = Category.objects.filter(is_deleted=False).order_by('name')
            for error in errors:
                messages.error(request, error)
            return render(request, 'offers/add_category_offer.html', {
                'categories': categories,
                'offer_name': offer_name,
                'description': description,
                'category_id': category_id,
                'discount_percentage': request.POST.get('discount_percentage', ''),
                'valid_from': valid_from,
                'valid_until': valid_until,
                'now': now,
            })
        
        try:
            CategoryOffer.objects.create(
                category=category,
                offer_name=offer_name,
                description=description,
                discount_percentage=discount_percentage,
                valid_from=from_date,
                valid_until=until_date,
                is_active=True
            )
            messages.success(request, f"Category offer '{offer_name}' created successfully")
            return redirect('category_offer_list')
        except Exception as e:
            messages.error(request, "An error occurred while creating the offer")
            categories = Category.objects.filter(is_deleted=False).order_by('name')
            return render(request, 'offers/add_category_offer.html', {
                'categories': categories,
                'offer_name': offer_name,
                'description': description,
                'category_id': category_id,
                'discount_percentage': request.POST.get('discount_percentage', ''),
                'valid_from': valid_from,
                'valid_until': valid_until,
                'now': now,
            })
    
    categories = Category.objects.filter(is_deleted=False).order_by('name')
    return render(request, 'offers/add_category_offer.html', {'categories': categories})

@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    
    if request.method == 'POST':
        offer_name = request.POST.get('offer_name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        discount_percentage = request.POST.get('discount_percentage', '').strip()
        valid_from = request.POST.get('valid_from', '').strip()
        valid_until = request.POST.get('valid_until', '').strip()
        
        errors = []
        
        # Validate offer name
        if not offer_name:
            errors.append("Offer name is required")
        elif len(offer_name) < 3:
            errors.append("Offer name should be at least 3 characters long")
        elif len(offer_name) > 100:
            errors.append("Offer name should not exceed 100 characters")
        
        # Validate category
        if not category_id:
            errors.append("Please select a category")
        else:
            try:
                category = Category.objects.get(id=category_id, is_deleted=False)
            except Category.DoesNotExist:
                errors.append("Selected category does not exist")
        
        # Validate discount percentage
        if not discount_percentage:
            errors.append("Discount percentage is required")
        else:
            try:
                discount_percentage = float(discount_percentage)
                if discount_percentage <= 0 or discount_percentage > 100:
                    errors.append("Discount percentage must be between 0.01 and 100")
            except ValueError:
                errors.append("Please enter a valid discount percentage")
        
        # Validate dates
        if not valid_from:
            errors.append("Valid from date is required")
        if not valid_until:
            errors.append("Valid until date is required")
        
        if valid_from and valid_until:
            try:
                from_date = datetime.strptime(valid_from, '%Y-%m-%dT%H:%M')
                until_date = datetime.strptime(valid_until, '%Y-%m-%dT%H:%M')
                
                if from_date >= until_date:
                    errors.append("Valid from date must be before valid until date")
                    
            except ValueError:
                errors.append("Please enter valid dates")
        
        if errors:
            categories = Category.objects.filter(is_deleted=False).order_by('name')
            for error in errors:
                messages.error(request, error)
            return render(request, 'offers/edit_category_offer.html', {
                'offer': offer,
                'categories': categories,
            })
        
        try:
            offer.category = category
            offer.offer_name = offer_name
            offer.description = description
            offer.discount_percentage = discount_percentage
            offer.valid_from = from_date
            offer.valid_until = until_date
            offer.save()
            
            messages.success(request, f"Category offer '{offer_name}' updated successfully")
            return redirect('category_offer_list')
        except Exception as e:
            messages.error(request, "An error occurred while updating the offer")
    
    categories = Category.objects.filter(is_deleted=False).order_by('name')
    return render(request, 'offers/edit_category_offer.html', {
        'offer': offer,
        'categories': categories,
    })
    
@login_required
@user_passes_test(lambda u: u.is_staff)
def toggle_category_offer_status(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'activate' and not offer.is_active:
            offer.is_active = True
            offer.save()
            messages.success(request, f"Category offer '{offer.offer_name}' has been activated")
        elif action == 'deactivate' and offer.is_active:
            offer.is_active = False
            offer.save()
            messages.success(request, f"Category offer '{offer.offer_name}' has been deactivated")
        else:
            messages.error(request, "Invalid action or offer status")
    
    return redirect('category_offer_list')

@never_cache
@login_required
@user_passes_test(lambda u: u.is_staff)
def referral_offer_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    
    offers = ReferralOffer.objects.all()
    
    if query:
        offers = offers.filter(
            Q(offer_name__icontains=query) |
            Q(description__icontains=query)
        )
    
    if status_filter == 'active':
        offers = offers.filter(is_active=True)
    elif status_filter == 'inactive':
        offers = offers.filter(is_active=False)
    
    offers = offers.order_by('-created_at')
    
    paginator = Paginator(offers, 10)
    page = request.GET.get('page')
    
    try:
        offers = paginator.page(page)
    except PageNotAnInteger:
        offers = paginator.page(1)
    except EmptyPage:
        offers = paginator.page(paginator.num_pages)
    
    # Statistics
    total_offers = ReferralOffer.objects.count()
    active_offers = ReferralOffer.objects.filter(is_active=True).count()
    total_referrals = ReferralReward.objects.count()
    
    context = {
        'offers': offers,
        'query': query,
        'status_filter': status_filter,
        'total_offers': total_offers,
        'active_offers': active_offers,
        'total_referrals': total_referrals,
    }
    
    return render(request, 'offers/referral_offer_list.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def add_referral_offer(request):
    if request.method == 'POST':
        offer_name = request.POST.get('offer_name', '').strip()
        description = request.POST.get('description', '').strip()
        reward_type = request.POST.get('reward_type', 'coupon')
        reward_value = request.POST.get('reward_value', '').strip()
        reward_type_detail = request.POST.get('reward_type_detail', 'percentage')
        minimum_order_amount = request.POST.get('minimum_order_amount', '0').strip()
        max_referrals = request.POST.get('max_referrals', '').strip()
        
        errors = []
        
        # Validate offer name
        if not offer_name:
            errors.append("Offer name is required")
        elif len(offer_name) < 3:
            errors.append("Offer name should be at least 3 characters long")
        elif len(offer_name) > 100:
            errors.append("Offer name should not exceed 100 characters")
        
        # Validate reward value
        if not reward_value:
            errors.append("Reward value is required")
        else:
            try:
                reward_value = float(reward_value)
                if reward_value <= 0:
                    errors.append("Reward value must be greater than 0")
                if reward_type_detail == 'percentage' and reward_value > 100:
                    errors.append("Percentage reward cannot exceed 100%")
            except ValueError:
                errors.append("Please enter a valid reward value")
        
        # Validate minimum order amount
        try:
            minimum_order_amount = float(minimum_order_amount)
            if minimum_order_amount < 0:
                errors.append("Minimum order amount cannot be negative")
        except ValueError:
            errors.append("Please enter a valid minimum order amount")
        
        # Validate max referrals
        if max_referrals:
            try:
                max_referrals = int(max_referrals)
                if max_referrals <= 0:
                    errors.append("Maximum referrals must be greater than 0")
            except ValueError:
                errors.append("Please enter a valid maximum referrals number")
        else:
            max_referrals = None
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'offers/add_referral_offer.html', {
                'offer_name': offer_name,
                'description': description,
                'reward_type': reward_type,
                'reward_value': request.POST.get('reward_value', ''),
                'reward_type_detail': reward_type_detail,
                'minimum_order_amount': request.POST.get('minimum_order_amount', ''),
                'max_referrals': request.POST.get('max_referrals', ''),
            })
        
        try:
            ReferralOffer.objects.create(
                offer_name=offer_name,
                description=description,
                reward_type=reward_type,
                reward_value=reward_value,
                reward_type_detail=reward_type_detail,
                minimum_order_amount=minimum_order_amount,
                max_referrals=max_referrals,
                is_active=True
            )
            messages.success(request, f"Referral offer '{offer_name}' created successfully")
            return redirect('referral_offer_list')
        except Exception as e:
            messages.error(request, "An error occurred while creating the offer")
            return render(request, 'offers/add_referral_offer.html', {
                'offer_name': offer_name,
                'description': description,
                'reward_type': reward_type,
                'reward_value': request.POST.get('reward_value', ''),
                'reward_type_detail': reward_type_detail,
                'minimum_order_amount': request.POST.get('minimum_order_amount', ''),
                'max_referrals': request.POST.get('max_referrals', ''),
            })
    
    return render(request, 'offers/add_referral_offer.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_referral_offer(request, offer_id):
    offer = get_object_or_404(ReferralOffer, id=offer_id)
    
    if request.method == 'POST':
        offer_name = request.POST.get('offer_name', '').strip()
        description = request.POST.get('description', '').strip()
        reward_type = request.POST.get('reward_type', 'coupon')
        reward_value = request.POST.get('reward_value', '').strip()
        reward_type_detail = request.POST.get('reward_type_detail', 'percentage')
        minimum_order_amount = request.POST.get('minimum_order_amount', '0').strip()
        max_referrals = request.POST.get('max_referrals', '').strip()
        
        errors = []
        
        # Validate offer name
        if not offer_name:
            errors.append("Offer name is required")
        elif len(offer_name) < 3:
            errors.append("Offer name should be at least 3 characters long")
        elif len(offer_name) > 100:
            errors.append("Offer name should not exceed 100 characters")
        
        # Validate reward value
        if not reward_value:
            errors.append("Reward value is required")
        else:
            try:
                reward_value = float(reward_value)
                if reward_value <= 0:
                    errors.append("Reward value must be greater than 0")
                if reward_type_detail == 'percentage' and reward_value > 100:
                    errors.append("Percentage reward cannot exceed 100%")
            except ValueError:
                errors.append("Please enter a valid reward value")
        
        # Validate minimum order amount
        try:
            minimum_order_amount = float(minimum_order_amount)
            if minimum_order_amount < 0:
                errors.append("Minimum order amount cannot be negative")
        except ValueError:
            errors.append("Please enter a valid minimum order amount")
        
        # Validate max referrals
        if max_referrals:
            try:
                max_referrals = int(max_referrals)
                if max_referrals <= 0:
                    errors.append("Maximum referrals must be greater than 0")
            except ValueError:
                errors.append("Please enter a valid maximum referrals number")
        else:
            max_referrals = None
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'offers/edit_referral_offer.html', {'offer': offer})
        
        try:
            offer.offer_name = offer_name
            offer.description = description
            offer.reward_type = reward_type
            offer.reward_value = reward_value
            offer.reward_type_detail = reward_type_detail
            offer.minimum_order_amount = minimum_order_amount
            offer.max_referrals = max_referrals
            offer.save()
            
            messages.success(request, f"Referral offer '{offer_name}' updated successfully")
            return redirect('referral_offer_list')
        except Exception as e:
            messages.error(request, "An error occurred while updating the offer")
    
    return render(request, 'offers/edit_referral_offer.html', {'offer': offer})

@login_required
@user_passes_test(lambda u: u.is_staff)
def toggle_referral_offer_status(request, offer_id):
    offer = get_object_or_404(ReferralOffer, id=offer_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'activate' and not offer.is_active:
            offer.is_active = True
            offer.save()
            messages.success(request, f"Referral offer '{offer.offer_name}' has been activated")
        elif action == 'deactivate' and offer.is_active:
            offer.is_active = False
            offer.save()
            messages.success(request, f"Referral offer '{offer.offer_name}' has been deactivated")
        else:
            messages.error(request, "Invalid action or offer status")
    
    return redirect('referral_offer_list')

@never_cache
@login_required
@user_passes_test(lambda u: u.is_staff)
def referral_rewards_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    
    rewards = ReferralReward.objects.select_related(
        'referrer', 'referred_user', 'referral_offer', 'coupon'
    ).all()
    
    if query:
        rewards = rewards.filter(
            Q(referrer__full_name__icontains=query) |
            Q(referrer__email__icontains=query) |
            Q(referred_user__full_name__icontains=query) |
            Q(referred_user__email__icontains=query)
        )
    
    if status_filter == 'claimed':
        rewards = rewards.filter(is_claimed=True)
    elif status_filter == 'unclaimed':
        rewards = rewards.filter(is_claimed=False)
    
    rewards = rewards.order_by('-created_at')
    
    paginator = Paginator(rewards, 15)
    page = request.GET.get('page')
    
    try:
        rewards = paginator.page(page)
    except PageNotAnInteger:
        rewards = paginator.page(1)
    except EmptyPage:
        rewards = paginator.page(paginator.num_pages)
    
    # Statistics
    total_rewards = ReferralReward.objects.count()
    claimed_rewards = ReferralReward.objects.filter(is_claimed=True).count()
    total_reward_value = ReferralReward.objects.aggregate(
        total=Sum('reward_amount')
    )['total'] or 0
    
    context = {
        'rewards': rewards,
        'query': query,
        'status_filter': status_filter,
        'total_rewards': total_rewards,
        'claimed_rewards': claimed_rewards,
        'total_reward_value': total_reward_value,
    }
    
    return render(request, 'offers/referral_rewards_list.html', context)