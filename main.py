from fastapi import FastAPI
from app.database.firebase import db

app = FastAPI()

@app.get("/")
def read_root():
    products = db.collection('products').stream()
    return {"products": [doc.to_dict() for doc in products]}

@app.get("/products/{product_id}")
def read_product(product_id: str):
    product_ref = db.collection('products').document(product_id)
    product = product_ref.get()
    if product.exists:
        return {"product": product.to_dict()}
    else:
        return {"error": "Product not found"}, 404
