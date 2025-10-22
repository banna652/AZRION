from .common_imports import *

@login_required
@user_passes_test(lambda u: u.is_staff)
def wallet_management_page(request):
    query = request.GET.get('q','').strip()
    transaction_type = request.GET.get('type', 'all')
    sort_order = request.GET.get('sort', 'desc')
    
    transactions = WalletTransaction.objects.select_related('wallet__user').all()
    
    if query:
        transactions = transactions.filter(
            Q(wallet__user__full_name__icontains=query) |
            Q(wallet__user__email__icontains=query) |
            Q(description__icontains=query)
        ).distinct()
        
    if transaction_type != 'all':
        transactions = transactions.filter(transaction_type=transaction_type)
        
    if sort_order == 'asc':
        transactions = transactions.order_by('created_at')
    else:
        transactions = transactions.order_by('-created_at')
        
    total_transactions = WalletTransaction.objects.count()
    credit_transactions = WalletTransaction.objects.filter(transaction_type='credit').count()
    debit_transactions = WalletTransaction.objects.filter(transaction_type='debit').count()
    total_credit_amount = WalletTransaction.objects.filter(transaction_type='credit').aggregate(total=Sum('amount'))['total'] or 0
    total_debit_amount = WalletTransaction.objects.filter(transaction_type='debit').aggregate(total=Sum('amount'))['total'] or 0
    
    paginator = Paginator(transactions, 7)
    page = request.GET.get('page')
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)
        
    context = {
        'transactions': transactions,
        'query': query,
        'transaction_type': transaction_type,
        'sort_order': sort_order,
        'total_transactions': total_transactions,
        'credit_transactions': credit_transactions,
        'debit_transactions': debit_transactions,
        'total_credit_amount': total_credit_amount,
        'total_debit_amount': total_debit_amount,
    }
    
    return render(request, 'wallet/wallet_management.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def wallet_transaction_detail(request, transaction_id):
    transaction = get_object_or_404(WalletTransaction, id=transaction_id)
    
    related_order = None
    if 'order' in (transaction.description or '').lower():
        match = re.search(r'order\s+(\w+)', transaction.description, re.IGNORECASE)
        if match:
            order_number = match.group(1)
            try:
                related_order = Order.objects.get(order_number=order_number)
            except Order.DoesNotExist:
                pass
            
    context = {
        'transaction': transaction,
        'user': transaction.wallet.user,
        'related_order': related_order,
    }
    
    return render(request, 'wallet/wallet_transaction_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def user_wallet_detail(request, user_id):
    user = get_object_or_404(User, id=user_id)
    wallet, created = Wallet.objects.get_or_create(user=user)
    
    transactions = wallet.transactions.all().order_by('-created_at')
    
    paginator = Paginator(transactions, 10)
    page = request.GET.get('page')
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)
        
    context = {
        'user': user,
        'wallet': wallet,
        'transaction': transactions,
    }
    
    return render(request, 'wallet/user_wallet_detail.html', context)