from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import jwt
from datetime import datetime, timedelta
from firebase_admin import firestore
from anand_mobiles.settings import SECRET_KEY # Assuming SECRET_KEY is in your project settings
from .utils import partner_required # Import the new decorator
from shop_admin.utils import admin_required # For admin verification

# Get Firebase client
db = firestore.client()
PARTNERS_COLLECTION = 'delivery_partners'

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
                'created_at': datetime.now()
            }
            doc_ref = db.collection(PARTNERS_COLLECTION).add(new_partner_data)
            return JsonResponse({'message': 'Partner registration successful. Awaiting admin verification.', 'partner_id': doc_ref[1].id}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
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
            if not partner_data:
                return JsonResponse({'error': 'Invalid partner data'}, status=500)
                
            # In a real app, use check_password(password, partner_data.get('password'))
            stored_password = partner_data.get('password')
            if stored_password != password: 
                return JsonResponse({'error': 'Invalid credentials'}, status=401)

            if not partner_data.get('is_verified', False):
                return JsonResponse({'error': 'Partner account not verified by admin'}, status=403)

            # Generate JWT token
            payload = {
                'partner_id': partner_doc.id,
                'email': partner_data.get('email', ''),
                'exp': datetime.now() + timedelta(hours=24) # Token expires in 24 hours
            }
            # Ensure SECRET_KEY is not None
            if not SECRET_KEY:
                return JsonResponse({'error': 'Server configuration error'}, status=500)
                
            token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

            return JsonResponse({'message': 'Login successful', 'token': token, 'partner_id': partner_doc.id})
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"Error during partner login: {str(e)}")  # Log the error for debugging
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
def get_assigned_orders(request):
    """Fetch all orders currently assigned to the logged-in delivery partner that are not yet in a final state."""
    partner_id = request.partner_id 

    try:
        orders_list = []
        # Fetch orders from all users since orders are stored as subcollections under users
        users_ref = db.collection('users').stream()
        
        for user_doc in users_ref:
            user_id = user_doc.id
            # Get orders for each user that are assigned to this partner
            # Filter by assigned_partner_id only, then check status in the loop
            orders_ref = db.collection('users').document(user_id).collection('orders')\
                          .where('assigned_partner_id', '==', partner_id)\
                          .stream()
            
            for order_doc in orders_ref:
                order_data = order_doc.to_dict()
                
                # Check if order is in a final state, skip if so
                delivery_status = order_data.get('delivery_status')
                order_status = order_data.get('status')
                
                # Skip orders that are in final states
                final_delivery_statuses = ['delivered', 'cancelled_by_admin', 'cancelled_by_user', 'cancelled', 'failed_final']
                final_order_statuses = ['cancelled', 'delivered', 'refunded']
                
                if delivery_status in final_delivery_statuses or order_status in final_order_statuses:
                    continue
                
                # Calculate total item count from order_items
                order_items = order_data.get('order_items', [])
                total_item_count = 0
                if order_items:
                    for item in order_items:
                        item_quantity = item.get('quantity', 1)
                        total_item_count += item_quantity
                
                # Add any other relevant details you want to show in the list
                orders_list.append({
                    'order_id': order_doc.id,
                    'user_id': user_id,
                    'status': order_data.get('status'),
                    'delivery_status': order_data.get('delivery_status'),
                    'assigned_at': order_data.get('assigned_at'),
                    'assigned_partner_name': order_data.get('assigned_partner_name'),
                    'total_amount': order_data.get('total_amount'),
                    'currency': order_data.get('currency', 'INR'),
                    'item_count': total_item_count,
                    'order_items': order_items,
                    'customer_name': order_data.get('address', {}).get('name') or order_data.get('shipping_address', {}).get('name'),
                    'customer_phone': order_data.get('address', {}).get('phone_number') or order_data.get('shipping_address', {}).get('phone_number'),
                    'delivery_address': {
                        'street_address': order_data.get('address', {}).get('street_address') or order_data.get('shipping_address', {}).get('address_line_1'),
                        'city': order_data.get('address', {}).get('city') or order_data.get('shipping_address', {}).get('city'),
                        'state': order_data.get('address', {}).get('state') or order_data.get('shipping_address', {}).get('state'),
                        'postal_code': order_data.get('address', {}).get('postal_code') or order_data.get('shipping_address', {}).get('postal_code')
                    },
                    'created_at': order_data.get('created_at'),
                    'estimated_delivery': order_data.get('estimated_delivery')
                })
            
        return JsonResponse({'assigned_orders': orders_list})
    except Exception as e:
        # Consider logging the error
        return JsonResponse({'error': f'An error occurred while fetching assigned orders: {str(e)}'}, status=500)

@csrf_exempt
@partner_required
def get_assigned_order_details(request, order_id):
    """Fetch details of a specific order assigned to the logged-in delivery partner."""
    partner_id = request.partner_id

    try:
        # Search for the order across all users since orders are stored as subcollections
        order_found = False
        order_data = None
        user_id = None
        
        users_ref = db.collection('users').stream()
        for user_doc in users_ref:
            user_id = user_doc.id
            order_ref = db.collection('users').document(user_id).collection('orders').document(order_id)
            order_doc = order_ref.get()
            
            if order_doc.exists:
                order_data = order_doc.to_dict()
                order_found = True
                break

        if not order_found:
            return JsonResponse({'error': 'Order not found'}, status=404)
        
        if order_data.get('assigned_partner_id') != partner_id:
            return JsonResponse({'error': 'Access denied. This order is not assigned to you.'}, status=403)
            
        # Prepare detailed order information
        # You might want to fetch product details for items, etc.
        # For now, returning the raw order data along with the ID
        order_data['order_id'] = order_id
        order_data['user_id'] = user_id
            
        return JsonResponse({'order_details': order_data})
            
    except Exception as e:
        # Consider logging the error
        return JsonResponse({'error': f'An error occurred while fetching order details: {str(e)}'}, status=500)

@csrf_exempt
@partner_required
def update_order_status_by_partner(request, order_id): # Renamed from update_delivery_status
    """Allows a delivery partner to update the status of an order assigned to them."""
    if request.method == 'PATCH':
        partner_id = request.partner_id
        try:
            data = json.loads(request.body)
            new_status = data.get('status') 
            notes = data.get('notes', '') # Optional notes from partner
            estimated_delivery = data.get('estimated_delivery') # Get estimated delivery date if provided
            carrier = data.get('carrier', '') # Get carrier name if provided
            tracking_number = data.get('tracking_number', '') # Get tracking number if provided

            if not new_status:
                return JsonResponse({'error': 'New status is required'}, status=400)              # Define valid statuses a partner can set. Admin might have more control.
            valid_partner_statuses = ['out_for_delivery', 'delivered', 'failed_attempt', 'returning_to_warehouse', 'shipped', 'processing', 'packed', 'other'] 
            if new_status not in valid_partner_statuses:
                return JsonResponse({'error': f'Invalid status. Must be one of {valid_partner_statuses}'}, status=400)            # Search for the order across all users since orders are stored as subcollections
            order_found = False
            order_ref = None
            user_id = None
            order_doc = None
            
            users_ref = db.collection('users').stream()
            for user_doc in users_ref:
                user_id = user_doc.id
                order_ref = db.collection('users').document(user_id).collection('orders').document(order_id)
                order_doc = order_ref.get()
                if order_doc.exists:
                    order_found = True
                    break
                    
            if not order_found or not order_ref or not order_doc:
                return JsonResponse({'error': 'Order not found'}, status=404)
            
            order_data = order_doc.to_dict() if order_doc else {}
            if order_data.get('assigned_partner_id') != partner_id:
                return JsonResponse({'error': 'Order not assigned to this partner or access denied'}, status=403)            # Prevent updating status of already delivered or cancelled orders by partner
            if order_data.get('delivery_status') in ['delivered', 'cancelled_by_admin', 'cancelled_by_user']:
                 return JsonResponse({'error': f'Order is already in a final state: {order_data.get("delivery_status")}'}, status=400)

            # Update the delivery status and add a timestamped history entry
            # Use tracking_info.status_history to align with admin logic
            tracking_info = order_data.get('tracking_info', {})
            status_history = tracking_info.get('status_history', [])            # Add new status entry to tracking_info.status_history
            status_description = f'Order status updated to {new_status} by delivery partner.'
            
            # Handle 'other' status and extract the custom status text
            if new_status == 'other' and notes and notes.startswith('Custom status:'):
                custom_status = notes.split('Custom status:')[1].split('-')[0].strip()
                status_description = f'Order status updated to {custom_status} by delivery partner.'
                # For display purposes in OrderTrackingDetail, keep the custom text
                history_entry_status = custom_status
            else:
                history_entry_status = new_status
            
            history_entry = {
                'timestamp': datetime.now(),
                'updated_by': 'partner',
                'partner_id': partner_id,
                'status': history_entry_status,
                'description': status_description
            }
            
            if notes:
                history_entry['notes'] = notes
            if estimated_delivery:
                history_entry['estimated_delivery'] = estimated_delivery
            status_history.append(history_entry)            # Get the existing tracking info or create a new one
            tracking_info = order_data.get('tracking_info', {})
            
            # Set the status history
            tracking_info['status_history'] = status_history
            
            # Prepare the update payload
            update_payload = {
                'delivery_status': new_status,
                'tracking_info': tracking_info,
                'last_updated_by_partner_at': datetime.now() # Specific timestamp for partner update
            }
            
            # If carrier and tracking number are provided, add them to tracking_info
            if carrier:
                update_payload['tracking_info']['carrier'] = carrier
            
            if tracking_number:
                update_payload['tracking_info']['tracking_number'] = tracking_number
                # Create a tracking URL if carrier is recognized
                if carrier and carrier.lower() in ['fedex', 'ups', 'usps', 'dhl']:
                    tracking_url = ""
                    if carrier.lower() == 'fedex':
                        tracking_url = f"https://www.fedex.com/apps/fedextrack/?tracknumbers={tracking_number}"
                    elif carrier.lower() == 'ups':
                        tracking_url = f"https://www.ups.com/track?tracknum={tracking_number}"
                    elif carrier.lower() == 'usps':
                        tracking_url = f"https://tools.usps.com/go/TrackConfirmAction?tLabels={tracking_number}"
                    elif carrier.lower() == 'dhl':
                        tracking_url = f"https://www.dhl.com/en/express/tracking.html?AWB={tracking_number}"
                    
                    if tracking_url:
                        update_payload['tracking_info']['tracking_url'] = tracking_url
            
            # If estimated delivery date is provided, add it to the update payload
            if estimated_delivery:
                update_payload['estimated_delivery'] = estimated_delivery
            
            # If status is 'delivered', add delivered_at timestamp
            if new_status == 'delivered':
                update_payload['delivered_at'] = datetime.now()
            
            order_ref.update(update_payload)
            return JsonResponse({'message': f'Delivery status for order {order_id} updated to {new_status}.'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            # Consider logging the error
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method. Use PATCH.'}, status=405)

@csrf_exempt
@partner_required
def delivery_history(request):
    partner_id = request.partner_id
    try:
        history_list = []
        # Query orders from all users since orders are stored as subcollections under users
        users_ref = db.collection('users').stream()
        
        for user_doc in users_ref:
            user_id = user_doc.id
            # Query orders that were assigned to this partner and are in a final state
            completed_orders_query = db.collection('users').document(user_id).collection('orders')\
                                       .where('assigned_partner_id', '==', partner_id)\
                                       .where('delivery_status', 'in', ['delivered', 'cancelled', 'failed_final']) \
                                       .stream()
            
            for order_doc in completed_orders_query:
                order_data = order_doc.to_dict()
                order_data['order_id'] = order_doc.id
                order_data['user_id'] = user_id
                history_list.append(order_data)
            
        return JsonResponse({'delivery_history': history_list})
    except Exception as e:
        return JsonResponse({'error': f'An error occurred while fetching delivery history: {str(e)}'}, status=500)

@csrf_exempt
@partner_required
def get_partner_profile(request):
    """Get the profile details of the logged-in delivery partner."""
    if request.method == 'GET':
        partner_id = request.partner_id
        try:
            partner_ref = db.collection(PARTNERS_COLLECTION).document(partner_id)
            partner_doc = partner_ref.get()
            
            if not partner_doc.exists:
                return JsonResponse({'error': 'Partner not found'}, status=404)
            
            partner_data = partner_doc.to_dict()
            # Remove sensitive data before sending
            partner_data.pop('password', None)
            partner_data['partner_id'] = partner_id
            
            return JsonResponse({'partner': partner_data})
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@partner_required
def update_partner_profile(request):
    """Update the profile details of the logged-in delivery partner."""
    if request.method == 'PATCH':
        partner_id = request.partner_id
        try:
            data = json.loads(request.body)
            
            # Get current partner data
            partner_ref = db.collection(PARTNERS_COLLECTION).document(partner_id)
            partner_doc = partner_ref.get()
            
            if not partner_doc.exists:
                return JsonResponse({'error': 'Partner not found'}, status=404)
            
            current_data = partner_doc.to_dict()
            
            # Prepare update data
            update_data = {}
            
            # Update basic profile fields
            if 'name' in data:
                update_data['name'] = data['name']
            if 'phone' in data:
                update_data['phone'] = data['phone']
            if 'address' in data:
                update_data['address'] = data['address']
            if 'vehicle_type' in data:
                update_data['vehicle_type'] = data['vehicle_type']
            if 'vehicle_number' in data:
                update_data['vehicle_number'] = data['vehicle_number']
            
            # Handle password change if provided
            if 'current_password' in data and 'new_password' in data:
                current_password = data.get('current_password')
                new_password = data.get('new_password')
                
                # Verify current password (in production, use proper password hashing)
                if current_data.get('password') != current_password:
                    return JsonResponse({'error': 'Current password is incorrect'}, status=400)
                
                if len(new_password) < 6:
                    return JsonResponse({'error': 'New password must be at least 6 characters'}, status=400)
                
                update_data['password'] = new_password  # In production, hash this
            
            # Add update timestamp
            update_data['updated_at'] = datetime.now()
            
            # Update the document
            partner_ref.update(update_data)
            
            return JsonResponse({'message': 'Profile updated successfully'})
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method. Use PATCH.'}, status=405)
