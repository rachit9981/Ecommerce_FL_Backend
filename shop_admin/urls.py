from django.urls import path
from .views import *
app_name = 'shop_admin'

urlpatterns = [
    path('signup',admin_register, name='admin_register'),
    path('login',admin_login, name='admin_login'),
]
