from fastapi import APIRouter, Header, HTTPException
from datetime import datetime, timedelta
from db import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.post("/track")
async def track_visit():
    db = get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Increment daily count
    await db.analytics.update_one(
        {"date": today},
        {"$inc": {"count": 1}},
        upsert=True
    )
    return {"ok": True}

@router.get("/stats")
async def get_stats(x_admin_secret: str = Header(None)):
    from db import settings
    if x_admin_secret != settings.admin_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db = get_db()
    
    # Get last 30 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=29)
    
    cursor = db.analytics.find({
        "date": {"$gte": start_date.strftime("%Y-%m-%d")}
    }).sort("date", 1)
    
    results = await cursor.to_list(length=30)
    
    # Fill in missing dates with zero
    data_map = {r["date"]: r["count"] for r in results}
    
    stats = []
    for i in range(30):
        current = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        stats.append({
            "date": current,
            "count": data_map.get(current, 0)
        })
        
    return stats
