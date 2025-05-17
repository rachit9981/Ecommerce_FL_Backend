from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class ProductSchema(BaseModel):
    productId: str
    variants: Dict
    images: List[str]
    category: str
    brand: str
    price: float
    discount: float
    stock: int
    description: str
    specs: Dict

class UserSchema(BaseModel):
    userID: str
    orders: Optional[List[str]] = []
    wishlists: Optional[List[str]] = []
    carts: Optional[List[str]] = []
    email: str
    phone_number: str
    address: str
    pincode: int
    firstName: str
    lastName: str
    type: str  # admin, user, delivery

class OrderSchema(BaseModel):
    orderId: str
    userId: str
    productId: str
    totalPrice: float
    status: str
    shippingAddress: str
    paymentMethod: str
    orderDate: datetime
    deliveryDate: Optional[datetime] = None
    trackingNumber: Optional[int] = None

class ReviewSchema(BaseModel):
    reviewId: str
    userId: str
    productId: str
    rating: int
    comment: str
    reviewDate: datetime

class BannerSchema(BaseModel):
    bannerId: str
    link: str
    position: int
