from django.urls import path
from .views import *
app_name = 'shop_admin'

urlpatterns = [
    path('signup',admin_register, name='admin_register'),
    path('login',admin_login, name='admin_login'),
    path('get_all_users', get_all_users, name='get_all_users'),
    path('get_all_products', get_all_products, name='get_all_products'),
    path('get_all_orders', get_all_orders, name='get_all_orders'),
    path('get_all_admins', get_all_admins, name='get_all_admins'),
    path('delete_admin/<str:admin_id>', delete_admin, name='delete_admin'),
    path('toggle-featured/<str:product_id>/', toggle_featured_product, name='toggle_featured'),
    path('delete-product/<str:product_id>/', delete_product, name='delete_product'),
    path('products/add/', add_product, name='add_product'),
    path('products/edit/<str:product_id>/', edit_product, name='edit_product'),
    path('products/upload-image/', upload_product_image, name='upload_product_image'),
    path('users/ban/<str:user_id>/', ban_user, name='ban_user'),path('users/<str:user_id>/', get_user_by_id, name='get_user_by_id'),    path('users/<str:user_id>/orders/<str:order_id>/assign-partner/', assign_order_to_delivery_partner, name='assign_order_to_delivery_partner'),
    path('users/<str:user_id>/orders/<str:order_id>/edit/', edit_order, name='edit_order'),
    
    # Banner management URLs
    path('banners/', get_all_banners, name='get_all_banners'),
    path('banners/add/', add_banner, name='add_banner'),
    path('banners/edit/<str:banner_id>/', edit_banner, name='edit_banner'),
    path('banners/delete/<str:banner_id>/', delete_banner, name='delete_banner'),
    path('banners/toggle/<str:banner_id>/', toggle_banner_active, name='toggle_banner_active'),
    
    # Public banner endpoint (no auth required)
    path('banners/public/', get_public_banners, name='get_public_banners'),

    # Review management URLs
    path('reviews/', get_all_product_reviews, name='get_all_product_reviews'),
    path('reviews/reported/', get_reported_reviews, name='get_reported_reviews'),
    path('reviews/<str:product_id>/<str:review_id>/delete/', delete_review, name='delete_review'),

]
