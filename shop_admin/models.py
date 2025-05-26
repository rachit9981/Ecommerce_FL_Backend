from django.db import models
from django.conf import settings
from firebase_admin import firestore
import uuid

# Get Firebase client from settings
db = firestore.client()

# Create your models here.
class ShopAdmin:
    """
    Model representing a shop admin using Firebase Firestore.
    """
    COLLECTION_NAME = 'shop_admins'
    
    def __init__(self, username=None, password=None, admin_id=None):
        self.username = username
        self.password = password
        self.admin_id = admin_id or str(uuid.uuid4())
    
    def save(self):
        """Save the shop admin to Firestore"""
        doc_ref = db.collection(self.COLLECTION_NAME).document(self.admin_id)
        doc_ref.set({
            'username': self.username,
            'password': self.password,
            'admin_id': self.admin_id
        })
        return self
    
    @classmethod
    def get_by_id(cls, admin_id):
        """Get shop admin by ID from Firestore"""
        doc_ref = db.collection(cls.COLLECTION_NAME).document(admin_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return cls(
                username=data.get('username'),
                password=data.get('password'),
                admin_id=data.get('admin_id')
            )
        return None
    
    @classmethod
    def get_by_username(cls, username):
        """Get shop admin by username from Firestore"""
        docs = db.collection(cls.COLLECTION_NAME).where('username', '==', username).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            return cls(
                username=data.get('username'),
                password=data.get('password'),
                admin_id=data.get('admin_id')
            )
        return None
    
    @classmethod
    def exists_by_username(cls, username):
        """Check if shop admin exists by username"""
        docs = db.collection(cls.COLLECTION_NAME).where('username', '==', username).limit(1).stream()
        return any(True for _ in docs)
    
    @classmethod
    def create(cls, username, password):
        """Create a new shop admin"""
        admin = cls(username=username, password=password)
        return admin.save()
    
    @classmethod
    def get_all(cls):
        """Get all shop admins from Firestore"""
        docs = db.collection(cls.COLLECTION_NAME).stream()
        admins = []
        for doc in docs:
            data = doc.to_dict()
            admins.append(cls(
                username=data.get('username'),
                password=data.get('password'),
                admin_id=data.get('admin_id')
            ))
        return admins
    
    def to_dict(self):
        """Convert shop admin to dictionary"""
        return {
            'admin_id': self.admin_id,
            'username': self.username,
            'password': self.password
        }
    
    def __str__(self):
        return self.username

# Keep the Django model for backwards compatibility if needed
class ShopAdminDjango(models.Model):
    """
    Django model for shop admin (kept for backwards compatibility).
    """
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)

    def __str__(self):
        return self.username