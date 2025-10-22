from django.urls import path
from vault.views import logout_view
from .views import *

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
    
    path('user-management/', user_management_page, name='user_management'),
    path('block-user/<int:user_id>/', block_user, name='block_user'),
    path('unblock-user/<int:user_id>/', unblock_user, name='unblock_user'),
    
    path('logout/', logout_view, name='logout'),
    
    path('categories/', category_list, name='category_list'),
    path('categories-add/', add_category, name='add_category'),
    path('categories-edit/<int:category_id>/', edit_category, name='edit_category'),
    path('toggle-status/<int:category_id>/', toggle_category_status, name='toggle_category_status'),
    
    path('admin/category-offers/', category_offer_list, name='category_offer_list'),
    path('admin/category-offers/add/', add_category_offer, name='add_category_offer'),
    path('admin/category-offers/edit/<int:offer_id>/', edit_category_offer, name='edit_category_offer'),
    path('admin/category-offers/toggle/<int:offer_id>/', toggle_category_offer_status, name='toggle_category_offer_status'),
    
    path('admin/referral-offers/', referral_offer_list, name='referral_offer_list'),
    path('admin/referral-offers/add/', add_referral_offer, name='add_referral_offer'),
    path('admin/referral-offers/edit/<int:offer_id>/', edit_referral_offer, name='edit_referral_offer'),
    path('admin/referral-offers/toggle/<int:offer_id>/', toggle_referral_offer_status, name='toggle_referral_offer_status'),
    path('admin/referral-rewards/', referral_rewards_list, name='referral_rewards_list'),
    
    # path('register/<uuid:token>/', views.register_with_referral_token, name='register_with_referral_token'),
    
    path('product-list/', product_list, name='product_list'),
    path('products-add/', add_product, name='add_product'),
    path('product-details/<int:product_id>/', product_detail, name='product_detail'),
    path('product-edit/<int:product_id>/', edit_product, name='edit_product'),
    path('product-toggle-status/<int:product_id>/', toggle_product_status, name='toggle_product_status'),
    
    path('product-variants/<int:product_id>/', product_variants, name='product_variants'),
    path('variant-add/<int:product_id>/', add_variant, name='add_variant'),
    path('variant-edit/<int:variant_id>/', edit_variant, name='edit_variant'),
    path('variant-toggle-status/<int:variant_id>/', toggle_variant_status, name='toggle_variant_status'),
    
    path('orders/', order_management_page, name='order_management_page'),
    path('orders/<int:order_id>/', order_detail_view, name='order_detail_view'),
    path('orders/<int:order_id>/update-status/', update_order_status, name='update_order_status'),
    
    path('return-requests/', return_requests_page, name='return_requests_page'),
    path('verify-return-request/<int:return_request_id>/', verify_return_request, name='verify_return_request'),
    path('verify-item-return-request/<int:item_return_id>/', verify_item_return_request, name='verify_item_return_request'),
    
    path('inventory/', inventory_management, name='inventory_management'),
    path('inventory/<int:variant_id>/update-stock/', update_stock, name='update_stock'),
    
    path('admin-profile/', admin_profile, name='settings'),
    
    path('coupons/', coupon_list, name='coupon_list'),
    path('coupons/add/', add_coupon, name='add_coupon'),
    path('coupons/edit/<int:coupon_id>/', edit_coupon, name='edit_coupon'),
    path('coupons/toggle/<int:coupon_id>/', toggle_coupon_status, name='toggle_coupon_status'),
    
    path('reports/sales/', sales_report, name='sales_report'),
    path('reports/sales/download/', download_sales_report, name='download_sales_report'),
    
    path('wallet-management/', wallet_management_page, name='wallet_management_page'),
    path('wallet-transaction/<int:transaction_id>/', wallet_transaction_detail, name='wallet_transaction_detail'),
    path('user-wallet/<int:user_id>/', user_wallet_detail, name='user_wallet_detail'),
]