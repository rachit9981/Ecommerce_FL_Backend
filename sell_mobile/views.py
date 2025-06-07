from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from anand_mobiles.settings import db  # Import the Firestore client
from google.cloud import firestore  # Import firestore for Query constants
import json
from datetime import datetime
import os
from shop_users.utils import user_required
from pathlib import Path

# Create your views here.

@csrf_exempt
def submit_sell_mobile(request):
    """
    Submit a mobile for selling
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            required_fields = ['user_name', 'phone_number', 'email', 'location', 
                             'mobile_brand', 'mobile_model', 'condition', 'expected_price']
            
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Missing required field: {field}'
                    }, status=400)
            
            data['status'] = 'pending'
            data['created_at'] = datetime.now().isoformat()
            data['updated_at'] = datetime.now().isoformat()
            
            doc_ref = db.collection('sell_mobiles').document()
            doc_ref.set(data)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Mobile submitted for selling successfully',
                'id': doc_ref.id
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)  # Fixed the missing closing parenthesis
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method allowed'
    }, status=405)

@csrf_exempt
def fetch_sell_mobiles(request):
    """
    Fetch all approved sell mobile listings with pagination and filtering, 
    grouped by model with nested variant and condition data
    """
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        status = request.GET.get('status', 'approved')
        brand = request.GET.get('brand', '')
        condition = request.GET.get('condition', '')
        min_price = request.GET.get('min_price', '')
        max_price = request.GET.get('max_price', '')
        
        query = db.collection('sell_mobiles').where('status', '==', status)
        
        if brand:
            query = query.where('mobile_brand', '==', brand)
        
        # We'll filter by condition and price after grouping
        
        docs = query.stream()
        
        # Group by model, collecting all variants and conditions
        grouped_phones = {}
        
        for doc in docs:
            mobile_data = doc.to_dict()
            mobile_data['id'] = doc.id
            
            # Skip if price filters don't match
            price = float(mobile_data.get('expected_price', 0))
            if min_price and price < float(min_price):
                continue
            if max_price and price > float(max_price):
                continue
            
            # Skip if condition filter doesn't match
            if condition and mobile_data.get('condition') != condition:
                continue
            
            # Extract the base model name (remove variant info)
            full_model = mobile_data.get('mobile_model', '')
            variant = mobile_data.get('variant', '')
            base_model = full_model.replace(f" {variant}", "") if variant else full_model
            
            # Create a unique key for each model
            model_key = f"{mobile_data.get('mobile_brand', '')}-{base_model}"
            
            if model_key not in grouped_phones:
                grouped_phones[model_key] = {
                    'name': base_model,
                    'brand': mobile_data.get('mobile_brand', ''),
                    'image': mobile_data.get('image_url', ''),
                    'variant_prices': {},
                    'created_at': mobile_data.get('created_at', ''),
                    'id': model_key  # Use a unique identifier
                }
            
            # Get or create the variant entry
            variant_entry = grouped_phones[model_key]['variant_prices'].setdefault(variant, {})
            
            # Add the condition and price
            condition_name = mobile_data.get('condition', 'Unknown')
            price_value = mobile_data.get('expected_price', 0)
            variant_entry[condition_name] = f"₹{int(price_value)}"
            
            # Update image if it's missing
            if not grouped_phones[model_key]['image'] and mobile_data.get('image_url'):
                grouped_phones[model_key]['image'] = mobile_data.get('image_url')
        
        # Convert to list and sort by created_at
        phones_list = list(grouped_phones.values())
        phones_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Apply pagination
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_phones = phones_list[start_index:end_index]
        
        return JsonResponse({
            'status': 'success',
            'data': paginated_phones,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': len(phones_list),
                'total_pages': (len(phones_list) + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)

@csrf_exempt
def fetch_sell_mobile_details(request, mobile_id):
    """
    Fetch details of a specific sell mobile listing
    """
    try:
        doc_ref = db.collection('sell_mobiles').document(mobile_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return JsonResponse({
                'status': 'error',
                'message': 'Mobile listing not found'
            }, status=404)
        
        mobile_data = doc.to_dict()
        mobile_data['id'] = doc.id
        
        inquiries_ref = db.collection('sell_mobile_inquiries').where('sell_mobile_id', '==', mobile_id)
        inquiries = []
        
        for inquiry_doc in inquiries_ref.stream():
            inquiry_data = inquiry_doc.to_dict()
            inquiry_data['id'] = inquiry_doc.id
            inquiries.append(inquiry_data)
        
        mobile_data['inquiries'] = inquiries
        
        return JsonResponse({
            'status': 'success',
            'data': mobile_data
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)

@user_required
@csrf_exempt
def submit_inquiry(request):
    """
    Submit an inquiry for a sell mobile listing
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            required_fields = ['sell_mobile_id', 'user_id', 'buyer_phone', 'selected_variant', 
                              'selected_condition', 'address']
            
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Missing required field: {field}'
                    }, status=400)
            
            # Validate address structure
            address = data.get('address')
            if not isinstance(address, dict):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Address must be a properly structured object'
                }, status=400)
                
            # Check required address fields
            required_address_fields = ['street_address', 'city', 'state', 'postal_code']
            for field in required_address_fields:
                if field not in address:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Missing required address field: {field}'
                    }, status=400)
            
            # First check if the mobile exists in the sell_mobiles collection
            sell_mobile_id = data['sell_mobile_id']
            sell_mobile_ref = db.collection('sell_mobiles').document(sell_mobile_id)
            mobile_found = sell_mobile_ref.get().exists
            
            # If not found in sell_mobiles, check the mobile_catalog collection
            if not mobile_found:
                catalog_ref = db.collection('mobile_catalog').document(sell_mobile_id)
                mobile_found = catalog_ref.get().exists
            
            if not mobile_found:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Mobile listing not found with ID: {sell_mobile_id}. Please check if you are using the correct ID.'
                }, status=404)
            
            # Set default status as 'pending' if not provided
            if 'status' not in data:
                data['status'] = 'pending'
            else:
                # Validate status if provided
                valid_statuses = ['pending', 'accepted', 'completed', 'rejected']
                if data['status'] not in valid_statuses:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Invalid status. Valid options: {valid_statuses}'
                    }, status=400)
            
            data['created_at'] = datetime.now().isoformat()
            data['updated_at'] = datetime.now().isoformat()
            
            doc_ref = db.collection('sell_mobile_inquiries').document()
            doc_ref.set(data)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Inquiry submitted successfully',
                'id': doc_ref.id
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method allowed'
    }, status=405)

@csrf_exempt
def update_sell_mobile_status(request, mobile_id):
    """
    Update the status of a sell mobile listing (Admin function)
    """
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            
            if 'status' not in data:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Status field is required'
                }, status=400)
            
            valid_statuses = ['pending', 'approved', 'rejected', 'sold', 'withdrawn']
            if data['status'] not in valid_statuses:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid status. Valid options: {valid_statuses}'
                }, status=400)
            
            doc_ref = db.collection('sell_mobiles').document(mobile_id)
            
            if not doc_ref.get().exists:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Mobile listing not found'
                }, status=404)
            
            update_data = {
                'status': data['status'],
                'updated_at': datetime.now().isoformat()
            }
            
            if 'admin_notes' in data:
                update_data['admin_notes'] = data['admin_notes']
            
            doc_ref.update(update_data)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Status updated successfully'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only PUT method allowed'
    }, status=405)

@csrf_exempt
def upload_phone_data(request):
    """
    Clear the mobile_catalog collection and upload phone data from simplified_phone_data.json
    directly to Firestore in catalog format, with prices as int and no extra fields.
    """
    try:
        # Get the path to the JSON file
        base_dir = Path(__file__).resolve().parent.parent
        json_file_path = base_dir / 'simplified_phone_data.json'

        # Load the JSON data
        with open(json_file_path, 'r') as file:
            phones_data = json.load(file)

        # Clear the mobile_catalog collection
        catalog_ref = db.collection('mobile_catalog')
        docs = catalog_ref.stream()
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()

        # Count successfully uploaded phones
        uploaded_count = 0

        # Helper to convert price string to int
        def clean_price(val):
            if isinstance(val, str):
                # Remove all non-digit characters
                digits = ''.join(filter(str.isdigit, val))
                return int(digits) if digits else 0
            return val

        # Process each phone and store in catalog format
        for phone in phones_data:
            # Deep copy and clean prices
            variant_prices = {}
            for variant, conds in phone.get('variant_prices', {}).items():
                variant_prices[variant] = {}
                for cond, price in conds.items():
                    variant_prices[variant][cond] = clean_price(price)

            catalog_entry = {
                'name': phone.get('name', ''),
                'brand': phone.get('brand', ''),
                'image': phone.get('image', ''),
                'variant_prices': variant_prices
            }

            # Add to the mobile_catalog collection
            doc_ref = db.collection('mobile_catalog').document()
            doc_ref.set(catalog_entry)
            uploaded_count += 1

        return JsonResponse({
            'status': 'success',
            'message': f'Successfully uploaded {uploaded_count} phones to catalog',
        })

    except FileNotFoundError:
        return JsonResponse({
            'status': 'error',
            'message': 'Phone data file not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data in phone data file'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)

@csrf_exempt
def fetch_all_mobiles_catalog(request):
    """
    Fetch all mobile listings in the catalog format with nested variant and condition data,
    without pagination or filtering.
    """
    try:
        catalog_phones = []
        # Fetch all documents from mobile_catalog collection
        catalog_ref = db.collection('mobile_catalog')
        docs = catalog_ref.stream()
        for doc in docs:
            mobile_data = doc.to_dict()
            mobile_data['id'] = doc.id
            catalog_phones.append(mobile_data)

        return JsonResponse({
            'status': 'success',
            'data': catalog_phones
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)
