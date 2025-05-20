from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from firebase_admin import auth as firebase_auth
import uuid

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError('Users must have an email address')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        # If user has a password (not OAuth), set it
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
            
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Creates and saves a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model that supports using email instead of username
    and integrates with Firebase Authentication
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    
    # Firebase UID for OAuth users
    firebase_uid = models.CharField(max_length=128, blank=True, null=True, unique=True)
    
    # Provider information
    auth_provider = models.CharField(max_length=50, blank=True, null=True)  # 'email', 'google', etc.
    
    # Standard Django user model fields
    date_joined = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_short_name(self):
        return self.first_name
    
    @classmethod
    def create_firebase_user(cls, firebase_user_record):
        """
        Create a user from Firebase auth information
        """
        # Extract user data from Firebase auth
        email = firebase_user_record.email
        uid = firebase_user_record.uid
        
        # Create or update user in Django
        user, created = cls.objects.get_or_create(
            email=email,
            defaults={
                'firebase_uid': uid,
                'first_name': firebase_user_record.display_name.split()[0] if firebase_user_record.display_name else '',
                'last_name': ' '.join(firebase_user_record.display_name.split()[1:]) if firebase_user_record.display_name and len(firebase_user_record.display_name.split()) > 1 else '',
                'auth_provider': firebase_user_record.provider_id,
                'is_active': True
            }
        )
        
        # If user existed but didn't have Firebase UID, update it
        if not created and not user.firebase_uid:
            user.firebase_uid = uid
            user.auth_provider = firebase_user_record.provider_id
            user.save()
        
        return user
