from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
import json

# Create your views here.
@csrf_exempt
def signup(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    data = json.loads(request.body)
    # Implement your signup logic here
    return JsonResponse({'message': 'Signup successful'}, status=status.HTTP_201_CREATED)

@csrf_exempt
def login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    data = json.loads(request.body)
    # Implement your login logic here
    return JsonResponse({'message': 'Login successful'}, status=status.HTTP_200_OK)

