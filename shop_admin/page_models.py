from django.db import models
from firebase_admin import firestore

# Get Firebase client
db = firestore.client()

class PageContent:
    """
    Model for storing static page content using Firebase Firestore.
    """
    COLLECTION_NAME = 'page_contents'
    
    def __init__(self, page_path=None, content=None, last_updated=None, doc_id=None, title=None, is_custom=False):
        self.page_path = page_path
        self.content = content or ""
        self.last_updated = last_updated
        self.doc_id = doc_id or page_path  # Use page path as document ID
        self.title = title or self._generate_title_from_path(page_path)
        self.is_custom = is_custom
    
    def _generate_title_from_path(self, path):
        """Generate a title from the path"""
        if not path:
            return ""
        words = path.replace('-', ' ').split()
        return ' '.join(word.capitalize() for word in words)
    
    def save(self):
        """Save the page content to Firestore"""
        from datetime import datetime
        doc_ref = db.collection(self.COLLECTION_NAME).document(self.doc_id)
        doc_ref.set({
            'page_path': self.page_path,
            'content': self.content,
            'last_updated': datetime.now(),
            'title': self.title,
            'is_custom': self.is_custom
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
                doc_id=doc.id,
                title=data.get('title', ''),
                is_custom=data.get('is_custom', False)
            )
        return cls(page_path=page_path)  # Return empty content if not found
    
    @classmethod
    def update(cls, page_path, content, is_custom=False):
        """Update or create page content"""
        instance = cls(page_path=page_path, content=content, is_custom=is_custom)
        return instance.save()
    
    def to_dict(self):
        """Convert page content to dictionary"""
        return {
            'page_path': self.page_path,
            'content': self.content,
            'last_updated': self.last_updated,
            'title': self.title,
            'is_custom': self.is_custom
        }
    
    @classmethod
    def get_all(cls):
        """Get all pages from Firestore"""
        docs = db.collection(cls.COLLECTION_NAME).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            instance = cls(
                page_path=data.get('page_path'),
                content=data.get('content'),
                last_updated=data.get('last_updated'),
                doc_id=doc.id,
                title=data.get('title', ''),
                is_custom=data.get('is_custom', False)
            )
            results.append(instance)
        return results
    
    def delete(self):
        """Delete the page content from Firestore"""
        if not self.doc_id:
            return False
        db.collection(self.COLLECTION_NAME).document(self.doc_id).delete()
        return True
    
    def to_dict(self):
        """Convert page content to dictionary"""
        return {
            'page_path': self.page_path,
            'content': self.content,
            'last_updated': self.last_updated
        }
