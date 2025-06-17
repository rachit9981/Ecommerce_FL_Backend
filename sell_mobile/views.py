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
    Submit a mobile for selling with dynamic pricing based on questions and variants.
    This validates against the phone catalog and calculates price based on question answers.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            required_fields = ['user_name', 'phone_number', 'email', 'location', 
                             'brand', 'phone_series', 'phone_model', 'selected_variant', 
                             'question_answers']
            
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Missing required field: {field}'
                    }, status=400)
            
            # Get phone catalog to validate the submission
            catalog_doc_ref = db.collection('phone_catalog').document('catalog_data')
            catalog_doc = catalog_doc_ref.get()
            
            if not catalog_doc.exists:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Phone catalog not found'
                }, status=404)
            
            catalog_data = catalog_doc.to_dict()
            brands = catalog_data.get('brands', {})
            
            # Validate phone exists in catalog
            brand = data['brand']
            phone_series = data['phone_series']
            phone_model = data['phone_model']
            
            if brand not in brands:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Brand "{brand}" not found in catalog'
                }, status=400)
            
            if phone_series not in brands[brand].get('phone_series', {}):
                return JsonResponse({
                    'status': 'error',
                    'message': f'Phone series "{phone_series}" not found for brand "{brand}"'
                }, status=400)
            
            phones = brands[brand]['phone_series'][phone_series].get('phones', {})
            if phone_model not in phones:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Phone model "{phone_model}" not found in series "{phone_series}"'
                }, status=400)
            
            phone_data = phones[phone_model]
            
            # Validate selected variant
            selected_variant = data.get('selected_variant', {})
            if not isinstance(selected_variant, dict):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid selected_variant format, must be a dictionary'
                }, status=400)
            
            # Validate storage and RAM combination exists in variant_prices
            storage = selected_variant.get('storage')
            ram = selected_variant.get('ram')
            
            if not storage or not ram:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Storage and RAM must be specified in selected_variant'
                }, status=400)
            
            variant_prices = phone_data.get('variant_prices', {})
            if storage not in variant_prices or ram not in variant_prices[storage]:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Variant combination {storage}/{ram} not available for this phone model'
                }, status=400)
            
            base_price = variant_prices[storage][ram]
            
            # Validate and calculate price based on question answers
            question_answers = data.get('question_answers', {})
            if not isinstance(question_answers, dict):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid question_answers format, must be a dictionary'
                }, status=400)
            
            calculated_price = base_price
            question_groups = phone_data.get('question_groups', {})
            
            # Process each question group and calculate price modifiers
            for group_key, group_data in question_groups.items():
                questions = group_data.get('questions', [])
                for question in questions:
                    question_id = question.get('id')
                    if question_id in question_answers:
                        user_answers = question_answers[question_id]
                        if not isinstance(user_answers, list):
                            user_answers = [user_answers]
                        
                        for answer in user_answers:
                            # Find the option and apply price modifier
                            for option in question.get('options', []):
                                if option.get('label') == answer:
                                    calculated_price += option.get('price_modifier', 0)
                                    break
            
            data['calculated_price'] = calculated_price
            data['base_price'] = base_price
            data['status'] = 'pending'
            data['created_at'] = datetime.now().isoformat()
            data['updated_at'] = datetime.now().isoformat()
              # Store in sell_mobile_listings collection
            doc_ref = db.collection('sell_mobile_listings').document()
            doc_ref.set(data)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Mobile submitted for selling successfully',
                'id': doc_ref.id,
                'calculated_price': calculated_price
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
        
        query = db.collection('sell_mobile_listings').where('status', '==', status)
        
        if brand_filter:
            query = query.where('brand', '==', brand_filter)
        if phone_series_filter:
            query = query.where('phone_series', '==', phone_series_filter)
        
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
                    'display_name': phone_model,
                    'listings': [],
                    'price_range': {'min': float('inf'), 'max': float('-inf')}
                }
            
            listing_info = {
                'id': mobile_data['id'],
                'user_name': mobile_data.get('user_name', ''),
                'location': mobile_data.get('location', ''),
                'selected_variant': mobile_data.get('selected_variant', {}),
                'calculated_price': mobile_data.get('calculated_price', 0),
                'base_price': mobile_data.get('base_price', 0),
                'created_at': mobile_data.get('created_at', ''),
                'question_answers': mobile_data.get('question_answers', {})
            }
            
            grouped_phones[brand_name][series_name][phone_model]['listings'].append(listing_info)
            
            current_min = grouped_phones[brand_name][series_name][phone_model]['price_range']['min']
            current_max = grouped_phones[brand_name][series_name][phone_model]['price_range']['max']
            grouped_phones[brand_name][series_name][phone_model]['price_range']['min'] = min(current_min, price)
            grouped_phones[brand_name][series_name][phone_model]['price_range']['max'] = max(current_max, price)
        
        phones_list = []
        for brand_name, series_dict in grouped_phones.items():
            for series_name, phones_dict_val in series_dict.items():
                for phone_model_name, model_data in phones_dict_val.items():
                    if model_data['listings']:
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
        doc_ref = db.collection('sell_mobile_listings').document(mobile_id)
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
    Submit an inquiry for a sell mobile listing with storage, RAM preferences and questionnaire answers
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            required_fields = ['phone_model_id', 'user_id', 'address'] # buyer_phone is optional
            if data.get('user_id') != request.user_id:
                 return JsonResponse({'status': 'error', 'message': 'User ID mismatch or not authorized.'}, status=403)

            for field in required_fields:
                if field not in data:
                    return JsonResponse({'status': 'error', 'message': f'Missing required field: {field}'}, status=400)
            
            # Validate buyer_phone if provided
            buyer_phone = data.get('buyer_phone', '')
            if buyer_phone and not isinstance(buyer_phone, str):
                return JsonResponse({'status': 'error', 'message': 'buyer_phone must be a string.'}, status=400)
            
            # Validate address structure
            address = data.get('address')
            if not isinstance(address, dict):
                return JsonResponse({'status': 'error', 'message': 'Address must be a dictionary.'}, status=400)
                
            required_address_fields = ['street_address', 'city', 'state', 'postal_code']
            for field in required_address_fields:
                if field not in address:
                    return JsonResponse({'status': 'error', 'message': f'Missing address field: {field}'}, status=400)
            
            # Validate optional storage and RAM preferences
            selected_storage = data.get('selected_storage')
            selected_ram = data.get('selected_ram')
            
            if selected_storage and not isinstance(selected_storage, str):
                return JsonResponse({'status': 'error', 'message': 'selected_storage must be a string value.'}, status=400)
            
            if selected_ram and not isinstance(selected_ram, str):
                return JsonResponse({'status': 'error', 'message': 'selected_ram must be a string value.'}, status=400)
            
            # Validate questionnaire answers structure
            questionnaire_answers = data.get('questionnaire_answers', {})
            if questionnaire_answers and not isinstance(questionnaire_answers, dict):
                return JsonResponse({'status': 'error', 'message': 'questionnaire_answers must be a dictionary.'}, status=400)
              # Validate that each questionnaire answer contains a list
            for question_key, answer_value in questionnaire_answers.items():
                if not isinstance(answer_value, list):
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'questionnaire_answers[{question_key}] must be a list of answers.'
                    }, status=400)            
            phone_model_id = data['phone_model_id']
            
            # Get phone catalog data to validate the phone model and variants
            catalog_ref = db.collection('phone_catalog').document('catalog_data')
            catalog_doc = catalog_ref.get()
            
            if not catalog_doc.exists:
                return JsonResponse({'status': 'error', 'message': 'Phone catalog not found.'}, status=404)
            
            catalog_data = catalog_doc.to_dict()
            
            # Find the phone model in the catalog
            phone_data = None
            brand = None
            phone_series = None
            
            for brand_key, brand_data in catalog_data.get('brands', {}).items():
                for series_key, series_data in brand_data.get('phone_series', {}).items():
                    if phone_model_id in series_data.get('phones', {}):
                        phone_data = series_data['phones'][phone_model_id]
                        brand = brand_key
                        phone_series = series_key
                        break
                if phone_data:
                    break
            
            if not phone_data:
                return JsonResponse({'status': 'error', 'message': f'Phone model "{phone_model_id}" not found in catalog.'}, status=404)
            
            # Validate selected storage and RAM against the phone catalog
            variant_options = phone_data.get('variant_options', {})
            variant_prices = phone_data.get('variant_prices', {})
            
            if selected_storage:
                available_storage = variant_options.get('storage', [])
                if selected_storage not in available_storage:
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Invalid storage option: {selected_storage}. Available options: {available_storage}'
                    }, status=400)
            
            if selected_ram:
                available_ram = variant_options.get('ram', [])
                if selected_ram not in available_ram:
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Invalid RAM option: {selected_ram}. Available options: {available_ram}'
                    }, status=400)
            
            # Validate that the storage/RAM combination is available in variant_prices
            if selected_storage and selected_ram:
                if (selected_storage not in variant_prices or 
                    selected_ram not in variant_prices.get(selected_storage, {})):
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Variant combination {selected_storage}/{selected_ram} is not available for this phone model.'
                    }, status=400)
              # Validate questionnaire answers against phone catalog questions
            question_groups = phone_data.get('question_groups', {})
            
            # Build a map of question_id to valid options for easier validation
            question_id_to_options = {}
            for group_name, group_data in question_groups.items():
                for question in group_data.get('questions', []):
                    question_id = question.get('id')
                    if question_id:
                        question_id_to_options[question_id] = {
                            'options': [opt.get('label') for opt in question.get('options', [])],
                            'type': question.get('type', 'multi_choice')
                        }
              # Validate each questionnaire answer
            for question_id, user_answers in questionnaire_answers.items():
                if question_id not in question_id_to_options:
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Invalid question ID: {question_id}'
                    }, status=400)
                
                question_info = question_id_to_options[question_id]
                valid_options = question_info['options']
                question_type = question_info['type']
                
                # Validate answer format based on question type
                if question_type == 'single_choice' and len(user_answers) > 1:
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Question "{question_id}" is single choice but multiple answers provided'
                    }, status=400)
                
                # Validate each answer
                for user_answer in user_answers:
                    if user_answer not in valid_options:
                        return JsonResponse({
                            'status': 'error', 
                            'message': f'Invalid answer "{user_answer}" for question "{question_id}". Valid options: {valid_options}'
                        }, status=400)
            
            # Calculate estimated price for quote inquiries
            estimated_price = 0
            if selected_storage and selected_ram and variant_prices:
                # Get base price for the selected variant
                base_price = variant_prices.get(selected_storage, {}).get(selected_ram, 0)
                estimated_price = base_price
                
                # Apply questionnaire modifiers to calculate estimated price
                for question_id, user_answers in questionnaire_answers.items():
                    if question_id in question_id_to_options:
                        # Find the corresponding question in question_groups to get price modifiers
                        for group_name, group_data in question_groups.items():
                            for question in group_data.get('questions', []):
                                if question.get('id') == question_id:
                                    # Apply price modifiers for each selected answer
                                    for user_answer in user_answers:
                                        for option in question.get('options', []):
                                            if option.get('label') == user_answer:
                                                price_modifier = option.get('price_modifier', 0)
                                                estimated_price += price_modifier
                                                break
                                    break
                            else:
                                continue
                            break
            
            # Add phone catalog information to the inquiry data
            data['brand'] = brand
            data['phone_series'] = phone_series
            data['phone_model'] = phone_model_id
            data['phone_display_name'] = phone_data.get('display_name', phone_model_id)
            data['estimated_price'] = estimated_price
            data['base_price'] = variant_prices.get(selected_storage, {}).get(selected_ram, 0) if selected_storage and selected_ram else 0
              # Set default status and timestamps
            data['status'] = data.get('status', 'pending') # Default status
            data['created_at'] = datetime.now().isoformat()
            data['updated_at'] = datetime.now().isoformat()
            
            # Save inquiry to Firestore
            doc_ref = db.collection('phone_inquiries').document()
            doc_ref.set(data)
            
            return JsonResponse({
                'status': 'success',
                'message': 'Inquiry submitted successfully',
                'id': doc_ref.id,
                'estimated_price': estimated_price,
                'base_price': data.get('base_price', 0)
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
        inquiries_ref = db.collection('phone_inquiries').where('user_id', '==', user_id).order_by('created_at', direction=firestore.Query.DESCENDING)
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
                mobile_doc_ref = db.collection('sell_mobile_listings').document(sell_mobile_id)
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
        
        query = db.collection('phone_inquiries')
        
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
def temp_bulk_upload_from_json_file(request):
    """
    Temporary view to upload phone catalog data from simplified_phone_data.json
    located in the project root.
    """
    if request.method == 'GET': # Or POST, GET is simpler for a temp one-off
        try:
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

@csrf_exempt
def get_quote_estimate(request):
    """
    Get an estimated price quote for a mobile phone based on specifications and condition.
    This endpoint provides a quick price estimate without creating an inquiry record.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            required_fields = ['phone_model_id', 'selected_storage', 'selected_ram', 'questionnaire_answers']
            
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Missing required field: {field}'
                    }, status=400)
            
            phone_model_id = data['phone_model_id']
            selected_storage = data['selected_storage']
            selected_ram = data['selected_ram']
            questionnaire_answers = data['questionnaire_answers']
            
            # Validate questionnaire answers structure
            if not isinstance(questionnaire_answers, dict):
                return JsonResponse({
                    'status': 'error',
                    'message': 'questionnaire_answers must be a dictionary.'
                }, status=400)
            
            # Get phone catalog data
            catalog_ref = db.collection('phone_catalog').document('catalog_data')
            catalog_doc = catalog_ref.get()
            
            if not catalog_doc.exists:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Phone catalog not found.'
                }, status=404)
            
            catalog_data = catalog_doc.to_dict()
            
            # Find the phone model in the catalog
            phone_data = None
            brand = None
            phone_series = None
            
            for brand_key, brand_data in catalog_data.get('brands', {}).items():
                for series_key, series_data in brand_data.get('phone_series', {}).items():
                    if phone_model_id in series_data.get('phones', {}):
                        phone_data = series_data['phones'][phone_model_id]
                        brand = brand_key
                        phone_series = series_key
                        break
                if phone_data:
                    break
            
            if not phone_data:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Phone model "{phone_model_id}" not found in catalog.'
                }, status=404)
            
            # Validate storage and RAM options
            variant_options = phone_data.get('variant_options', {})
            variant_prices = phone_data.get('variant_prices', {})
            
            available_storage = variant_options.get('storage', [])
            if selected_storage not in available_storage:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid storage option: {selected_storage}. Available options: {available_storage}'
                }, status=400)
            
            available_ram = variant_options.get('ram', [])
            if selected_ram not in available_ram:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid RAM option: {selected_ram}. Available options: {available_ram}'
                }, status=400)
            
            # Validate variant combination
            if (selected_storage not in variant_prices or 
                selected_ram not in variant_prices.get(selected_storage, {})):
                return JsonResponse({
                    'status': 'error',
                    'message': f'Variant combination {selected_storage}/{selected_ram} is not available for this phone model.'
                }, status=400)
            
            # Get base price
            base_price = variant_prices[selected_storage][selected_ram]
            estimated_price = base_price
            
            # Build question validation map
            question_groups = phone_data.get('question_groups', {})
            question_id_to_options = {}
            for group_name, group_data in question_groups.items():
                for question in group_data.get('questions', []):
                    question_id = question.get('id')
                    if question_id:
                        question_id_to_options[question_id] = {
                            'options': [opt.get('label') for opt in question.get('options', [])],
                            'type': question.get('type', 'multi_choice')
                        }
            
            # Validate and apply questionnaire answers
            applied_modifiers = []
            for question_id, user_answers in questionnaire_answers.items():
                if question_id not in question_id_to_options:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Invalid question ID: {question_id}'
                    }, status=400)
                
                if not isinstance(user_answers, list):
                    user_answers = [user_answers]
                
                question_info = question_id_to_options[question_id]
                valid_options = question_info['options']
                question_type = question_info['type']
                
                # Validate answer format
                if question_type == 'single_choice' and len(user_answers) > 1:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Question "{question_id}" is single choice but multiple answers provided'
                    }, status=400)
                
                # Validate and apply price modifiers
                for user_answer in user_answers:
                    if user_answer not in valid_options:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'Invalid answer "{user_answer}" for question "{question_id}". Valid options: {valid_options}'
                        }, status=400)
                    
                    # Find and apply price modifier
                    for group_name, group_data in question_groups.items():
                        for question in group_data.get('questions', []):
                            if question.get('id') == question_id:
                                for option in question.get('options', []):
                                    if option.get('label') == user_answer:
                                        price_modifier = option.get('price_modifier', 0)
                                        estimated_price += price_modifier
                                        applied_modifiers.append({
                                            'question_id': question_id,
                                            'answer': user_answer,
                                            'modifier': price_modifier
                                        })
                                        break
                                break
                        else:
                            continue
                        break
            
            return JsonResponse({
                'status': 'success',
                'quote_estimate': {
                    'phone_model_id': phone_model_id,
                    'brand': brand,
                    'phone_series': phone_series,
                    'phone_display_name': phone_data.get('display_name', phone_model_id),
                    'selected_variant': {
                        'storage': selected_storage,
                        'ram': selected_ram
                    },
                    'base_price': base_price,
                    'estimated_price': estimated_price,
                    'price_difference': estimated_price - base_price,
                    'applied_modifiers': applied_modifiers,
                    'timestamp': datetime.now().isoformat()
                }
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
