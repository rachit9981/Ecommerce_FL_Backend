from django.contrib import admin
from .models import SellMobile, SellMobileInquiry

# Register your models here.

@admin.register(SellMobile)
class SellMobileAdmin(admin.ModelAdmin):
    list_display = ['user_name', 'mobile_brand', 'mobile_model', 'expected_price', 'condition', 'status', 'created_at']
    list_filter = ['status', 'condition', 'mobile_brand', 'created_at']
    search_fields = ['user_name', 'mobile_brand', 'mobile_model', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(SellMobileInquiry)
class SellMobileInquiryAdmin(admin.ModelAdmin):
    list_display = ['sell_mobile', 'buyer_name', 'buyer_phone', 'offered_price', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['buyer_name', 'buyer_phone', 'sell_mobile__mobile_model']
    readonly_fields = ['created_at']
