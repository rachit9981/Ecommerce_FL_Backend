from django.shortcuts import render
from django.http import JsonResponse
from .models import Product
import csv
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers import serialize

# Create your views here.

def insert_products_from_csv(request):
    file_path = 'c:/Users/Priyanshu Dayal/Desktop/Project/Ecommerce_FL_Backend/products/products.csv'
    with open(file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            try:
                price = float(row['Price'].replace('₹', '').replace(',', '')) if row['Price'] else 0.0
                offer_price = float(row['Offer Price'].replace('₹', '').replace(',', '')) if row['Offer Price'] else None
                discount = (
                    f"{round((1 - offer_price / price) * 100, 2)}%"
                    if offer_price and price > 0
                    else None
                )
                stock = int(row['Stock']) if row['Stock'] else 0
            except ValueError as e:
                return JsonResponse({'status': 'error', 'message': f"Invalid data in CSV: {e}"})

            product = Product(
                name=row['Model Name'],
                price=price,
                discount_price=offer_price,
                discount=discount,
                rating=4.5,  # Default rating as not provided in CSV
                reviews=128,  # Default reviews as not provided in CSV
                stock=stock,
                category=row['Category'] or 'Unknown',
                brand=row['Brand'] or 'Unknown',
                description=row['Description'] or '',
                images=[row['Product Image URL']] if row['Product Image URL'] else [],
                features=[],  # Features not provided in CSV
                specifications={},  # Specifications not provided in CSV
            )
            product.save()
    return JsonResponse({'status': 'success', 'message': 'Products inserted successfully'})

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
