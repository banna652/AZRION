from django.urls import path, include
from .views import *

urlpatterns = [
    path('', front_page, name='front'),
    path('home/', home_page, name='home'),
    path('login/', login_page, name='login'),
    path('terms/', t_o_s_page, name='terms'),
    path('privacy/', privacy_policy_page, name='privacy'),
    path('logout_home/', logout_view, name='logout_home'),
    path('SignUp/', sign_up_page, name='sign_up'),
    path('signup/<str:token>/', sign_up_page, name='sign_up_with_referral'),
    
    path('verify/', otp_verify, name='verify'),
    path('resend-otp/', resend_otp, name='resend_otp'),
    path('auth/', include('social_django.urls', namespace='social')),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('verify-reset-otp/', verify_reset_otp, name='verify_reset_otp'),
    path('reset-password/', reset_password, name='reset_password'),
    path('resend-reset-otp/', resend_reset_otp, name='resend_reset_otp'),
    
    path('products/', product_list, name='products_list'),
    path('product/<int:product_id>/', product_detail_page, name='products_details'),
    
    path('profile/', user_profile, name='user_profile'),
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('profile/verify-email/', verify_profile_email, name='verify_profile_email'),
    path('profile/change-password/', change_password, name='change_password'),
    path('profile/resend-otp/', resend_profile_otp, name='resend_profile_otp'),
    
    path('profile/addresses/', manage_addresses, name='manage_addresses'),
    path('profile/addresses/add/', add_address, name='add_address'),
    path('profile/addresses/edit/<int:address_id>/', edit_address, name='edit_address'),
    path('profile/addresses/set-default/<int:address_id>/', set_default_address, name='set_default_address'),
    path('profile/addresses/delete/<int:address_id>/', delete_address, name='delete_address'),
    
    path('profile/orders/', user_orders, name='user_orders'),
    path('profile/cancel-order/<int:order_id>/', cancel_order, name='cancel_order'),
    
    path('cart/', cart_view, name='cart_view'),
    path('cart/add/', add_to_cart, name='add_to_cart'),
    path('cart/update-quantity/', update_cart_quantity, name='update_cart_quantity'),
    path('cart/remove/', remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', clear_cart, name='clear_cart'),
    
    path('checkout/', checkout, name='checkout'),
    path('create-razorpay-order/', create_razorpay_order, name='create_razorpay_order'),
    path('payment-failure/<int:order_id>/', payment_failure, name='payment_failure'),
    
    path('verify-payment/', verify_payment, name='verify_payment'),
    path('place-order/', place_order, name='place_order'),
    path('retry-payment/<int:order_id>/', retry_payment, name='retry_payment'),
    path('order-success/<int:order_id>/', order_success, name='order_success'),
    
    path('order-detail/<int:order_id>/', order_detail, name='order_detail'),
    path('orders/', user_orders, name='user_orders'),
    path('order/<int:order_id>/cancel/', cancel_order, name='cancel_order'),
    
    path('apply-coupon/', apply_coupon, name='apply_coupon'),
    path('remove-coupon/', remove_coupon, name='remove_coupon'),
    
    path('order/<int:order_id>/request-return/', request_return, name='request_return'),
    
    path('cancel-item/<int:item_id>/', cancel_order_item, name='cancel_order_item'),
    path('return-item/<int:item_id>/', request_item_return, name='request_item_return'),
    
    path('wishlist/', wishlist_view, name='wishlist_view'),
    path('wishlist/add/', add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/', remove_from_wishlist, name='remove_from_wishlist'),
    path('wishlist/clear/', clear_wishlist, name='clear_wishlist'),
    
    path('profile/orders/<int:order_id>/invoice/', download_invoice, name='download_invoice'),
    
    path('wallet/', wallet_view, name='wallet_view'),
    path('generate-referral-link/', generate_referral_link, name='generate_referral_link'),
]
