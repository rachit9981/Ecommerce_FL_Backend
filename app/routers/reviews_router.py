from fastapi import APIRouter, HTTPException
from app.database.firebase import db
from app.schemas.schemas import ReviewSchema

router = APIRouter(prefix="/reviews", tags=["reviews"])

@router.post("/", response_model=ReviewSchema)
def create_review(review: ReviewSchema):
    db.collection('reviews').document(review.reviewId).set(review.dict())
    return review

@router.get("/", response_model=list[ReviewSchema])
def get_reviews():
    reviews = db.collection('reviews').stream()
    return [ReviewSchema(**doc.to_dict()) for doc in reviews]

@router.get("/{review_id}", response_model=ReviewSchema)
def get_review(review_id: str):
    doc = db.collection('reviews').document(review_id).get()
    if doc.exists:
        return ReviewSchema(**doc.to_dict())
    raise HTTPException(status_code=404, detail="Review not found")

@router.put("/{review_id}", response_model=ReviewSchema)
def update_review(review_id: str, review: ReviewSchema):
    ref = db.collection('reviews').document(review_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Review not found")
    ref.set(review.dict())
    return review

@router.delete("/{review_id}")
def delete_review(review_id: str):
    ref = db.collection('reviews').document(review_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Review not found")
    ref.delete()
    return {"detail": "Review deleted"}
