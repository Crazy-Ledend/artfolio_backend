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
    # Normalize order so pikachu+snorlax == snorlax+pikachu
    pair = tuple(sorted([payload.poke1.lower(), payload.poke2.lower()]))

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


@router.get("")
async def list_requests(db=Depends(get_db), _=Depends(require_admin)):
    cursor = db.fusion_requests.find({}).sort("votes", -1)
    docs = await cursor.to_list(length=500)
    return [
        {
            "id": str(d["_id"]),
            "poke1": d["poke1"],
            "poke2": d["poke2"],
            "votes": d.get("votes", 1),
            "created_at": d["created_at"],
        }
        for d in docs
    ]


@router.delete("/{request_id}", status_code=204)
async def delete_request(request_id: str, db=Depends(get_db), _=Depends(require_admin)):
    from bson import ObjectId
    await db.fusion_requests.delete_one({"_id": ObjectId(request_id)})