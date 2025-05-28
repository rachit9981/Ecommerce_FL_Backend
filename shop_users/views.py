from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password, check_password
import jwt
from firebase_admin.exceptions import FirebaseError
import json
from shop_users.utils import user_required
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

# Products related views would go here, similar to the previous example.

@user_required
@csrf_exempt
def add_review(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Extract required fields
        user_id = request.user_id
        rating = data.get('rating')
        comment = data.get('comment', '')
        email = request.user_email
        
        # Validate required fields
        if not user_id:
            return JsonResponse({'error': 'User ID is required'}, status=400)
        
        if not rating:
            return JsonResponse({'error': 'Rating is required'}, status=400)
        
        # Validate rating range
        try:
            rating = float(rating)
            if rating < 1 or rating > 5:
                return JsonResponse({'error': 'Rating must be between 1 and 5'}, status=400)
        except ValueError:
            return JsonResponse({'error': 'Rating must be a valid number'}, status=400)
        
        # Check if product exists
        product_doc = db.collection('products').document(product_id).get()
        if not product_doc.exists:
            return JsonResponse({'error': 'Product not found'}, status=404)
        
        # Check if user has already reviewed this product
        existing_review = db.collection('products').document(product_id).collection('reviews').where('user_id', '==', user_id).limit(1).stream()
        if list(existing_review):
            return JsonResponse({'error': 'User has already reviewed this product'}, status=400)
        
        # Create review data
        review_data = {
            'user_id': user_id,
            'email': email,
            'rating': rating,
            'comment': comment,
            'created_at': firestore.SERVER_TIMESTAMP,
            'is_verified': False,  # Default to false, admin can verify later
            'reported_count': 0,  # Initialize reported count
            'helpful_users': [],  # Initialize helpful users list
        }
        
        # Add review to subcollection
        review_ref = db.collection('products').document(product_id).collection('reviews').add(review_data)
        
        # Update product's average rating and review count
        reviews_ref = db.collection('products').document(product_id).collection('reviews').stream()
        total_rating = 0
        review_count = 0
        
        for review_doc in reviews_ref:
            review = review_doc.to_dict()
            total_rating += review.get('rating', 0)
            review_count += 1
        
        average_rating = round(total_rating / review_count, 2) if review_count > 0 else 0
        
        # Update product document with new rating and review count
        db.collection('products').document(product_id).update({
            'rating': average_rating,
            'reviews_count': review_count
        })
        
        return JsonResponse({
            'message': 'Review added successfully',
            'review_id': review_ref[1].id,
            'updated_rating': average_rating,
            'total_reviews': review_count
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error adding review: {str(e)}'}, status=500)


@user_required
@csrf_exempt
def report_review(request, product_id, review_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        user_id = request.user_id
        
        # Check if review exists
        review_doc_ref = db.collection('products').document(product_id).collection('reviews').document(review_id)
        review_doc = review_doc_ref.get()
        
        if not review_doc.exists:
            return JsonResponse({'error': 'Review not found'}, status=404)
        
        review_data = review_doc.to_dict()
        
        # Create reports subcollection if it doesn't exist, or add to it
        # First check if user already reported this review
        existing_report = review_doc_ref.collection('reports').where('user_id', '==', user_id).limit(1).stream()
        if list(existing_report):
            return JsonResponse({'error': 'You have already reported this review'}, status=400)
        
        # Add report
        report_data = {
            'user_id': user_id,
            'created_at': firestore.SERVER_TIMESTAMP,
        }
        report_ref = review_doc_ref.collection('reports').add(report_data)
        
        # Update report count in the review document
        reports_count = len(list(review_doc_ref.collection('reports').stream()))
        
        # Make sure reported_count field exists
        if 'reported_count' not in review_data:
            review_doc_ref.update({
                'reported_count': reports_count
            })
        else:
            review_doc_ref.update({
                'reported_count': reports_count
            })
        
        return JsonResponse({
            'message': 'Review reported successfully',
            'report_id': report_ref[1].id,
            'reported_count': reports_count
        }, status=200)
        
    except Exception as e:
        return JsonResponse({'error': f'Error reporting review: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def mark_review_helpful(request, product_id, review_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        user_id = request.user_id
        
        # Check if review exists
        review_doc_ref = db.collection('products').document(product_id).collection('reviews').document(review_id)
        review_doc = review_doc_ref.get()
        
        if not review_doc.exists:
            return JsonResponse({'error': 'Review not found'}, status=404)
        
        review_data = review_doc.to_dict()
        
        # Check if user already marked this review as helpful
        if 'helpful_users' not in review_data:
            # Initialize the field if it doesn't exist
            helpful_users = []
        else:
            helpful_users = review_data.get('helpful_users', [])
            
        if user_id in helpful_users:
            # User is unmarking the review as helpful (toggle functionality)
            helpful_users.remove(user_id)
            action = 'removed'
        else:
            # User is marking the review as helpful
            helpful_users.append(user_id)
            action = 'added'
        
        # Update the review document
        review_doc_ref.update({
            'helpful_users': helpful_users,
            'helpful_count': len(helpful_users)
        })
        
        return JsonResponse({
            'message': f'Helpfulness mark {action} successfully',
            'helpful_count': len(helpful_users),
            'is_marked_helpful': action == 'added'
        }, status=200)
        
    except Exception as e:
        return JsonResponse({'error': f'Error marking review as helpful: {str(e)}'}, status=500)