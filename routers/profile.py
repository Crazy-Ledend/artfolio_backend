from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from db import get_db, settings

router = APIRouter(prefix="/profile", tags=["profile"])


class SocialLink(BaseModel):
    platform: str   # instagram | twitter | artstation | deviantart | youtube | website | tiktok
    url: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    photo_gdrive_file_id: Optional[str] = None
    photo_gdrive_url: Optional[str] = None
    location: Optional[str] = None
    socials: Optional[list[SocialLink]] = None


def require_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.get("")
async def get_profile(db=Depends(get_db)):
    doc = await db.profile.find_one({})
    if not doc:
        return {
            "name": "Artist",
            "bio": "",
            "photo_url": None,
            "location": None,
            "socials": [],
            "stats": {"artworks": 0, "fusions": 0},
        }

    from services.gdrive_services import view_url, thumbnail_url

    # Compute live stats
    total_artworks = await db.artworks.count_documents({})
    fused_docs = await db.artworks.distinct("fusions")
    total_fusions = len([f for f in fused_docs if f])

    photo_fid = doc.get("photo_gdrive_file_id")

    return {
        "name": doc.get("name", "Artist"),
        "bio": doc.get("bio", ""),
        "photo_url": thumbnail_url(photo_fid, 400) if photo_fid else None,
        "location": doc.get("location"),
        "socials": doc.get("socials", []),
        "stats": {
            "artworks": total_artworks,
            "fusions": total_fusions,
        },
    }


@router.put("", status_code=200)
async def update_profile(
    payload: ProfileUpdate,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    from services.gdrive_services import extract_file_id

    updates = payload.model_dump(exclude_none=True)

    # Extract file_id from URL if provided
    if "photo_gdrive_url" in updates:
        fid = extract_file_id(updates.pop("photo_gdrive_url"))
        if fid:
            updates["photo_gdrive_file_id"] = fid
        else:
            updates.pop("photo_gdrive_url", None)

    if "socials" in updates:
        updates["socials"] = [s if isinstance(s, dict) else s.model_dump() for s in payload.socials or []]

    updates["updated_at"] = datetime.now(timezone.utc)

    existing = await db.profile.find_one({})
    if existing:
        await db.profile.update_one({"_id": existing["_id"]}, {"$set": updates})
    else:
        await db.profile.insert_one(updates)

    return {"ok": True}