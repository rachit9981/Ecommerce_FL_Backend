from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import jwt
import datetime
from firebase_admin import firestore
from anand_mobiles.settings import SECRET_KEY # Assuming SECRET_KEY is in your project settings
from .utils import partner_required # Import the new decorator
from shop_admin.utils import admin_required # For admin verification

# Get Firebase client
db = firestore.client()
PARTNERS_COLLECTION = 'delivery_partners'
ORDERS_COLLECTION = 'orders' # Assuming you have an orders collection

@csrf_exempt
def partner_register(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password') # Store hashed password in production
            name = data.get('name')
            phone = data.get('phone')

            if not all([email, password, name, phone]):
                return JsonResponse({'error': 'Missing required fields'}, status=400)

            # Check if partner already exists
            partner_ref = db.collection(PARTNERS_COLLECTION).where('email', '==', email).limit(1).stream()
            if next(partner_ref, None):
                return JsonResponse({'error': 'Partner with this email already exists'}, status=409)

            # Create new partner document
            # In a real app, hash the password before storing
            new_partner_data = {
                'email': email,
                'password': password, # HASH THIS in a real app: make_password(password)
                'name': name,
                'phone': phone,
                'is_verified': False, # Admin needs to verify
                'created_at': firestore.SERVER_TIMESTAMP
            }
            doc_ref = db.collection(PARTNERS_COLLECTION).add(new_partner_data)
            return JsonResponse({'message': 'Partner registration successful. Awaiting admin verification.', 'partner_id': doc_ref[1].id}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def partner_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                return JsonResponse({'error': 'Email and password are required'}, status=400)

            partners_ref = db.collection(PARTNERS_COLLECTION).where('email', '==', email).stream()
            partner_doc = next(partners_ref, None)

            if not partner_doc:
                return JsonResponse({'error': 'Invalid credentials'}, status=401)

            partner_data = partner_doc.to_dict()
            # In a real app, use check_password(password, partner_data.get('password'))
            if partner_data.get('password') != password: 
                return JsonResponse({'error': 'Invalid credentials'}, status=401)

            if not partner_data.get('is_verified'):
                return JsonResponse({'error': 'Partner account not verified by admin'}, status=403)

            # Generate JWT token
            payload = {
                'partner_id': partner_doc.id,
                'email': partner_data.get('email'),
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # Token expires in 24 hours
            }
            token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

            return JsonResponse({'message': 'Login successful', 'token': token, 'partner_id': partner_doc.id})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@admin_required # Assuming admin_required decorator from shop_admin.utils
def verify_partner(request, partner_id):
    if request.method == 'PATCH': # Use PATCH for partial updates
        try:
            partner_ref = db.collection(PARTNERS_COLLECTION).document(partner_id)
            partner_doc = partner_ref.get()

            if not partner_doc.exists:
                return JsonResponse({'error': 'Partner not found'}, status=404)

            partner_ref.update({'is_verified': True})
            return JsonResponse({'message': f'Partner {partner_id} verified successfully.'})
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@admin_required # Only admins can see all partners
def get_all_partners(request):
    if request.method == 'GET':
        try:
            partners_query = db.collection(PARTNERS_COLLECTION).stream()
            partners_list = []
            for partner_doc in partners_query:
                partner_data = partner_doc.to_dict()
                partner_data['partner_id'] = partner_doc.id
                # Optionally remove sensitive data like password before sending
                partner_data.pop('password', None) 
                partners_list.append(partner_data)
            return JsonResponse({'partners': partners_list})
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@partner_required
def delivery_assignment_list(request):
    # This view assumes orders are assigned to partners via a 'assigned_partner_id' field in the order document
    # and 'delivery_status' can be something like 'pending_assignment', 'assigned', 'out_for_delivery', 'delivered', 'cancelled'
    partner_id = request.partner_id # from partner_required decorator

    try:
        assigned_orders_query = db.collection(ORDERS_COLLECTION)\
                                  .where('assigned_partner_id', '==', partner_id)\
                                  .where('delivery_status', 'in', ['assigned', 'out_for_delivery'])\
                                  .stream()
        
        orders_list = []
        for order_doc in assigned_orders_query:
            order_data = order_doc.to_dict()
            order_data['order_id'] = order_doc.id
            orders_list.append(order_data)
            
        return JsonResponse({'assigned_deliveries': orders_list})
    except Exception as e:
        return JsonResponse({'error': f'An error occurred while fetching assignments: {str(e)}'}, status=500)

@csrf_exempt
@partner_required
def update_delivery_status(request, order_id):
    if request.method == 'PATCH':
        partner_id = request.partner_id
        try:
            data = json.loads(request.body)
            new_status = data.get('status') # e.g., "out_for_delivery", "delivered", "failed_attempt"

            if not new_status:
                return JsonResponse({'error': 'New status is required'}, status=400)
            
            valid_statuses = ['out_for_delivery', 'delivered', 'failed_attempt', 'returning'] # Define valid statuses a partner can set
            if new_status not in valid_statuses:
                return JsonResponse({'error': f'Invalid status. Must be one of {valid_statuses}'}, status=400)

            order_ref = db.collection(ORDERS_COLLECTION).document(order_id)
            order_doc = order_ref.get()

            if not order_doc.exists:
                return JsonResponse({'error': 'Order not found'}, status=404)
            
            order_data = order_doc.to_dict()
            if order_data.get('assigned_partner_id') != partner_id:
                return JsonResponse({'error': 'Order not assigned to this partner'}, status=403)

            # Update the delivery status and add a timestamped history entry
            status_update_history = order_data.get('status_update_history', [])
            status_update_history.append({
                'status': new_status,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'updated_by': 'partner',
                'partner_id': partner_id
            })

            order_ref.update({
                'delivery_status': new_status,
                'status_update_history': status_update_history,
                'last_updated': firestore.SERVER_TIMESTAMP
            })
            return JsonResponse({'message': f'Delivery status for order {order_id} updated to {new_status}.'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@partner_required
def delivery_history(request):
    partner_id = request.partner_id
    try:
        # Query orders that were assigned to this partner and are in a final state (e.g., delivered, cancelled, failed after max attempts)
        completed_orders_query = db.collection(ORDERS_COLLECTION)\
                                   .where('assigned_partner_id', '==', partner_id)\
                                   .where('delivery_status', 'in', ['delivered', 'cancelled', 'failed_final']) \
                                   .order_by('last_updated', direction=firestore.Query.DESCENDING)\
                                   .stream()
        
        history_list = []
        for order_doc in completed_orders_query:
            order_data = order_doc.to_dict()
            order_data['order_id'] = order_doc.id
            history_list.append(order_data)
            
        return JsonResponse({'delivery_history': history_list})
    except Exception as e:
        return JsonResponse({'error': f'An error occurred while fetching delivery history: {str(e)}'}, status=500)
