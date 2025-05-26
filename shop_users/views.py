from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password, check_password
import jwt
from firebase_admin.exceptions import FirebaseError
import json

from anand_mobiles.settings import SECRET_KEY
from firebase_admin import firestore, auth as firebase_auth

# Get Firebase client
db = firestore.client()

@csrf_exempt
def signup(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        if 'idToken' in data:
            # Firebase authentication flow (OAuth, Google, etc.)
            id_token = data.get('idToken')
            try:
                decoded_token = firebase_auth.verify_id_token(id_token)
                uid = decoded_token['uid']
                
                user_doc_ref = db.collection('users').document(uid)
                user_doc = user_doc_ref.get()
                
                first_name = ''
                last_name = ''
                email = decoded_token.get('email') # Email from token
                phone_number = None

                if user_doc.exists:
                    # User already exists in Firestore, treat as login/refresh
                    user_data = user_doc.to_dict()
                    user_id = user_doc.id
                    email = user_data.get('email', email) # Prefer stored email
                    first_name = user_data.get('first_name', '')
                    last_name = user_data.get('last_name', '')
                else:
                    # New user via Firebase Auth, create in Firestore
                    try:
                        firebase_user_record = firebase_auth.get_user(uid)
                        email = firebase_user_record.email # Prefer email from get_user
                        phone_number = firebase_user_record.phone_number

                        if firebase_user_record.display_name:
                            parts = firebase_user_record.display_name.split(' ', 1)
                            first_name = parts[0]
                            if len(parts) > 1:
                                last_name = parts[1]
                    except FirebaseError as e:
                        return JsonResponse({'error': f'Error fetching Firebase user details: {str(e)}'}, status=400)

                    user_payload = {
                        'email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'phone_number': phone_number,
                        'auth_provider': 'firebase',
                        'uid': uid, # Store Firebase UID
                        'created_at': firestore.SERVER_TIMESTAMP,
                    }
                    user_doc_ref.set(user_payload)
                    user_id = uid
                
                # Generate custom token for your application
                token_payload = {'user_id': user_id, 'email': email, 'uid': uid}
                app_token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')
                
                return JsonResponse({
                    'message': 'Firebase signup/login successful',
                    'user_id': user_id,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'token': app_token
                }, status=201 if not user_doc.exists else 200)
                
            except FirebaseError as e: # Errors from verify_id_token
                return JsonResponse({'error': f'Invalid Firebase token: {str(e)}'}, status=400)
            except Exception as e:
                return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)
        else:
            # Traditional email/password signup
            email = data.get('email')
            password = data.get('password')
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            phone_number = data.get('phone_number')
            
            if not all([email, password, first_name, last_name]):
                return JsonResponse({'error': 'Missing required fields: email, password, first_name, last_name'}, status=400)
            
            # Check if user already exists in Firestore by email
            users_ref = db.collection('users')
            query = users_ref.where('email', '==', email).limit(1).stream()
            if list(query):
                return JsonResponse({'error': 'User with this email already exists'}, status=400)
            
            hashed_password = make_password(password)
            
            user_payload = {
                'email': email,
                'password': hashed_password,
                'first_name': first_name,
                'last_name': last_name,
                'phone_number': phone_number,
                'auth_provider': 'email',
                'created_at': firestore.SERVER_TIMESTAMP,
            }
            # Firestore will auto-generate an ID for this document
            update_time, doc_ref = users_ref.add(user_payload)
            user_id = doc_ref.id
            
            # Generate custom token
            token_payload = {'user_id': user_id, 'email': email}
            app_token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')
            
            return JsonResponse({
                'message': 'Signup successful',
                'user_id': user_id,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'token': app_token
            }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'An internal server error occurred: {str(e)}'}, status=500)

@csrf_exempt
def login(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        if 'idToken' in data:
            # Firebase authentication flow (OAuth, Google, etc.)
            id_token = data.get('idToken')
            try:
                decoded_token = firebase_auth.verify_id_token(id_token)
                uid = decoded_token['uid']
                
                user_doc_ref = db.collection('users').document(uid)
                user_doc = user_doc_ref.get()
                
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    user_id = user_doc.id # This is the Firebase UID
                    
                    # Generate custom token for your application
                    token_payload = {'user_id': user_id, 'email': user_data.get('email'), 'uid': uid}
                    app_token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')
                    
                    return JsonResponse({
                        'message': 'Firebase login successful',
                        'user_id': user_id,
                        'email': user_data.get('email'),
                        'first_name': user_data.get('first_name'),
                        'last_name': user_data.get('last_name'),
                        'token': app_token
                    }, status=200)
                else:
                    # User authenticated with Firebase but not in our Firestore DB.
                    # This case might mean they need to complete a signup step if you require local user profiles.
                    # For simplicity here, we'll treat it as an error, or you could auto-create them.
                    # Re-using part of the signup logic for auto-creation:
                    try:
                        firebase_user_record = firebase_auth.get_user(uid)
                        email = firebase_user_record.email
                        phone_number = firebase_user_record.phone_number
                        first_name = ''
                        last_name = ''
                        if firebase_user_record.display_name:
                            parts = firebase_user_record.display_name.split(' ', 1)
                            first_name = parts[0]
                            if len(parts) > 1:
                                last_name = parts[1]
                        
                        user_payload = {
                            'email': email,
                            'first_name': first_name,
                            'last_name': last_name,
                            'phone_number': phone_number,
                            'auth_provider': 'firebase',
                            'uid': uid,
                            'created_at': firestore.SERVER_TIMESTAMP,
                        }
                        user_doc_ref.set(user_payload)
                        user_id = uid

                        token_payload = {'user_id': user_id, 'email': email, 'uid': uid}
                        app_token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')

                        return JsonResponse({
                            'message': 'Firebase login successful (new user profile created)',
                            'user_id': user_id,
                            'email': email,
                            'first_name': first_name,
                            'last_name': last_name,
                            'token': app_token
                        }, status=200) # Or 201 if you consider it a creation
                    except FirebaseError as fe:
                         return JsonResponse({'error': f'User not found in Firestore and Firebase user fetch failed: {str(fe)}'}, status=404)

            except FirebaseError as e: # Errors from verify_id_token
                return JsonResponse({'error': f'Invalid Firebase token: {str(e)}'}, status=401)
            except Exception as e:
                return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

        else:
            # Traditional email/password login
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                return JsonResponse({'error': 'Email and password are required'}, status=400)
            
            users_ref = db.collection('users')
            # Query for user by email, ensuring they used email provider
            query = users_ref.where('email', '==', email).where('auth_provider', '==', 'email').limit(1).stream()
            
            user_list = list(query)
            if not user_list:
                return JsonResponse({'error': 'Invalid credentials or user not found'}, status=401)
            
            user_doc = user_list[0]
            user_data = user_doc.to_dict()
            
            if check_password(password, user_data.get('password')):
                user_id = user_doc.id # Firestore document ID
                
                # Generate custom token
                token_payload = {'user_id': user_id, 'email': user_data.get('email')}
                app_token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')
                
                return JsonResponse({
                    'message': 'Login successful',
                    'user_id': user_id,
                    'email': user_data.get('email'),
                    'first_name': user_data.get('first_name'),
                    'last_name': user_data.get('last_name'),
                    'token': app_token
                }, status=200)
            else:
                return JsonResponse({'error': 'Invalid credentials'}, status=401)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'An internal server error occurred: {str(e)}'}, status=500)

