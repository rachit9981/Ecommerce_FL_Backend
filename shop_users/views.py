from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password, check_password
import jwt
from firebase_admin.exceptions import FirebaseError
import json
import time
import logging
from shop_users.utils import user_required
from anand_mobiles.settings import SECRET_KEY
from firebase_admin import firestore, auth as firebase_auth
from google.cloud.firestore import Query
import razorpay
from django.conf import settings # Import settings
from shop_admin.utils import (
    generate_invoice_pdf, 
    upload_pdf_to_cloudinary_util, 
    upload_pdf_to_cloudinary_base64,
    save_pdf_to_disk_debug,
    create_invoice_data, 
    save_invoice_to_firestore,
    PDFGenerationError
)
from datetime import datetime

# Get Firebase client
db = firestore.client()

# Set up logger
logger = logging.getLogger(__name__)

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
                        'created_at': datetime.now(),
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
                'created_at': datetime.now(),
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
                            'created_at': datetime.now(),
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
        title = data.get('title', '')
        comment = data.get('comment', '')
        email = request.user_email
        
        # Validate required fields
        if not user_id:
            return JsonResponse({'error': 'User ID is required'}, status=400)
        
        if not rating:
            return JsonResponse({'error': 'Rating is required'}, status=400)
        
        if not title.strip():
            return JsonResponse({'error': 'Review title is required'}, status=400)
        
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
            'title': title.strip(),
            'comment': comment,
            'created_at': datetime.now(),
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
            'created_at': datetime.now(),
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

@user_required
@csrf_exempt
def add_to_cart(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        data = json.loads(request.body) if request.body else {}
        quantity = data.get('quantity', 1)
        variant_id = data.get('variant_id', None)

        # Validate quantity
        try:
            quantity = int(quantity)
            if quantity < 1:
                return JsonResponse({'error': 'Quantity must be at least 1'}, status=400)
        except ValueError:
            return JsonResponse({'error': 'Invalid quantity format'}, status=400)

        # Check if product exists
        product_doc = db.collection('products').document(product_id).get()
        if not product_doc.exists:
            return JsonResponse({'error': 'Product not found'}, status=404)

        # If variant_id is provided, validate it exists in the product's valid_options
        if variant_id:
            product_data = product_doc.to_dict()
            valid_options = product_data.get('valid_options', [])
            variant_found = any(option.get('id') == variant_id for option in valid_options)
            if not variant_found:
                return JsonResponse({'error': 'Invalid variant ID'}, status=400)

        # Create a unique cart item identifier based on product_id and variant_id
        cart_item_id = f"{product_id}_{variant_id}" if variant_id else product_id
        cart_ref = db.collection('users').document(user_id).collection('cart').document(cart_item_id)
        cart_item = cart_ref.get()

        if cart_item.exists:
            # Update quantity if item already in cart
            current_data = cart_item.to_dict()
            new_quantity = current_data.get('quantity', 0) + quantity
            cart_ref.update({'quantity': new_quantity, 'updated_at': datetime.now()})
            message = 'Product quantity updated in cart'
        else:
            # Add new item to cart
            cart_data = {
                'product_id': product_id,
                'variant_id': variant_id,
                'quantity': quantity,
                'added_at': datetime.now(),
                'updated_at': datetime.now()
            }
            cart_ref.set(cart_data)
            message = 'Product added to cart'

        return JsonResponse({
            'message': message, 
            'product_id': product_id, 
            'variant_id': variant_id,
            'quantity': cart_ref.get().to_dict().get('quantity')
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error adding to cart: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def get_cart(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        cart_items_ref = db.collection('users').document(user_id).collection('cart').stream()
        
        cart = []
        for item_doc in cart_items_ref:
            item_data = item_doc.to_dict()
            product_id = item_data.get('product_id')
            # Fetch product details
            product_doc = db.collection('products').document(product_id).get()
            if product_doc.exists:
                product_data = product_doc.to_dict()
                variant_id = item_data.get('variant_id')
                variant_data = None
                
                # If variant_id exists, find the variant data from valid_options
                if variant_id and product_data.get('valid_options'):
                    for option in product_data.get('valid_options', []):
                        if option.get('id') == variant_id:
                            variant_data = option
                            break                # Determine price based on variant or product pricing
                price = None
                if variant_data:
                    price = variant_data.get('discounted_price') or variant_data.get('price')
                if not price:
                    price = product_data.get('discount_price') or product_data.get('discounted_price') or product_data.get('price')
                # Fallback to 0 if no price found
                if price is None:
                    price = 0
                
                cart_item = {
                    'item_id': item_doc.id, # This is the cart item ID (product_id + variant_id)
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'name': product_data.get('name'),
                    'price': price,
                    'image': product_data.get('images', [product_data.get('image_url', '')])[0] if product_data.get('images') else product_data.get('image_url'),
                    'image_url': product_data.get('images', [product_data.get('image_url', '')])[0] if product_data.get('images') else product_data.get('image_url'),
                    'quantity': item_data.get('quantity'),
                    'stock': variant_data.get('stock') if variant_data else product_data.get('stock'),
                    'category': product_data.get('category', 'Product'),
                    'brand': product_data.get('brand', 'Unknown'),
                    'variant': variant_data,
                    'added_at': item_data.get('added_at')
                }
                cart.append(cart_item)
            else:
                # Handle case where product might have been deleted but still in cart
                cart.append({
                    'item_id': item_doc.id,
                    'product_id': product_id,
                    'name': 'Product not found',
                    'quantity': item_data.get('quantity'),
                    'error': 'Product details could not be fetched.'
                })


        return JsonResponse({'cart': cart}, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Error getting cart: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def remove_from_cart(request, item_id): # item_id here is the cart item identifier (product_id or product_id_variant_id)
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        cart_item_ref = db.collection('users').document(user_id).collection('cart').document(item_id)
        cart_item_doc = cart_item_ref.get()
        
        if cart_item_doc.exists:
            cart_item_data = cart_item_doc.to_dict()
            product_id = cart_item_data.get('product_id')
            variant_id = cart_item_data.get('variant_id')
            
            # Delete the cart item
            cart_item_ref.delete()
            
            return JsonResponse({
                'message': 'Item removed from cart successfully', 
                'item_id': item_id,
                'product_id': product_id,
                'variant_id': variant_id
            }, status=200)
        else:
            return JsonResponse({'error': 'Item not found in cart'}, status=404)

    except Exception as e:
        return JsonResponse({'error': f'Error removing from cart: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def add_to_wishlist(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        data = json.loads(request.body) if request.body else {}
        variant_id = data.get('variant_id', None)

        # Check if product exists
        product_doc = db.collection('products').document(product_id).get()
        if not product_doc.exists:
            return JsonResponse({'error': 'Product not found'}, status=404)

        # If variant_id is provided, validate it exists in the product's valid_options
        if variant_id:
            product_data = product_doc.to_dict()
            valid_options = product_data.get('valid_options', [])
            variant_found = any(option.get('id') == variant_id for option in valid_options)
            if not variant_found:
                return JsonResponse({'error': 'Invalid variant ID'}, status=400)

        # Create a unique wishlist item identifier based on product_id and variant_id
        wishlist_item_id = f"{product_id}_{variant_id}" if variant_id else product_id
        wishlist_ref = db.collection('users').document(user_id).collection('wishlist').document(wishlist_item_id)
        
        if wishlist_ref.get().exists:
            return JsonResponse({
                'message': 'Product already in wishlist', 
                'product_id': product_id, 
                'variant_id': variant_id
            }, status=200)
        else:
            wishlist_data = {
                'product_id': product_id,
                'variant_id': variant_id,
                'added_at': datetime.now()
            }
            wishlist_ref.set(wishlist_data)
            return JsonResponse({
                'message': 'Product added to wishlist', 
                'product_id': product_id, 
                'variant_id': variant_id
            }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error adding to wishlist: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def get_wishlist(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        wishlist_items_ref = db.collection('users').document(user_id).collection('wishlist').stream()
        
        wishlist = []
        for item_doc in wishlist_items_ref:
            item_data = item_doc.to_dict()
            product_id = item_data.get('product_id')
            
            # Fetch product details
            product_doc = db.collection('products').document(product_id).get()
            if product_doc.exists:
                product_data = product_doc.to_dict()
                variant_id = item_data.get('variant_id')
                variant_data = None
                
                # If variant_id exists, find the variant data from valid_options
                if variant_id and product_data.get('valid_options'):
                    for option in product_data.get('valid_options', []):
                        if option.get('id') == variant_id:
                            variant_data = option
                            break
                
                # Get the first image from images array or fallback to image_url
                image_url = None
                if product_data.get('images') and len(product_data.get('images')) > 0:
                    image_url = product_data.get('images')[0]
                else:
                    image_url = product_data.get('image_url', '')
                
                # Determine price based on variant or product pricing
                price = None
                if variant_data:
                    price = variant_data.get('discounted_price') or variant_data.get('price')
                if not price:
                    price = product_data.get('discount_price') or product_data.get('discounted_price') or product_data.get('price')
                
                wishlist_item = {
                    'item_id': item_doc.id,  # This is the wishlist item ID (product_id + variant_id)
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'name': product_data.get('name', 'Unknown Product'),
                    'price': price,
                    'image': image_url,
                    'image_url': image_url,
                    'stock': variant_data.get('stock') if variant_data else product_data.get('stock', 0),
                    'category': product_data.get('category', 'Product'),
                    'brand': product_data.get('brand', 'Unknown'),
                    'variant': variant_data,
                    'added_at': item_data.get('added_at')
                }
                wishlist.append(wishlist_item)
            else:
                wishlist.append({
                    'item_id': item_doc.id,
                    'product_id': product_id,
                    'name': 'Product not found',
                    'error': 'Product details could not be fetched.'
                })

        return JsonResponse({'wishlist': wishlist}, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Error getting wishlist: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def remove_from_wishlist(request, item_id): # item_id here is the wishlist item identifier (product_id or product_id_variant_id)
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        wishlist_item_ref = db.collection('users').document(user_id).collection('wishlist').document(item_id)
        wishlist_item_doc = wishlist_item_ref.get()
        
        if wishlist_item_doc.exists:
            wishlist_item_data = wishlist_item_doc.to_dict()
            product_id = wishlist_item_data.get('product_id')
            variant_id = wishlist_item_data.get('variant_id')
            
            # Delete the wishlist item
            wishlist_item_ref.delete()
            
            return JsonResponse({
                'message': 'Item removed from wishlist successfully', 
                'item_id': item_id,
                'product_id': product_id,
                'variant_id': variant_id
            }, status=200)
        else:
            return JsonResponse({'error': 'Item not found in wishlist'}, status=404)

    except Exception as e:
        return JsonResponse({'error': f'Error removing from wishlist: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def create_razorpay_order(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        data = json.loads(request.body)
        print('Request data:', data)
        amount_in_paise = data.get('amount') # Amount should be in paise
        currency = data.get('currency', 'INR')
        product_ids = data.get('product_ids') # List of product_ids in the cart being ordered
        address_id = data.get('address_id') # ID of the selected shipping address
        is_single_product_order = data.get('single_product_order', False)
        product_details = data.get('product_details') # For single product orders

        if not amount_in_paise or not product_ids or not address_id:
            return JsonResponse({'error': 'Amount, product_ids, and address_id are required'}, status=400)

        try:
            amount_in_paise = int(amount_in_paise)
            if amount_in_paise <= 0:
                 return JsonResponse({'error': 'Amount must be greater than 0'}, status=400)
        except ValueError:
            return JsonResponse({'error': 'Invalid amount format'}, status=400)

        # Fetch address details to include in the order
        address_ref = db.collection('users').document(user_id).collection('addresses').document(address_id)
        address_doc = address_ref.get()
        if not address_doc.exists:
            return JsonResponse({'error': 'Selected address not found'}, status=400)        
        address_data = address_doc.to_dict()
        
        # Fetch product details to store with preliminary order
        preliminary_order_items = []
        print(f"Processing {len(product_ids)} product IDs for order creation: {product_ids}")
        for product_id in product_ids:
            # Check if this is a cart item ID (format: product_id or product_id_variant_id)
            # or a direct product ID (for single product orders)
            cart_item_ref = db.collection('users').document(user_id).collection('cart').document(product_id)
            cart_item_doc = cart_item_ref.get()
            
            if cart_item_doc.exists:
                # This is a cart-based order
                cart_item_data = cart_item_doc.to_dict()
                quantity = cart_item_data.get('quantity', 1)
                variant_id = cart_item_data.get('variant_id')
                actual_product_id = product_id.split('_')[0]  # Extract actual product_id
                print(f"Found cart item {product_id}: quantity={quantity}, variant_id={variant_id}")
            else:
                # This might be a single product order - check if we have product_details
                if is_single_product_order and product_details:
                    quantity = product_details.get('quantity', 1)
                    variant_id = product_details.get('variant_id')
                    actual_product_id = product_details.get('product_id', product_id)
                    print(f"Single product order for {product_id}: quantity={quantity}, variant_id={variant_id}")
                else:
                    # Fallback for other cases
                    quantity = 1
                    variant_id = None
                    actual_product_id = product_id
                    print(f"No cart item found for {product_id}, using defaults: quantity={quantity}, variant_id={variant_id}")
            
            product_ref = db.collection('products').document(actual_product_id)
            product_doc = product_ref.get()
            
            if product_doc.exists:
                product_data = product_doc.to_dict()
                variant_data = None
                
                # Find variant data if variant_id exists
                if variant_id and product_data.get('valid_options'):
                    for option in product_data.get('valid_options', []):
                        if option.get('id') == variant_id:
                            variant_data = option
                            break
                
                # Use variant price if available, otherwise product price
                item_price = variant_data.get('discounted_price') or variant_data.get('price') if variant_data else product_data.get('price', 0)
                
                order_item = {
                    'product_id': actual_product_id,
                    'variant_id': variant_id,
                    'name': product_data.get('name'),
                    'image_url': product_data.get('images', [product_data.get('image_url', '')])[0] if product_data.get('images') else product_data.get('image_url', ''),
                    'brand': product_data.get('brand', ''),
                    'variant_details': variant_data,
                    'quantity': quantity,
                    'price': item_price,
                    'total_item_price': item_price * quantity
                }
                preliminary_order_items.append(order_item)
                print(f"Added order item: {order_item['name']} x {quantity}")
            else:
                print(f"Product {actual_product_id} not found in products collection")

        print(f"Created preliminary order with {len(preliminary_order_items)} items")        # Initialize Razorpay client
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        # Create Razorpay order with a receipt ID that won't exceed 40 characters
        receipt_id = f'rcpt_{user_id[:8]}_{int(time.time())}'  # Shorter, unique receipt ID
        order_payload = {
            'amount': amount_in_paise,
            'currency': currency,
            'receipt': receipt_id,  # Unique receipt ID within 40 chars limit
            'payment_capture': 1 # Auto capture payment
        }
        razorpay_order = client.order.create(data=order_payload)

        # Generate expected delivery date (5-7 days from now)
        from datetime import datetime, timedelta
        order_date = datetime.now()
        est_delivery_date = order_date + timedelta(days=10)  # Default to 7 days

        # Store preliminary order details in Firestore (e.g., with 'pending_payment' status)
        # This helps in tracking orders even if payment fails or is abandoned.
        order_ref = db.collection('users').document(user_id).collection('orders').document()
        preliminary_order_data = {
            'razorpay_order_id': razorpay_order['id'],
            'user_id': user_id,
            'product_ids': product_ids, # Store product IDs for now
            'order_items': preliminary_order_items,  # Store detailed product info
            'address': address_data,  # Store complete address information
            'address_id': address_id,
            'total_amount': amount_in_paise / 100, # Store amount in rupees
            'currency': currency,
            'status': 'pending_payment',
            'created_at': datetime.now(),
            'estimated_delivery': est_delivery_date,
            'tracking_info': {
                'carrier': None,
                'tracking_number': None,
                'tracking_url': None,
                'status_history': [
                    {
                        'status': 'pending_payment',
                        'timestamp': datetime.now(),  # Use client-side timestamp here
                        'description': 'Order created, awaiting payment'
                    }
                ]
            },
            'payment_details': None # To be filled after successful payment
        }
        order_ref.set(preliminary_order_data)

        return JsonResponse({
            'message': 'Razorpay order created successfully',
            'razorpay_order_id': razorpay_order['id'],
            'app_order_id': order_ref.id, # Your application's order ID
            'amount': razorpay_order['amount'],
            'currency': razorpay_order['currency'],
            'key_id': settings.RAZORPAY_KEY_ID # Send key_id to frontend
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error creating Razorpay order: {str(e)}'}, status=500)


@user_required
@csrf_exempt
def verify_razorpay_payment(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        data = json.loads(request.body)
        print('Payment verification data:', data)

        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature = data.get('razorpay_signature')
        app_order_id = data.get('order_id') # Changed 'app_order_id' to 'order_id'

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, app_order_id]):
            return JsonResponse({'error': 'Missing Razorpay payment details or app_order_id/order_id'}, status=400)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        # Verify payment signature
        payment_verification = client.utility.verify_payment_signature(params_dict)

        order_doc_ref = db.collection('users').document(user_id).collection('orders').document(app_order_id)
        order_doc = order_doc_ref.get()

        if not order_doc.exists:
            return JsonResponse({'error': 'Order not found in our system.'}, status=404)
        
        order_data = order_doc.to_dict()

        if order_data.get('razorpay_order_id') != razorpay_order_id:
             return JsonResponse({'error': 'Razorpay Order ID mismatch.'}, status=400)

        if payment_verification: # This will be True if signature is valid, None otherwise
            # Payment is successful, now update your order status and details

            # Fetch payment details from Razorpay for more info (optional but good)
            payment_details = client.payment.fetch(razorpay_payment_id)              # Get product details and calculate final order items
            product_ids = order_data.get('product_ids', [])
            existing_order_items = order_data.get('order_items', [])
            order_items = []
            total_calculated_amount = 0            # Debug: Check if we have existing order items
            print(f"Existing order_items count: {len(existing_order_items)}")
            if existing_order_items:
                print(f"Sample existing order item: {existing_order_items[0]}")
            print(f"Product IDs to process: {product_ids}")

            # Start a Firestore transaction or batch write for atomicity
            batch = db.batch()

            for cart_item_id in product_ids:
                # Extract actual product_id from cart_item_id (format: product_id or product_id_variant_id)
                actual_product_id = cart_item_id.split('_')[0]
                
                # Get cart item data to get variant_id and quantity
                cart_item_ref = db.collection('users').document(user_id).collection('cart').document(cart_item_id)
                cart_item_doc = cart_item_ref.get()
                
                if not cart_item_doc.exists:
                    continue
                    
                cart_item_data = cart_item_doc.to_dict()
                quantity = cart_item_data.get('quantity', 1)
                variant_id = cart_item_data.get('variant_id')
                
                # Get product data
                product_ref = db.collection('products').document(actual_product_id)
                product_doc = product_ref.get()
                
                if product_doc.exists:
                    product_data = product_doc.to_dict()
                    variant_data = None
                    
                    # Find variant data if variant_id exists
                    if variant_id and product_data.get('valid_options'):
                        valid_options = product_data.get('valid_options', [])
                        for i, option in enumerate(valid_options):
                            if option.get('id') == variant_id:
                                variant_data = option
                                variant_index = i
                                break                    
                    # Use variant price if available, otherwise product price
                    item_price = variant_data.get('discounted_price') or variant_data.get('price') if variant_data else product_data.get('price', 0)
                    
                    order_items.append({
                        'product_id': actual_product_id,
                        'variant_id': variant_id,
                        'name': product_data.get('name'),
                        'brand': product_data.get('brand', ''),
                        'model': variant_data.get('name', '') if variant_data else product_data.get('model', ''),
                        'quantity': quantity,
                        'price_at_purchase': item_price,
                        'total_item_price': item_price * quantity,
                        'image_url': product_data.get('images', [product_data.get('image_url', '')])[0] if product_data.get('images') else product_data.get('image_url', ''),
                        'variant_details': variant_data
                    })
                    total_calculated_amount += item_price * quantity

                    # Update stock - either variant stock or product stock
                    if variant_data:
                        # Update variant stock
                        current_variant_stock = variant_data.get('stock', 0)
                        new_variant_stock = current_variant_stock - quantity
                        if new_variant_stock < 0:
                            print(f"Warning: Variant stock for product {actual_product_id}, variant {variant_id} has gone negative ({new_variant_stock}) after order {app_order_id}.")
                        
                        # Update the variant stock in valid_options
                        updated_valid_options = product_data.get('valid_options', [])
                        for i, option in enumerate(updated_valid_options):
                            if option.get('id') == variant_id:
                                updated_valid_options[i]['stock'] = new_variant_stock
                                break
                        
                        batch.update(product_ref, {'valid_options': updated_valid_options})
                    else:
                        # Update product stock
                        current_stock = product_data.get('stock', 0)
                        new_stock = current_stock - quantity
                        if new_stock < 0:
                            print(f"Warning: Stock for product {actual_product_id} has gone negative ({new_stock}) after order {app_order_id}.")
                        
                        batch.update(product_ref, {'stock': new_stock})
                      # Clear the item from the cart after successful order
                    batch.delete(cart_item_ref)            # If no order_items were created (cart items might have been cleared already), 
            # use the existing preliminary order items
            if not order_items and existing_order_items:
                print("No new order items created, using existing preliminary order items")
                order_items = existing_order_items
                # Recalculate total from existing items
                total_calculated_amount = sum(item.get('total_item_price', 0) for item in order_items)
            elif not order_items and not existing_order_items:
                # This shouldn't happen, but if both are empty, log an error
                print(f"ERROR: Both new order_items and existing_order_items are empty for order {app_order_id}")
                print(f"Product IDs: {product_ids}")
                print(f"Order data keys: {list(order_data.keys())}")
                # Try to reconstruct order items from the stored preliminary data
                order_items = existing_order_items  # Keep it empty for now to avoid errors

            # Verify total amount (optional but recommended)
            # Note: Razorpay amount is in paise.
            if order_data.get('total_amount') != (payment_details.get('amount') / 100):
                # Log discrepancy, but might proceed if signature is verified
                print(f"Warning: Amount mismatch. Stored: {order_data.get('total_amount')}, Razorpay: {payment_details.get('amount') / 100}")            # Generate shipping details with estimated dates
            import random

            # Update tracking info and status history
            tracking_info = order_data.get('tracking_info', {})
            if not tracking_info:
                tracking_info = {
                    'status_history': []
                }
                
            tracking_info['carrier'] = None
            tracking_info['tracking_number'] = None
            tracking_info['tracking_url'] = ""
            
            # Add new status to history
            status_history = tracking_info.get('status_history', [])
            status_history.append({
                'status': 'payment_successful',
                'timestamp': datetime.now(), # Use client-side timestamp
                'description': 'Payment received successfully'
            })
            tracking_info['status_history'] = status_history

            # Update order in Firestore
            final_order_update = {
                'status': 'payment_successful', # Or 'processing', 'confirmed' etc.
                'payment_details': {
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature,
                    'method': payment_details.get('method'),
                    'status': payment_details.get('status'), # Should be 'captured'
                    'captured_at': datetime.now(), # Or use payment_details.get('created_at')
                    'card_network': payment_details.get('card', {}).get('network'),  # Add card details if available
                    'card_last4': payment_details.get('card', {}).get('last4')
                },                'order_items': order_items,
                'total_amount_calculated': total_calculated_amount, # Store the server-calculated total
                'tracking_info': tracking_info,
                'updated_at': datetime.now()
            }
            batch.update(order_doc_ref, final_order_update)
              # Commit the batch
            batch.commit()

            # Get updated cart after clearing items
            try:
                updated_cart_items_ref = db.collection('users').document(user_id).collection('cart').stream()
                updated_cart = []
                for item_doc in updated_cart_items_ref:
                    item_data = item_doc.to_dict()
                    product_id = item_data.get('product_id')
                    # Fetch product details
                    product_doc = db.collection('products').document(product_id).get()
                    if product_doc.exists:
                        product_data = product_doc.to_dict()
                        variant_id = item_data.get('variant_id')
                        variant_data = None
                        
                        # If variant_id exists, find the variant data from valid_options
                        if variant_id and product_data.get('valid_options'):
                            for option in product_data.get('valid_options', []):
                                if option.get('id') == variant_id:
                                    variant_data = option
                                    break
                        
                        cart_item = {
                            'item_id': item_doc.id,
                            'product_id': product_id,
                            'variant_id': variant_id,
                            'name': product_data.get('name'),
                            'price': variant_data.get('discounted_price') or variant_data.get('price') if variant_data else product_data.get('discount_price') or product_data.get('price'),
                            'image_url': product_data.get('images', [product_data.get('image_url', '')])[0] if product_data.get('images') else product_data.get('image_url'),
                            'quantity': item_data.get('quantity'),
                            'stock': variant_data.get('stock') if variant_data else product_data.get('stock'),
                            'category': product_data.get('category', 'Product'),
                            'brand': product_data.get('brand', 'Unknown'),
                            'variant': variant_data,
                            'added_at': item_data.get('added_at')
                        }
                        updated_cart.append(cart_item)
            except Exception as cart_error:
                print(f"Error fetching updated cart: {str(cart_error)}")
                updated_cart = []            # Generate invoice after successful payment and order update
            try:
                logger.info(f"Starting invoice generation for order {app_order_id}")
                
                # Get user data for invoice
                user_doc = db.collection('users').document(user_id).get()
                user_data = user_doc.to_dict() if user_doc.exists else {}
                
                # Prepare complete order data for invoice creation
                complete_order_data = {
                    **order_data,
                    'order_id': app_order_id,
                    'total_amount': total_calculated_amount,
                    'shipping_cost': order_data.get('shipping_cost', 0)
                }
                  # Create invoice data
                invoice_data = create_invoice_data(complete_order_data, user_data, order_items)
                
                if invoice_data:
                    logger.info(f"Invoice data created successfully for order {app_order_id}")
                    
                    # Generate PDF
                    pdf_buffer = generate_invoice_pdf(invoice_data)
                    
                    if pdf_buffer:
                        logger.info(f"PDF generated successfully for order {app_order_id}")
                        
                        # Save PDF to disk for debugging (optional - can be removed in production)
                        debug_filename = f"debug_invoice_{invoice_data['invoice_id']}.pdf"
                        debug_path = save_pdf_to_disk_debug(pdf_buffer, debug_filename)
                        if debug_path:
                            logger.info(f"Debug PDF saved to: {debug_path}")
                        
                        # Validate PDF buffer before upload
                        pdf_buffer.seek(0)
                        pdf_bytes = pdf_buffer.getvalue()
                        logger.info(f"PDF buffer size: {len(pdf_bytes)} bytes")
                        
                        if len(pdf_bytes) > 100 and pdf_bytes.startswith(b'%PDF'):
                            # Upload PDF to Cloudinary
                            pdf_filename = f"invoice_{invoice_data['invoice_id']}"
                            pdf_url = upload_pdf_to_cloudinary_util(pdf_buffer, pdf_filename)
                            
                            # Try alternative upload method if first method fails
                            if not pdf_url:
                                logger.warning("Primary upload method failed, trying base64 method")
                                pdf_url = upload_pdf_to_cloudinary_base64(pdf_buffer, pdf_filename)
                            
                            if pdf_url:
                                logger.info(f"PDF uploaded successfully to Cloudinary for order {app_order_id}")
                                
                                # Save invoice to Firestore
                                invoice_doc_id = save_invoice_to_firestore(db, user_id, invoice_data, pdf_url)
                                
                                if invoice_doc_id:
                                    # Update order with invoice reference
                                    order_doc_ref.update({
                                        'invoice_id': invoice_data['invoice_id'],
                                        'invoice_pdf_url': pdf_url
                                    })
                                    logger.info(f"Invoice generated and saved successfully: {invoice_data['invoice_id']}")
                                else:
                                    logger.error("Failed to save invoice to Firestore")
                            else:
                                logger.error("Failed to upload invoice PDF to Cloudinary with all methods")
                        else:
                            logger.error(f"Invalid PDF buffer - Size: {len(pdf_bytes)}, Starts with PDF: {pdf_bytes.startswith(b'%PDF') if pdf_bytes else False}")
                    else:
                        logger.error("Failed to generate invoice PDF")
                else:
                    logger.error("Failed to create invoice data")
                    
            except PDFGenerationError as pdf_error:
                # Specific PDF generation error - don't fail the payment
                logger.error(f"PDF generation error: {str(pdf_error)}")
                print("Payment verification successful, but invoice generation failed")
            except Exception as invoice_error:
                # Log error but don't fail the payment verification
                logger.error(f"Error generating invoice: {str(invoice_error)}")
                import traceback
                logger.error(f"Invoice error traceback: {traceback.format_exc()}")
                print(f"Error generating invoice: {str(invoice_error)}")
                print(f"Invoice error traceback: {traceback.format_exc()}")

            return JsonResponse({
                'message': 'Payment verified successfully and order placed.',
                'app_order_id': app_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'order_status': final_order_update['status'],
                'updated_cart': updated_cart,
                'cart_items_removed': len(product_ids)
            }, status=200)
        else:
            # Payment verification failed
            
            # Update tracking info and status history
            tracking_info = order_data.get('tracking_info', {})
            if not tracking_info:
                tracking_info = {
                    'status_history': []
                }
                
            # Add new status to history
            status_history = tracking_info.get('status_history', [])
            status_history.append({
                'status': 'payment_failed',
                'timestamp': datetime.now(), # Use client-side timestamp
                'description': 'Payment verification failed'
            })
            tracking_info['status_history'] = status_history
            
            order_doc_ref.update({
                'status': 'payment_failed',
                'payment_details': {
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature,
                    'error_message': 'Signature verification failed'
                },
                'tracking_info': tracking_info,
                'updated_at': datetime.now()
            })
            return JsonResponse({'error': 'Payment verification failed. Signature mismatch.'}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except razorpay.errors.SignatureVerificationError as sve:
        # Also update order status in case of this specific error
        try:
            # Ensure app_order_id is defined in this scope if an error occurs before its main assignment
            app_order_id_for_error = data.get('order_id') # Attempt to get it again
            if app_order_id_for_error:
                order_doc_ref_error = db.collection('users').document(user_id).collection('orders').document(app_order_id_for_error)
                if order_doc_ref_error.get().exists:
                    order_doc = order_doc_ref_error.get()
                    order_data = order_doc.to_dict()
                    
                    # Update tracking info and status history
                    tracking_info = order_data.get('tracking_info', {})
                    if not tracking_info:
                        tracking_info = {
                            'status_history': []
                        }
                        
                    # Add new status to history
                    status_history = tracking_info.get('status_history', [])
                    status_history.append({
                        'status': 'payment_failed',
                        'timestamp': datetime.now(), # Use client-side timestamp
                        'description': 'Payment verification failed (Razorpay signature error)'
                    })
                    tracking_info['status_history'] = status_history
                    
                    order_doc_ref_error.update({
                        'status': 'payment_failed',
                        'payment_details': {
                            'razorpay_payment_id': data.get('razorpay_payment_id'),
                            'error_message': 'Signature verification failed (Razorpay lib error)'
                        },
                        'tracking_info': tracking_info,
                        'updated_at': datetime.now()
                    })
        except Exception as e_inner:
            print(f"Error updating order status after SignatureVerificationError: {e_inner}")

        return JsonResponse({'error': f'Payment verification failed: {str(sve)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error verifying payment: {str(e)}'}, status=500)

@user_required
@csrf_exempt # GET requests are generally not CSRF vulnerable, but good practice if any state changes
def get_user_orders(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        orders_ref = db.collection('users').document(user_id).collection('orders').order_by('created_at', direction=Query.DESCENDING).stream()
        
        orders_list = []
        for order_doc in orders_ref:
            order_data = order_doc.to_dict()            # Format timestamps for consistent display
            created_at = order_data.get('created_at')
            created_at_formatted = None
            if created_at:
                if hasattr(created_at, 'strftime'):
                    # Use the same format as get_order_details for consistency
                    created_at_formatted = created_at.strftime('%m/%d/%Y at %I:%M %p')
                else:
                    # Handle string timestamps or other formats
                    created_at_formatted = str(created_at)
                
            # Get first item image for preview
            order_items = order_data.get('order_items', [])
            preview_image = None
            if order_items and len(order_items) > 0:
                preview_image = order_items[0].get('image_url')
              # Calculate item count properly
            item_count = 0
            if order_items:
                # Sum up quantities of all items
                for item in order_items:
                    item_count += item.get('quantity', 1)
            
            # Debug: print the item count calculation
            print(f"Order {order_doc.id}: order_items count: {len(order_items) if order_items else 0}, calculated item_count: {item_count}")
              # Format estimated delivery date
            estimated_delivery = order_data.get('estimated_delivery')
            estimated_delivery_formatted = None
            if estimated_delivery:
                if hasattr(estimated_delivery, 'strftime'):
                    estimated_delivery_formatted = estimated_delivery.isoformat()
                else:
                    estimated_delivery_formatted = str(estimated_delivery)
            
            orders_list.append({
                'order_id': order_doc.id,
                'status': order_data.get('status'),
                'total_amount': order_data.get('total_amount'),
                'currency': order_data.get('currency', 'INR'),
                'created_at': created_at_formatted,
                'item_count': item_count,
                'preview_image': preview_image,
                'tracking_info': order_data.get('tracking_info', {}),
                'estimated_delivery': estimated_delivery_formatted
            })

        return JsonResponse({'orders': orders_list}, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Error fetching orders: {str(e)}'}, status=500)

@user_required
@csrf_exempt # As above
def get_order_details(request, order_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        order_doc_ref = db.collection('users').document(user_id).collection('orders').document(order_id)
        order_doc = order_doc_ref.get()

        if not order_doc.exists:
            return JsonResponse({'error': 'Order not found or access denied'}, status=404)

        order_data = order_doc.to_dict()
        
        # Ensure the order belongs to the user (already implicitly handled by Firestore path, but good for clarity)
        if order_data.get('user_id') != user_id:
             return JsonResponse({'error': 'Order not found or access denied'}, status=404)

        # Format the timestamps for better readability
        created_at = order_data.get('created_at')
        if created_at:
            if hasattr(created_at, 'strftime'):
                order_data['created_at_formatted'] = created_at.strftime('%m/%d/%Y at %I:%M %p')
        
        # Format the payment capture timestamp
        payment_details = order_data.get('payment_details', {})
        if payment_details and payment_details.get('captured_at'):
            captured_at = payment_details.get('captured_at')
            if hasattr(captured_at, 'strftime'):
                payment_details['captured_at_formatted'] = captured_at.strftime('%m/%d/%Y at %I:%M %p')
        
        # Format estimated delivery date
        estimated_delivery = order_data.get('estimated_delivery')
        if estimated_delivery:
            if hasattr(estimated_delivery, 'strftime'):
                order_data['estimated_delivery_formatted'] = estimated_delivery.strftime('%m/%d/%Y')
        
        # Process status history timestamps
        tracking_info = order_data.get('tracking_info', {})
        status_history = tracking_info.get('status_history', [])
        for status in status_history:
            timestamp = status.get('timestamp')
            if timestamp and hasattr(timestamp, 'strftime'):
                status['timestamp_formatted'] = timestamp.strftime('%m/%d/%Y at %I:%M %p')
          # Get shipping address if not already included
        if 'address' not in order_data and 'address_id' in order_data:
            address_id = order_data.get('address_id')
            address_doc = db.collection('users').document(user_id).collection('addresses').document(address_id).get()
            if address_doc.exists:
                order_data['address'] = address_doc.to_dict()

        # Include invoice information if available
        invoice_info = {}
        if 'invoice_id' in order_data:
            invoice_info['invoice_id'] = order_data['invoice_id']
        if 'invoice_pdf_url' in order_data:
            invoice_info['invoice_pdf_url'] = order_data['invoice_pdf_url']
        
        if invoice_info:
            order_data['invoice'] = invoice_info

        return JsonResponse({'order_details': order_data}, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Error fetching order details: {str(e)}'}, status=500)

# @user_required
# @csrf_exempt # GET requests are generally not CSRF vulnerable, but good practice if any state changes
# def get_user_orders(request):
#     if request.method != 'GET':
#         return JsonResponse({'error': 'Invalid request method'}, status=405)

#     try:
#         user_id = request.user_id
#         orders_ref = db.collection('users').document(user_id).collection('orders').order_by('created_at', direction=firestore.Query.DESCENDING).stream()

#         orders_list = []
#         for order_doc in orders_ref:
#             order_data = order_doc.to_dict()
#             orders_list.append({
#                 'order_id': order_doc.id,
#                 'status': order_data.get('status'),
#                 'total_amount': order_data.get('total_amount'),
#                 'currency': order_data.get('currency'),
#                 'created_at': order_data.get('created_at'),
#                 'item_count': len(order_data.get('order_items', []))
#             })

#         return JsonResponse({'orders': orders_list}, status=200)

#     except Exception as e:
#         return JsonResponse({'error': f'Error fetching orders: {str(e)}'}, status=500)

# @user_required
# @csrf_exempt # As above
# def get_order_details(request, order_id):
#     if request.method != 'GET':
#         return JsonResponse({'error': 'Invalid request method'}, status=405)

#     try:
#         user_id = request.user_id
#         order_doc_ref = db.collection('users').document(user_id).collection('orders').document(order_id)
#         order_doc = order_doc_ref.get()

#         if not order_doc.exists:
#             return JsonResponse({'error': 'Order not found or access denied'}, status=404)

#         order_data = order_doc.to_dict()
        
#         # Ensure the order belongs to the user (already implicitly handled by Firestore path, but good for clarity)
#         if order_data.get('user_id') != user_id:
#              return JsonResponse({'error': 'Order not found or access denied'}, status=404)


#         return JsonResponse({'order_details': order_data}, status=200)

#     except Exception as e:
#         return JsonResponse({'error': f'Error fetching order details: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def add_address(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    try:
        user_id = request.user_id
        data = json.loads(request.body)

        required_fields = ['type', 'street_address', 'city', 'state', 'postal_code', 'phone_number']
        if not all(field in data for field in required_fields):
            return JsonResponse({'error': f'Missing one or more required fields: {", ".join(required_fields)}'}, status=400)

        is_default = data.get('is_default', False)

        addresses_ref = db.collection('users').document(user_id).collection('addresses')

        # If this address is being set as default, unset other default addresses
        if is_default:
            default_addresses_query = addresses_ref.where('is_default', '==', True).stream()
            batch = db.batch()
            for addr_doc in default_addresses_query:
                batch.update(addr_doc.reference, {'is_default': False})
            batch.commit()

        address_payload = {
            'type': data['type'],
            'street_address': data['street_address'],
            'city': data['city'],
            'state': data['state'],
            'postal_code': data['postal_code'],
            'phone_number': data['phone_number'],
            'is_default': is_default,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        }
        _, new_address_ref = addresses_ref.add(address_payload) # Use _ for unused update_time
        
        # Fetch the newly created document to get resolved timestamps
        new_address_doc = new_address_ref.get()
        response_address_data = new_address_doc.to_dict()
        response_address_data['id'] = new_address_ref.id # Add the ID to the response data

        return JsonResponse({'message': 'Address added successfully', 'address_id': new_address_ref.id, 'address': response_address_data}, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error adding address: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def get_addresses(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    try:
        user_id = request.user_id
        addresses_stream = db.collection('users').document(user_id).collection('addresses').order_by('is_default', direction=Query.DESCENDING).stream()
        
        addresses_list = []
        for addr_doc in addresses_stream:
            address_data = addr_doc.to_dict()
            address_data['id'] = addr_doc.id
            addresses_list.append(address_data)
        
        return JsonResponse({'addresses': addresses_list}, status=200)
    except Exception as e:
        return JsonResponse({'error': f'Error fetching addresses: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def update_address(request, address_id):
    if request.method != 'PUT': # Typically PUT for updates
        return JsonResponse({'error': 'Invalid request method, use PUT'}, status=405)
    try:
        user_id = request.user_id
        data = json.loads(request.body)
        address_ref = db.collection('users').document(user_id).collection('addresses').document(address_id)

        if not address_ref.get().exists:
            return JsonResponse({'error': 'Address not found'}, status=404)

        is_default = data.get('is_default')
        addresses_collection_ref = db.collection('users').document(user_id).collection('addresses')

        # If this address is being set as default, unset other default addresses
        if is_default is True:
            default_addresses_query = addresses_collection_ref.where('is_default', '==', True).stream()
            batch = db.batch()
            for addr_doc in default_addresses_query:
                if addr_doc.id != address_id: # Don't unset the current one if it's already default
                    batch.update(addr_doc.reference, {'is_default': False})
            batch.commit() # Commit this batch first
        
        # Prepare payload, only update fields that are provided
        update_payload = {}
        allowed_fields = ['type', 'street_address', 'city', 'state', 'postal_code', 'phone_number', 'is_default']
        for field in allowed_fields:
            if field in data:
                update_payload[field] = data[field]
        
        if not update_payload:
            return JsonResponse({'error': 'No update data provided'}, status=400)

        update_payload['updated_at'] = datetime.now()
        address_ref.update(update_payload)
        updated_address = address_ref.get().to_dict()
        updated_address['id'] = address_id

        return JsonResponse({'message': 'Address updated successfully', 'address': updated_address}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error updating address: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def delete_address(request, address_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    try:
        user_id = request.user_id
        address_ref = db.collection('users').document(user_id).collection('addresses').document(address_id)
        address_doc = address_ref.get()

        if not address_doc.exists:
            return JsonResponse({'error': 'Address not found'}, status=404)
        
        # If deleting the default address, ideally the user should be prompted to set a new default.
        # For now, we just delete it. Consider application logic for this.
        # if address_doc.to_dict().get('is_default') is True:
            # Potentially find another address and make it default, or leave no default.

        address_ref.delete()
        return JsonResponse({'message': 'Address deleted successfully', 'address_id': address_id}, status=200)
    except Exception as e:
        return JsonResponse({'error': f'Error deleting address: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def set_default_address(request, address_id):
    if request.method != 'POST': # Using POST to make a specific address default
        return JsonResponse({'error': 'Invalid request method, use POST'}, status=405)
    try:
        user_id = request.user_id
        target_address_ref = db.collection('users').document(user_id).collection('addresses').document(address_id)

        if not target_address_ref.get().exists:
            return JsonResponse({'error': 'Target address not found'}, status=404)

        addresses_collection_ref = db.collection('users').document(user_id).collection('addresses')
        default_addresses_query = addresses_collection_ref.where('is_default', '==', True).stream()
        
        batch = db.batch()
        # Unset current default(s)
        for addr_doc in default_addresses_query:
            if addr_doc.id != address_id:
                batch.update(addr_doc.reference, {'is_default': False})
        
        # Set the new default
        batch.update(target_address_ref, {'is_default': True, 'updated_at': datetime.now()})
        batch.commit()

        return JsonResponse({'message': f'Address {address_id} set as default successfully'}, status=200)
    except Exception as e:
        return JsonResponse({'error': f'Error setting default address: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def get_profile(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    try:
        user_id = request.user_id
        user_doc_ref = db.collection('users').document(user_id)
        user_doc = user_doc_ref.get()

        if not user_doc.exists:
            return JsonResponse({'error': 'User profile not found'}, status=404)
        
        user_data = user_doc.to_dict()
        # Exclude sensitive information like password
        profile_data = {
            'user_id': user_doc.id,
            'email': user_data.get('email'),
            'first_name': user_data.get('first_name'),
            'last_name': user_data.get('last_name'),
            'phone_number': user_data.get('phone_number'),
            'auth_provider': user_data.get('auth_provider'),
            'uid': user_data.get('uid') # Firebase UID if available
        }
        return JsonResponse(profile_data, status=200)
    except Exception as e:
        return JsonResponse({'error': f'Error fetching profile: {str(e)}'}, status=500)


@user_required
@csrf_exempt
def update_profile(request):
    if request.method != 'POST': # Using POST as it can modify multiple fields including password
        return JsonResponse({'error': 'Invalid request method, use POST'}, status=405)
    
    try:
        user_id = request.user_id
        data = json.loads(request.body)
        user_doc_ref = db.collection('users').document(user_id)
        user_doc = user_doc_ref.get()

        if not user_doc.exists:
            return JsonResponse({'error': 'User not found'}, status=404)
        
        user_data = user_doc.to_dict()
        update_payload = {}
        response_message = "Profile updated successfully"

        # Update basic profile information
        if 'first_name' in data:
            update_payload['first_name'] = data['first_name']
        if 'last_name' in data:
            update_payload['last_name'] = data['last_name']
        if 'phone_number' in data:
            update_payload['phone_number'] = data['phone_number']

        # Handle password change for email provider users
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_new_password = data.get('confirm_new_password')

        if current_password and new_password and confirm_new_password:
            if user_data.get('auth_provider') == 'email':
                if not check_password(current_password, user_data.get('password')):
                    return JsonResponse({'error': 'Invalid current password'}, status=400)
                if new_password != confirm_new_password:
                    return JsonResponse({'error': 'New passwords do not match'}, status=400)
                if len(new_password) < 6: # Basic password strength check
                    return JsonResponse({'error': 'New password must be at least 6 characters long'}, status=400)
                
                update_payload['password'] = make_password(new_password)
                response_message = "Profile and password updated successfully"
            else:
                # For Firebase auth users, password change should be handled via Firebase mechanisms
                return JsonResponse({
                    'error': 'Password change not allowed for this account type. Please use the provider\'s method to change your password.',
                    'profile_updated': bool(update_payload) # Inform if other fields were processed
                }, status=400)
        elif current_password or new_password or confirm_new_password:
            # If any password field is present, all must be present
            return JsonResponse({'error': 'All password fields (current, new, confirm) are required to change password'}, status=400)

        if update_payload:
            update_payload['updated_at'] = datetime.now()
            user_doc_ref.update(update_payload)
            
            # Fetch updated data to return (optional, but good for confirmation)
            updated_user_data = user_doc_ref.get().to_dict()
            profile_data_to_return = {
                'email': updated_user_data.get('email'),
                'first_name': updated_user_data.get('first_name'),
                'last_name': updated_user_data.get('last_name'),
                'phone_number': updated_user_data.get('phone_number')
            }
            return JsonResponse({'message': response_message, 'user': profile_data_to_return}, status=200)
        else:
            return JsonResponse({'message': 'No changes provided'}, status=200)    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error updating profile: {str(e)}'}, status=500)


@user_required
def check_user_review(request, product_id):
    """Check if the current user has already reviewed a specific product"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        user_id = request.user_id
        print(f"Checking review for user {user_id} and product {product_id}")  # Debug log
        
        # Check if product exists
        product_doc = db.collection('products').document(product_id).get()
        if not product_doc.exists:
            print(f"Product {product_id} not found")  # Debug log
            return JsonResponse({'error': 'Product not found'}, status=404)
        
        # Check if user has already reviewed this product
        existing_review = db.collection('products').document(product_id).collection('reviews').where('user_id', '==', user_id).limit(1).stream()
        reviews_list = list(existing_review)
        has_reviewed = len(reviews_list) > 0
        
        print(f"Review check result: user {user_id}, product {product_id}, has_reviewed: {has_reviewed}, found {len(reviews_list)} reviews")  # Debug log
        
        return JsonResponse({
            'has_reviewed': has_reviewed,
            'product_id': product_id,
            'user_id': user_id
        }, status=200)
        
    except Exception as e:
        print(f"Error in check_user_review: {str(e)}")  # Debug log
        return JsonResponse({'error': f'Error checking review status: {str(e)}'}, status=500)



