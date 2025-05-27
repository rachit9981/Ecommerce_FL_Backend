from django.urls import path
from .views import *


urlpatterns = [
    path('signup',signup, name='signup'),
    path('login',login, name='login'),
    path('add-review/<str:product_id>/', add_review, name='add_review'),
]
