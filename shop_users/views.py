from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login as auth_login, get_user_model
from rest_framework import status
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
import json

User = get_user_model()

@csrf_exempt
def signup(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    try:
        data = json.loads(request.body)
        
        # Check if it's a Firebase OAuth signup
        if 'idToken' in data:
            # Firebase authentication flow
            id_token = data.get('idToken')
            try:
                # Verify the Firebase ID token
                decoded_token = firebase_auth.verify_id_token(id_token)
                uid = decoded_token['uid']
                
                # Get the user from Firebase
                firebase_user = firebase_auth.get_user(uid)
                
                # Create or get the user in our database
                user = User.create_firebase_user(firebase_user)
                
                # Log the user in
                auth_login(request, user, backend='shop_users.backends.FirebaseAuthenticationBackend')
                
                return JsonResponse({
                    'message': 'Firebase signup successful',
                    'user_id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }, status=status.HTTP_201_CREATED)
                
            except FirebaseError as e:
                return JsonResponse({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Traditional email/password signup
            email = data.get('email')
            password = data.get('password')
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            phone_number = data.get('phone_number')
            
            # Validate required fields
            if not all([email, password, first_name, last_name]):
                return JsonResponse({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                return JsonResponse({'error': 'User with this email already exists'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Create the user
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                auth_provider='email'
            )
            
            # Log the user in
            auth_login(request, user, backend='shop_users.backends.EmailPasswordBackend')
            
            return JsonResponse({
                'message': 'Signup successful',
                'user_id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
def login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    
    try:
        data = json.loads(request.body)
        
        # Check if it's a Firebase OAuth login
        if 'idToken' in data:
            # Firebase authentication flow
            id_token = data.get('idToken')
            user = authenticate(request, firebase_id_token=id_token)
            
            if user is not None:
                auth_login(request, user, backend='shop_users.backends.FirebaseAuthenticationBackend')
                return JsonResponse({
                    'message': 'Firebase login successful',
                    'user_id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }, status=status.HTTP_200_OK)
            else:
                return JsonResponse({'error': 'Invalid token or user not found'}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            # Traditional email/password login
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                return JsonResponse({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)
                
            user = authenticate(request, email=email, password=password)
            
            if user is not None:
                auth_login(request, user, backend='shop_users.backends.EmailPasswordBackend')
                return JsonResponse({
                    'message': 'Login successful',
                    'user_id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }, status=status.HTTP_200_OK)
            else:
                return JsonResponse({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

