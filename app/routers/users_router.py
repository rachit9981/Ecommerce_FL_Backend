from fastapi import APIRouter, HTTPException
from app.database.firebase import db
from app.schemas.schemas import UserSchema

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserSchema)
def create_user(user: UserSchema):
    db.collection('users').document(user.userID).set(user.dict())
    return user

@router.get("/", response_model=list[UserSchema])
def get_users():
    users = db.collection('users').stream()
    return [UserSchema(**doc.to_dict()) for doc in users]

@router.get("/{user_id}", response_model=UserSchema)
def get_user(user_id: str):
    doc = db.collection('users').document(user_id).get()
    if doc.exists:
        return UserSchema(**doc.to_dict())
    raise HTTPException(status_code=404, detail="User not found")

@router.put("/{user_id}", response_model=UserSchema)
def update_user(user_id: str, user: UserSchema):
    ref = db.collection('users').document(user_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")
    ref.set(user.dict())
    return user

@router.delete("/{user_id}")
def delete_user(user_id: str):
    ref = db.collection('users').document(user_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")
    ref.delete()
    return {"detail": "User deleted"}
