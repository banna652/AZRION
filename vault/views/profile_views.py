from .common_imports import *

@never_cache
@login_required
def user_profile(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    user = request.user
    addresses = user.addresses.all()
    recent_orders = user.orders.all()[:3]
    
    wishlist_count = 0
    try:
        wishlist = Wishlist.objects.get(user=user)
        wishlist_count = wishlist.items.count()
    except Wishlist.DoesNotExist:
        pass
    
    context = {
        'user': user,
        'addresses': addresses,
        'recent_orders': recent_orders,
        'total_orders': user.orders.count(),
        'wishlist_count': wishlist_count,
    }
    
    return render(request, 'profile/user_profile.html', context)

@never_cache
@login_required
def edit_profile(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    user = request.user
    errors = {}
    form_data = {}
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        ph_number = request.POST.get('ph_number', '').strip()
        profile_image = request.FILES.get('profile_image')
        
        form_data = {
            'full_name': full_name,
            'email': email,
            'ph_number': ph_number,
        }
        
        if not re.fullmatch(r'[A-Za-z ]+', full_name):
            errors['full_name'] = "Name must contain only letters and spaces."
        
        if not email:
            errors['email'] = "Email is required."
        elif email != user.email and User.objects.filter(email=email).exists():
            errors['email'] = "Email is already registered."
        
        if not re.fullmatch(r'^[0-9]{10,15}$', ph_number):
            errors['ph_number'] = "Enter a valid 10-15 digit phone number."
        
        if errors:
            return render(request, 'profile/edit_profile.html', {
                'errors': errors,
                'form_data': form_data,
                'user': user
            })
        
        email_changed = email != user.email
        if email_changed:
            otp = generate_otp()
            request.session['profile_update_data'] = {
                'full_name': full_name,
                'email': email,
                'ph_number': ph_number,
                'otp': otp,
            }
            
            if profile_image:
                image_name = f"temp_profile_{user.id}_{timezone.now().timestamp()}.{profile_image.name.split('.')[-1]}"
                image_path = default_storage.save(f"temp_profiles/{image_name}", ContentFile(profile_image.read()))
                request.session['profile_update_data']['temp_image_path'] = image_path
            
            send_mail(
                subject='Email Verification for Profile Update',
                message=f'Your OTP for email verification is: {otp}',
                from_email='muhammaduhasanulbanna652@gmail.com',
                recipient_list=[email],
                fail_silently=False,
            )
            
            request.session['profile_otp_sent_time'] = timezone.now().timestamp()
            messages.success(request, f"OTP has been sent to {email}. Please verify to complete profile update.")
            return redirect('verify_profile_email')
        else:
            user.full_name = full_name
            user.ph_number = ph_number
            if profile_image:
                if user.pro_image:
                    if default_storage.exists(user.pro_image.name):
                        default_storage.delete(user.pro_image.name)
                user.pro_image = profile_image
            user.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('user_profile')
    
    return render(request, 'profile/edit_profile.html', {'user': user})

@never_cache
@login_required
def verify_profile_email(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    profile_data = request.session.get('profile_update_data')
    if not profile_data:
        messages.error(request, "Session expired. Please try updating your profile again.")
        return redirect('edit_profile')
    
    if request.method == 'POST':
        otp_input = ''.join([
            request.POST.get('otp1', ''),
            request.POST.get('otp2', ''),
            request.POST.get('otp3', ''),
            request.POST.get('otp4', ''),
            request.POST.get('otp5', ''),
            request.POST.get('otp6', ''),
        ])
        
        if profile_data['otp'] == otp_input:
            user = request.user
            user.full_name = profile_data['full_name']
            user.email = profile_data['email']
            user.ph_number = profile_data['ph_number']
            
            if 'temp_image_path' in profile_data:
                if user.pro_image:
                    if default_storage.exists(user.pro_image.name):
                        default_storage.delete(user.pro_image.name)
                
                temp_path = profile_data['temp_image_path']
                if default_storage.exists(temp_path):
                    with default_storage.open(temp_path, 'rb') as temp_file:
                        permanent_name = f"profile_images/user_{user.id}_{timezone.now().timestamp()}.{temp_path.split('.')[-1]}"
                        user.pro_image.save(permanent_name, ContentFile(temp_file.read()), save=False)
                    default_storage.delete(temp_path)
            
            user.save()
            request.session.pop('profile_update_data', None)
            request.session.pop('profile_otp_sent_time', None)
            messages.success(request, "Profile updated successfully with new email!")
            return redirect('user_profile')
        else:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'profile/verify_profile_email.html', {
                'email': profile_data['email']
            })
            
@never_cache
@login_required
def change_password(request):
    if check_user_blocked(request.user):
        logout(request)
        request.session.flush()
        messages.error(request, "Your account has been temporarily blocked.")
        return redirect('front')
    
    errors = {}
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if not current_password:
            errors['current_password'] = "Current password is required."
        elif not check_password(current_password, request.user.password):
            errors['current_password'] = "Current password is incorrect."
        
        if len(new_password) < 8 or not re.search(r'[^A-Za-z0-9]', new_password):
            errors['new_password'] = "Password must be at least 8 characters long and include a special character."
        
        if new_password != confirm_password:
            errors['confirm_password'] = "New passwords do not match."
        
        if current_password == new_password:
            errors['new_password'] = "New password must be different from current password."
        
        if errors:
            return render(request, 'profile/change_password.html', {'errors': errors})
        
        request.user.password = make_password(new_password)
        request.user.save()
        messages.success(request, "Password changed successfully!")
        return redirect('user_profile')
    
    return render(request, 'profile/change_password.html')

def resend_profile_otp(request):
    if request.method == 'POST':
        profile_data = request.session.get('profile_update_data')
        if not profile_data:
            messages.error(request, "Session expired. Please try updating your profile again.")
            return redirect('edit_profile')
        
        new_otp = generate_otp()
        profile_data['otp'] = new_otp
        request.session['profile_update_data'] = profile_data
        
        send_mail(
            subject='New Email Verification OTP',
            message=f'Your new OTP for email verification is: {new_otp}',
            from_email='muhammaduhasanulbanna652@gmail.com',
            recipient_list=[profile_data['email']],
            fail_silently=False,
        )
        
        request.session['profile_otp_sent_time'] = timezone.now().timestamp()
        messages.success(request, "New OTP has been sent to your email.")
    
    return redirect('verify_profile_email')