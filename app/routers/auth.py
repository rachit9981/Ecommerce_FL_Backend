from fastapi import APIRouter, HTTPException, status
from firebase_admin import auth, firestore
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from app.database.firebase import db

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

class UserSignUp(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    uid: str
    email: str
    display_name: Optional[str] = None
    is_new_user: bool = False
    token: str

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserSignUp):
    try:
        user = auth.create_user(
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.display_name,
            phone_number=user_data.phone_number
        )
        
        user_doc = {
            "email": user_data.email,
            "display_name": user_data.display_name,
            "phone_number": user_data.phone_number,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        db.collection("users").document(user.uid).set(user_doc)
        
        token = auth.create_custom_token(user.uid)
        
        return UserResponse(
            uid=user.uid,
            email=user.email,
            display_name=user.display_name,
            is_new_user=True,
            token=token.decode('utf-8')
        )
        
    except auth.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/login", response_model=UserResponse)
async def login(user_data: UserLogin):
    try:
        try:
            user = auth.get_user_by_email(user_data.email)
            token = auth.create_custom_token(user.uid)
            
            return UserResponse(
                uid=user.uid,
                email=user.email,
                display_name=user.display_name,
                token=token.decode('utf-8')
            )
        except auth.UserNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

def verify_token(token: str):
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"Invalid token: {str(e)}"
        )
