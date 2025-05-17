from fastapi import APIRouter, HTTPException
from app.database.firebase import db
from app.schemas.schemas import OrderSchema

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/", response_model=OrderSchema)
def create_order(order: OrderSchema):
    db.collection('orders').document(order.orderId).set(order.dict())
    return order

@router.get("/", response_model=list[OrderSchema])
def get_orders():
    orders = db.collection('orders').stream()
    return [OrderSchema(**doc.to_dict()) for doc in orders]

@router.get("/{order_id}", response_model=OrderSchema)
def get_order(order_id: str):
    doc = db.collection('orders').document(order_id).get()
    if doc.exists:
        return OrderSchema(**doc.to_dict())
    raise HTTPException(status_code=404, detail="Order not found")

@router.put("/{order_id}", response_model=OrderSchema)
def update_order(order_id: str, order: OrderSchema):
    ref = db.collection('orders').document(order_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Order not found")
    ref.set(order.dict())
    return order

@router.delete("/{order_id}")
def delete_order(order_id: str):
    ref = db.collection('orders').document(order_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Order not found")
    ref.delete()
    return {"detail": "Order deleted"}
