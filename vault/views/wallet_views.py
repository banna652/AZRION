from .common_imports import *

@never_cache
@login_required
def wallet_view(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    # Get or create wallet
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    # Get transactions with pagination
    transactions = wallet.transactions.all().order_by('-created_at')
    paginator = Paginator(transactions, 10)
    page = request.GET.get('page')
    
    try:
        transactions_page = paginator.page(page)
    except PageNotAnInteger:
        transactions_page = paginator.page(1)
    except EmptyPage:
        transactions_page = paginator.page(paginator.num_pages)
    
    # Get referral statistics
    referral_rewards = ReferralReward.objects.filter(referrer=request.user)
    total_referrals = referral_rewards.count()
    total_referral_earnings = referral_rewards.aggregate(
        total=models.Sum('reward_amount')
    )['total'] or 0
    
    # Get referred users - Fixed the field name from date_joined to created_at
    referred_users = User.objects.filter(referred_by=request.user).order_by('-created_at')[:5]
    
    # Generate referral link
    current_site = get_current_site(request)
    referral_link = f"http://{current_site.domain}{reverse('sign_up_with_referral', kwargs={'token': request.user.referral_token})}"
    
    # Get active referral offer
    active_referral_offer = ReferralOffer.objects.filter(is_active=True).first()
    
    context = {
        'wallet': wallet,
        'transactions': transactions_page,
        'total_referrals': total_referrals,
        'total_referral_earnings': total_referral_earnings,
        'referred_users': referred_users,
        'referral_link': referral_link,
        'referral_code': request.user.referral_code,
        'active_referral_offer': active_referral_offer,
    }
    
    return render(request, 'wallet/wallet.html', context)

@login_required
@require_POST
def generate_referral_link(request):
    if check_user_blocked(request.user):
        return JsonResponse({
            'success': False,
            'message': 'Your account has been temporarily blocked.'
        })
    
    try:
        current_site = get_current_site(request)
        referral_link = f"http://{current_site.domain}{reverse('sign_up_with_referral', kwargs={'token': request.user.referral_token})}"
        
        return JsonResponse({
            'success': True,
            'referral_link': referral_link,
            'referral_code': request.user.referral_code
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error generating referral link.'
        })