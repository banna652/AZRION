from .common_imports import *

@never_cache
@login_required
@user_passes_test(lambda u: u.is_staff)
def product_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    category_filter = request.GET.get('category', 'all')
    sort_order = request.GET.get('sort', 'desc')

    products = Product.objects.select_related('category').prefetch_related('variants__images').annotate(
        variant_count=Count('variants')
    )

    if status_filter == 'active':
        products = products.filter(is_deleted=False)
    elif status_filter == 'inactive':
        products = products.filter(is_deleted=True)

    if category_filter != 'all':
        try:
            category_filter = int(category_filter)
            products = products.filter(category_id=category_filter)
        except (ValueError, TypeError):
            pass

    if query:
        search_terms = re.findall(r'\w+', query.lower())
        if search_terms:
            search_query = Q()
            for term in search_terms:
                search_query |= (
                    Q(product_name__icontains=term) |
                    Q(product_description__icontains=term) |
                    Q(category__name__icontains=term)
                )
            products = products.filter(search_query)
        else:
            products = products.filter(
                Q(product_name__icontains=query) |
                Q(product_description__icontains=query) |
                Q(category__name__icontains=query)
            )

    if sort_order == 'asc':
        products = products.order_by('created_at')
    else:
        products = products.order_by('-created_at')

    categories = Category.objects.filter(is_deleted=False).order_by('name')
    paginator = Paginator(products, 10)
    page = request.GET.get('page')
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    total_products = Product.objects.count()
    active_products = Product.objects.filter(is_deleted=False).count()
    inactive_products = Product.objects.filter(is_deleted=True).count()

    return render(request, 'product_lists.html', {
        'products': products,
        'categories': categories,
        'query': query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'sort_order': sort_order,
        'total_products': total_products,
        'active_products': active_products,
        'inactive_products': inactive_products,
    })
    
@login_required
@user_passes_test(lambda u: u.is_staff)
def add_product(request):
    if request.method == 'POST':
        product_name = request.POST.get('product_name', '').strip()
        product_description = request.POST.get('product_description', '').strip()
        category_id = request.POST.get('category')
        price = request.POST.get('price', '').strip()
        product_offer = request.POST.get('product_offer', '0').strip()
        main_image = request.FILES.get('main_image')
        errors = []

        if not product_name:
            errors.append("Product name is required")
        elif len(product_name) < 2:
            errors.append("Product name should be at least 2 characters long")
        elif len(product_name) > 100:
            errors.append("Product name should not exceed 100 characters")
        elif Product.objects.filter(product_name__iexact=product_name, is_deleted=False).exists():
            errors.append("A product with this name already exists")

        if not category_id:
            errors.append("Please select a category")
        else:
            try:
                category = Category.objects.get(id=category_id, is_deleted=False)
            except Category.DoesNotExist:
                errors.append("Selected category does not exist")

        if not price:
            errors.append("Price is required")
        else:
            try:
                price = int(price)
                if price <= 0:
                    errors.append("Price must be greater than 0")
            except ValueError:
                errors.append("Please enter a valid price")

        try:
            product_offer = float(product_offer)
            if product_offer < 0 or product_offer > 100:
                errors.append("Offer percentage must be between 0 and 100")
        except ValueError:
            errors.append("Please enter a valid offer percentage")

        if not main_image:
            errors.append("Main product image is required")
        else:
            if not main_image.content_type.startswith('image/'):
                errors.append("Please upload a valid image file for main image")
            if main_image.size > 10 * 1024 * 1024:
                errors.append("Main image should be less than 10MB")

        if errors:
            categories = Category.objects.filter(is_deleted=False).order_by('name')
            for error in errors:
                messages.error(request, error)
            return render(request, 'add_product.html', {
                'categories': categories,
                'product_name': product_name,
                'product_description': product_description,
                'category_id': category_id,
                'price': request.POST.get('price', ''),
                'product_offer': request.POST.get('product_offer', ''),
            })

        try:
            processed_main_image = resize_and_crop_image(main_image)
            
            product = Product.objects.create(
                product_name=product_name,
                product_description=product_description,
                category=category,
                price=price,
                product_offer=product_offer
            )

            product.main_image.save(
                f"{product.product_name}_main.jpg",
                processed_main_image,
                save=True
            )

            messages.success(request, f"Product '{product_name}' added successfully. You can now add color variants.")
            return redirect('product_variants', product_id=product.id)
        except Exception as e:
            messages.error(request, "An error occurred while adding the product")
            categories = Category.objects.filter(is_deleted=False).order_by('name')
            return render(request, 'add_product.html', {
                'categories': categories,
                'product_name': product_name,
                'product_description': product_description,
                'category_id': category_id,
                'price': request.POST.get('price', ''),
                'product_offer': request.POST.get('product_offer', ''),
            })

    categories = Category.objects.filter(is_deleted=False).order_by('name')
    return render(request, 'add_product.html', {'categories': categories})

@login_required
@user_passes_test(lambda u: u.is_staff)
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variants = product.variants.prefetch_related('images').all()
    return render(request, 'products_details.html', {
        'product': product,
        'variants': variants
    })
    
@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product_name = request.POST.get('product_name', '').strip()
        product_description = request.POST.get('product_description', '').strip()
        category_id = request.POST.get('category')
        price = request.POST.get('price', '').strip()
        product_offer = request.POST.get('product_offer', '0').strip()
        main_image = request.FILES.get('main_image')
        errors = []

        if not product_name:
            errors.append("Product name is required")
        elif len(product_name) < 2:
            errors.append("Product name should be at least 2 characters long")
        elif len(product_name) > 100:
            errors.append("Product name should not exceed 100 characters")
        elif Product.objects.filter(product_name__iexact=product_name, is_deleted=False).exclude(id=product_id).exists():
            errors.append("A product with this name already exists")

        if not category_id:
            errors.append("Please select a category")
        else:
            try:
                category = Category.objects.get(id=category_id, is_deleted=False)
            except Category.DoesNotExist:
                errors.append("Selected category does not exist")

        if not price:
            errors.append("Price is required")
        else:
            try:
                price = int(price)
                if price <= 0:
                    errors.append("Price must be greater than 0")
            except ValueError:
                errors.append("Please enter a valid price")

        try:
            product_offer = float(product_offer)
            if product_offer < 0 or product_offer > 100:
                errors.append("Offer percentage must be between 0 and 100")
        except ValueError:
            errors.append("Please enter a valid offer percentage")

        if main_image:
            if not main_image.content_type.startswith('image/'):
                errors.append("Please upload a valid image file for main image")
            if main_image.size > 10 * 1024 * 1024:
                errors.append("Main image should be less than 10MB")

        if errors:
            categories = Category.objects.filter(is_deleted=False).order_by('name')
            for error in errors:
                messages.error(request, error)
            return render(request, 'edit_product.html', {
                'product': product,
                'categories': categories,
            })

        try:
            product.product_name = product_name
            product.product_description = product_description
            product.category = category
            product.price = price
            product.product_offer = product_offer

            if main_image:
                processed_main_image = resize_and_crop_image(main_image)
                product.main_image.save(
                    f"{product.product_name}_main.jpg",
                    processed_main_image,
                    save=False
                )

            product.save()
            messages.success(request, f"Product '{product_name}' updated successfully")
            return redirect('product_list')
        except Exception as e:
            messages.error(request, "An error occurred while updating the product")
            categories = Category.objects.filter(is_deleted=False).order_by('name')
            return render(request, 'edit_product.html', {
                'product': product,
                'categories': categories,
            })

    categories = Category.objects.filter(is_deleted=False).order_by('name')
    return render(request, 'edit_product.html', {
        'product': product,
        'categories': categories,
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def toggle_product_status(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        
        action = request.POST.get('action')
        product_name = product.product_name

        if action == 'deactivate' and not product.is_deleted:
            product.is_deleted = True
            product.save()
            messages.success(request, f"Product '{product_name}' has been deactivated successfully")
        elif action == 'activate' and product.is_deleted:
            product.is_deleted = False
            product.save()
            messages.success(request, f"Product '{product_name}' has been activated successfully")
        else:
            messages.error(request, "Invalid action or product status")
        return redirect('product_list')

    return render(request, 'toggle_product_status.html', {
        'product': product,
        
    })
    
@login_required
@user_passes_test(lambda u: u.is_staff)
def product_variants(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variants = product.variants.prefetch_related('images').all()
    
    return render(request, 'product_variants.html', {
        'product': product,
        'variants': variants
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def add_variant(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        color_type = request.POST.get('color_type', '').strip()
        color = request.POST.get('color', '').strip()
        color_code = request.POST.get('color_code', '').strip()
        stock_quantity = request.POST.get('stock_quantity', '0').strip()
        images = request.FILES.getlist('images')
        errors = []

        try:
            stock_quantity = int(stock_quantity)
            if stock_quantity < 0:
                errors.append("Stock quantity cannot be negative")
            elif stock_quantity > 9999:
                errors.append("Stock quantity cannot exceed 9999")
        except ValueError:
            errors.append("Please enter a valid stock quantity")

        if color_type == 'predefined':
            if not color:
                errors.append("Please select a predefined color")
            else:
                if ProductVariant.objects.filter(product=product, color=color, color_code__isnull=True).exists():
                    errors.append("A variant with this predefined color already exists for this product")
                color_code = None
        elif color_type == 'custom':
            if not color_code:
                errors.append("Please enter a custom hex color code")
            elif not re.match(r'^#[0-9A-Fa-f]{6}$', color_code):
                errors.append("Please enter a valid hex color code (e.g., #FF0000)")
            else:
                color = 'custom'
                if ProductVariant.objects.filter(product=product, color_code=color_code).exists():
                    errors.append("A variant with this custom color already exists for this product")
        else:
            errors.append("Please select either a predefined color or enter a custom color")

        if len(images) < 3:
            errors.append("Please upload at least 3 images for the variant")
        elif len(images) > 10:
            errors.append("Maximum 10 images allowed per variant")
        else:
            for image in images:
                if not image.content_type.startswith('image/'):
                    errors.append("Please upload only image files")
                    break
                if image.size > 10 * 1024 * 1024:
                    errors.append("Each image should be less than 10MB")
                    break

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'add_variant.html', {
                'product': product,
                'color': color,
                'color_code': color_code,
                'stock_quantity': request.POST.get('stock_quantity', ''),
            })

        try:
            variant = ProductVariant.objects.create(
                product=product,
                color=color,
                color_code=color_code,
                stock_quantity=stock_quantity
            )

            for i, image in enumerate(images):
                try:
                    processed_image = resize_and_crop_image(image)
                    variant_image = VariantImage(
                        variant=variant,
                        is_primary=(i == 0)
                    )
                    variant_image.image.save(
                        f"{product.product_name}_{variant.color}_{i+1}.jpg",
                        processed_image,
                        save=True
                    )
                except Exception as e:
                    messages.warning(request, f"Error processing image {i+1}: {str(e)}")

            if color_type == 'predefined':
                color_display = dict(ProductVariant.COLOR_CHOICES).get(color, color)
                messages.success(request, f"Variant '{color_display}' added successfully with {stock_quantity} items in stock")
            else:
                messages.success(request, f"Custom color variant '{color_code}' added successfully with {stock_quantity} items in stock")
            
            return redirect('product_variants', product_id=product.id)
        except Exception as e:
            messages.error(request, "An error occurred while adding the variant")

    return render(request, 'add_variant.html', {
        'product': product,
        'color_choices': ProductVariant.COLOR_CHOICES
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def edit_variant(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    
    if request.method == 'POST':
        color_type = request.POST.get('color_type', '').strip()
        color = request.POST.get('color', '').strip()
        color_code = request.POST.get('color_code', '').strip()
        stock_quantity = request.POST.get('stock_quantity', '0').strip()
        images = request.FILES.getlist('images')
        remove_images = request.POST.getlist('remove_images')
        primary_image = request.POST.get('primary_image')
        errors = []

        try:
            stock_quantity = int(stock_quantity)
            if stock_quantity < 0:
                errors.append("Stock quantity cannot be negative")
            elif stock_quantity > 9999:
                errors.append("Stock quantity cannot exceed 9999")
        except ValueError:
            errors.append("Please enter a valid stock quantity")

        if color_type == 'predefined':
            if not color:
                errors.append("Please select a predefined color")
            else:
                if ProductVariant.objects.filter(
                    product=variant.product, 
                    color=color, 
                    color_code__isnull=True
                ).exclude(id=variant.id).exists():
                    errors.append("A variant with this predefined color already exists for this product")
                color_code = None
        elif color_type == 'custom':
            if not color_code:
                errors.append("Please enter a custom hex color code")
            elif not re.match(r'^#[0-9A-Fa-f]{6}$', color_code):
                errors.append("Please enter a valid hex color code (e.g., #FF0000)")
            else:
                color = 'custom'
                if ProductVariant.objects.filter(
                    product=variant.product, 
                    color_code=color_code
                ).exclude(id=variant.id).exists():
                    errors.append("A variant with this custom color already exists for this product")
        else:
            errors.append("Please select either a predefined color or enter a custom color")

        current_images_count = variant.images.count() - len(remove_images)
        total_images_after = current_images_count + len(images)

        if total_images_after < 3:
            errors.append("Variant must have at least 3 images")
        elif total_images_after > 10:
            errors.append("Maximum 10 images allowed per variant")

        if images:
            for image in images:
                if not image.content_type.startswith('image/'):
                    errors.append("Please upload only image files")
                    break
                if image.size > 10 * 1024 * 1024:
                    errors.append("Each image should be less than 10MB")
                    break

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'edit_variant.html', {
                'variant': variant,
                'color_choices': ProductVariant.COLOR_CHOICES
            })

        try:
            variant.color = color
            variant.color_code = color_code
            variant.stock_quantity = stock_quantity
            
            variant.save()

            if remove_images:
                VariantImage.objects.filter(id__in=remove_images, variant=variant).delete()

            for i, image in enumerate(images):
                try:
                    processed_image = resize_and_crop_image(image)
                    variant_image = VariantImage(variant=variant)
                    variant_image.image.save(
                        f"{variant.product.product_name}_{variant.color}_{variant.images.count() + i + 1}.jpg",
                        processed_image,
                        save=True
                    )
                except Exception as e:
                    messages.warning(request, f"Error processing image {i+1}: {str(e)}")

            if primary_image:
                try:
                    VariantImage.objects.filter(variant=variant).update(is_primary=False)
                    VariantImage.objects.filter(id=primary_image, variant=variant).update(is_primary=True)
                except:
                    pass

            if color_type == 'predefined':
                color_display = dict(ProductVariant.COLOR_CHOICES).get(color, color)
                messages.success(request, f"Variant '{color_display}' updated successfully. Stock: {stock_quantity} items")
            else:
                messages.success(request, f"Custom color variant '{color_code}' updated successfully. Stock: {stock_quantity} items")
            
            return redirect('product_variants', product_id=variant.product.id)
        except Exception as e:
            messages.error(request, f"An error occurred while updating the variant =={e}")
            print(e)
    return render(request, 'edit_variant.html', {
        'variant': variant,
        'color_choices': ProductVariant.COLOR_CHOICES
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def toggle_variant_status(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')

        if variant.color_code:
            variant_color = f"Custom Color ({variant.color_code})"
        else:
            variant_color = variant.get_color_display()
        
        if action == 'deactivate' and variant.is_active:
            variant.is_active = False
            variant.save()
            messages.success(request, f"Variant '{variant_color}' has been deactivated successfully")
        elif action == 'activate' and not variant.is_active:
            variant.is_active = True
            variant.save()
            messages.success(request, f"Variant '{variant_color}' has been activated successfully")
        else:
            messages.error(request, "Invalid action or variant status")
    
    return redirect('product_variants', product_id=variant.product.id)

def resize_and_crop_image(image_file, size=(800, 600)):
    try:
        img = Image.open(image_file)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')

        img_ratio = img.width / img.height
        target_ratio = size[0] / size[1]

        if img_ratio > target_ratio:
            new_height = img.height
            new_width = int(new_height * target_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, new_height))
        else:
            new_width = img.width
            new_height = int(new_width / target_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, new_width, top + new_height))

        img = img.resize(size, Image.Resampling.LANCZOS)
        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        return ContentFile(output.read())
    except Exception as e:
        raise Exception(f"Error processing image: {str(e)}")
