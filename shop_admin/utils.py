import jwt
from functools import wraps
from django.http import JsonResponse
from anand_mobiles.settings import SECRET_KEY

def admin_required(view_func):
    """
    Middleware decorator that checks for valid admin JWT token in the
    Authorization header and adds the admin username to the request object.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get the authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authentication required!'}, status=401)
        
        # Extract the token
        token = auth_header.split(' ')[1]
        
        try:
            # Verify the token
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            
            # Add admin username to request object
            request.admin = payload.get('username')
            
            # Continue to the view if token is valid
            return view_func(request, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return JsonResponse({'error': 'Token has expired!'}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({'error': 'Invalid token!'}, status=401)
        except Exception as e:
            return JsonResponse({'error': f'Authentication error: {str(e)}'}, status=401)
    
    return wrapper