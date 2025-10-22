from .common_imports import *

@login_required
@user_passes_test(lambda u: u.is_staff)
def category_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    categories = Category.objects.all()

    if status_filter == 'active':
        categories = categories.filter(is_deleted=False)
    elif status_filter == 'inactive':
        categories = categories.filter(is_deleted=True)

    if query:
        categories = categories.filter(Q(name__icontains=query) | Q(description__icontains=query))

    categories = categories.order_by('-created_at')
    total_categories = Category.objects.count()
    active_categories = Category.objects.filter(is_deleted=False).count()
    inactive_categories = Category.objects.filter(is_deleted=True).count()

    paginator = Paginator(categories, 10)
    page = request.GET.get('page')
    try:
        categories = paginator.page(page)
    except PageNotAnInteger:
        categories = paginator.page(1)
    except EmptyPage:
        categories = paginator.page(paginator.num_pages)

    return render(request, 'category_list.html', {
        'categories': categories,
        'query': query,
        'status_filter': status_filter,
        'total_categories': total_categories,
        'active_categories': active_categories,
        'inactive_categories': inactive_categories,
    })
    
@login_required
@user_passes_test(lambda u: u.is_staff)
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        image = request.FILES.get('image')
        errors = []

        if not name:
            errors.append("Enter category name")
        elif not re.match(r'^[a-zA-Z\s]+$', name):
            errors.append("Category name should only contain letters and spaces")
        elif len(name) < 2:
            errors.append("Category name should be at least 2 characters long")
        elif len(name) > 50:
            errors.append("Category name should not exceed 50 characters")

        if not image:
            errors.append("Category image is required")
        else:
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if image.content_type not in allowed_types:
                errors.append("Please upload a valid image file (JPG, PNG, GIF)")
            if image.size > 10 * 1024 * 1024:
                errors.append("Image size should be less than 10MB")

        if not errors and Category.objects.filter(name__iexact=name, is_deleted=False).exists():
            errors.append("A category with this name already exists")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'add_category.html', {
                'name': name,
                'description': description
            })

        try:
            Category.objects.create(name=name, description=description, image=image)
            messages.success(request, f"Category '{name}' added successfully")
            return redirect('category_list')
        except Exception as e:
            messages.error(request, "An error occurred while adding the category")
            return render(request, 'add_category.html', {
                'name': name,
                'description': description
            })

    return render(request, 'add_category.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id, is_deleted=False)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        image = request.FILES.get('image')
        errors = []

        if not name:
            errors.append("Enter category name")
        elif not re.match(r'^[a-zA-Z\s]+$', name):
            errors.append("Category name should only contain letters and spaces")
        elif len(name) < 2:
            errors.append("Category name should be at least 2 characters long")
        elif len(name) > 50:
            errors.append("Category name should not exceed 50 characters")

        if not errors and Category.objects.filter(name__iexact=name, is_deleted=False).exclude(id=category_id).exists():
            errors.append("A category with this name already exists")

        if image:
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if image.content_type not in allowed_types:
                errors.append("Please upload a valid image file (JPG, PNG, GIF)")
            if image.size > 10 * 1024 * 1024:
                errors.append("Image size should be less than 10MB")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'edit_category.html', {
                'category': category,
                'name': name,
                'description': description
            })

        try:
            category.name = name
            category.description = description
            if image:
                category.image = image
            category.save()
            messages.success(request, f"Category '{name}' updated successfully")
            return redirect('category_list')
        except Exception as e:
            messages.error(request, "An error occurred while updating the category")
            return render(request, 'edit_category.html', {
                'category': category,
                'name': name,
                'description': description
            })

    return render(request, 'edit_category.html', {
        'category': category
    })
    
@login_required
@user_passes_test(lambda u: u.is_staff)
def toggle_category_status(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        category_name = category.name

        if action == 'deactivate' and not category.is_deleted:
            category.is_deleted = True
            category.save()
            messages.success(request, f"Category '{category_name}' has been deactivated successfully")
        elif action == 'activate' and category.is_deleted:
            category.is_deleted = False
            category.save()
            messages.success(request, f"Category '{category_name}' has been activated successfully")
        else:
            messages.error(request, "Invalid action or category status")
        return redirect('category_list')

    return render(request, 'toggle_category_status.html', {
        'category': category,
        
    })
    
