from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ShopAdmin

# Create your views here.
@csrf_exempt
def admin_register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if username and password:
            try:
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
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            shop_admin = ShopAdmin.objects.get(username=username, password=password)
            return JsonResponse({'message': 'Login successful!', 'admin_id': shop_admin.id}, status=200)
        except ShopAdmin.DoesNotExist:
            return JsonResponse({'error': 'Invalid username or password!'}, status=401)
    return JsonResponse({'error': 'Invalid request method!'}, status=405)