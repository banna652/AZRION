from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.front_page, name='front'),
    path('home/', views.home_page, name='home'),
    path('login/', views.login_page, name='login'),
    path('terms/', views.t_o_s_page, name='terms'),
    path('privacy/', views.privacy_policy_page, name='privacy'),
    path('logout_home/', views.logout_view, name='logout_home'),
    path('SignUp/', views.sign_up_page, name='sign_up'),
    path('signup/<str:token>/', views.sign_up_page, name='sign_up_with_referral'),
    path('verify/', views.otp_verify, name='verify'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('auth/', include('social_django.urls', namespace='social')),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-reset-otp/', views.verify_reset_otp, name='verify_reset_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('resend-reset-otp/', views.resend_reset_otp, name='resend_reset_otp'),
    path('products/', views.product_list, name='products_list'),
    path('product/<int:product_id>/', views.product_detail_page, name='products_details'),
    
    # Profile URLs
    
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/verify-email/', views.verify_profile_email, name='verify_profile_email'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/resend-otp/', views.resend_profile_otp, name='resend_profile_otp'),
    
    # Address URLs
    
    path('profile/addresses/', views.manage_addresses, name='manage_addresses'),
    path('profile/addresses/add/', views.add_address, name='add_address'),
    path('profile/addresses/edit/<int:address_id>/', views.edit_address, name='edit_address'),
    path('profile/addresses/set-default/<int:address_id>/', views.set_default_address, name='set_default_address'),
    path('profile/addresses/delete/<int:address_id>/', views.delete_address, name='delete_address'),
    
    # Order URLs
    
    path('profile/orders/', views.user_orders, name='user_orders'),
    path('profile/cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    
    # Cart Management URLs
    
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/update-quantity/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/remove/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    
    # Checkout and Order URLs
    
    path('checkout/', views.checkout, name='checkout'),
    path('create-razorpay-order/', views.create_razorpay_order, name='create_razorpay_order'),
    path('payment-failure/<int:order_id>/', views.payment_failure, name='payment_failure'),
    path('verify-payment/', views.verify_payment, name='verify_payment'),
    path('place-order/', views.place_order, name='place_order'),
    path('retry-payment/<int:order_id>/', views.retry_payment, name='retry_payment'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),
    path('order-detail/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/', views.user_orders, name='user_orders'),
    path('order/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    
    path('order/<int:order_id>/request-return/', views.request_return, name='request_return'),
    
    path('cancel-item/<int:item_id>/', views.cancel_order_item, name='cancel_order_item'),
    path('return-item/<int:item_id>/', views.request_item_return, name='request_item_return'),
    
    # Wishlist related
    path('wishlist/', views.wishlist_view, name='wishlist_view'),
    path('wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('wishlist/clear/', views.clear_wishlist, name='clear_wishlist'),
    
    path('profile/orders/<int:order_id>/invoice/', views.download_invoice, name='download_invoice'),
    
    # Wallet URLs
    path('wallet/', views.wallet_view, name='wallet_view'),
    path('generate-referral-link/', views.generate_referral_link, name='generate_referral_link'),
]
