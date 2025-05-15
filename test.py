import firebase_admin
from firebase_admin import credentials, auth, firestore

# Initialize Firebase app
cred = credentials.Certificate("config_anand.json")
firebase_admin.initialize_app(cred)

# Firestore client
db = firestore.client()
print("Firestore client initialized.")