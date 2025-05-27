import jwt
import logging
from functools import wraps
from django.http import JsonResponse
from anand_mobiles.settings import SECRET_KEY

# Set up logger for User authentication
logger = logging.getLogger(__name__)

def user_required(view_func):
    """
    Decorator that validates User JWT tokens from the Authorization header.
    
    Expected format: Authorization: Bearer <User_token>
    
    On success: Adds request.User (username) and request.User_payload (full JWT payload)
    On failure: Returns 401 response with specific error message
    
    Compatible with frontend User API interceptors that handle 401 responses
    for automatic token cleanup and re-authentication.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get the authorization header
        auth_header = request.headers.get('Authorization')
        
        # Check for missing or malformed authorization header
        if not auth_header:
            logger.warning(f"User access attempt without authorization header from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authorization header required',
                'code': 'AUTH_HEADER_MISSING'
            }, status=401)
        
        if not auth_header.startswith('Bearer '):
            logger.warning(f"User access attempt with invalid authorization format from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Invalid authorization format. Expected: Bearer <token>',
                'code': 'AUTH_FORMAT_INVALID'
            }, status=401)
        
        # Extract the token
        try:
            token = auth_header.split(' ')[1]
            if not token.strip():
                raise IndexError("Empty token")
        except IndexError:
            logger.warning(f"User access attempt with empty token from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authorization token is empty',
                'code': 'TOKEN_EMPTY'
            }, status=401)
        
        try:
            # Verify and decode the JWT token
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            
            # Validate required fields in token
            email = payload.get('email')
            if not email:
                logger.warning(f"User token missing email field from {request.META.get('REMOTE_ADDR')}")
                return JsonResponse({
                    'error': 'Invalid token: missing email field',
                    'code': 'TOKEN_INVALID_PAYLOAD'
                }, status=401)
            
            # Add user info to request object for use in views
            request.user_email = email
            request.user_id = payload.get('user_id')
            request.user_payload = payload
            
            logger.info(f"User '{email}' authenticated successfully for {request.method} {request.path}")
            
            # Continue to the protected view
            return view_func(request, *args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            logger.info(f"User access attempt with expired token from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authentication token has expired',
                'code': 'TOKEN_EXPIRED'
            }, status=401)
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"User access attempt with invalid token from {request.META.get('REMOTE_ADDR')}: {str(e)}")
            return JsonResponse({
                'error': 'Invalid authentication token',
                'code': 'TOKEN_INVALID'
            }, status=401)
            
        except Exception as e:
            logger.error(f"Unexpected authentication error from {request.META.get('REMOTE_ADDR')}: {str(e)}")
            return JsonResponse({
                'error': 'Authentication service error',
                'code': 'AUTH_SERVICE_ERROR'
            }, status=401)
    
    return wrapper