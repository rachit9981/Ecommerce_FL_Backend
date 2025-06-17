from django.urls import path
from .views import (
    submit_sell_mobile,
    fetch_sell_mobiles,
    fetch_sell_mobile_details,
    submit_inquiry,
    fetch_user_inquiries,
    fetch_inquiries_for_mobile, # Can be used by admin or to show inquiries on a listing
    update_sell_mobile_status, # Admin action
    upload_phone_data,         # Endpoint to upload/update the catalog
    fetch_all_mobiles_catalog, # Endpoint to get the entire catalog (e.g., for admin or initial load)
    get_phone_details,         # Endpoint to get details for a specific phone model for price calculation UI
    temp_bulk_upload_from_json_file, # Temporary endpoint for bulk upload
    manage_faqs,               # For GET all FAQs and POST new FAQ
    manage_faq_detail          # For GET, PUT, DELETE specific FAQ by ID
)

urlpatterns = [
    # Sell Mobile Listings & Details
    path('submit/', submit_sell_mobile, name='submit-sell-mobile'),
    path('listings/', fetch_sell_mobiles, name='fetch-sell-mobiles'), # GET approved listings
    path('listings/<str:mobile_id>/', fetch_sell_mobile_details, name='fetch-sell-mobile-details'),
    path('listings/<str:mobile_id>/status/', update_sell_mobile_status, name='update-sell-mobile-status'), # PUT to change status

    # Inquiries
    path('inquiries/submit/', submit_inquiry, name='submit-inquiry'), # Renamed for clarity
    path('inquiries/user/', fetch_user_inquiries, name='get-user-inquiries'), # GET user's own inquiries
    path('inquiries/', fetch_inquiries_for_mobile, name='get-mobile-inquiries'), # GET inquiries (can filter by mobile_id via query param)

    # Phone Catalog Management & Usage
    path('catalog/upload/', upload_phone_data, name='upload-phone-catalog'), # POST new catalog
    path('catalog/all/', fetch_all_mobiles_catalog, name='fetch-all-mobiles-catalog'), # GET entire catalog
    path('catalog/details/<str:brand>/<str:phone_series>/<str:phone_model>/', get_phone_details, name='get-phone-model-details'), # GET specific model details

    # Temporary Bulk Upload URL (Consider removing or securing after use)
    path('catalog/temp-bulk-upload/', temp_bulk_upload_from_json_file, name='temp-bulk-upload-catalog'),

    # FAQ Management URLs
    path('faqs/', manage_faqs, name='manage-faqs'), # GET for all, POST for new
    path('faqs/<str:faq_id>/', manage_faq_detail, name='manage-faq-detail'), # GET, PUT, DELETE by ID
]
