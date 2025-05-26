from django.urls import path
from .views import *
app_name = 'shop_admin'

urlpatterns = [
    path('signup',admin_register, name='admin_register'),
    path('login',admin_login, name='admin_login'),
    path('get_all_users', get_all_users, name='get_all_users'),
    path('get_all_products', get_all_products, name='get_all_products'),
    path('get_all_orders', get_all_orders, name='get_all_orders'),
    
]
