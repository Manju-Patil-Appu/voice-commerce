from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from PIL import Image
from sqlalchemy.orm import Session

from app.models.product import Product


REPO_DIR = Path(__file__).resolve().parents[3]
DATASETS_DIR = REPO_DIR / "datasets"
IMAGE_ROOT = DATASETS_DIR / "images"
IMAGE_COUNT = 3
MAX_WORKERS = 12

COLORS = ["black", "white", "red", "blue", "brown", "gray", "navy", "olive"]
STYLES = ["mesh", "leather", "walking", "athletic", "casual", "premium", "comfort", "men", "women"]
ADJECTIVES = ["single shoe", "single pair", "product photo", "side view", "ecommerce", "white background"]
TRUSTED_IMAGE_DOMAINS = [
    "static.nike.com",
    "assets.adidas.com",
    "images.puma.com",
    "reebok",
    "skechers",
    "bata",
    "woodland",
    "campusshoes",
    "m.media-amazon.com",
    "assets.myntassets.com",
    "rukminim",
    "flipkart",
]


def sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", str(name).strip().lower()).strip("_")
    return safe[:90] or "product"


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_DIR).as_posix()


def _sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def _resize_to_square(source: Path, target: Path) -> bool:
    try:
        with Image.open(source) as img:
            img = img.convert("RGB")
            img.thumbnail((224, 224))
            canvas = Image.new("RGB", (224, 224), (255, 255, 255))
            canvas.paste(img, ((224 - img.width) // 2, (224 - img.height) // 2))
            target.parent.mkdir(parents=True, exist_ok=True)
            canvas.save(target, "JPEG", quality=86, optimize=True)
        return True
    except Exception:
        return False


def _download_url(url: str, target: Path) -> bool:
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if response.status_code != 200 or "image" not in response.headers.get("content-type", ""):
            return False
        with tempfile.NamedTemporaryFile(delete=False, suffix=".img") as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)
        try:
            with Image.open(tmp_path) as img:
                width, height = img.size
                if width < 500 or height < 500:
                    return False
            return _resize_to_square(tmp_path, target)
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception:
        return False


def _duckduckgo_image_urls(query: str, limit: int = 12) -> list[str]:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        page = requests.get("https://duckduckgo.com/", params={"q": query}, headers=headers, timeout=6).text
        marker = 'vqd="'
        start = page.find(marker)
        if start < 0:
            return []
        start += len(marker)
        end = page.find('"', start)
        if end < 0:
            return []
        response = requests.get(
            "https://duckduckgo.com/i.js",
            params={"l": "us-en", "o": "json", "q": query, "vqd": page[start:end], "f": ",,,", "p": "1"},
            headers={**headers, "Referer": "https://duckduckgo.com/"},
            timeout=7,
        )
        return [item["image"] for item in response.json().get("results", []) if item.get("image")][:limit]
    except Exception:
        return []


def _product_identity(product: Any, fallback: str = "") -> dict[str, str]:
    if isinstance(product, dict):
        return {
            "id": str(product.get("id") or product.get("product_id") or fallback),
            "name": str(product.get("name") or product.get("title") or fallback),
            "brand": str(product.get("brand") or ""),
            "category": str(product.get("category") or ""),
            "color": str(product.get("color") or ""),
            "description": str(product.get("description") or ""),
        }
    return {
        "id": str(getattr(product, "id", fallback)),
        "name": str(getattr(product, "name", fallback)),
        "brand": str(getattr(product, "brand", "") or ""),
        "category": str(getattr(product, "category", "") or ""),
        "color": str(getattr(product, "color", "") or ""),
        "description": str(getattr(product, "description", "") or ""),
    }


def _search_queries(identity: dict[str, str]) -> list[str]:
    seed = int(hashlib.sha256(f"{identity['id']}:{identity['name']}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    category_term = "sneaker" if "sneaker" in identity["category"].lower() else "shoe"
    if "sandal" in identity["category"].lower():
        category_term = "sandal"
    base = " ".join(part for part in [identity["brand"], identity["name"], identity["category"], identity["color"]] if part)
    terms = []
    for _ in range(8):
        terms.append(
            " ".join(
                [
                    base,
                    category_term,
                    "product",
                    "photo",
                    "single pair",
                    "white background",
                    rng.choice(COLORS),
                    rng.choice(STYLES),
                    rng.choice(ADJECTIVES),
                ]
            ).strip()
        )
    generic_base = " ".join(part for part in [identity["brand"], identity["color"], identity["category"]] if part)
    terms.extend(
        [
            f"{generic_base} {category_term} product photo single pair white background",
            f"{generic_base} footwear ecommerce product image side view",
            f"{generic_base} men {category_term} white background",
        ]
    )
    return terms


def _score_image_url(identity: dict[str, str], url: str) -> int:
    value = url.lower()
    score = 0
    if any(domain in value for domain in TRUSTED_IMAGE_DOMAINS):
        score += 50
    brand = identity.get("brand", "").strip().lower()
    if brand and brand in value:
        score += 20
    category = identity.get("category", "").strip().lower().replace(" ", "-")
    if category and category in value:
        score += 8
    if any(term in value for term in ["shoe", "shoes", "sneaker", "sandal", "footwear"]):
        score += 8
    if any(term in value for term in ["icon", "logo", "svg", "clipart", "drawing", "cartoon"]):
        score -= 40
    return score


def _candidate_urls(identity: dict[str, str]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for query in _search_queries(identity)[:2]:
        for url in _duckduckgo_image_urls(query):
            if url not in seen:
                seen.add(url)
                urls.append(url)
        if len(urls) >= 24:
            break
    return sorted(urls, key=lambda url: _score_image_url(identity, url), reverse=True)


def _legacy_folder(product: Any) -> str:
    identity = _product_identity(product)
    product_id = identity.get("id", "")
    if not product_id:
        return ""
    return f"{sanitize_filename(identity['name'])}_{product_id}"


def _expected_folder(product: Any) -> str:
    return sanitize_filename(_product_identity(product)["name"])


def _needs_image_replacement(product: Product) -> bool:
    images = product.images or []
    expected_prefix = f"datasets/images/{_expected_folder(product)}/"
    legacy_prefix = f"datasets/images/{_legacy_folder(product)}/"
    if len(images) < IMAGE_COUNT:
        return True
    for rel in images[:IMAGE_COUNT]:
        if not isinstance(rel, str) or not rel.startswith(expected_prefix):
            return True
        if legacy_prefix and rel.startswith(legacy_prefix):
            return True
        if not (REPO_DIR / rel).exists():
            return True
    return False


def _normalize_existing(folder: Path, used_hashes: set[str]) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    kept: list[Path] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        digest = _sha256(path)
        if not digest or digest in used_hashes:
            path.unlink(missing_ok=True)
            continue
        used_hashes.add(digest)
        kept.append(path)
        if len(kept) == IMAGE_COUNT:
            break

    normalized: list[str] = []
    for index, path in enumerate(kept, start=1):
        target = folder / f"img_{index}.jpg"
        if path != target:
            temp = folder / f"tmp_{index}_{path.name}"
            path.replace(temp)
            if not _resize_to_square(temp, target):
                temp.replace(target)
            temp.unlink(missing_ok=True)
        normalized.append(_relative(target))
    return normalized


def ensure_product_images(product: Any, used_hashes: set[str], force_refresh: bool = False) -> list[str]:
    identity = _product_identity(product)
    folder = IMAGE_ROOT / sanitize_filename(identity["name"])
    if force_refresh and folder.exists():
        for path in folder.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)
    images = [] if force_refresh else _normalize_existing(folder, used_hashes)
    if len(images) >= IMAGE_COUNT:
        return images[:IMAGE_COUNT]

    urls = _candidate_urls(identity)[:24]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_root = Path(tmp_dir)
        executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        futures = {
            executor.submit(_download_url, url, tmp_root / f"candidate_{idx}.jpg"): tmp_root / f"candidate_{idx}.jpg"
            for idx, url in enumerate(urls)
        }
        try:
            for future in as_completed(futures):
                if len(images) >= IMAGE_COUNT:
                    break
                candidate = futures[future]
                if not future.result():
                    candidate.unlink(missing_ok=True)
                    continue
                digest = _sha256(candidate)
                if not digest or digest in used_hashes:
                    candidate.unlink(missing_ok=True)
                    continue
                target = folder / f"img_{len(images) + 1}.jpg"
                candidate.replace(target)
                used_hashes.add(digest)
                images.append(_relative(target))
        finally:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)

    return images[:IMAGE_COUNT]


def ensure_db_product_images(
    db: Session,
    force_refresh: bool = False,
    only_legacy: bool = False,
    limit: int | None = None,
) -> dict[str, int]:
    products = db.query(Product).order_by(Product.id.asc()).all()
    used_hashes: set[str] = set()
    updated = 0
    complete = 0
    processed = 0
    skipped = 0

    for index, product in enumerate(products, start=1):
        needs_replacement = force_refresh or _needs_image_replacement(product)
        if only_legacy and not needs_replacement:
            for rel in (product.images or [])[:IMAGE_COUNT]:
                digest = _sha256(REPO_DIR / rel)
                if digest:
                    used_hashes.add(digest)
            skipped += 1
            continue
        if limit is not None and processed >= limit:
            skipped += 1
            continue

        images = ensure_product_images(product, used_hashes, force_refresh=needs_replacement)
        processed += 1
        if len(images) == IMAGE_COUNT:
            complete += 1
        if product.images != images:
            product.images = images
            updated += 1
        if index % 1 == 0:
            db.commit()
    db.commit()
    return {
        "total": len(products),
        "processed": processed,
        "skipped": skipped,
        "updated": updated,
        "complete": complete,
        "missing": processed - complete,
    }


def _is_product_record(record: Any) -> bool:
    return isinstance(record, dict) and bool(record.get("name") or record.get("title")) and (
        "price" in record or "brand" in record or "category" in record
    )


def _walk_json_products(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        products: list[dict[str, Any]] = []
        for item in data:
            products.extend(_walk_json_products(item))
        return products
    if isinstance(data, dict):
        if _is_product_record(data):
            return [data]
        products = []
        for value in data.values():
            products.extend(_walk_json_products(value))
        return products
    return []


def ensure_dataset_product_images() -> dict[str, Any]:
    used_hashes: set[str] = set()
    files_updated = 0
    products_seen = 0
    products_complete = 0

    for path in sorted(DATASETS_DIR.rglob("*")):
        if path.suffix.lower() == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            products = _walk_json_products(data)
            if not products:
                continue
            for index, product in enumerate(products, start=1):
                products_seen += 1
                images = ensure_product_images(product, used_hashes)
                product["images"] = images
                if len(images) == IMAGE_COUNT:
                    products_complete += 1
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            files_updated += 1
        elif path.suffix.lower() == ".csv":
            try:
                with path.open("r", encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
            except Exception:
                continue
            products = [row for row in rows if _is_product_record(row)]
            if not products:
                continue
            fieldnames = list(rows[0].keys())
            if "images" not in fieldnames:
                fieldnames.append("images")
            for row in products:
                products_seen += 1
                images = ensure_product_images(row, used_hashes)
                row["images"] = json.dumps(images)
                if len(images) == IMAGE_COUNT:
                    products_complete += 1
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            files_updated += 1

    return {
        "files_updated": files_updated,
        "products_seen": products_seen,
        "products_complete": products_complete,
        "products_missing": products_seen - products_complete,
    }
