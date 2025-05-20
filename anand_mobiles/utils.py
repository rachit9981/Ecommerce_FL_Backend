import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from functools import wraps

User = get_user_model()

def generate_jwt_token(user_id, expiry_days=1):
    """
    Generate a JWT token for authentication
    
    Args:
        user_id: The ID of the user
        expiry_days: Number of days until token expires (default: 1)
        
    Returns:
        str: JWT token
    """
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=expiry_days),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token


def verify_jwt_token(token):
    """
    Verify the JWT token and return the user
    
    Args:
        token: JWT token to verify
        
    Returns:
        User object if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        
        # Check if token is expired
        if datetime.utcfromtimestamp(payload.get('exp')) < datetime.utcnow():
            return None
        
        # Get the user
        user = User.objects.filter(id=user_id).first()
        return user
    except jwt.PyJWTError:
        return None


def jwt_auth_middleware(view_func):
    """
    Middleware decorator that verifies JWT token in the Authorization header
    
    Usage:
        @jwt_auth_middleware
        def your_view(request):
            # Your view logic here
            # request.user is now available
            pass
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'error': 'Authentication credentials not provided or invalid format',
                'status': 'error'
            }, status=401)
        
        token = auth_header.split(' ')[1]
        user = verify_jwt_token(token)
        
        if not user:
            return JsonResponse({
                'error': 'Invalid or expired token',
                'status': 'error'
            }, status=401)
        
        # Attach the user to the request
        request.user = user
        return view_func(request, *args, **kwargs)
    
    return wrapper