from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password, check_password
import jwt
from firebase_admin.exceptions import FirebaseError
import json
from shop_users.utils import user_required
from anand_mobiles.settings import SECRET_KEY
from firebase_admin import firestore, auth as firebase_auth
import razorpay
from django.conf import settings # Import settings

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

@user_required
@csrf_exempt
def add_to_cart(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        data = json.loads(request.body)
        quantity = data.get('quantity', 1)

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

        cart_ref = db.collection('users').document(user_id).collection('cart').document(product_id)
        cart_item = cart_ref.get()

        if cart_item.exists:
            # Update quantity if item already in cart
            new_quantity = cart_item.to_dict().get('quantity', 0) + quantity
            cart_ref.update({'quantity': new_quantity, 'updated_at': firestore.SERVER_TIMESTAMP})
            message = 'Product quantity updated in cart'
        else:
            # Add new item to cart
            cart_data = {
                'product_id': product_id,
                'quantity': quantity,
                'added_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            cart_ref.set(cart_data)
            message = 'Product added to cart'

        return JsonResponse({'message': message, 'product_id': product_id, 'quantity': cart_ref.get().to_dict().get('quantity')}, status=200)

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
                cart.append({
                    'item_id': item_doc.id, # This is the product_id in the cart subcollection
                    'product_id': product_id,
                    'name': product_data.get('name'),
                    'price': product_data.get('price'),
                    'image_url': product_data.get('image_url'), # Assuming you have an image_url field
                    'quantity': item_data.get('quantity'),
                    'added_at': item_data.get('added_at')
                })
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
def remove_from_cart(request, item_id): # item_id here is the product_id in the cart
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        cart_item_ref = db.collection('users').document(user_id).collection('cart').document(item_id)
        
        if cart_item_ref.get().exists:
            cart_item_ref.delete()
            return JsonResponse({'message': 'Item removed from cart successfully', 'item_id': item_id}, status=200)
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

        # Check if product exists
        product_doc = db.collection('products').document(product_id).get()
        if not product_doc.exists:
            return JsonResponse({'error': 'Product not found'}, status=404)

        wishlist_ref = db.collection('users').document(user_id).collection('wishlist').document(product_id)
        
        if wishlist_ref.get().exists:
            return JsonResponse({'message': 'Product already in wishlist', 'product_id': product_id}, status=200)
        else:
            wishlist_data = {
                'product_id': product_id,
                'added_at': firestore.SERVER_TIMESTAMP
            }
            wishlist_ref.set(wishlist_data)
            return JsonResponse({'message': 'Product added to wishlist', 'product_id': product_id}, status=201)

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
                wishlist.append({
                    'item_id': item_doc.id, # This is the product_id in the wishlist subcollection
                    'product_id': product_id,
                    'name': product_data.get('name'),
                    'price': product_data.get('price'),
                    'image_url': product_data.get('image_url'), # Assuming image_url field
                    'added_at': item_data.get('added_at')
                })
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
def remove_from_wishlist(request, item_id): # item_id here is the product_id in the wishlist
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id
        wishlist_item_ref = db.collection('users').document(user_id).collection('wishlist').document(item_id)
        
        if wishlist_item_ref.get().exists:
            wishlist_item_ref.delete()
            return JsonResponse({'message': 'Item removed from wishlist successfully', 'item_id': item_id}, status=200)
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
        amount_in_paise = data.get('amount') # Amount should be in paise
        currency = data.get('currency', 'INR')
        product_ids = data.get('product_ids') # List of product_ids in the cart being ordered
        address_id = data.get('address_id') # ID of the selected shipping address

        if not amount_in_paise or not product_ids or not address_id:
            return JsonResponse({'error': 'Amount, product_ids, and address_id are required'}, status=400)

        try:
            amount_in_paise = int(amount_in_paise)
            if amount_in_paise <= 0:
                 return JsonResponse({'error': 'Amount must be greater than 0'}, status=400)
        except ValueError:
            return JsonResponse({'error': 'Invalid amount format'}, status=400)

        # Initialize Razorpay client
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        # Create Razorpay order
        order_payload = {
            'amount': amount_in_paise,
            'currency': currency,
            'receipt': f'receipt_user_{user_id}_{firestore.SERVER_TIMESTAMP}', # Unique receipt ID
            'payment_capture': 1 # Auto capture payment
        }
        razorpay_order = client.order.create(data=order_payload)

        # Store preliminary order details in Firestore (e.g., with 'pending_payment' status)
        # This helps in tracking orders even if payment fails or is abandoned.
        order_ref = db.collection('users').document(user_id).collection('orders').document()
        preliminary_order_data = {
            'razorpay_order_id': razorpay_order['id'],
            'user_id': user_id,
            'product_ids': product_ids, # Store product IDs for now
            'address_id': address_id,
            'total_amount': amount_in_paise / 100, # Store amount in rupees
            'currency': currency,
            'status': 'pending_payment',
            'created_at': firestore.SERVER_TIMESTAMP,
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

        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_signature = data.get('razorpay_signature')
        app_order_id = data.get('app_order_id') # Your application's order ID

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, app_order_id]):
            return JsonResponse({'error': 'Missing Razorpay payment details or app_order_id'}, status=400)

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
            payment_details = client.payment.fetch(razorpay_payment_id)
            
            # Get product details and calculate final order items
            product_ids = order_data.get('product_ids', [])
            order_items = []
            total_calculated_amount = 0

            # Start a Firestore transaction or batch write for atomicity
            batch = db.batch()

            for product_id in product_ids:
                product_ref = db.collection('products').document(product_id)
                product_doc = product_ref.get()
                if product_doc.exists:
                    product_data = product_doc.to_dict()
                    
                    # Get quantity from user's cart for this product
                    cart_item_ref = db.collection('users').document(user_id).collection('cart').document(product_id)
                    cart_item_doc = cart_item_ref.get()
                    quantity = 1 # Default quantity
                    if cart_item_doc.exists:
                        quantity = cart_item_doc.to_dict().get('quantity', 1)
                    
                    item_price = product_data.get('price', 0)
                    order_items.append({
                        'product_id': product_id,
                        'name': product_data.get('name'),
                        'quantity': quantity,
                        'price_at_purchase': item_price, # Price at the time of order
                        'total_item_price': item_price * quantity
                    })
                    total_calculated_amount += item_price * quantity

                    # Decrease product stock
                    current_stock = product_data.get('stock', 0)
                    new_stock = current_stock - quantity
                    if new_stock < 0:
                        # Log a warning or handle insufficient stock post-payment as per business logic
                        # For example, you might allow backorders or flag the order for manual review.
                        print(f"Warning: Stock for product {product_id} has gone negative ({new_stock}) after order {app_order_id}.")
                        # Potentially set new_stock to 0 if negative stock is not allowed and it's a critical issue.
                        # new_stock = 0 # Uncomment if you want to prevent negative stock values explicitly here
                    
                    batch.update(product_ref, {'stock': new_stock})
                    
                    # Clear the item from the cart after successful order
                    if cart_item_doc.exists:
                        batch.delete(cart_item_ref)

            # Verify total amount (optional but recommended)
            # Note: Razorpay amount is in paise.
            if order_data.get('total_amount') != (payment_details.get('amount') / 100):
                # Log discrepancy, but might proceed if signature is verified
                print(f"Warning: Amount mismatch. Stored: {order_data.get('total_amount')}, Razorpay: {payment_details.get('amount') / 100}")


            # Update order in Firestore
            final_order_update = {
                'status': 'payment_successful', # Or 'processing', 'confirmed' etc.
                'payment_details': {
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature,
                    'method': payment_details.get('method'),
                    'status': payment_details.get('status'), # Should be 'captured'
                    'captured_at': firestore.SERVER_TIMESTAMP, # Or use payment_details.get('created_at')
                },
                'order_items': order_items,
                'total_amount_calculated': total_calculated_amount, # Store the server-calculated total
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            batch.update(order_doc_ref, final_order_update)
            
            # Commit the batch
            batch.commit()

            return JsonResponse({
                'message': 'Payment verified successfully and order placed.',
                'app_order_id': app_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'order_status': final_order_update['status']
            }, status=200)
        else:
            # Payment verification failed
            order_doc_ref.update({
                'status': 'payment_failed',
                'payment_details': {
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature,
                    'error_message': 'Signature verification failed'
                },
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            return JsonResponse({'error': 'Payment verification failed. Signature mismatch.'}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except razorpay.errors.SignatureVerificationError as sve:
        # Also update order status in case of this specific error
        try:
            order_doc_ref = db.collection('users').document(user_id).collection('orders').document(app_order_id)
            if order_doc_ref.get().exists:
                 order_doc_ref.update({
                    'status': 'payment_failed',
                    'payment_details': {
                        'razorpay_payment_id': data.get('razorpay_payment_id'),
                        'error_message': 'Signature verification failed (Razorpay lib error)'
                    },
                    'updated_at': firestore.SERVER_TIMESTAMP
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
        orders_ref = db.collection('users').document(user_id).collection('orders').order_by('created_at', direction=firestore.Query.DESCENDING).stream()

        orders_list = []
        for order_doc in orders_ref:
            order_data = order_doc.to_dict()
            orders_list.append({
                'order_id': order_doc.id,
                'status': order_data.get('status'),
                'total_amount': order_data.get('total_amount'),
                'currency': order_data.get('currency'),
                'created_at': order_data.get('created_at'),
                'item_count': len(order_data.get('order_items', []))
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


        return JsonResponse({'order_details': order_data}, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Error fetching order details: {str(e)}'}, status=500)

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
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
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
        addresses_stream = db.collection('users').document(user_id).collection('addresses').order_by('is_default', direction=firestore.Query.DESCENDING).stream()
        
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

        update_payload['updated_at'] = firestore.SERVER_TIMESTAMP
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
        batch.update(target_address_ref, {'is_default': True, 'updated_at': firestore.SERVER_TIMESTAMP})
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
            update_payload['updated_at'] = firestore.SERVER_TIMESTAMP
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

