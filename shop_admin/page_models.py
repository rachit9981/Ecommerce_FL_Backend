from django.db import models
from firebase_admin import firestore

# Get Firebase client
db = firestore.client()

class PageContent:
    """
    Model for storing static page content using Firebase Firestore.
    """
    COLLECTION_NAME = 'page_contents'
    
    def __init__(self, page_path=None, content=None, last_updated=None, doc_id=None):
        self.page_path = page_path
        self.content = content or ""
        self.last_updated = last_updated
        self.doc_id = doc_id or page_path  # Use page path as document ID
    
    def save(self):
        """Save the page content to Firestore"""
        from datetime import datetime
        doc_ref = db.collection(self.COLLECTION_NAME).document(self.doc_id)
        doc_ref.set({
            'page_path': self.page_path,
            'content': self.content,
            'last_updated': datetime.now()
        })
        return self
    
    @classmethod
    def get_by_path(cls, page_path):
        """Get page content by path from Firestore"""
        doc_ref = db.collection(cls.COLLECTION_NAME).document(page_path)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return cls(
                page_path=data.get('page_path'),
                content=data.get('content'),
                last_updated=data.get('last_updated'),
                doc_id=doc.id
            )
        return cls(page_path=page_path)  # Return empty content if not found
    
    @classmethod
    def update(cls, page_path, content):
        """Update or create page content"""
        instance = cls(page_path=page_path, content=content)
        return instance.save()
    
    def to_dict(self):
        """Convert page content to dictionary"""
        return {
            'page_path': self.page_path,
            'content': self.content,
            'last_updated': self.last_updated
        }
