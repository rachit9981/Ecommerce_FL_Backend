from django.urls import path
from .views import *


urlpatterns = [
    path('signup',signup, name='signup'),
    path('login',login, name='login'),
    path('add-review/<str:product_id>/', add_review, name='add_review'),
    path('products/<str:product_id>/reviews/<str:review_id>/report/', report_review, name='report_review'),
    path('products/<str:product_id>/reviews/<str:review_id>/helpful/', mark_review_helpful, name='mark_review_helpful')

]
