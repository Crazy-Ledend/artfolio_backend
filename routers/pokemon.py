from fastapi import APIRouter, Depends
from db import get_db

router = APIRouter(prefix="/pokemon", tags=["pokemon"])


@router.get("/fusions")
async def get_fusions(db=Depends(get_db)):
    """
    Returns a map of pokemon_name -> list of artworks that include it in fusions.
    Frontend uses this to know which pokemon to light up.
    """
    cursor = db.artworks.find(
        {"fusions": {"$exists": True, "$ne": []}},
        {"_id": 1, "title": 1, "fusions": 1, "gdrive_file_id": 1,
         "description": 1, "medium": 1, "year": 1, "tags": 1}
    )
    docs = await cursor.to_list(length=1000)

    from services.gdrive_services import thumbnail_url, view_url

    # Build map: pokemon_name -> [{artwork info}]
    fusion_map: dict[str, list] = {}
    for doc in docs:
        artwork_info = {
            "id": str(doc["_id"]),
            "title": doc["title"],
            "fusions": doc.get("fusions", []),
            "image_url": thumbnail_url(doc["gdrive_file_id"], 400),
            "full_url": view_url(doc["gdrive_file_id"]),
            "description": doc.get("description"),
            "medium": doc.get("medium"),
            "year": doc.get("year"),
            "tags": doc.get("tags", []),
        }
        for poke in doc.get("fusions", []):
            name = poke.lower()
            if name not in fusion_map:
                fusion_map[name] = []
            fusion_map[name].append(artwork_info)

    return {"fusions": fusion_map}