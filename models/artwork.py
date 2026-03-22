from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from bson import ObjectId


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)


# ── Artwork ──────────────────────────────────────────────

class ArtworkBase(BaseModel):
    title: str
    description: Optional[str] = None
    medium: Optional[str] = None
    dimensions: Optional[str] = None
    year: Optional[int] = None
    tags: list[str] = []
    collection_id: Optional[str] = None
    gdrive_file_id: str
    is_available: bool = True
    sort_order: int = 0
    fusions: list[str] = []   # lowercase pokemon names e.g. ["bulbasaur", "pikachu"]


class ArtworkCreate(ArtworkBase):
    gdrive_url: Optional[str] = None
    model_config = {"arbitrary_types_allowed": True}


class ArtworkUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    medium: Optional[str] = None
    dimensions: Optional[str] = None
    year: Optional[int] = None
    tags: Optional[list[str]] = None
    collection_id: Optional[str] = None
    gdrive_file_id: Optional[str] = None
    gdrive_url: Optional[str] = None
    is_available: Optional[bool] = None
    sort_order: Optional[int] = None
    fusions: Optional[list[str]] = None


class ArtworkOut(ArtworkBase):
    id: str
    image_url: str
    full_url: str
    created_at: datetime
    updated_at: datetime
    model_config = {"arbitrary_types_allowed": True}


# ── Collection ────────────────────────────────────────────

class CollectionBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    cover_gdrive_file_id: Optional[str] = None
    sort_order: int = 0


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    cover_gdrive_file_id: Optional[str] = None
    sort_order: Optional[int] = None


class CollectionOut(CollectionBase):
    id: str
    cover_url: Optional[str] = None
    artwork_count: int = 0
    created_at: datetime
    model_config = {"arbitrary_types_allowed": True}


# ── Contact ───────────────────────────────────────────────

class ContactMessage(BaseModel):
    name: str
    email: str
    subject: Optional[str] = None
    message: str
    artwork_id: Optional[str] = None


# ── Filters ───────────────────────────────────────────────

class ArtworkFilters(BaseModel):
    collection_id: Optional[str] = None
    medium: Optional[str] = None
    tag: Optional[str] = None
    year: Optional[int] = None
    search: Optional[str] = None
    page: int = 1
    limit: int = 24