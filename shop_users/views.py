from django.shortcuts import render
from rest_framework import viewsets, permissions, generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

# Create your views here.
class APIHomeView(APIView):
    """
    API Home view for shop_users
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, format=None):
        return Response({
            "message": "Welcome to Anand Mobiles API",
            "status": "success"
        }, status=status.HTTP_200_OK)
