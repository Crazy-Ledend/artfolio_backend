import time
from fastapi import APIRouter, Depends
from db import get_db

router = APIRouter(prefix="/pokemon", tags=["pokemon"])

# In-memory cache — fusion map rarely changes
_cache: dict = {}
_cache_time: float = 0
CACHE_TTL = 60  # seconds


@router.get("/fusions")
async def get_fusions(db=Depends(get_db)):
    global _cache, _cache_time

    # Return cached if fresh
    if _cache and (time.time() - _cache_time) < CACHE_TTL:
        return _cache

    cursor = db.artworks.find(
        {"fusions": {"$exists": True, "$not": {"$size": 0}}},
        {"_id": 1, "title": 1, "fusions": 1, "gdrive_file_id": 1,
         "description": 1, "medium": 1, "year": 1, "tags": 1, "obtainable_in": 1}
    )
    docs = await cursor.to_list(length=1000)

    from services.gdrive_services import view_url

    fusion_map: dict[str, list] = {}
    for doc in docs:
        full_res_url = view_url(doc["gdrive_file_id"])
        artwork_info = {
            "id": str(doc["_id"]),
            "title": doc["title"],
            "fusions": doc.get("fusions", []),
            "image_url": full_res_url,
            "full_url": full_res_url,
            "description": doc.get("description"),
            "medium": doc.get("medium"),
            "year": doc.get("year"),
            "tags": doc.get("tags", []),
            "obtainable_in": doc.get("obtainable_in", []),
        }
        for poke in doc.get("fusions", []):
            name = poke.lower()
            if name not in fusion_map:
                fusion_map[name] = []
            fusion_map[name].append(artwork_info)

    _cache = {"fusions": fusion_map}
    _cache_time = time.time()
    return _cache


@router.post("/fusions/invalidate")
async def invalidate_cache():
    """Call this after uploading new artwork to refresh the fusion map."""
    global _cache_time
    _cache_time = 0
    return {"ok": True}
