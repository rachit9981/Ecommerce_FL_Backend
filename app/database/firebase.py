# Firebase initialization for FastAPI backend
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("config_anand.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
