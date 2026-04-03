from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from jose import jwt

from db import get_db, settings
from models.artwork import (
    ArtworkCreate, ArtworkUpdate, ArtworkOut, ArtworkFilters
)
from services.gdrive_services import (
    extract_file_id, view_url
)

router = APIRouter(prefix="/artworks", tags=["artworks"])
security = HTTPBearer(auto_error=False)


def require_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """Returns the Discord user ID from the JWT, or None if not authenticated."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload.get("id")
    except Exception:
        return None


def artwork_to_out(doc: dict, viewer_id: Optional[str] = None) -> ArtworkOut:
    fid = doc["gdrive_file_id"]
    full_res_url = view_url(fid)
    liked_by: list[str] = doc.get("liked_by", [])
    return ArtworkOut(
        id=str(doc["_id"]),
        title=doc["title"],
        description=doc.get("description"),
        medium=doc.get("medium"),
        dimensions=doc.get("dimensions"),
        year=doc.get("year"),
        tags=doc.get("tags", []),
        collection_id=doc.get("collection_id"),
        gdrive_file_id=fid,
        is_available=doc.get("is_available", True),
        sort_order=doc.get("sort_order", 0),
        fusions=doc.get("fusions", []),
        image_url=full_res_url,
        full_url=full_res_url,
        like_count=doc.get("like_count", 0),
        liked_by_me=viewer_id in liked_by if viewer_id else False,
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.get("", response_model=dict)
async def list_artworks(
    collection_id: Optional[str] = Query(None),
    medium: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    db=Depends(get_db),
    viewer_id: Optional[str] = Depends(get_current_user_id),
):
    query: dict = {}

    if collection_id:
        query["collection_id"] = collection_id
    if medium:
        query["medium"] = medium
    if tag:
        query["tags"] = tag
    if year:
        query["year"] = year
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
            {"medium": {"$regex": search, "$options": "i"}},
        ]

    total = await db.artworks.count_documents(query)
    skip = (page - 1) * limit

    cursor = db.artworks.find(query).sort(
        [("sort_order", 1), ("created_at", -1)]
    ).skip(skip).limit(limit)

    docs = await cursor.to_list(length=limit)
    items = [artwork_to_out(d, viewer_id) for d in docs]

    return {
        "items": [a.model_dump() for a in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/meta", response_model=dict)
async def get_meta(db=Depends(get_db)):
    """Return distinct mediums, tags, and years for filter UI."""
    mediums = await db.artworks.distinct("medium")
    tags = await db.artworks.distinct("tags")
    years = await db.artworks.distinct("year")
    return {
        "mediums": sorted([m for m in mediums if m]),
        "tags": sorted([t for t in tags if t]),
        "years": sorted([y for y in years if y], reverse=True),
    }


@router.get("/{artwork_id}", response_model=ArtworkOut)
async def get_artwork(
    artwork_id: str,
    db=Depends(get_db),
    viewer_id: Optional[str] = Depends(get_current_user_id),
):
    if not ObjectId.is_valid(artwork_id):
        raise HTTPException(status_code=400, detail="Invalid artwork ID")
    doc = await db.artworks.find_one({"_id": ObjectId(artwork_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Artwork not found")
    return artwork_to_out(doc, viewer_id)


@router.post("/{artwork_id}/like", response_model=dict)
async def toggle_like(
    artwork_id: str,
    db=Depends(get_db),
    viewer_id: Optional[str] = Depends(get_current_user_id),
):
    """Toggle like on an artwork. Requires authentication."""
    if not viewer_id:
        raise HTTPException(status_code=401, detail="Must be logged in to like")
    if not ObjectId.is_valid(artwork_id):
        raise HTTPException(status_code=400, detail="Invalid artwork ID")

    oid = ObjectId(artwork_id)
    doc = await db.artworks.find_one({"_id": oid}, {"liked_by": 1, "like_count": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Artwork not found")

    already_liked = viewer_id in doc.get("liked_by", [])

    if already_liked:
        # Unlike
        await db.artworks.update_one(
            {"_id": oid},
            {
                "$pull": {"liked_by": viewer_id},
                "$inc": {"like_count": -1},
            },
        )
        liked = False
    else:
        # Like
        await db.artworks.update_one(
            {"_id": oid},
            {
                "$addToSet": {"liked_by": viewer_id},
                "$inc": {"like_count": 1},
            },
        )
        liked = True

    updated = await db.artworks.find_one({"_id": oid}, {"like_count": 1})
    return {
        "liked": liked,
        "like_count": updated.get("like_count", 0),
    }


@router.post("", response_model=ArtworkOut, status_code=201)
async def create_artwork(
    payload: ArtworkCreate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    file_id = payload.gdrive_file_id
    if payload.gdrive_url:
        extracted = extract_file_id(payload.gdrive_url)
        if not extracted:
            raise HTTPException(
                status_code=422,
                detail="Could not extract file ID from the GDrive URL"
            )
        file_id = extracted

    now = datetime.now(timezone.utc)
    doc = {
        **payload.model_dump(exclude={"gdrive_url"}),
        "gdrive_file_id": file_id,
        "like_count": 0,
        "liked_by": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.artworks.insert_one(doc)
    doc["_id"] = result.inserted_id
    from routers.pokemon import invalidate_cache as _inv; await _inv()
    return artwork_to_out(doc)


@router.patch("/{artwork_id}", response_model=ArtworkOut)
async def update_artwork(
    artwork_id: str,
    payload: ArtworkUpdate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    if not ObjectId.is_valid(artwork_id):
        raise HTTPException(status_code=400, detail="Invalid artwork ID")

    updates = payload.model_dump(exclude_none=True)

    if "gdrive_url" in updates:
        extracted = extract_file_id(updates.pop("gdrive_url"))
        if not extracted:
            raise HTTPException(
                status_code=422,
                detail="Could not extract file ID from the GDrive URL"
            )
        updates["gdrive_file_id"] = extracted

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db.artworks.find_one_and_update(
        {"_id": ObjectId(artwork_id)},
        {"$set": updates},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Artwork not found")
    return artwork_to_out(result)


@router.delete("/{artwork_id}", status_code=204)
async def delete_artwork(
    artwork_id: str,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    if not ObjectId.is_valid(artwork_id):
        raise HTTPException(status_code=400, detail="Invalid artwork ID")
    result = await db.artworks.delete_one({"_id": ObjectId(artwork_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Artwork not found")