from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from anand_mobiles.settings import db  # Import the Firestore client
from google.cloud import firestore  # Import firestore for Query constants
import json
from datetime import datetime

# Create your views here.

@csrf_exempt
def submit_sell_mobile(request):
    """
    Submit a mobile for selling
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['user_name', 'phone_number', 'email', 'location', 
                             'mobile_brand', 'mobile_model', 'condition', 'expected_price']
            
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Missing required field: {field}'
                    }, status=400)
            
            # Add timestamp and default status
            data['status'] = 'pending'
            data['created_at'] = datetime.now().isoformat()
            data['updated_at'] = datetime.now().isoformat()
            
            # Create a new document in Firestore
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
    Fetch all approved sell mobile listings with pagination and filtering
    """
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        status = request.GET.get('status', 'approved')
        brand = request.GET.get('brand', '')
        condition = request.GET.get('condition', '')
        min_price = request.GET.get('min_price', '')
        max_price = request.GET.get('max_price', '')
        
        # Build query
        query = db.collection('sell_mobiles').where('status', '==', status)
        
        if brand:
            query = query.where('mobile_brand', '==', brand)
        
        if condition:
            query = query.where('condition', '==', condition)
        
        # Execute query
        docs = query.stream()
        sell_mobiles = []
        
        for doc in docs:
            mobile_data = doc.to_dict()
            mobile_data['id'] = doc.id
            
            # Apply price filtering (since Firestore doesn't support range queries with other filters)
            if min_price and float(mobile_data.get('expected_price', 0)) < float(min_price):
                continue
            if max_price and float(mobile_data.get('expected_price', 0)) > float(max_price):
                continue
                
            sell_mobiles.append(mobile_data)
        
        # Sort by created_at (newest first)
        sell_mobiles.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Manual pagination
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_mobiles = sell_mobiles[start_index:end_index]
        
        return JsonResponse({
            'status': 'success',
            'data': paginated_mobiles,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': len(sell_mobiles),
                'total_pages': (len(sell_mobiles) + per_page - 1) // per_page
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
        
        # Also fetch inquiries for this mobile
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

@csrf_exempt
def submit_inquiry(request):
    """
    Submit an inquiry for a sell mobile listing
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['sell_mobile_id', 'buyer_name', 'buyer_phone']
            
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Missing required field: {field}'
                    }, status=400)
            
            # Check if the sell mobile exists
            sell_mobile_ref = db.collection('sell_mobiles').document(data['sell_mobile_id'])
            if not sell_mobile_ref.get().exists:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Mobile listing not found'
                }, status=404)
            
            # Add timestamp and default status
            data['status'] = 'pending'
            data['created_at'] = datetime.now().isoformat()
            
            # Create a new inquiry document
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
            
            # Update the document
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
def fetch_brands(request):
    """
    Fetch unique brands from sell mobile listings
    """
    try:
        docs = db.collection('sell_mobiles').stream()
        brands = set()
        
        for doc in docs:
            mobile_data = doc.to_dict()
            if 'mobile_brand' in mobile_data:
                brands.add(mobile_data['mobile_brand'])
        
        return JsonResponse({
            'status': 'success',
            'data': sorted(list(brands))
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)
