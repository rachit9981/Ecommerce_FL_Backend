from django.shortcuts import render
from rest_framework import viewsets, permissions, generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

# Create your views here.
class AdminAPIHomeView(APIView):
    """
    API Home view for shop_admin
    """
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request, format=None):
        return Response({
            "message": "Welcome to Anand Mobiles Admin API",
            "status": "success"
        }, status=status.HTTP_200_OK)
