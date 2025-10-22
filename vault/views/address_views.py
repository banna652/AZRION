from .common_imports import *

@never_cache
@login_required
def manage_addresses(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    addresses = request.user.addresses.all()
    return render(request, 'profile/manage_addresses.html', {'addresses': addresses})

@never_cache
@login_required
def add_address(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    errors = {}
    form_data = {}
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        address_line_1 = request.POST.get('address_line_1', '').strip()
        address_line_2 = request.POST.get('address_line_2', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        postal_code = request.POST.get('postal_code', '').strip()
        country = request.POST.get('country', '').strip()
        address_type = request.POST.get('address_type', 'home')
        is_default = request.POST.get('is_default') == 'on'
        
        form_data = {
            'full_name': full_name,
            'phone_number': phone_number,
            'address_line_1': address_line_1,
            'address_line_2': address_line_2,
            'city': city,
            'state': state,
            'postal_code': postal_code,
            'country': country,
            'address_type': address_type,
            'is_default': is_default,
        }
        
        if not re.fullmatch(r'[A-Za-z ]+', full_name):
            errors['full_name'] = "Name must contain only letters and spaces."
        
        if not re.fullmatch(r'^[0-9]{10,15}$', phone_number):
            errors['phone_number'] = "Enter a valid 10-15 digit phone number."
        
        if not address_line_1:
            errors['address_line_1'] = "Address line 1 is required."
        
        if not city:
            errors['city'] = "City is required."
        
        if not state:
            errors['state'] = "State is required."
        
        if not re.fullmatch(r'^[0-9]{6}$', postal_code):
            errors['postal_code'] = "Enter a valid 6-digit postal code."
        
        if not country:
            errors['country'] = "Country is required."
        
        if errors:
            return render(request, 'profile/add_address.html', {
                'errors': errors,
                'form_data': form_data
            })
        
        Address.objects.create(
            user=request.user,
            full_name=full_name,
            phone_number=phone_number,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            address_type=address_type,
            is_default=is_default,
        )
        
        messages.success(request, "Address added successfully!")
        return redirect('manage_addresses')
    
    return render(request, 'profile/add_address.html')

@never_cache
@login_required
def edit_address(request, address_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    address = get_object_or_404(Address, id=address_id, user=request.user)
    errors = {}
    form_data = {}
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        address_line_1 = request.POST.get('address_line_1', '').strip()
        address_line_2 = request.POST.get('address_line_2', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        postal_code = request.POST.get('postal_code', '').strip()
        country = request.POST.get('country', '').strip()
        address_type = request.POST.get('address_type', 'home')
        is_default = request.POST.get('is_default') == 'on'
        
        form_data = {
            'full_name': full_name,
            'phone_number': phone_number,
            'address_line_1': address_line_1,
            'address_line_2': address_line_2,
            'city': city,
            'state': state,
            'postal_code': postal_code,
            'country': country,
            'address_type': address_type,
            'is_default': is_default,
        }
        
        if not re.fullmatch(r'[A-Za-z ]+', full_name):
            errors['full_name'] = "Name must contain only letters and spaces."
        
        if not re.fullmatch(r'^[0-9]{10,15}$', phone_number):
            errors['phone_number'] = "Enter a valid 10-15 digit phone number."
        
        if not address_line_1:
            errors['address_line_1'] = "Address line 1 is required."
        
        if not city:
            errors['city'] = "City is required."
        
        if not state:
            errors['state'] = "State is required."
        
        if not re.fullmatch(r'^[0-9]{6}$', postal_code):
            errors['postal_code'] = "Enter a valid 6-digit postal code."
        
        if not country:
            errors['country'] = "Country is required."
        
        if errors:
            return render(request, 'profile/edit_address.html', {
                'errors': errors,
                'form_data': form_data,
                'address': address
            })
        
        address.full_name = full_name
        address.phone_number = phone_number
        address.address_line_1 = address_line_1
        address.address_line_2 = address_line_2
        address.city = city
        address.state = state
        address.postal_code = postal_code
        address.country = country
        address.address_type = address_type
        address.is_default = is_default
        address.save()
        
        messages.success(request, "Address updated successfully!")
        return redirect('manage_addresses')
    
    form_data = {
        'full_name': address.full_name,
        'phone_number': address.phone_number,
        'address_line_1': address.address_line_1,
        'address_line_2': address.address_line_2,
        'city': address.city,
        'state': address.state,
        'postal_code': address.postal_code,
        'country': address.country,
        'address_type': address.address_type,
        'is_default': address.is_default,
    }
    
    return render(request, 'profile/edit_address.html', {
        'form_data': form_data,
        'address': address
    })
    
@never_cache
@login_required
def set_default_address(request, address_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    if request.method == 'POST':
        try:
            address = get_object_or_404(Address, id=address_id, user=request.user)
            address.is_default = True
            address.save()
            messages.success(request, "Default address updated successfully!")
        except Exception as e:
            messages.error(request, f"Error setting default address: {e}")
    else:
        messages.error(request, "Invalid request method.")
    
    return redirect('manage_addresses')

@never_cache
@login_required
def delete_address(request, address_id):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        try:
            address.delete()
            messages.success(request, "Address deleted successfully!")
        except Exception as e:
            messages.error(request, f"Error deleting address: {e}")
    else:
        messages.error(request, "Invalid request method.")
    
    return redirect('manage_addresses')

