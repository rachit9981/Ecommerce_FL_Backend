from fastapi import APIRouter, HTTPException
from app.database.firebase import db
from app.schemas.schemas import ProductSchema, UserSchema, OrderSchema, ReviewSchema, BannerSchema
from typing import List
from datetime import datetime
from app.routers import products_router, users_router, orders_router, reviews_router, banners_router

router = APIRouter()

router.include_router(products_router.router)
router.include_router(users_router.router)
router.include_router(orders_router.router)
router.include_router(reviews_router.router)
router.include_router(banners_router.router)

# Products CRUD
@router.get('/products', response_model=List[dict])
def get_products():
    products = db.collection('products').stream()
    return [doc.to_dict() for doc in products]

@router.get('/products/{product_id}', response_model=dict)
def get_product(product_id: str):
    doc = db.collection('products').document(product_id).get()
    if doc.exists:
        return doc.to_dict()
    raise HTTPException(status_code=404, detail='Product not found')

@router.post('/products', response_model=dict)
def create_product(product: ProductSchema):
    db.collection('products').document(product.productId).set(product.dict())
    return product.dict()

@router.put('/products/{product_id}', response_model=dict)
def update_product(product_id: str, product: ProductSchema):
    db.collection('products').document(product_id).update(product.dict())
    return product.dict()

@router.delete('/products/{product_id}')
def delete_product(product_id: str):
    db.collection('products').document(product_id).delete()
    return {'message': 'Product deleted'}

# Users CRUD
@router.get('/users', response_model=List[dict])
def get_users():
    users = db.collection('users').stream()
    return [doc.to_dict() for doc in users]

@router.get('/users/{user_id}', response_model=dict)
def get_user(user_id: str):
    doc = db.collection('users').document(user_id).get()
    if doc.exists:
        return doc.to_dict()
    raise HTTPException(status_code=404, detail='User not found')

@router.post('/users', response_model=dict)
def create_user(user: UserSchema):
    db.collection('users').document(user.userID).set(user.dict())
    return user.dict()

@router.put('/users/{user_id}', response_model=dict)
def update_user(user_id: str, user: UserSchema):
    db.collection('users').document(user_id).update(user.dict())
    return user.dict()

@router.delete('/users/{user_id}')
def delete_user(user_id: str):
    db.collection('users').document(user_id).delete()
    return {'message': 'User deleted'}

# Orders CRUD
@router.get('/orders', response_model=List[dict])
def get_orders():
    orders = db.collection('orders').stream()
    return [doc.to_dict() for doc in orders]

@router.get('/orders/{order_id}', response_model=dict)
def get_order(order_id: str):
    doc = db.collection('orders').document(order_id).get()
    if doc.exists:
        return doc.to_dict()
    raise HTTPException(status_code=404, detail='Order not found')

@router.post('/orders', response_model=dict)
def create_order(order: OrderSchema):
    db.collection('orders').document(order.orderId).set(order.dict())
    return order.dict()

@router.put('/orders/{order_id}', response_model=dict)
def update_order(order_id: str, order: OrderSchema):
    db.collection('orders').document(order_id).update(order.dict())
    return order.dict()

@router.delete('/orders/{order_id}')
def delete_order(order_id: str):
    db.collection('orders').document(order_id).delete()
    return {'message': 'Order deleted'}

# Reviews CRUD
@router.get('/reviews', response_model=List[dict])
def get_reviews():
    reviews = db.collection('reviews').stream()
    return [doc.to_dict() for doc in reviews]

@router.get('/reviews/{review_id}', response_model=dict)
def get_review(review_id: str):
    doc = db.collection('reviews').document(review_id).get()
    if doc.exists:
        return doc.to_dict()
    raise HTTPException(status_code=404, detail='Review not found')

@router.post('/reviews', response_model=dict)
def create_review(review: ReviewSchema):
    db.collection('reviews').document(review.reviewId).set(review.dict())
    return review.dict()

@router.put('/reviews/{review_id}', response_model=dict)
def update_review(review_id: str, review: ReviewSchema):
    db.collection('reviews').document(review_id).update(review.dict())
    return review.dict()

@router.delete('/reviews/{review_id}')
def delete_review(review_id: str):
    db.collection('reviews').document(review_id).delete()
    return {'message': 'Review deleted'}

# Banners CRUD
@router.get('/banners', response_model=List[dict])
def get_banners():
    banners = db.collection('banners').stream()
    return [doc.to_dict() for doc in banners]

@router.get('/banners/{banner_id}', response_model=dict)
def get_banner(banner_id: str):
    doc = db.collection('banners').document(banner_id).get()
    if doc.exists:
        return doc.to_dict()
    raise HTTPException(status_code=404, detail='Banner not found')

@router.post('/banners', response_model=dict)
def create_banner(banner: BannerSchema):
    db.collection('banners').document(banner.bannerId).set(banner.dict())
    return banner.dict()

@router.put('/banners/{banner_id}', response_model=dict)
def update_banner(banner_id: str, banner: BannerSchema):
    db.collection('banners').document(banner_id).update(banner.dict())
    return banner.dict()

@router.delete('/banners/{banner_id}')
def delete_banner(banner_id: str):
    db.collection('banners').document(banner_id).delete()
    return {'message': 'Banner deleted'}
