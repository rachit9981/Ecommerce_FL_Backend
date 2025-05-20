from django.urls import path
from . import views

app_name = 'shop_admin'

urlpatterns = [
    path('', views.AdminAPIHomeView.as_view(), name='admin-api-home'),
    # Add your admin API endpoints here
    # Example: path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
]
