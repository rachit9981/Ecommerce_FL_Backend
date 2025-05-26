from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ShopAdmin
from django.contrib.auth.hashers import make_password, check_password
import json
import jwt
from .utils import admin_required
from anand_mobiles.settings import SECRET_KEY
from shop_users.models import User,UserManager
from products.models import Product,Cart,CartItem,Review,Order,OrderItem,Wishlist

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
                
                # Check if the username already exists
                if ShopAdmin.objects.filter(username=username).exists():
                    return JsonResponse({'error': 'Username already exists!'}, status=400)
                # hash the password
                password = make_password(password)
                # Create a new shop admin
                ShopAdmin.objects.create(username=username, password=password)
                return JsonResponse({'message': 'Shop admin registered successfully!'}, status=201)
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
            shop_admin = ShopAdmin.objects.get(username=username)
            if check_password(password, shop_admin.password):
                #sign the token with username
                token = jwt.encode({'username': username}, SECRET_KEY, algorithm='HS256')
                return JsonResponse({'message': 'Login successful!', 'admin_id': shop_admin.id, 'token': token}, status=200)
            else:
                return JsonResponse({'error': 'Invalid username or password!'}, status=401)
        except ShopAdmin.DoesNotExist:
            return JsonResponse({'error': 'Invalid username or password!'}, status=401)
    return JsonResponse({'error': 'Invalid request method!'}, status=405)

# get all users 
@csrf_exempt
@admin_required
def get_all_users(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        users = User.objects.all()
        user_data = [user.to_json() for user in users]
        return JsonResponse({'users': user_data}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
# get all products
@csrf_exempt
@admin_required
def get_all_products(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        products = Product.objects.all()
        product_data = [ product.to_json() for product in products]
        return JsonResponse({'products': product_data}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# get all orders
@csrf_exempt
def get_all_orders(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method!'}, status=405)
    try:
        orders = Order.objects.all()
        order_data = [order.to_json() for order in orders]
        return JsonResponse({'orders': order_data}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

