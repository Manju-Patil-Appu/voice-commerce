from __future__ import annotations

import os
import random
import re
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BASE_DIR.parent
DATASET_IMAGE_DIR = REPO_DIR / "datasets" / "images"
sys.path.append(str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.example")
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:password@localhost:5432/ecommerce"
if not os.getenv("JWT_SECRET"):
    os.environ["JWT_SECRET"] = "change-me"

from app.db.session import SessionLocal
from app.models.product import Product
from app.services.product_image_service import ensure_db_product_images


TOTAL_PRODUCTS = 240

CATEGORIES = [
    "Running Shoes",
    "Casual Shoes",
    "Sports Shoes",
    "Formal Shoes",
    "Sneakers",
    "Sandals",
]

BRANDS = [
    "Nike",
    "Adidas",
    "Puma",
    "Reebok",
    "Skechers",
    "Bata",
    "Woodland",
    "Campus",
]

SIZES = ["6", "7", "8", "9", "10"]
COLORS = ["Black", "White", "Blue", "Red", "Gray", "Navy", "Olive", "Brown"]

PRICE_TIERS = {
    "Budget": (999, 1999),
    "Mid": (2000, 4999),
    "Premium": (5000, 9999),
}

CATEGORY_NAME_HINT = {
    "Running Shoes": ["SprintFlow", "AirStride", "RoadPulse", "TrackLite"],
    "Casual Shoes": ["DailyEase", "CityWalk", "StreetFlex", "UrbanComfort"],
    "Sports Shoes": ["PowerDrive", "GameFit", "ProMotion", "Athletica"],
    "Formal Shoes": ["Executive", "Classic Oxford", "Office Elite", "Heritage"],
    "Sneakers": ["StreetMax", "CourtWave", "KickShift", "MetroSneak"],
    "Sandals": ["TrailSand", "BreezeStep", "ComfortGrip", "SummerWalk"],
}


def sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return safe[:80] or "product"


def _existing_image_paths(folder: Path) -> list[str]:
    folder = folder.resolve()
    if not folder.exists():
        return []
    paths = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    return [p.relative_to(REPO_DIR).as_posix() for p in paths]


def _resize_to_square(source: Path, target: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(source) as img:
            img = img.convert("RGB")
            img.thumbnail((224, 224))
            canvas = Image.new("RGB", (224, 224), (255, 255, 255))
            left = (224 - img.width) // 2
            top = (224 - img.height) // 2
            canvas.paste(img, (left, top))
            canvas.save(target, "JPEG", quality=88)
        return True
    except Exception:
        return False


def _duckduckgo_image_urls(query: str, limit: int) -> list[str]:
    try:
        import requests

        headers = {"User-Agent": "Mozilla/5.0"}
        page = requests.get(
            "https://duckduckgo.com/",
            params={"q": query},
            headers=headers,
            timeout=15,
        ).text
        marker = 'vqd="'
        start = page.find(marker)
        if start < 0:
            return []
        start += len(marker)
        end = page.find('"', start)
        if end < 0:
            return []
        vqd = page[start:end]
        response = requests.get(
            "https://duckduckgo.com/i.js",
            params={"l": "us-en", "o": "json", "q": query, "vqd": vqd, "f": ",,,", "p": "1"},
            headers={**headers, "Referer": "https://duckduckgo.com/"},
            timeout=20,
        )
        results = response.json().get("results", [])
        urls = [item.get("image") for item in results if item.get("image")]
        return urls[:limit]
    except Exception:
        return []


def _download_url_to_square(url: str, target: Path) -> bool:
    try:
        import requests

        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200 or "image" not in content_type:
            return False
        with tempfile.NamedTemporaryFile(delete=False, suffix=".img") as tmp_file:
            tmp_file.write(response.content)
            tmp_path = Path(tmp_file.name)
        try:
            return _resize_to_square(tmp_path, target)
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass
    except Exception:
        return False


def download_images(query: str, folder: Path, limit: int = 3) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    existing = _existing_image_paths(folder)
    if len(existing) >= 2:
        return existing[:limit]

    try:
        from simple_image_download import simple_image_download as simp

        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = Path.cwd()
            os.chdir(tmp)
            try:
                response = simp.simple_image_download()
                response.download(query, limit + 4)
            finally:
                os.chdir(original_cwd)

            candidates = [
                p for p in Path(tmp).rglob("*")
                if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            ]
            saved_count = len(existing)
            for candidate in candidates:
                if saved_count >= limit:
                    break
                target = folder / f"image_{saved_count + 1}.jpg"
                if target.exists():
                    saved_count += 1
                    continue
                if _resize_to_square(candidate, target):
                    saved_count += 1
    except Exception:
        pass

    existing = _existing_image_paths(folder)
    if len(existing) >= 2:
        return existing[:limit]

    saved_count = len(existing)
    for url in _duckduckgo_image_urls(query, limit + 8):
        if saved_count >= limit:
            break
        target = folder / f"image_{saved_count + 1}.jpg"
        if target.exists():
            saved_count += 1
            continue
        if _download_url_to_square(url, target):
            saved_count += 1

    existing = _existing_image_paths(folder)
    if len(existing) >= 2:
        return existing[:limit]

    try:
        import requests

        saved_count = len(existing)
        headers = {"User-Agent": "Mozilla/5.0"}
        for idx in range(limit + 3):
            if saved_count >= limit:
                break
            url = (
                "https://source.unsplash.com/600x600/?"
                f"{query.replace(' ', ',')},single,footwear&sig={sanitize_filename(query)}_{idx}"
            )
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            content_type = response.headers.get("content-type", "")
            if response.status_code != 200 or "image" not in content_type:
                continue
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                tmp_file.write(response.content)
                tmp_path = Path(tmp_file.name)
            try:
                target = folder / f"image_{saved_count + 1}.jpg"
                if _resize_to_square(tmp_path, target):
                    saved_count += 1
            finally:
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
    except Exception:
        pass

    return _existing_image_paths(folder)[:limit]


def _product_images(name: str, brand: str, category: str) -> list[str]:
    safe_name = sanitize_filename(name)
    query = f"{brand} {name} {category}"
    return download_images(query, DATASET_IMAGE_DIR / safe_name)


def _local_product_images(name: str) -> list[str]:
    return _existing_image_paths(DATASET_IMAGE_DIR / sanitize_filename(name))[:3]


def _ensure_images_column(db) -> None:
    db.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS images VARCHAR[]"))
    db.commit()


def _product_name(brand: str, category: str, color: str, size: str, idx: int) -> str:
    hint = random.choice(CATEGORY_NAME_HINT[category])
    return f"{brand} {hint} {color} Size {size} ({idx + 1})"


def _product_description(category: str, brand: str, color: str, size: str, tier: str) -> str:
    line1 = (
        f"{brand} {category.lower()} built for all-day comfort with breathable upper and durable outsole."
    )
    line2 = (
        f"Designed in {color.lower()} with cushioned support, stable grip, and true-to-fit size {size}."
    )
    line3 = (
        f"Ideal for daily wear and long sessions, this {tier.lower()} range option balances style and performance."
    )
    return f"{line1}\n{line2}\n{line3}"


def _build_products() -> list[Product]:
    products: list[Product] = []

    # 6 categories x 8 brands = 48 balanced pairs; repeat 5 times => 240 products.
    category_brand_pairs = [(c, b) for c in CATEGORIES for b in BRANDS]

    tier_plan = (["Budget"] * 80) + (["Mid"] * 80) + (["Premium"] * 80)
    random.shuffle(tier_plan)

    for i in range(TOTAL_PRODUCTS):
        category, brand = category_brand_pairs[i % len(category_brand_pairs)]
        size = random.choice(SIZES)
        color = random.choice(COLORS)
        tier = tier_plan[i]
        low, high = PRICE_TIERS[tier]

        product = Product(
            name=_product_name(brand, category, color, size, i),
            category=category,
            brand=brand,
            size=size,
            color=color,
            price=float(random.randint(low, high)),
            stock=random.randint(10, 50),
            description=_product_description(category, brand, color, size, tier),
        )
        products.append(product)

    return products


def main() -> None:
    random.seed(42)
    db = SessionLocal()
    try:
        _ensure_images_column(db)
        force_images = os.getenv("PRODUCT_IMAGES_FORCE_REFRESH") == "1"
        only_legacy = os.getenv("PRODUCT_IMAGES_ONLY_LEGACY") == "1"
        image_limit = int(os.getenv("PRODUCT_IMAGES_LIMIT") or "0") or None
        existing_products = db.query(Product).all()
        if existing_products:
            summary = ensure_db_product_images(
                db,
                force_refresh=force_images,
                only_legacy=only_legacy,
                limit=image_limit,
            )
            print(f"Image enforcement summary: {summary}")
            return

        products = _build_products()
        db.add_all(products)
        db.commit()
        summary = ensure_db_product_images(
            db,
            force_refresh=force_images,
            only_legacy=only_legacy,
            limit=image_limit,
        )
        print(f"Total products inserted: {len(products)}")
        print(f"Image enforcement summary: {summary}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
