from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.product import Product
from app.schemas.product import ProductOut
from app.services.product_image_service import ensure_dataset_product_images, ensure_db_product_images

router = APIRouter()

@router.get("/", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).all()


@router.post("/images/ensure")
def ensure_product_images(
    force: bool = False,
    only_legacy: bool = False,
    limit: int | None = None,
    db: Session = Depends(get_db),
):
    db_summary = ensure_db_product_images(
        db,
        force_refresh=force,
        only_legacy=only_legacy,
        limit=limit,
    )
    dataset_summary = {} if only_legacy else ensure_dataset_product_images()
    return {"database": db_summary, "datasets": dataset_summary}
