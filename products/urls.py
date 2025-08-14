from django.urls import path
from .views import *


urlpatterns = [
    path('i/', insert_products_from_csv, name='product-list'),
    path('products/', fetch_all_products, name='fetch-all-products'),
    path('categories/', fetch_categories, name='fetch-categories'),
    path('products/<str:product_id>/', fetch_product_details, name='fetch-product-details'),
    path('search/', search_and_filter_products, name='search-and-filter-products'),
    path('products/category/<str:category>/', fetch_products_by_category, name='fetch-products-by-category'),
    path('test/api/', test_api, name='test-api'),
]
