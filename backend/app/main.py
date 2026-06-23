from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
from app.api.routes import auth, products, cart, orders, voice, voice_to_text, text_to_speech, intent
from app.core.config import settings
from app.db.session import engine

app = FastAPI(title="E-commerce API")

DATASETS_DIR = Path(__file__).resolve().parents[2] / "datasets"


@app.on_event("startup")
def ensure_product_image_column() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS images VARCHAR[]"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_id VARCHAR"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer JSON"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS items JSON"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS pricing JSON"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment JSON"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery JSON"))
            conn.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS invoice_text VARCHAR"))
    except Exception:
        pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(cart.router, prefix="/cart", tags=["cart"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(voice.router, prefix="/voice", tags=["voice"])
app.include_router(voice_to_text.router, tags=["voice-to-text"])
app.include_router(text_to_speech.router, tags=["text-to-speech"])
app.include_router(intent.router, tags=["intent"])

if DATASETS_DIR.exists():
    app.mount("/datasets", StaticFiles(directory=str(DATASETS_DIR)), name="datasets")
