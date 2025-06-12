from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ShopAdmin
from django.contrib.auth.hashers import make_password, check_password
import json
import jwt
from .utils import admin_required, upload_image_to_cloudinary_util
from anand_mobiles.settings import SECRET_KEY
from firebase_admin import firestore
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Get Firebase client
db = firestore.client()

# Create your views here.
@csrf_exempt
def admin_register(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        secret= data.get('secret')
        if username and password and secret:
            try:
                # Check if the secret is correct
                if secret != SECRET_KEY:
                    return JsonResponse({'error': 'Invalid secret key!'}, status=403)
                
                # Check if the username already exists using Firebase
                if ShopAdmin.exists_by_username(username):
                    return JsonResponse({'error': 'Username already exists!'}, status=400)
                
                # hash the password
                hashed_password = make_password(password)
                
                # Create a new shop admin using Firebase
                admin = ShopAdmin.create(username=username, password=hashed_password)
                return JsonResponse({'message': 'Shop admin registered successfully!', 'admin_id': admin.admin_id}, status=201)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)
        else:
            return JsonResponse({'error': 'Username and password are required!'}, status=400)
    return JsonResponse({'error': 'Invalid request method!'}, status=405)

@csrf_exempt
def admin_login(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        # Get the username and password from the request
        username = data.get('username')
        password = data.get('password')
        try:
            # Get shop admin from Firebase
            shop_admin = ShopAdmin.get_by_username(username)
            if shop_admin and check_password(password, shop_admin.password):
                #sign the token with username
                token = jwt.encode({'username': username, 'admin_id': shop_admin.admin_id}, SECRET_KEY, algorithm='HS256')
                return JsonResponse({'message': 'Login successful!', 'admin_id': shop_admin.admin_id, 'token': token}, status=200)
            else:
                return JsonResponse({'error': 'Invalid username or password!'}, status=401)
        except Exception as e:
            return JsonResponse({'error': 'Invalid username or password!'}, status=401)
    return JsonResponse({'error': 'Invalid request method!'}, status=405)

# get all users 
@csrf_exempt
@admin_required
def get_all_users(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Get users from Firebase
        users_ref = db.collection('users')
        docs = users_ref.stream()
        users = []
        for doc in docs:
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            users.append(user_data)
        return JsonResponse({'users': users}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


    
# get all products
@csrf_exempt
@admin_required
def get_all_products(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Get products from Firebase
        products_ref = db.collection('products')
        docs = products_ref.stream()
        products = []
        for doc in docs:
            product_data = doc.to_dict()
            product_data['id'] = doc.id
            products.append(product_data)
        return JsonResponse({'products': products}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# get all orders
@csrf_exempt
@admin_required
def get_all_orders(request): # Removed user_id from parameters
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        all_orders = []
        users_ref = db.collection('users').stream() # Get all users

        for user_doc in users_ref:
            user_id = user_doc.id
            # Get orders for each user
            orders_ref = db.collection('users').document(user_id).collection('orders').stream()
            for order_doc in orders_ref:
                order_data = order_doc.to_dict()
                order_data['order_id'] = order_doc.id # Use 'order_id' for clarity
                order_data['user_id'] = user_id # Add user_id to identify the owner of the order
                # Optionally, you might want to add more user details here if needed
                # e.g., user_data = user_doc.to_dict()
                # order_data['user_email'] = user_data.get('email')
                all_orders.append(order_data)
        
        return JsonResponse({'orders': all_orders}, status=200)
    except Exception as e:
        return JsonResponse({'error': f'Error fetching all orders: {str(e)}'}, status=500)

# Add timestamp for last update by admin
from datetime import datetime
        
@csrf_exempt
@admin_required
def edit_order(request, user_id, order_id):
    """Edit an existing order by its ID for a specific user (e.g., update status, items - carefully)"""
    if request.method not in ['PUT', 'PATCH']:
        return JsonResponse({'error': 'Invalid request method! Use PUT or PATCH.'}, status=405)
    try:
        data = json.loads(request.body)
        # Ensure user_id is present, though it's from the URL
        if not user_id:
            return JsonResponse({'error': 'User ID is required in the path.'}, status=400)

        order_ref = db.collection('users').document(user_id).collection('orders').document(order_id)
        
        if not order_ref.get().exists:
            return JsonResponse({'error': f'Order not found for user {user_id}!'}, status=404)

        
        data['last_updated_by_admin_at'] = datetime.now()
        
        # Update order in Firebase
        order_ref.update(data)
        return JsonResponse({'message': 'Order updated successfully!', 'user_id': user_id, 'order_id': order_id}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def assign_order_to_delivery_partner(request, user_id, order_id):
    """Assign an order for a specific user to a delivery partner"""
    if request.method != 'POST': 
        return JsonResponse({'error': 'Invalid request method! Use POST.'}, status=405)
    try:
        data = json.loads(request.body)
        print('data:', data)  # Debugging line to check incoming data
        partner_id = data.get('partner_id')

        if not partner_id:
            return JsonResponse({'error': 'Partner ID is required.'}, status=400)
        
        # Ensure user_id is present
        if not user_id:
            return JsonResponse({'error': 'User ID is required in the path.'}, status=400)

        order_ref = db.collection('users').document(user_id).collection('orders').document(order_id)
        order_doc = order_ref.get()

        if not order_doc.exists:
            return JsonResponse({'error': f'Order not found for user {user_id}!'}, status=404)

        # Check if partner exists and is verified
        partner_ref = db.collection('delivery_partners').document(partner_id)
        partner_doc = partner_ref.get()
        if not partner_doc.exists:
            return JsonResponse({'error': 'Delivery partner not found.'}, status=404)
        
        partner_data = partner_doc.to_dict()
        if not partner_data.get('is_verified'):
            return JsonResponse({'error': 'Delivery partner not verified.'}, status=404)
        
        partner_name = partner_data.get('name', 'N/A') # Get partner name, default to N/A if not found

        update_data = {
            'assigned_partner_id': partner_id,
            'assigned_partner_name': partner_name, # Add partner name to the order
            'assigned_at': datetime.now(),  # Uses client-side timestamp
            'last_updated_by_admin_at': datetime.now() # Uses server-side timestamp
        }
        
        order_data = order_doc.to_dict()
        # Ensure status_update_history is initialized if it doesn't exist
        tracking_info = order_data.get('tracking_info', {})
        status_update_history = tracking_info.get('status_history', [])
        
        status_update_history.append({
            'timestamp': datetime.now(),  # Use client-side timestamp for history entries
            'updated_by': 'admin',
            'admin_id': request.admin_payload.get('admin_id'), 
            'assigned_partner_id': partner_id,
            'assigned_partner_name': partner_name, # Add partner name to history
            'description': f'Order assigned to delivery partner {partner_name} (ID: {partner_id}) by admin.'
        })
        
        # Ensure tracking_info structure is correctly updated
        if 'tracking_info' not in order_data:
            order_data['tracking_info'] = {}
        order_data['tracking_info']['status_history'] = status_update_history
        
        # Merge update_data with the modified tracking_info
        update_data['tracking_info'] = order_data['tracking_info']
        
        order_ref.update(update_data)
        return JsonResponse({'message': f'Order {order_id} for user {user_id} assigned to partner {partner_name} (ID: {partner_id}) successfully!'}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Additional admin functions using Firebase

@csrf_exempt
@admin_required
def get_all_admins(request):
    """Get all shop admins"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        admins = ShopAdmin.get_all()
        admin_data = []
        for admin in admins:
            # Don't include password in response
            admin_dict = admin.to_dict()
            admin_dict.pop('password', None)
            admin_data.append(admin_dict)
        return JsonResponse({'admins': admin_data}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def delete_admin(request, admin_id):
    """Delete a shop admin"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Delete admin from Firebase
        db.collection(ShopAdmin.COLLECTION_NAME).document(admin_id).delete()
        return JsonResponse({'message': 'Admin deleted successfully!'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


## Views for product management

@csrf_exempt
@admin_required
def delete_product(request, product_id):
    """Delete a product by its ID"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Delete product from Firebase
        product_ref = db.collection('products').document(product_id)
        if product_ref.get().exists:
            product_ref.delete()
            return JsonResponse({'message': 'Product deleted successfully!'}, status=200)
        else:
            return JsonResponse({'error': 'Product not found!'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@csrf_exempt
@admin_required
def toggle_featured_product(request, product_id):
    """Toggle the 'featured' field of a product by its ID"""
    if request.method != 'PATCH':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Get the product reference from Firebase
        product_ref = db.collection('products').document(product_id)
        product = product_ref.get()

        if not product.exists:
            return JsonResponse({'error': 'Product not found!'}, status=404)

        # Get the current product data
        product_data = product.to_dict()

        # Toggle the 'featured' field
        current_featured = product_data.get('featured', False)
        new_featured = not current_featured

        # Update the product in Firebase
        product_ref.update({'featured': new_featured})

        return JsonResponse({'message': 'Product featured status updated!', 'featured': new_featured}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def add_product(request):
    """Add a new product
    
    Accepts the following fields in the request body:
    - name (required): Product name
    - brand (required): Brand name
    - category (required): Product category
    - price (required): Original price
    - stock (required): Stock quantity
    - description (required): Product description
    - images (required): Array of image URLs
    - discount_price (optional): Discounted price
    - discount (optional): Discount percentage
    - specifications (optional): Object containing specification key-value pairs
    - attributes (optional): Object containing attribute key-value pairs
    - features (optional): Array of product features
    - variant (optional): Object containing product variants (colors, storage, etc.)
    - featured (optional): Boolean indicating if product is featured
    - rating (optional): Product rating
    - reviews (optional): Number of reviews
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        data = json.loads(request.body)
        # Basic validation (you might want to add more comprehensive validation)
        required_fields = ['name', 'brand', 'category', 'price', 'stock', 'description', 'images']
        for field in required_fields:
            if field not in data:
                return JsonResponse({'error': f'Missing required field: {field}'}, status=400)

        # Initialize optional fields if not provided
        if 'attributes' not in data:
            data['attributes'] = {}

        # Add product to Firebase
        # The document ID will be auto-generated by Firestore
        product_ref, doc_ref = db.collection('products').add(data)
        return JsonResponse({'message': 'Product added successfully!', 'product_id': doc_ref.id}, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def edit_product(request, product_id):
    """Edit an existing product by its ID
    
    Accepts any of the following fields in the request body:
    - name: Product name
    - brand: Brand name
    - category: Product category
    - price: Original price
    - discount_price: Discounted price
    - discount: Discount percentage
    - stock: Stock quantity
    - description: Product description
    - images: Array of image URLs
    - specifications: Object containing specification key-value pairs
    - attributes: Object containing attribute key-value pairs
    - features: Array of product features
    - variant: Object containing product variants (colors, storage, etc.)
    - featured: Boolean indicating if product is featured
    """
    if request.method not in ['PUT', 'PATCH']:
        return JsonResponse({'error': 'Invalid request method! Use PUT or PATCH.'}, status=405)
    try:
        data = json.loads(request.body)
        product_ref = db.collection('products').document(product_id)
        
        if not product_ref.get().exists:
            return JsonResponse({'error': 'Product not found!'}, status=404)

        # Update product in Firebase
        product_ref.update(data)
        return JsonResponse({'message': 'Product updated successfully!', 'product_id': product_id}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# User management functions
@csrf_exempt
@admin_required
def ban_user(request, user_id):
    """Toggle the 'is_banned' field of a user by their ID"""
    if request.method != 'PATCH':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Get the user reference from Firebase
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return JsonResponse({'error': 'User not found!'}, status=404)

        # Get the current user data
        user_data = user_doc.to_dict()

        # Toggle the 'is_banned' field, default to False if not present
        current_is_banned = user_data.get('is_banned', False)
        new_is_banned = not current_is_banned

        # Update the user in Firebase
        user_ref.update({'is_banned': new_is_banned})

        return JsonResponse({'message': f'User ban status updated successfully!', 'user_id': user_id, 'is_banned': new_is_banned}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def get_user_by_id(request, user_id):
    """Get a user by their ID"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_data['id'] = user_doc.id  # Add the document ID to the response
            return JsonResponse({'user': user_data}, status=200)
        else:
            return JsonResponse({'error': 'User not found!'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

## Views for banner management

@csrf_exempt
def get_all_banners(request):
    """Get all banners"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Get banners from Firebase
        banners_ref = db.collection('banners')
        docs = banners_ref.stream()
        banners = []
        for doc in docs:
            banner_data = doc.to_dict()
            banner_data['id'] = doc.id
            banners.append(banner_data)
        
        # Sort by created_at if available, otherwise by position
        banners.sort(key=lambda x: x.get('created_at', x.get('position', 'hero')))
        return JsonResponse({'banners': banners}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def add_banner(request):
    """Add a new banner"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Handle multipart/form-data for file uploads
        data = request.POST.dict()  # Get form data
        image_file = request.FILES.get('image_file')  # Get uploaded file
        
        # Basic validation
        required_fields = ['title', 'position']
        for field in required_fields:
            if field not in data:
                return JsonResponse({'error': f'Missing required field: {field}'}, status=400)
        
        if not image_file:
            return JsonResponse({'error': 'Image file is required'}, status=400)
        
        # Upload image to Cloudinary
        image_url = upload_image_to_cloudinary_util(image_file, folder_name="banners")
        if not image_url:
            return JsonResponse({'error': 'Failed to upload image'}, status=500)
        
        # Prepare banner data
        banner_data = {
            'title': data.get('title'),
            'subtitle': data.get('subtitle', ''),
            'description': data.get('description', ''),
            'image': image_url,  # Use uploaded image URL
            'link': data.get('link', ''),
            'position': data.get('position'),
            'tag': data.get('tag', ''),
            'cta': data.get('cta', ''),
            'backgroundColor': data.get('backgroundColor', '#ffffff'),
            'active': data.get('active', 'true').lower() == 'true',
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        # Add banner to Firebase
        doc_ref = db.collection('banners').add(banner_data)[1]
        return JsonResponse({'message': 'Banner added successfully!', 'banner_id': doc_ref.id}, status=201)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def edit_banner(request, banner_id):
    """Edit an existing banner by its ID"""
    if request.method not in ['PUT', 'PATCH']:
        return JsonResponse({'error': 'Invalid request method! Use PUT or PATCH.'}, status=405)
    try:
        banner_ref = db.collection('banners').document(banner_id)
        
        if not banner_ref.get().exists:
            return JsonResponse({'error': 'Banner not found!'}, status=404)

        # Check if request is multipart/form-data or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle form data
            data = request.POST.dict()
            image_file = request.FILES.get('image_file')
            
            # If there's an image file, upload it to Cloudinary
            if image_file:
                image_url = upload_image_to_cloudinary_util(image_file, folder_name="banners")
                if not image_url:
                    return JsonResponse({'error': 'Failed to upload image'}, status=500)
                data['image'] = image_url
        else:
            # Handle JSON data
            data = json.loads(request.body)

        # Add update timestamp
        data['updated_at'] = datetime.now()
        
        # Handle boolean fields properly
        if 'active' in data and isinstance(data['active'], str):
            data['active'] = data['active'].lower() == 'true'
            
        # Update banner in Firebase
        banner_ref.update(data)
        return JsonResponse({'message': 'Banner updated successfully!', 'banner_id': banner_id}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def delete_banner(request, banner_id):
    """Delete a banner by its ID"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Delete banner from Firebase
        banner_ref = db.collection('banners').document(banner_id)
        if banner_ref.get().exists:
            banner_ref.delete()
            return JsonResponse({'message': 'Banner deleted successfully!'}, status=200)
        else:
            return JsonResponse({'error': 'Banner not found!'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def toggle_banner_active(request, banner_id):
    """Toggle the 'active' field of a banner by its ID"""
    if request.method != 'PATCH':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Get the banner reference from Firebase
        banner_ref = db.collection('banners').document(banner_id)
        banner = banner_ref.get()

        if not banner.exists:
            return JsonResponse({'error': 'Banner not found!'}, status=404)

        # Get the current banner data
        banner_data = banner.to_dict()

        # Toggle the 'active' field
        current_active = banner_data.get('active', True)
        new_active = not current_active

        # Update the banner in Firebase
        banner_ref.update({
            'active': new_active,
            'updated_at': datetime.now()
        })

        return JsonResponse({'message': 'Banner status updated!', 'active': new_active}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def get_public_banners(request):
    """Get all active banners for public display (no authentication required)"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Get only active banners from Firebase
        banners_ref = db.collection('banners').where('is_active', '==', True)
        docs = banners_ref.stream()
        
        banners = []
        for doc in docs:
            banner_data = doc.to_dict()
            banner_data['id'] = doc.id
            banners.append(banner_data)
        
        # Sort by position and created_at
        position_order = {'hero': 0, 'home-middle': 1, 'home-bottom': 2, 'category-top': 3, 'sidebar': 4}
        banners.sort(key=lambda x: (
            position_order.get(x.get('position', 'hero'), 999),
            x.get('created_at', datetime.min)
        ))
        
        return JsonResponse({'banners': banners}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

## Views for review management

@csrf_exempt
@admin_required
def get_all_product_reviews(request):
    """Get all reviews for products that have at least one review with all review details"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        # Get all products from Firebase
        products_ref = db.collection('products').stream()
        
        all_reviews = []
        
        for product_doc in products_ref:
            product_data = product_doc.to_dict()
            product_id = product_doc.id
            
            # Get reviews for this product
            reviews_ref = db.collection('products').document(product_id).collection('reviews').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
            
            product_reviews = []
            for review_doc in reviews_ref:
                review_data = review_doc.to_dict()
                review_data['id'] = review_doc.id
                review_data['product_id'] = product_id
                review_data['product_name'] = product_data.get('name', 'Unknown Product')
                
                # Format the created_at timestamp
                if 'created_at' in review_data and review_data['created_at']:
                    review_data['created_at'] = review_data['created_at'].isoformat()
                
                product_reviews.append(review_data)
            
            # Only include products that have reviews
            if product_reviews:
                all_reviews.extend(product_reviews)
        
        # Sort all reviews by created_at (most recent first)
        all_reviews.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return JsonResponse({
            'reviews': all_reviews,
            'total_count': len(all_reviews)
        }, status=200)
        
    except Exception as e:
        return JsonResponse({'error': f'Error fetching reviews: {str(e)}'}, status=500)

@csrf_exempt
@admin_required
def get_reported_reviews(request):
    """Get all reviews that have been reported by users"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        # Get all products from Firebase
        products_ref = db.collection('products').stream()
        
        reported_reviews = []
        
        for product_doc in products_ref:
            product_data = product_doc.to_dict()
            product_id = product_doc.id
            
            # Get reviews for this product that have been reported
            reviews_ref = db.collection('products').document(product_id).collection('reviews').where('reported_count', '>', 0).order_by('reported_count', direction=firestore.Query.DESCENDING).stream()
            
            for review_doc in reviews_ref:
                review_data = review_doc.to_dict()
                review_data['id'] = review_doc.id
                review_data['product_id'] = product_id
                review_data['product_name'] = product_data.get('name', 'Unknown Product')
                
                # Format the created_at timestamp
                if 'created_at' in review_data and review_data['created_at']:
                    review_data['created_at'] = review_data['created_at'].isoformat()
                
                # Get report details
                reports_ref = db.collection('products').document(product_id).collection('reviews').document(review_doc.id).collection('reports').stream()
                reports = []
                for report_doc in reports_ref:
                    report_data = report_doc.to_dict()
                    report_data['id'] = report_doc.id
                    if 'created_at' in report_data and report_data['created_at']:
                        report_data['created_at'] = report_data['created_at'].isoformat()
                    reports.append(report_data)
                
                review_data['reports'] = reports
                reported_reviews.append(review_data)
        
        # Sort by reported_count (highest first) then by created_at
        reported_reviews.sort(key=lambda x: (x.get('reported_count', 0), x.get('created_at', '')), reverse=True)
        
        return JsonResponse({
            'reported_reviews': reported_reviews,
            'total_count': len(reported_reviews)
        }, status=200)
        
    except Exception as e:
        return JsonResponse({'error': f'Error fetching reported reviews: {str(e)}'}, status=500)

@csrf_exempt
@admin_required
def delete_review(request, product_id, review_id):
    """Delete a review by its ID for a specific product"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        # Check if product exists
        product_doc = db.collection('products').document(product_id).get()
        if not product_doc.exists:
            return JsonResponse({'error': 'Product not found'}, status=404)
        
        # Check if review exists
        review_doc_ref = db.collection('products').document(product_id).collection('reviews').document(review_id)
        review_doc = review_doc_ref.get()
        
        if not review_doc.exists:
            return JsonResponse({'error': 'Review not found'}, status=404)
        
        # Delete all reports in the review's reports subcollection
        reports_ref = review_doc_ref.collection('reports').stream()
        for report_doc in reports_ref:
            report_doc.reference.delete()
        
        # Delete the review document
        review_doc_ref.delete()
        
        # Recalculate product's average rating and review count after deletion
        remaining_reviews_ref = db.collection('products').document(product_id).collection('reviews').stream()
        total_rating = 0
        review_count = 0
        
        for remaining_review_doc in remaining_reviews_ref:
            remaining_review = remaining_review_doc.to_dict()
            total_rating += remaining_review.get('rating', 0)
            review_count += 1
        
        # Update product document with new rating and review count
        if review_count > 0:
            average_rating = round(total_rating / review_count, 2)
        else:
            average_rating = 0
            
        db.collection('products').document(product_id).update({
            'rating': average_rating,
            'reviews_count': review_count
        })
        
        return JsonResponse({
            'message': 'Review deleted successfully',
            'updated_rating': average_rating,
            'total_reviews': review_count
        }, status=200)
        
    except Exception as e:
        return JsonResponse({'error': f'Error deleting review: {str(e)}'}, status=500)




@csrf_exempt
@admin_required
def upload_product_image(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        # Check if image file is provided
        if 'image' not in request.FILES:
            return JsonResponse({
                'error': 'No image file provided',
                'code': 'IMAGE_MISSING'
            }, status=400)
        
        image_file = request.FILES['image']
        
        # Validate file type (optional but recommended)
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if image_file.content_type not in allowed_types:
            return JsonResponse({
                'error': 'Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed.',
                'code': 'INVALID_FILE_TYPE'
            }, status=400)
        # Validate file size (optional - limit to 40MB)
        max_size = 40 * 1024 * 1024  # 40MB in bytes
        if image_file.size > max_size:
            return JsonResponse({
                'error': 'File size too large. Maximum size is 40MB.',
                'code': 'FILE_TOO_LARGE'
            }, status=400)
        
        # Upload to Cloudinary using the utility function
        secure_url = upload_image_to_cloudinary_util(image_file, folder_name="product_images")
        
        if secure_url:
            logger.info(f"Product image uploaded successfully by admin '{request.admin}': {secure_url}")
            return JsonResponse({
                'success': True,
                'image_url': secure_url,
                'message': 'Image uploaded successfully'
            }, status=200)
        else:
            logger.error(f"Failed to upload product image for admin '{request.admin}'")
            return JsonResponse({
                'error': 'Failed to upload image to cloud storage',
                'code': 'UPLOAD_FAILED'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error in upload_product_image for admin '{request.admin}': {str(e)}")
        return JsonResponse({
            'error': 'Internal server error during image upload',
            'code': 'INTERNAL_ERROR'
        }, status=500)

@csrf_exempt
@admin_required
def upload_logo(request):
    """Upload/update shop logo"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        if 'logo' not in request.FILES:
            return JsonResponse({'error': 'No logo file provided'}, status=400)
        
        # Upload logo to Cloudinary
        logo_file = request.FILES['logo']
        print('logo_file:', logo_file)  # Debugging line to check incoming file
        logo_url = upload_image_to_cloudinary_util(logo_file, folder_name="shop_logo")
        
        if not logo_url:
            return JsonResponse({'error': 'Failed to upload logo to Cloudinary'}, status=500)
        
        # Save logo URL in Firebase settings
        settings_ref = db.collection('settings').document('general')
        settings_ref.set({
            'logo_url': logo_url,
            'updated_at': datetime.now(),
            'updated_by': request.admin
        }, merge=True)
        
        return JsonResponse({
            'message': 'Logo uploaded successfully',
            'logo_url': logo_url
        }, status=200)
            
    except Exception as e:
        logger.error(f"Error uploading logo: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def get_logo(request):
    """Get the shop logo URL from settings"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        # Get logo URL from settings in Firebase
        settings_ref = db.collection('settings').document('general')
        settings_doc = settings_ref.get()
        
        if not settings_doc.exists:
            return JsonResponse({'error': 'Settings not found'}, status=404)
            
        settings_data = settings_doc.to_dict()
        logo_url = settings_data.get('logo_url', '')
        
        return JsonResponse({'logo_url': logo_url}, status=200)
        
    except Exception as e:
        logger.error(f"Error fetching logo: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@admin_required
def delete_logo(request):
    """Delete the shop logo"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        # Get the current logo URL from settings
        settings_ref = db.collection('settings').document('general')
        settings_doc = settings_ref.get()
        
        if not settings_doc.exists:
            return JsonResponse({'error': 'Settings not found'}, status=404)
            
        settings_data = settings_doc.to_dict()
        current_logo_url = settings_data.get('logo_url')
        
        # Reset the logo URL in Firebase
        settings_ref.update({
            'logo_url': None,
            'updated_at': datetime.now(),
            'updated_by': request.admin
        })
        
        # Here you could also delete the image from Cloudinary if needed
        # For now, we'll just remove the reference
        
        return JsonResponse({
            'message': 'Logo deleted successfully',
            'previous_url': current_logo_url
        }, status=200)
        
    except Exception as e:
        logger.error(f"Error deleting logo: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

## Views for category management

@csrf_exempt
def get_all_categories(request):
    """Get all product categories"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        categories_ref = db.collection('categories').order_by('name').stream()
        categories = []
        for doc in categories_ref:
            category_data = doc.to_dict()
            category_data['id'] = doc.id
            categories.append(category_data)
        return JsonResponse({'categories': categories}, status=200)
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        return JsonResponse({'error': f'Error fetching categories: {str(e)}'}, status=500)

@csrf_exempt
@admin_required
def add_category(request):
    """Add a new product category"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        data = json.loads(request.body)
        name = data.get('name')
        image_url = data.get('image_url')
        redirect_url = data.get('redirect_url')

        if not name:
            return JsonResponse({'error': 'Category name is required'}, status=400)

        # Add category to Firebase
        category_ref = db.collection('categories').document()
        category_data = {
            'name': name,
            'image_url': image_url,
            'redirect_url': redirect_url,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'order': data.get('order', 0),  # Default order to 0 if not provided
        }
        category_ref.set(category_data)
        category_data['id'] = category_ref.id
        return JsonResponse({'message': 'Category added successfully!', 'category': category_data}, status=201)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error adding category: {str(e)}")
        return JsonResponse({'error': f'Error adding category: {str(e)}'}, status=500)

@csrf_exempt
@admin_required
def edit_category(request, category_id):
    """Edit an existing product category by its ID"""
    if request.method not in ['PUT', 'PATCH']:
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        data = json.loads(request.body)
        category_ref = db.collection('categories').document(category_id)

        if not category_ref.get().exists:
            return JsonResponse({'error': 'Category not found'}, status=404)

        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'image_url' in data:
            update_data['image_url'] = data['image_url']
        if 'redirect_url' in data:
            update_data['redirect_url'] = data['redirect_url']
        if 'order' in data:
            update_data['order'] = data['order']
        
        if not update_data:
            return JsonResponse({'error': 'No fields to update'}, status=400)

        update_data['updated_at'] = datetime.now()
        category_ref.update(update_data)
        
        updated_category = category_ref.get().to_dict()
        updated_category['id'] = category_id
        return JsonResponse({'message': 'Category updated successfully!', 'category': updated_category}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error editing category {category_id}: {str(e)}")
        return JsonResponse({'error': f'Error editing category: {str(e)}'}, status=500)

@csrf_exempt
@admin_required
def upload_category_image(request):
    """Upload an image for a category"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    
    try:
        # Check if image file is provided
        if 'image' not in request.FILES:
            return JsonResponse({
                'error': 'No image file provided',
                'code': 'IMAGE_MISSING'
            }, status=400)
        
        image_file = request.FILES['image']
        
        # Validate file type (optional but recommended)
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if image_file.content_type not in allowed_types:
            return JsonResponse({
                'error': 'Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed.',
                'code': 'INVALID_FILE_TYPE'
            }, status=400)
        
        # Validate file size (optional - limit to 10MB for category images)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if image_file.size > max_size:
            return JsonResponse({
                'error': 'File size too large. Maximum size is 10MB for category images.',
                'code': 'FILE_TOO_LARGE'
            }, status=400)
        
        # Upload to Cloudinary using the utility function
        # You might want a specific folder for category images, e.g., "category_images"
        secure_url = upload_image_to_cloudinary_util(image_file, folder_name="category_images")
        
        if secure_url:
            # Assuming request.admin is set by your admin_required decorator
            admin_identifier = getattr(request, 'admin', 'Unknown Admin') 
            logger.info(f"Category image uploaded successfully by admin '{admin_identifier}': {secure_url}")
            return JsonResponse({
                'success': True,
                'image_url': secure_url,
                'message': 'Image uploaded successfully'
            }, status=200)
        else:
            admin_identifier = getattr(request, 'admin', 'Unknown Admin')
            logger.error(f"Failed to upload category image for admin '{admin_identifier}'")
            return JsonResponse({
                'success': False, # Ensure success is false on failure
                'error': 'Failed to upload image to cloud storage',
                'code': 'UPLOAD_FAILED'
            }, status=500)
            
    except Exception as e:
        admin_identifier = getattr(request, 'admin', 'Unknown Admin')
        logger.error(f"Error in upload_category_image for admin '{admin_identifier}': {str(e)}")
        return JsonResponse({
            'success': False, # Ensure success is false on error
            'error': 'Internal server error during image upload',
            'code': 'INTERNAL_ERROR'
        }, status=500)
