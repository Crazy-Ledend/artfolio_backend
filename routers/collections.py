from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from bson import ObjectId

from db import get_db, settings
from models.artwork import CollectionCreate, CollectionUpdate, CollectionOut
from services.gdrive_services import view_url, extract_file_id

router = APIRouter(prefix="/collections", tags=["collections"])


def require_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


def col_to_out(doc: dict, count: int = 0) -> CollectionOut:
    raw_fid = doc.get("cover_gdrive_file_id")
    fid = extract_file_id(raw_fid) if raw_fid else None
    if not fid and raw_fid:
        fid = raw_fid
    return CollectionOut(
        id=str(doc["_id"]),
        name=doc["name"],
        slug=doc["slug"],
        description=doc.get("description"),
        cover_gdrive_file_id=raw_fid,
        sort_order=doc.get("sort_order", 0),
        cover_url=view_url(fid) if fid else None,
        artwork_count=count,
        created_at=doc["created_at"],
    )


@router.get("", response_model=list[CollectionOut])
async def list_collections(db=Depends(get_db)):
    cursor = db.collections.find({}).sort([("sort_order", 1), ("name", 1)])
    docs = await cursor.to_list(length=200)
    result = []
    for doc in docs:
        count = await db.artworks.count_documents(
            {"collection_id": str(doc["_id"])}
        )
        result.append(col_to_out(doc, count))
    return result


@router.get("/{collection_id}", response_model=CollectionOut)
async def get_collection(collection_id: str, db=Depends(get_db)):
    query = (
        {"slug": collection_id}
        if not ObjectId.is_valid(collection_id)
        else {"_id": ObjectId(collection_id)}
    )
    doc = await db.collections.find_one(query)
    if not doc:
        raise HTTPException(status_code=404, detail="Collection not found")
    count = await db.artworks.count_documents(
        {"collection_id": str(doc["_id"])}
    )
    return col_to_out(doc, count)


@router.post("", response_model=CollectionOut, status_code=201)
async def create_collection(
    payload: CollectionCreate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    existing = await db.collections.find_one({"slug": payload.slug})
    if existing:
        raise HTTPException(
            status_code=409, detail="A collection with this slug already exists"
        )
    now = datetime.now(timezone.utc)
    doc = {**payload.model_dump(), "created_at": now}
    result = await db.collections.insert_one(doc)
    doc["_id"] = result.inserted_id
    return col_to_out(doc)


@router.patch("/{collection_id}", response_model=CollectionOut)
async def update_collection(
    collection_id: str,
    payload: CollectionUpdate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    if not ObjectId.is_valid(collection_id):
        raise HTTPException(status_code=400, detail="Invalid collection ID")
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    doc = await db.collections.find_one_and_update(
        {"_id": ObjectId(collection_id)},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Collection not found")
    count = await db.artworks.count_documents(
        {"collection_id": str(doc["_id"])}
    )
    return col_to_out(doc, count)


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: str,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    if not ObjectId.is_valid(collection_id):
        raise HTTPException(status_code=400, detail="Invalid collection ID")
    result = await db.collections.delete_one({"_id": ObjectId(collection_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Collection not found")