from django.urls import path
from vault.views import logout_view
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    
    path('user-management/', views.user_management_page, name='user_management'),
    path('block-user/<int:user_id>/', views.block_user, name='block_user'),
    path('unblock-user/<int:user_id>/', views.unblock_user, name='unblock_user'),
    
    path('logout/', logout_view, name='logout'),
    
    path('categories/', views.category_list, name='category_list'),
    path('categories-add/', views.add_category, name='add_category'),
    path('categories-edit/<int:category_id>/', views.edit_category, name='edit_category'),
    path('toggle-status/<int:category_id>/', views.toggle_category_status, name='toggle_category_status'),
    
    path('admin/category-offers/', views.category_offer_list, name='category_offer_list'),
    path('admin/category-offers/add/', views.add_category_offer, name='add_category_offer'),
    path('admin/category-offers/edit/<int:offer_id>/', views.edit_category_offer, name='edit_category_offer'),
    path('admin/category-offers/toggle/<int:offer_id>/', views.toggle_category_offer_status, name='toggle_category_offer_status'),
    
    path('admin/referral-offers/', views.referral_offer_list, name='referral_offer_list'),
    path('admin/referral-offers/add/', views.add_referral_offer, name='add_referral_offer'),
    path('admin/referral-offers/edit/<int:offer_id>/', views.edit_referral_offer, name='edit_referral_offer'),
    path('admin/referral-offers/toggle/<int:offer_id>/', views.toggle_referral_offer_status, name='toggle_referral_offer_status'),
    path('admin/referral-rewards/', views.referral_rewards_list, name='referral_rewards_list'),
    
    # path('register/<uuid:token>/', views.register_with_referral_token, name='register_with_referral_token'),
    
    path('product-list/', views.product_list, name='product_list'),
    path('products-add/', views.add_product, name='add_product'),
    path('product-details/<int:product_id>/', views.product_detail, name='product_detail'),
    path('product-edit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('product-toggle-status/<int:product_id>/', views.toggle_product_status, name='toggle_product_status'),
    
    path('product-variants/<int:product_id>/', views.product_variants, name='product_variants'),
    path('variant-add/<int:product_id>/', views.add_variant, name='add_variant'),
    path('variant-edit/<int:variant_id>/', views.edit_variant, name='edit_variant'),
    path('variant-toggle-status/<int:variant_id>/', views.toggle_variant_status, name='toggle_variant_status'),
    
    path('orders/', views.order_management_page, name='order_management_page'),
    path('orders/<int:order_id>/', views.order_detail_view, name='order_detail_view'),
    path('orders/<int:order_id>/update-status/', views.update_order_status, name='update_order_status'),
    
    path('return-requests/', views.return_requests_page, name='return_requests_page'),
    path('verify-return-request/<int:return_request_id>/', views.verify_return_request, name='verify_return_request'),
    path('verify-item-return-request/<int:item_return_id>/', views.verify_item_return_request, name='verify_item_return_request'),
    
    path('inventory/', views.inventory_management, name='inventory_management'),
    path('inventory/<int:variant_id>/update-stock/', views.update_stock, name='update_stock'),
    
    path('admin-profile/', views.admin_profile, name='settings'),
    
    path('coupons/', views.coupon_list, name='coupon_list'),
    path('coupons/add/', views.add_coupon, name='add_coupon'),
    path('coupons/edit/<int:coupon_id>/', views.edit_coupon, name='edit_coupon'),
    path('coupons/toggle/<int:coupon_id>/', views.toggle_coupon_status, name='toggle_coupon_status'),
    
    path('reports/sales/', views.sales_report, name='sales_report'),
    path('reports/sales/download/', views.download_sales_report, name='download_sales_report'),
]