from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError

User = get_user_model()

class FirebaseAuthenticationBackend(ModelBackend):
    """
    Custom authentication backend that authenticates using Firebase.
    """
    def authenticate(self, request, firebase_id_token=None, **kwargs):
        """
        Authenticate a user based on Firebase ID token.
        """
        if not firebase_id_token:
            return None
            
        try:
            # Verify the Firebase ID token
            decoded_token = firebase_auth.verify_id_token(firebase_id_token)
            uid = decoded_token['uid']
            
            # Try to find user with this Firebase UID
            try:
                user = User.objects.get(firebase_uid=uid)
                return user
            except User.DoesNotExist:
                # If user doesn't exist, we need to create one based on the Firebase user
                try:
                    firebase_user = firebase_auth.get_user(uid)
                    return User.create_firebase_user(firebase_user)
                except FirebaseError:
                    return None
                    
        except (FirebaseError, ValueError):
            # Invalid token or other Firebase error
            return None

    def get_user(self, user_id):
        """
        Get a User object from the user_id.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


class EmailPasswordBackend(ModelBackend):
    """
    Custom authentication backend for email/password authentication
    """
    def authenticate(self, request, email=None, password=None, **kwargs):
        if email is None or password is None:
            return None
            
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None