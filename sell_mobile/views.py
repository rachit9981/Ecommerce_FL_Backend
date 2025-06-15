from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from anand_mobiles.settings import db  # Import the Firestore client
from google.cloud import firestore  # Import firestore for Query constants
import json
from datetime import datetime
from shop_users.utils import user_required
from pathlib import Path # Ensure Path is imported
import os # For joining paths

# Create your views here.

@csrf_exempt
def submit_sell_mobile(request):
    """
    Submit a mobile for selling with dynamic pricing based on questions and variants
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            required_fields = ['user_name', 'phone_number', 'email', 'location', 
                             'brand', 'phone_series', 'phone_model', 'selected_variant', 
                             'question_answers', 'calculated_price']
            
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Missing required field: {field}'
                    }, status=400)
            
            # Validate question_answers structure
            question_answers = data.get('question_answers', {})
            if not isinstance(question_answers, dict):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid question_answers format, must be a dictionary'
                }, status=400)
            
            # Validate selected_variant structure (e.g., storage, ram, color)
            selected_variant = data.get('selected_variant', {})
            if not isinstance(selected_variant, dict):
                 return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid selected_variant format, must be a dictionary'
                }, status=400)
            
            data['status'] = 'pending' # Initial status
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
def fetch_sell_mobiles(request):
    """
    Fetch all approved sell mobile listings with pagination and filtering,
    organized by brand, series, and phone model
    """
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        status = request.GET.get('status', 'approved') # Default to approved
        brand_filter = request.GET.get('brand', '')
        phone_series_filter = request.GET.get('phone_series', '')
        min_price_filter = request.GET.get('min_price', '')
        max_price_filter = request.GET.get('max_price', '')
        
        query = db.collection('sell_mobiles').where('status', '==', status)
        
        if brand_filter:
            query = query.where('brand', '==', brand_filter)
        if phone_series_filter:
            query = query.where('phone_series', '==', phone_series_filter)
        
        # Firestore does not support multiple inequality filters on different fields or combining orderBy with all types of filters easily.
        # Price filtering will be done client-side or after fetching initial data if complex.
        # For server-side, if only price filtering is needed without brand/series, it's simpler.
        # Here, we fetch then filter by price in Python.
        
        docs = query.stream()
        
        grouped_phones = {}
        
        for doc in docs:
            mobile_data = doc.to_dict()
            mobile_data['id'] = doc.id
            
            price = float(mobile_data.get('calculated_price', 0))
            if min_price_filter and price < float(min_price_filter):
                continue
            if max_price_filter and price > float(max_price_filter):
                continue
            
            brand_name = mobile_data.get('brand', '')
            series_name = mobile_data.get('phone_series', '')
            phone_model = mobile_data.get('phone_model', '')
            
            if brand_name not in grouped_phones:
                grouped_phones[brand_name] = {}
            if series_name not in grouped_phones[brand_name]:
                grouped_phones[brand_name][series_name] = {}
            if phone_model not in grouped_phones[brand_name][series_name]:
                grouped_phones[brand_name][series_name][phone_model] = {
                    'display_name': phone_model, # Or fetch from catalog if needed
                    'listings': [],
                    'price_range': {'min': float('inf'), 'max': float('-inf')}
                }
            
            listing_info = {
                'id': mobile_data['id'],
                'user_name': mobile_data.get('user_name', ''),
                'location': mobile_data.get('location', ''),
                'selected_variant': mobile_data.get('selected_variant', {}),
                'calculated_price': mobile_data.get('calculated_price', 0),
                'created_at': mobile_data.get('created_at', ''),
                'question_answers': mobile_data.get('question_answers', {}) # Include for completeness
            }
            
            grouped_phones[brand_name][series_name][phone_model]['listings'].append(listing_info)
            
            current_min = grouped_phones[brand_name][series_name][phone_model]['price_range']['min']
            current_max = grouped_phones[brand_name][series_name][phone_model]['price_range']['max']
            grouped_phones[brand_name][series_name][phone_model]['price_range']['min'] = min(current_min, price)
            grouped_phones[brand_name][series_name][phone_model]['price_range']['max'] = max(current_max, price)
        
        phones_list = []
        for brand_name, series_dict in grouped_phones.items():
            for series_name, phones_dict_val in series_dict.items(): # renamed phones_dict to avoid conflict
                for phone_model_name, model_data in phones_dict_val.items(): # iterate through models
                    if model_data['listings']: # Only add if there are listings
                        phones_list.append({
                            'brand': brand_name,
                            'phone_series': series_name,
                            'phone_model': phone_model_name,
                            'display_name': model_data.get('display_name', phone_model_name),
                            'listings': model_data['listings'],
                            'price_range': model_data['price_range']
                        })
        
        # Sort by the latest 'created_at' among listings in each group
        phones_list.sort(key=lambda x: max([listing.get('created_at', '') for listing in x['listings']], default=''), reverse=True)
        
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_phones = phones_list[start_index:end_index]
        
        return JsonResponse({
            'status': 'success',
            'data': paginated_phones,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': len(phones_list),
                'total_pages': (len(phones_list) + per_page - 1) // per_page if per_page > 0 else 0
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred in fetch_sell_mobiles: {str(e)}'
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
        
        # Fetch inquiries related to this mobile listing
        inquiries_ref = db.collection('sell_mobile_inquiries').where('sell_mobile_id', '==', mobile_id).order_by('created_at', direction=firestore.Query.DESCENDING)
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
            
            required_fields = ['sell_mobile_id', 'user_id', 'buyer_phone', 'address'] # user_id is from @user_required
            if data.get('user_id') != request.user_id:
                 return JsonResponse({'status': 'error', 'message': 'User ID mismatch or not authorized.'}, status=403)

            for field in required_fields:
                if field not in data:
                    return JsonResponse({'status': 'error', 'message': f'Missing required field: {field}'}, status=400)
            
            address = data.get('address')
            if not isinstance(address, dict):
                return JsonResponse({'status': 'error', 'message': 'Address must be a dictionary.'}, status=400)
                
            required_address_fields = ['street_address', 'city', 'state', 'postal_code']
            for field in required_address_fields:
                if field not in address:
                    return JsonResponse({'status': 'error', 'message': f'Missing address field: {field}'}, status=400)
            
            sell_mobile_id = data['sell_mobile_id']
            sell_mobile_ref = db.collection('sell_mobiles').document(sell_mobile_id)
            mobile_doc = sell_mobile_ref.get()
            
            if not mobile_doc.exists:
                return JsonResponse({'status': 'error', 'message': 'Sell mobile listing not found.'}, status=404)
            
            data['status'] = data.get('status', 'pending') # Default status
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
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Only POST method allowed'}, status=405)

@user_required
@csrf_exempt
def fetch_user_inquiries(request):
    """
    Fetch all inquiries made by the logged-in user
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

    try:
        user_id = request.user_id # From @user_required decorator
        inquiries_ref = db.collection('sell_mobile_inquiries').where('user_id', '==', user_id).order_by('created_at', direction=firestore.Query.DESCENDING)
        inquiries_list = []
        
        for inquiry_doc in inquiries_ref.stream():
            inquiry_data = inquiry_doc.to_dict()
            inquiry_data['id'] = inquiry_doc.id
            
            created_at = inquiry_data.get('created_at')
            if created_at and isinstance(created_at, datetime): # Ensure it's datetime before formatting
                inquiry_data['created_at'] = created_at.isoformat()
            
            updated_at = inquiry_data.get('updated_at')
            if updated_at and isinstance(updated_at, datetime):
                inquiry_data['updated_at'] = updated_at.isoformat()

            sell_mobile_id = inquiry_data.get('sell_mobile_id')
            mobile_listing_details = None
            
            if sell_mobile_id:
                mobile_doc_ref = db.collection('sell_mobiles').document(sell_mobile_id)
                mobile_doc = mobile_doc_ref.get()
                if mobile_doc.exists:
                    mobile_listing_data = mobile_doc.to_dict()
                    mobile_listing_details = {
                        'brand': mobile_listing_data.get('brand'),
                        'phone_series': mobile_listing_data.get('phone_series'),
                        'phone_model': mobile_listing_data.get('phone_model'),
                        'calculated_price': mobile_listing_data.get('calculated_price'),
                        'selected_variant': mobile_listing_data.get('selected_variant')
                    }
            inquiry_data['mobile_listing_details'] = mobile_listing_details
            inquiries_list.append(inquiry_data)

        return JsonResponse({'status': 'success', 'inquiries': inquiries_list}, status=200)

    except Exception as e:
        # Log the error for debugging
        print(f"Error fetching inquiries for user {user_id}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Error fetching inquiries: {str(e)}'}, status=500)

@csrf_exempt
def fetch_inquiries_for_mobile(request):
    """
    Fetch all inquiries, optionally filtered by a specific sell_mobile_id.
    If 'sell_mobile_id' query parameter is provided, filters for that mobile.
    Otherwise, returns all inquiries (intended for admin or broader views).
    """
    try:
        sell_mobile_id_filter = request.GET.get('sell_mobile_id')
        
        query = db.collection('sell_mobile_inquiries')
        
        if sell_mobile_id_filter:
            query = query.where('sell_mobile_id', '==', sell_mobile_id_filter)
            
        # Consider adding ordering, e.g., by creation date
        query = query.order_by('created_at', direction=firestore.Query.DESCENDING)
        
        inquiries = []
        for inquiry_doc in query.stream():
            inquiry_data = inquiry_doc.to_dict()
            inquiry_data['id'] = inquiry_doc.id
            # Format timestamps if they are datetime objects
            if 'created_at' in inquiry_data and isinstance(inquiry_data['created_at'], datetime):
                inquiry_data['created_at'] = inquiry_data['created_at'].isoformat()
            if 'updated_at' in inquiry_data and isinstance(inquiry_data['updated_at'], datetime):
                inquiry_data['updated_at'] = inquiry_data['updated_at'].isoformat()
            inquiries.append(inquiry_data)
        
        return JsonResponse({
            'status': 'success',
            'data': inquiries
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)

@csrf_exempt
def update_sell_mobile_status(request, mobile_id):
    """
    Update the status of a sell mobile listing (Admin function)
    """
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')

            if not new_status:
                return JsonResponse({'status': 'error', 'message': 'Status is required.'}, status=400)

            doc_ref = db.collection('sell_mobiles').document(mobile_id)
            doc = doc_ref.get()

            if not doc.exists:
                return JsonResponse({'status': 'error', 'message': 'Mobile listing not found.'}, status=404)

            update_data = {
                'status': new_status,
                'updated_at': datetime.now().isoformat()
            }
            doc_ref.update(update_data)
            
            return JsonResponse({'status': 'success', 'message': 'Status updated successfully.'})
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred: {str(e)}'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Only PUT method allowed'}, status=405)

@csrf_exempt
def upload_phone_data(request):
    """
    Upload dynamic phone catalog data directly to Firestore.
    Expects JSON data in the request body with the complete brands structure.
    This will overwrite any existing catalog data.
    """
    if request.method == 'POST':
        try:
            catalog_data = json.loads(request.body)
            
            # Basic validation: check if 'brands' key exists
            if 'brands' not in catalog_data or not isinstance(catalog_data['brands'], dict):
                return JsonResponse({
                    'status': 'error',
                    'message': "Invalid catalog structure: 'brands' key is missing or not a dictionary."
                }, status=400)

            # Store the entire catalog under a single document for easier management
            catalog_doc_ref = db.collection('phone_catalog').document('catalog_data')
            catalog_doc_ref.set(catalog_data) # Overwrites the document
            
            return JsonResponse({
                'status': 'success',
                'message': 'Phone catalog data uploaded successfully.'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data provided.'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred during catalog upload: {str(e)}'
            }, status=500)
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method allowed for uploading phone data.'
        }, status=405)

@csrf_exempt
def fetch_all_mobiles_catalog(request):
    """
    Fetch the complete phone catalog with the dynamic structure.
    """
    try:
        catalog_doc_ref = db.collection('phone_catalog').document('catalog_data')
        catalog_doc = catalog_doc_ref.get()
        
        if not catalog_doc.exists:
            return JsonResponse({
                'status': 'error',
                'message': 'Phone catalog not found. Please upload catalog data first.'
            }, status=404)
        
        catalog_data = catalog_doc.to_dict()
        
        return JsonResponse({
            'status': 'success',
            'data': catalog_data
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred while fetching catalog: {str(e)}'
        }, status=500)

@csrf_exempt
def get_phone_details(request, brand, phone_series, phone_model):
    """
    Get detailed information for a specific phone model from the catalog,
    including questions, variant options, and base pricing.
    """
    try:
        catalog_doc_ref = db.collection('phone_catalog').document('catalog_data')
        catalog_doc = catalog_doc_ref.get()
        
        if not catalog_doc.exists:
            return JsonResponse({'status': 'error', 'message': 'Phone catalog not found.'}, status=404)
        
        catalog_data = catalog_doc.to_dict()
        
        brands_data = catalog_data.get('brands', {})
        if brand not in brands_data:
            return JsonResponse({'status': 'error', 'message': f"Brand '{brand}' not found in catalog."}, status=404)
        
        brand_info = brands_data[brand]
        phone_series_data = brand_info.get('phone_series', {})
        if phone_series not in phone_series_data:
            return JsonResponse({'status': 'error', 'message': f"Phone series '{phone_series}' not found for brand '{brand}'."}, status=404)
        
        series_info = phone_series_data[phone_series]
        phones_data = series_info.get('phones', {})
        if phone_model not in phones_data:
            return JsonResponse({'status': 'error', 'message': f"Phone model '{phone_model}' not found in series '{phone_series}'."}, status=404)
        
        specific_phone_data = phones_data[phone_model]
        
        # Optionally enrich with brand/series info if not already deeply nested in specific_phone_data
        response_data = {
            'brand_name': brand,
            'brand_logo_url': brand_info.get('logo_url', ''),
            'phone_series_name': phone_series,
            'phone_series_display_name': series_info.get('display_name', phone_series),
            'phone_model_name': phone_model,
            **specific_phone_data # Includes display_name, image_url, variant_options, variant_prices, question_groups etc.
        }
        
        return JsonResponse({
            'status': 'success',
            'data': response_data
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred retrieving phone details: {str(e)}'
        }, status=500)

@csrf_exempt
def calculate_phone_price(request):
    """
    Calculate the final price for a phone based on its base variant price and
    adjustments from question answers, using the dynamic catalog.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            required_fields = ['brand', 'phone_series', 'phone_model', 'selected_variant', 'question_answers']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({'status': 'error', 'message': f'Missing field: {field}'}, status=400)

            brand = data['brand']
            phone_series = data['phone_series']
            phone_model = data['phone_model']
            selected_variant = data['selected_variant'] # e.g., {"storage": "128GB", "ram": "4GB"}
            question_answers = data['question_answers'] # e.g., {"screen_condition": "Flawless", "faults_detected": ["No faults"]}

            # 1. Fetch phone details from catalog
            catalog_doc_ref = db.collection('phone_catalog').document('catalog_data')
            catalog_doc = catalog_doc_ref.get()
            if not catalog_doc.exists:
                return JsonResponse({'status': 'error', 'message': 'Phone catalog not found.'}, status=404)
            
            catalog = catalog_doc.to_dict()
            try:
                phone_data = catalog['brands'][brand]['phone_series'][phone_series]['phones'][phone_model]
            except KeyError:
                return JsonResponse({'status': 'error', 'message': 'Phone model not found in catalog with provided path.'}, status=404)

            # 2. Determine base price from selected_variant and variant_prices
            variant_prices = phone_data.get('variant_prices', {})
            storage_selected = selected_variant.get('storage')
            ram_selected = selected_variant.get('ram') # RAM might be optional in selection if only one option

            base_price = 0
            if storage_selected and storage_selected in variant_prices:
                if ram_selected and ram_selected in variant_prices[storage_selected]:
                    base_price = variant_prices[storage_selected][ram_selected]
                elif not ram_selected and len(variant_prices[storage_selected]) == 1: # If RAM not specified and only one RAM option for storage
                    ram_key = list(variant_prices[storage_selected].keys())[0]
                    base_price = variant_prices[storage_selected][ram_key]
                elif isinstance(variant_prices[storage_selected], (int, float)): # Simpler structure: "128GB": 50000
                     base_price = variant_prices[storage_selected]
                else:
                    return JsonResponse({'status': 'error', 'message': f'RAM option for storage {storage_selected} not found or ambiguous.'}, status=400)
            else:
                return JsonResponse({'status': 'error', 'message': f'Storage option {storage_selected} not found in variant_prices.'}, status=400)

            # 3. Calculate adjustments from question_answers
            total_adjustment = 0
            adjustments_details = []
            
            all_questions_map = {} # Map question_id to question details for easy lookup
            for group_key, group_data in phone_data.get('question_groups', {}).items():
                for question in group_data.get('questions', []):
                    all_questions_map[question['id']] = question
            
            for q_id, answered_labels in question_answers.items():
                if q_id in all_questions_map:
                    question_detail = all_questions_map[q_id]
                    options_map = {opt['label']: opt for opt in question_detail['options']}
                    
                    if isinstance(answered_labels, list): # Multi-choice
                        for label in answered_labels:
                            if label in options_map:
                                modifier = options_map[label].get('price_modifier', 0)
                                total_adjustment += modifier
                                adjustments_details.append({'question': q_id, 'option': label, 'modifier': modifier})
                            # else: log unknown label?
                    else: # Single-choice
                        label = answered_labels
                        if label in options_map:
                            modifier = options_map[label].get('price_modifier', 0)
                            total_adjustment += modifier
                            adjustments_details.append({'question': q_id, 'option': label, 'modifier': modifier})
                        # else: log unknown label?
            
            final_price = base_price + total_adjustment
            
            return JsonResponse({
                'status': 'success',
                'calculated_price': final_price,
                'base_price': base_price,
                'total_adjustment': total_adjustment,
                'adjustments_details': adjustments_details
            })

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except KeyError as ke:
            return JsonResponse({'status': 'error', 'message': f'Missing key in input or catalog structure: {str(ke)}'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'An error occurred during price calculation: {str(e)}'}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Only POST method allowed'}, status=405)

@csrf_exempt
def temp_bulk_upload_from_json_file(request):
    """
    Temporary view to upload phone catalog data from simplified_phone_data.json
    located in the project root.
    """
    if request.method == 'GET': # Or POST, GET is simpler for a temp one-off
        try:
            # Construct the absolute path to the JSON file
            # Assuming the script is run from the project root or paths are set up correctly for Django
            # settings.BASE_DIR should point to the project root "Ecommerce_FL_Backend"
            # For simplicity, constructing path from a known structure.
            # If manage.py is at "c:\\Users\\Anubhav Choubey\\Documents\\New_Freelance_Ecommerce_Work\\Ecommerce_FL_Backend\\manage.py"
            # then BASE_DIR is "c:\\Users\\Anubhav Choubey\\Documents\\New_Freelance_Ecommerce_Work\\Ecommerce_FL_Backend"
            
            # It's better to use settings.BASE_DIR if available and configured
            # from django.conf import settings
            # base_dir = settings.BASE_DIR
            # file_path = os.path.join(base_dir, 'simplified_phone_data.json')

            # Hardcoding path for this specific case as BASE_DIR context isn't directly available to the tool
            # This assumes the server is run from the workspace root.
            # A more robust solution in a real Django app would use settings.BASE_DIR
            workspace_root = "c:\\\\Users\\\\Anubhav Choubey\\\\Documents\\\\New_Freelance_Ecommerce_Work\\\\Ecommerce_FL_Backend"
            file_path = os.path.join(workspace_root, 'simplified_phone_data.json')

            if not os.path.exists(file_path):
                return JsonResponse({
                    'status': 'error',
                    'message': f'File not found: {file_path}'
                }, status=404)

            with open(file_path, 'r') as f:
                catalog_data = json.load(f)
            
            if 'brands' not in catalog_data or not isinstance(catalog_data['brands'], dict):
                return JsonResponse({
                    'status': 'error',
                    'message': "Invalid catalog structure in JSON file: 'brands' key is missing or not a dictionary."
                }, status=400)

            catalog_doc_ref = db.collection('phone_catalog').document('catalog_data')
            catalog_doc_ref.set(catalog_data)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Phone catalog data uploaded successfully from simplified_phone_data.json.'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data in simplified_phone_data.json.'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred during bulk upload: {str(e)}'
            }, status=500)
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Only GET method allowed for this temporary upload.'
        }, status=405)

# FAQ Management Views

@csrf_exempt
def manage_faqs(request):
    """
    Manages FAQs.
    GET: Fetches all FAQs.
    POST: Adds a new FAQ.
    """
    if request.method == 'GET':
        try:
            faqs_ref = db.collection('sell_mobile_faqs').order_by('created_at', direction=firestore.Query.ASCENDING)
            faqs = []
            for doc in faqs_ref.stream():
                faq_data = doc.to_dict()
                faq_data['id'] = doc.id
                # Ensure timestamps are ISO format strings if they are datetime objects
                if 'created_at' in faq_data and isinstance(faq_data['created_at'], datetime):
                    faq_data['created_at'] = faq_data['created_at'].isoformat()
                if 'updated_at' in faq_data and isinstance(faq_data['updated_at'], datetime):
                    faq_data['updated_at'] = faq_data['updated_at'].isoformat()
                faqs.append(faq_data)
            return JsonResponse({'status': 'success', 'faqs': faqs})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            question = data.get('question')
            answer = data.get('answer')

            if not question or not answer:
                return JsonResponse({'status': 'error', 'message': 'Question and Answer are required.'}, status=400)

            faq_data = {
                'question': question,
                'answer': answer,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            doc_ref = db.collection('sell_mobile_faqs').document()
            doc_ref.set(faq_data)
            return JsonResponse({'status': 'success', 'message': 'FAQ added successfully.', 'id': doc_ref.id}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    else:
        return JsonResponse({'status': 'error', 'message': 'Method not allowed.'}, status=405)

@csrf_exempt
def manage_faq_detail(request, faq_id):
    """
    Manages a specific FAQ by its ID.
    GET: Fetches a single FAQ.
    PUT: Updates an existing FAQ.
    DELETE: Deletes an FAQ.
    """
    try:
        faq_ref = db.collection('sell_mobile_faqs').document(faq_id)
        faq_doc = faq_ref.get()

        if not faq_doc.exists:
            return JsonResponse({'status': 'error', 'message': 'FAQ not found.'}, status=404)

        if request.method == 'GET':
            faq_data = faq_doc.to_dict()
            faq_data['id'] = faq_doc.id
            if 'created_at' in faq_data and isinstance(faq_data['created_at'], datetime):
                faq_data['created_at'] = faq_data['created_at'].isoformat()
            if 'updated_at' in faq_data and isinstance(faq_data['updated_at'], datetime):
                faq_data['updated_at'] = faq_data['updated_at'].isoformat()
            return JsonResponse({'status': 'success', 'faq': faq_data})

        elif request.method == 'PUT':
            data = json.loads(request.body)
            update_data = {}
            if 'question' in data:
                update_data['question'] = data['question']
            if 'answer' in data:
                update_data['answer'] = data['answer']
            
            if not update_data:
                return JsonResponse({'status': 'error', 'message': 'No fields to update provided.'}, status=400)

            update_data['updated_at'] = datetime.now().isoformat()
            faq_ref.update(update_data)
            return JsonResponse({'status': 'success', 'message': 'FAQ updated successfully.'})

        elif request.method == 'DELETE':
            faq_ref.delete()
            return JsonResponse({'status': 'success', 'message': 'FAQ deleted successfully.'})
        
        else:
            return JsonResponse({'status': 'error', 'message': 'Method not allowed.'}, status=405)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data for PUT request.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
