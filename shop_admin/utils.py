import jwt
import logging
from functools import wraps
from django.http import JsonResponse
from anand_mobiles.settings import SECRET_KEY
import cloudinary
from anand_mobiles.settings import CLOUDINARY_URL
import cloudinary.uploader

# Set up logger for admin authentication
logger = logging.getLogger(__name__)

def admin_required(view_func):
    """
    Decorator that validates admin JWT tokens from the Authorization header.
    
    Expected format: Authorization: Bearer <admin_token>
    
    On success: Adds request.admin (username) and request.admin_payload (full JWT payload)
    On failure: Returns 401 response with specific error message
    
    Compatible with frontend admin API interceptors that handle 401 responses
    for automatic token cleanup and re-authentication.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get the authorization header
        auth_header = request.headers.get('Authorization')
        # Check for missing or malformed authorization header
        if not auth_header:
            logger.warning(f"Admin access attempt without authorization header from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authorization header required',
                'code': 'AUTH_HEADER_MISSING'
            }, status=401)
        
        if not auth_header.startswith('Bearer '):
            logger.warning(f"Admin access attempt with invalid authorization format from {request.META.get('REMOTE_ADDR')}")
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
            logger.warning(f"Admin access attempt with empty token from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authorization token is empty',
                'code': 'TOKEN_EMPTY'
            }, status=401)
        
        try:
            # Verify and decode the JWT token
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            
            # Validate required fields in token
            username = payload.get('username')
            if not username:
                logger.warning(f"Admin token missing username field from {request.META.get('REMOTE_ADDR')}")
                return JsonResponse({
                    'error': 'Invalid token: missing username',
                    'code': 'TOKEN_INVALID_PAYLOAD'
                }, status=401)
            
            # Add admin info to request object for use in views
            request.admin = username
            request.admin_payload = payload
            
            logger.info(f"Admin '{username}' authenticated successfully for {request.method} {request.path}")
            
            # Continue to the protected view
            return view_func(request, *args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            logger.info(f"Admin access attempt with expired token from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Authentication token has expired',
                'code': 'TOKEN_EXPIRED'
            }, status=401)
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"Admin access attempt with invalid token from {request.META.get('REMOTE_ADDR')}: {str(e)}")
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

def upload_image_to_cloudinary_util(image_file, folder_name="shop_images"):
    """
    Uploads an image file to Cloudinary and returns its secure URL.

    Args:
        image_file: The image file object to upload (e.g., request.FILES['image']).
        folder_name (str): The name of the folder in Cloudinary to upload the image to.

    Returns:
        str: The secure URL of the uploaded image, or None if upload fails.
    """
    if not image_file:
        logger.error("No image file provided for Cloudinary upload.")
        return None

    try:
        # Configure Cloudinary using CLOUDINARY_URL from settings.py
        if CLOUDINARY_URL:
            cloudinary.config(cloudinary_url=CLOUDINARY_URL, secure=True)
        else:
            logger.error("CLOUDINARY_URL is not set in settings.")
            return None

        upload_result = cloudinary.uploader.upload(
            image_file,
            folder=folder_name,
            # Additional upload options can be added here
        )
        
        secure_url = upload_result.get('secure_url')
        
        if secure_url:
            logger.info(f"Image uploaded successfully to Cloudinary: {secure_url}")
            return secure_url
        else:
            logger.error("Failed to upload image to Cloudinary. No secure_url in response.")
            return None
    except Exception as e:
        logger.error(f"Error uploading image to Cloudinary: {str(e)}")
        return None
