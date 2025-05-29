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
    path('users/ban/<str:user_id>/', ban_user, name='ban_user'),
    path('orders/assign-order/<str:order_id>/', assign_order_to_delivery_partner, name='assign_order_to_delivery_partner'),
    path('order/edit/<str:order_id>/', edit_order, name='edit_order'),

]
