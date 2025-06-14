from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from firebase_admin import firestore
from shop_users.utils import user_required
import json
from datetime import datetime

# Get Firebase client
db = firestore.client()

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
                
                cart_item = {
                    'item_id': item_doc.id,  # This is the cart item ID (product_id + variant_id)
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'name': product_data.get('name', 'Unknown Product'),
                    'price': price,
                    'image': image_url,
                    'image_url': image_url,
                    'quantity': item_data.get('quantity', 1),
                    'stock': variant_data.get('stock') if variant_data else product_data.get('stock', 0),
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
                    'quantity': item_data.get('quantity', 1),
                    'error': 'Product details could not be fetched.'
                })

        return JsonResponse({'cart': cart}, status=200)

    except Exception as e:
        return JsonResponse({'error': f'Error getting cart: {str(e)}'}, status=500)

@user_required
@csrf_exempt
def remove_from_cart(request, item_id):
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
def remove_from_wishlist(request, item_id):
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
