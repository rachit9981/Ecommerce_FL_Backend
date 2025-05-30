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
            'last_updated_by_admin_at': firestore.SERVER_TIMESTAMP # Uses server-side timestamp
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
    """Add a new product"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        data = json.loads(request.body)
        # Basic validation (you might want to add more comprehensive validation)
        required_fields = ['name', 'brand', 'category', 'price', 'stock', 'description', 'images']
        for field in required_fields:
            if field not in data:
                return JsonResponse({'error': f'Missing required field: {field}'}, status=400)

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
    """Edit an existing product by its ID"""
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
@admin_required
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
    """Get all active banners for public display"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        # Get only active banners from Firebase
        banners_ref = db.collection('banners').where('active', '==', True)
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