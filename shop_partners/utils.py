import jwt
import logging
from functools import wraps
from django.http import JsonResponse
from anand_mobiles.settings import SECRET_KEY # Assuming SECRET_KEY is in your project settings

# Set up logger for Partner authentication
logger = logging.getLogger(__name__)

def partner_required(view_func):
    """
    Decorator that validates Partner JWT tokens from the Authorization header.
    
    Expected format: Authorization: Bearer <Partner_token>
    
    On success: Adds request.partner_email, request.partner_id, and request.partner_payload (full JWT payload)
    On failure: Returns 401 response with specific error message
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            logger.warning(f"Partner access attempt without authorization header from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authorization header required',
                'code': 'AUTH_HEADER_MISSING'
            }, status=401)
        
        if not auth_header.startswith('Bearer '):
            logger.warning(f"Partner access attempt with invalid authorization format from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Invalid authorization format. Expected: Bearer <token>',
                'code': 'AUTH_FORMAT_INVALID'
            }, status=401)
        
        try:
            token = auth_header.split(' ')[1]
            if not token.strip():
                raise IndexError("Empty token")
        except IndexError:
            logger.warning(f"Partner access attempt with empty token from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authorization token is empty',
                'code': 'TOKEN_EMPTY'
            }, status=401)
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            
            email = payload.get('email')
            partner_id = payload.get('partner_id')

            if not email or not partner_id:
                logger.warning(f"Partner token missing required fields (email or partner_id) from {request.META.get('REMOTE_ADDR')}")
                return JsonResponse({
                    'error': 'Invalid token: missing required fields',
                    'code': 'TOKEN_INVALID_PAYLOAD'
                }, status=401)
            
            request.partner_email = email
            request.partner_id = partner_id
            request.partner_payload = payload
            
            logger.info(f"Partner '{email}' (ID: {partner_id}) authenticated successfully for {request.method} {request.path}")
            
            return view_func(request, *args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            logger.info(f"Partner access attempt with expired token from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authentication token has expired',
                'code': 'TOKEN_EXPIRED'
            }, status=401)
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"Partner access attempt with invalid token from {request.META.get('REMOTE_ADDR')}: {str(e)}")
            return JsonResponse({
                'error': 'Invalid authentication token',
                'code': 'TOKEN_INVALID'
            }, status=401)
            
        except Exception as e:
            logger.error(f"Unexpected partner authentication error from {request.META.get('REMOTE_ADDR')}: {str(e)}")
            return JsonResponse({
                'error': 'Authentication service error',
                'code': 'AUTH_SERVICE_ERROR'
            }, status=401)
    
    return wrapper
