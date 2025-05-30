from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.partner_register, name='partner_register'),
    path('login/', views.partner_login, name='partner_login'),
    path('verify/<str:partner_id>/', views.verify_partner, name='admin_verify_partner'), # Admin action
    path('all/', views.get_all_partners, name='get_all_partners'), # Admin action
    path('deliveries/assigned/', views.get_assigned_orders, name='delivery_assignment_list'),
    path('deliveries/update_status/<str:order_id>/', views.update_order_status_by_partner, name='update_delivery_status'),
    path('deliveries/history/', views.delivery_history, name='delivery_history'),
]
