from django.shortcuts import render
from django.http import JsonResponse
from .models import Product
import csv
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers import serialize
from anand_mobiles.settings import db # Import the Firestore client
import json # Import json for parsing specifications

# Create your views here.

@csrf_exempt
def insert_products_from_csv(request):
    # Path to the JSON file
    file_path = 'c:/Users/Anubhav Choubey/Documents/New_Freelance_Ecommerce_Work/Ecommerce_FL_Backend/products.json'
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            products_data = json.load(f)
    except FileNotFoundError:
        return JsonResponse({'status': 'error', 'message': f"JSON file not found at {file_path}"}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Error decoding JSON file'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f"An error occurred: {str(e)}"}, status=500)
    
    if not isinstance(products_data, list):
        return JsonResponse({'status': 'error', 'message': 'JSON data should be a list of products'}, status=400)
    
    success_count = 0
    error_count = 0
    errors = []
    
    # Add batch processing for better performance
    batch = db.batch()
    batch_size = 0
    batch_limit = 500  # Firestore batch limit is 500
    
    for product in products_data:
        try:
            # Create a new document reference
            doc_ref = db.collection('products').document()
            
            # Add the product data to the batch
            batch.set(doc_ref, product)
            batch_size += 1
            
            # If we've reached the batch limit, commit and start a new batch
            if batch_size >= batch_limit:
                batch.commit()
                batch = db.batch()
                batch_size = 0
            
            success_count += 1
        except Exception as e:
            error_count += 1
            errors.append(f"Error adding product '{product.get('name', 'Unknown')}': {str(e)}")
    
    # Commit any remaining products in the batch
    if batch_size > 0:
        batch.commit()
    
    if error_count > 0:
        return JsonResponse({
            'status': 'partial_success',
            'message': f'Successfully added {success_count} products to Firebase. Failed to add {error_count} products.',
            'errors': errors
        }, status=207)  # 207 Multi-Status
    
    return JsonResponse({'status': 'success', 'message': f'Successfully added all {success_count} products to Firebase Firestore.'})

# Fetch products by category
def fetch_products_by_category(request, category):
    products = Product.objects.filter(category__iexact=category)
    return JsonResponse({'products': list(products.values())})

# Search and filter products
def search_and_filter_products(request):
    query = request.GET.get('query', '')
    brand = request.GET.get('brand', '')
    min_price = request.GET.get('min_price', 0)
    max_price = request.GET.get('max_price', 1000000)

    filters = Q(name__icontains=query) | Q(description__icontains=query)
    if brand:
        filters &= Q(brand__iexact=brand)
    filters &= Q(price__gte=min_price, price__lte=max_price)

    products = Product.objects.filter(filters)
    return JsonResponse({'products': list(products.values())})

# Fetch product details
def fetch_product_details(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        reviews = product.reviews.all()
        return JsonResponse({
            'product': {
                'name': product.name,
                'price': product.price,
                'discount_price': product.discount_price,
                'discount': product.discount,
                'rating': product.rating,
                'reviews': list(reviews.values('user_name', 'rating', 'comment', 'date')),
                'stock': product.stock,
                'category': product.category,
                'brand': product.brand,
                'description': product.description,
                'images': product.images,
                'features': product.features,
                'specifications': product.specifications,
            }
        })
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)

# Fetch all products
@csrf_exempt
def fetch_all_products(request):
    products = Product.objects.all()
    return JsonResponse({'products': list(products.values())})

# Fetch product categories
@csrf_exempt
def fetch_categories(request):
    categories = Product.objects.values_list('category', flat=True).distinct()
    return JsonResponse({'categories': list(categories)})

@csrf_exempt
def add_product(request):
    if request.method == 'POST':
        data = request.POST

        try:
            product_data = {
                'name': data.get('name'),
                'price': float(data.get('price')),
                'discount_price': float(data.get('discount_price')) if data.get('discount_price') else None,
                'discount': data.get('discount', None),
                'rating': float(data.get('rating', 0.0)), # Default to 0.0 if not provided
                # 'reviews' field might need clarification: is it a count or a list of review objects?
                'reviews_count': int(data.get('reviews', 0)), # Renamed for clarity if it's a count
                'stock': int(data.get('stock')),
                'category': data.get('category'),
                'brand': data.get('brand'),
                'description': data.get('description', ''),
                'images': data.getlist('images') if hasattr(data, 'getlist') else data.get('images', []), # Handle both form-data and JSON
                'features': data.getlist('features') if hasattr(data, 'getlist') else data.get('features', []), # Handle both form-data and JSON
            }

            specifications_data = data.get('specifications', '{}')
            if isinstance(specifications_data, str):
                try:
                    product_data['specifications'] = json.loads(specifications_data)
                except json.JSONDecodeError:
                    product_data['specifications'] = specifications_data if specifications_data else {}
            else:
                product_data['specifications'] = specifications_data # Assumes it's already a dict if not a string

            required_fields = ['name', 'price', 'stock', 'category', 'brand']
            missing_fields = [field for field in required_fields if not product_data.get(field)]
            if missing_fields:
                return JsonResponse({'status': 'error', 'message': f"Missing required fields: {', '.join(missing_fields)}"}, status=400)

            doc_ref = db.collection('products').add(product_data)
            return JsonResponse({'status': 'success', 'message': 'Product added successfully to Firebase', 'product_id': doc_ref[1].id})
        except ValueError as e:
            return JsonResponse({'status': 'error', 'message': f"Invalid data format: {str(e)}"}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)