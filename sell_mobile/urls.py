from django.urls import path
from .views import *

urlpatterns = [
    path('submit/', submit_sell_mobile, name='submit-sell-mobile'),
    path('listings/', fetch_sell_mobiles, name='fetch-sell-mobiles'),
    path('listings/<str:mobile_id>/', fetch_sell_mobile_details, name='fetch-sell-mobile-details'),
    path('submit_inquiry/', submit_inquiry, name='submit-sell-mobile-inquiry'),
    path('listings/<str:mobile_id>/status/', update_sell_mobile_status, name='update-sell-mobile-status'),
    path('upload-phone-data/', upload_phone_data, name='upload-phone-data'),
    path('catalog/', fetch_all_mobiles_catalog, name='fetch-all-mobiles-catalog'),
]
