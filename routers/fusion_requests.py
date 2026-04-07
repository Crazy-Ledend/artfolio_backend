from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from db import get_db, settings

router = APIRouter(prefix="/fusion-requests", tags=["fusion-requests"])


def require_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


class FusionRequestIn(BaseModel):
    poke1: str
    poke2: str


@router.post("", status_code=201)
async def create_request(payload: FusionRequestIn, request: Request, db=Depends(get_db)):
    # Preserve order so Head + Body are distinct
    pair = (payload.poke1.lower(), payload.poke2.lower())

    # Check if already requested — upsert vote count
    existing = await db.fusion_requests.find_one({"poke1": pair[0], "poke2": pair[1]})
    if existing:
        await db.fusion_requests.update_one(
            {"_id": existing["_id"]},
            {"$inc": {"votes": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        return {"id": str(existing["_id"]), "votes": existing["votes"] + 1}

    doc = {
        "poke1": pair[0],
        "poke2": pair[1],
        "votes": 1,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.fusion_requests.insert_one(doc)
    return {"id": str(result.inserted_id), "votes": 1}


@router.get("/check/{poke1}/{poke2}")
async def check_request(poke1: str, poke2: str, db=Depends(get_db)):
    # Check if a fusion request currently exists
    existing = await db.fusion_requests.find_one({
        "poke1": poke1.lower(),
        "poke2": poke2.lower()
    })
    return {"exists": bool(existing)}


@router.get("")
async def list_requests(
    page: int = 1,
    limit: int = 50,
    db=Depends(get_db), 
    _=Depends(require_admin)
):
    total = await db.fusion_requests.count_documents({})
    skip = (page - 1) * limit
    
    cursor = db.fusion_requests.find({}).sort("votes", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    
    items = [
        {
            "id": str(d["_id"]),
            "poke1": d["poke1"],
            "poke2": d["poke2"],
            "votes": d.get("votes", 1),
            "created_at": d["created_at"],
            "completed": d.get("completed", False),
        }
        for d in docs
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.delete("/{request_id}", status_code=204)
async def delete_request(request_id: str, db=Depends(get_db), _=Depends(require_admin)):
    from bson import ObjectId
    await db.fusion_requests.delete_one({"_id": ObjectId(request_id)})

@router.patch("/{request_id}/complete", status_code=200)
async def complete_request(request_id: str, db=Depends(get_db), _=Depends(require_admin)):
    from bson import ObjectId
    await db.fusion_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"completed": True}}
    )
    return {"ok": True}