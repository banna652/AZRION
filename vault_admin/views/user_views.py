from .common_imports import *

@never_cache
@login_required
@user_passes_test(lambda u: u.is_staff)
def user_management_page(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', 'all')
    sort_order = request.GET.get('sort', 'desc')
    user_list = User.objects.filter(is_staff=False)

    if query:
        user_list = user_list.filter(
            Q(full_name__icontains=query) |
            Q(email__icontains=query) |
            Q(ph_number__icontains=query)
        )

    if status == 'active':
        user_list = user_list.filter(is_active=True)
    elif status == 'blocked':
        user_list = user_list.filter(is_active=False)

    if sort_order == 'asc':
        user_list = user_list.order_by('created_at')
    else:
        user_list = user_list.order_by('-created_at')

    paginator = Paginator(user_list, 10)
    page = request.GET.get('page')
    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        users = paginator.page(paginator.num_pages)

    active_count = User.objects.filter(is_active=True, is_staff=False).count()
    blocked_count = User.objects.filter(is_active=False, is_staff=False).count()

    return render(request, 'user_management.html', {
        'users': users,
        'active_count': active_count,
        'blocked_count': blocked_count,
        'query': query,
        'status': status,
        'sort_order': sort_order,
    })
    
@login_required
def block_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user.is_staff:
        user.is_active = False
        user.save()
    return redirect('user_management')

@login_required
def unblock_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user.is_staff:
        user.is_active = True
        user.save()
    return redirect('user_management')

def admin_profile(request):
    return render(request, 'settings.html')