from fastapi import APIRouter, HTTPException
from app.database.firebase import db
from app.schemas.schemas import ProductSchema

router = APIRouter(prefix="/products", tags=["products"])

@router.post("/", response_model=ProductSchema)
def create_product(product: ProductSchema):
    db.collection('products').document(product.productId).set(product.dict())
    return product

@router.get("/", response_model=list[ProductSchema])
def get_products():
    products = db.collection('products').stream()
    return [ProductSchema(**doc.to_dict()) for doc in products]

@router.get("/{product_id}", response_model=ProductSchema)
def get_product(product_id: str):
    doc = db.collection('products').document(product_id).get()
    if doc.exists:
        return ProductSchema(**doc.to_dict())
    raise HTTPException(status_code=404, detail="Product not found")

@router.put("/{product_id}", response_model=ProductSchema)
def update_product(product_id: str, product: ProductSchema):
    ref = db.collection('products').document(product_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Product not found")
    ref.set(product.dict())
    return product

@router.delete("/{product_id}")
def delete_product(product_id: str):
    ref = db.collection('products').document(product_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Product not found")
    ref.delete()
    return {"detail": "Product deleted"}
