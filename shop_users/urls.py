from django.urls import path
from .views import *


urlpatterns = [
    path('signup',signup, name='signup'),
    path('login',login, name='login'),
    path('add-review/<str:product_id>/', add_review, name='add_review'),
    path('products/<str:product_id>/reviews/<str:review_id>/report/', report_review, name='report_review'),
    path('products/<str:product_id>/reviews/<str:review_id>/helpful/', mark_review_helpful, name='mark_review_helpful'),

    # Cart URLs
    path('cart/add/<str:product_id>/', add_to_cart, name='add_to_cart'),
    path('cart/', get_cart, name='get_cart'),
    path('cart/remove/<str:item_id>/', remove_from_cart, name='remove_from_cart'),

    # Wishlist URLs
    path('wishlist/add/<str:product_id>/', add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/', get_wishlist, name='get_wishlist'),
    path('wishlist/remove/<str:item_id>/', remove_from_wishlist, name='remove_from_wishlist'),

    # Order & Payment URLs
    path('order/razorpay/create/', create_razorpay_order, name='create_razorpay_order'),
    path('order/razorpay/verify/', verify_razorpay_payment, name='verify_razorpay_payment'),
    path('orders/', get_user_orders, name='get_user_orders'),
    path('orders/<str:order_id>/', get_order_details, name='get_order_details'),

    # Addresses URLs
    path('addresses/', get_addresses, name='get_addresses'),
    path('addresses/add/', add_address, name='add_address'),
    path('addresses/update/<str:address_id>/', update_address, name='update_address'),
    path('addresses/delete/<str:address_id>/', delete_address, name='delete_address'),
    path('addresses/set-default/<str:address_id>/', set_default_address, name='set_default_address'),

    # Profile URLs
    path('profile/', get_profile, name='get_profile'),
    path('profile/update/', update_profile, name='update_profile'),
]
