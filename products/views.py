from django.shortcuts import render
from django.http import JsonResponse
# Remove import of Product model as we're using Firestore now
# from .models import Product
import csv
# Remove Django ORM specific imports
# from django.db.models import Q
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
    try:
        # Query Firestore for products with matching category
        products_ref = db.collection('products').where('category', '==', category).stream()
        
        # Convert to list of dictionaries
        products_list = []
        for doc in products_ref:
            product_data = doc.to_dict()
            product_data['id'] = doc.id
            products_list.append(product_data)
            
        return JsonResponse({'products': products_list})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f"Error fetching products by category: {str(e)}"}, status=500)

# Search and filter products
def search_and_filter_products(request):
    print("Called search_and_filter_products")
    try:
        query = request.GET.get('query', '')
        brand = request.GET.get('brand', '')
        min_price = float(request.GET.get('min_price', 0))
        max_price = float(request.GET.get('max_price', 1000000))
        
        products_ref = db.collection('products')
        products_ref = products_ref.where('price', '>=', min_price).where('price', '<=', max_price)
        if brand:
            products_ref = products_ref.where('brand', '==', brand)

        product_docs = products_ref.stream()

        products_list = []
        for doc in product_docs:
            product_data = doc.to_dict()
            product_data['id'] = doc.id
            
            if query:
                name = product_data.get('name', '').lower()
                description = product_data.get('description', '').lower()
                query_lower = query.lower()
                
                if query_lower in name or query_lower in description:
                    products_list.append(product_data)
            else:
                products_list.append(product_data)
        
        return JsonResponse({'products': products_list})
    
    except ValueError as e:
        # Handle price conversion errors
        return JsonResponse({'status': 'error', 'message': f"Invalid price format: {str(e)}"}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f"Error searching products: {str(e)}"}, status=500)

# Fetch product details
def fetch_product_details(request, product_id):
    try:
        # Get the product document from Firestore
        product_doc = db.collection('products').document(product_id).get()
        
        if not product_doc.exists:
            return JsonResponse({'error': 'Product not found'}, status=404)
        
        # Convert the document to a dictionary
        product_data = product_doc.to_dict()
        product_data['id'] = product_doc.id  # Add the document ID
        
        # Check if reviews are stored as a subcollection
        reviews = []
        reviews_ref = db.collection('products').document(product_id).collection('reviews').stream()
        
        # If the reviews subcollection exists, process it
        for review_doc in reviews_ref:
            review_data = review_doc.to_dict()
            review_data['id'] = review_doc.id
            reviews.append(review_data)
        
        # If no reviews found in subcollection, check if they're embedded in the product document
        if not reviews and 'reviews' in product_data and isinstance(product_data['reviews'], list):
            reviews = product_data['reviews']
        
        # Add reviews to product data (overwrite if embedded, add if from subcollection)
        product_data['reviews'] = reviews
        
        return JsonResponse({'product': product_data})
    
    except Exception as e:
        return JsonResponse({'error': f'Error fetching product: {str(e)}'}, status=500)

# Fetch all products
@csrf_exempt
def fetch_all_products(request):
    try:
        # Get all documents from the products collection
        products_ref = db.collection('products').stream()
        
        # Convert document snapshots to a list of dictionaries
        products_list = []
        for doc in products_ref:
            product_data = doc.to_dict()
            product_data['id'] = doc.id  # Add the document ID as a field
            products_list.append(product_data)
            
        return JsonResponse({'products': products_list})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# Fetch product categories
@csrf_exempt
def fetch_categories(request):
    try:
        # Get all products from Firestore
        products_ref = db.collection('products').stream()
        
        # Extract unique categories
        categories = set()
        for doc in products_ref:
            product_data = doc.to_dict()
            if 'category' in product_data and product_data['category']:
                categories.add(product_data['category'])
                
        return JsonResponse({'categories': list(categories)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f"Error fetching categories: {str(e)}"}, status=500)

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