from fastapi import APIRouter, HTTPException
from app.database.firebase import db
from app.schemas.schemas import BannerSchema

router = APIRouter(prefix="/banners", tags=["banners"])

@router.post("/", response_model=BannerSchema)
def create_banner(banner: BannerSchema):
    db.collection('banners').document(banner.bannerId).set(banner.dict())
    return banner

@router.get("/", response_model=list[BannerSchema])
def get_banners():
    banners = db.collection('banners').stream()
    return [BannerSchema(**doc.to_dict()) for doc in banners]

@router.get("/{banner_id}", response_model=BannerSchema)
def get_banner(banner_id: str):
    doc = db.collection('banners').document(banner_id).get()
    if doc.exists:
        return BannerSchema(**doc.to_dict())
    raise HTTPException(status_code=404, detail="Banner not found")

@router.put("/{banner_id}", response_model=BannerSchema)
def update_banner(banner_id: str, banner: BannerSchema):
    ref = db.collection('banners').document(banner_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Banner not found")
    ref.set(banner.dict())
    return banner

@router.delete("/{banner_id}")
def delete_banner(banner_id: str):
    ref = db.collection('banners').document(banner_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Banner not found")
    ref.delete()
    return {"detail": "Banner deleted"}
