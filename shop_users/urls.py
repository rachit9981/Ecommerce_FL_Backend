from django.urls import path
from . import views

app_name = 'shop_users'

urlpatterns = [
    path('', views.APIHomeView.as_view(), name='api-home'),
    # Add your API endpoints here
    # Example: path('products/', views.ProductListView.as_view(), name='product-list'),
]
