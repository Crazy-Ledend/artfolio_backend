from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException
from db import get_db, settings
from models.artwork import ContactMessage

router = APIRouter(prefix="/contact", tags=["contact"])


def require_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.post("", status_code=201)
@router.post("/", status_code=201, include_in_schema=False)
async def submit_contact(payload: ContactMessage, db=Depends(get_db)):
    doc = {
        **payload.model_dump(),
        "created_at": datetime.now(timezone.utc),
        "read": False,
    }
    result = await db.contacts.insert_one(doc)
    return {"id": str(result.inserted_id), "message": "Message received"}


@router.get("", response_model=list[dict])
async def list_contacts(db=Depends(get_db), _=Depends(require_admin)):
    cursor = db.contacts.find({}).sort("created_at", -1).limit(200)
    docs = await cursor.to_list(length=200)
    return [
        {**{k: v for k, v in d.items() if k != "_id"}, "id": str(d["_id"])}
        for d in docs
    ]


@router.patch("/{contact_id}/read", status_code=200)
async def mark_read(
    contact_id: str, db=Depends(get_db), _=Depends(require_admin)
):
    from bson import ObjectId
    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)}, {"$set": {"read": True}}
    )
    return {"ok": True}


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: str, db=Depends(get_db), _=Depends(require_admin)
):
    from bson import ObjectId
    result = await db.contacts.delete_one({"_id": ObjectId(contact_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
