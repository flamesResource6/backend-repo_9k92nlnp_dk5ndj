import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import db, create_document, get_documents
from schemas import Player, Milestone, Reward

app = FastAPI(title="Misión AMVISION 10K API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Misión AMVISION 10K Backend Ready"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# ---------- Data bootstrap endpoints ----------
class BootstrapResponse(BaseModel):
    milestones_created: int

@app.post("/api/bootstrap", response_model=BootstrapResponse)
def bootstrap():
    """Idempotently ensure the mission milestone catalog exists."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    existing = {m.get("milestone_id") for m in db["milestone"].find({}, {"milestone_id": 1})}
    # Updated catalog based on user-provided milestones
    catalog = [
        {"milestone_id": "m1",  "title": "Email y WhatsApp de Bienvenida es Enviado",              "order": 1},
        {"milestone_id": "m2",  "title": "Formulario de Onboarding es completado",                  "order": 2},
        {"milestone_id": "m3",  "title": "Llamada de Onboarding es llamada completada",             "order": 3},
        {"milestone_id": "m4",  "title": "Status es Producto Ganador",                               "order": 4},
        {"milestone_id": "m5",  "title": "Status es Elegido Proveedor",                              "order": 5},
        {"milestone_id": "m6",  "title": "Status es Confirmado",                                     "order": 6},
        {"milestone_id": "m7",  "title": "Tienda, Status es Creada",                                 "order": 7},
        {"milestone_id": "m8",  "title": "Business Manager Status es Creado",                        "order": 8},
        {"milestone_id": "m9",  "title": "Primeros ADS Subidos",                                     "order": 9},
        {"milestone_id": "m10", "title": "🔥 Primera Venta",                                          "order": 10},
        {"milestone_id": "m11", "title": "😍 $1.000USD Facturación",                                  "order": 11},
    ]
    created = 0
    for item in catalog:
        if item["milestone_id"] not in existing:
            create_document("milestone", item)
            created += 1
    return {"milestones_created": created}

# ---------- Player endpoints ----------
class CreatePlayer(BaseModel):
    name: str
    email: str

@app.post("/api/player", response_model=dict)
def create_player(payload: CreatePlayer):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    # Check if exists
    found = db["player"].find_one({"email": payload.email})
    if found:
        return {"player_id": str(found.get("_id"))}
    player = Player(name=payload.name, email=payload.email)
    new_id = create_document("player", player)
    return {"player_id": new_id}

@app.get("/api/milestones", response_model=List[Milestone])
def list_milestones():
    docs = get_documents("milestone", {}, None)
    # Sort by order asc
    docs.sort(key=lambda x: x.get("order", 999))
    # Remove Mongo _id for Pydantic
    for d in docs:
        d.pop("_id", None)
    return docs

class CompleteMilestoneRequest(BaseModel):
    player_email: str
    milestone_id: str
    speed: Optional[str] = None  # 'fast' | 'normal' | 'slow'
    revenue_increase: Optional[float] = 0

class CompleteMilestoneResponse(BaseModel):
    av_coins_awarded: int
    revenue_usd: float
    unlocked_world: Optional[str] = None
    message: str

@app.post("/api/complete", response_model=CompleteMilestoneResponse)
def complete_milestone(payload: CompleteMilestoneRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    player = db["player"].find_one({"email": payload.player_email})
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # idempotent: don't double-complete
    completed = set(player.get("completed_milestones", []))
    if payload.milestone_id in completed:
        coins = 0
    else:
        completed.add(payload.milestone_id)
        # Speed-based rewards
        speed = (payload.speed or "normal").lower()
        speed_reward = {"fast": 50, "normal": 30, "slow": 15}.get(speed, 30)
        coins = 100 + speed_reward  # base + speed bonus
        create_document("reward", {
            "player_id": str(player.get("_id")),
            "milestone_id": payload.milestone_id,
            "reason": f"Completed {payload.milestone_id} ({speed})",
            "coins": coins,
        })
        db["player"].update_one(
            {"_id": player["_id"]},
            {"$set": {"completed_milestones": list(completed)}, "$inc": {"av_coins": coins}}
        )

    # revenue update and world unlock
    rev_inc = float(payload.revenue_increase or 0)
    new_revenue = float(player.get("revenue_usd", 0)) + rev_inc
    unlocked = None
    if new_revenue >= 1000 and "world_1" not in player.get("unlocked_worlds", []):
        unlocked = "world_1"
        db["player"].update_one({"_id": player["_id"]}, {"$addToSet": {"unlocked_worlds": unlocked}})

    db["player"].update_one({"_id": player["_id"]}, {"$set": {"revenue_usd": new_revenue}})

    return {
        "av_coins_awarded": coins,
        "revenue_usd": new_revenue,
        "unlocked_world": unlocked,
        "message": "¡Progreso registrado! Sigue avanzando."
    }

@app.get("/api/player/summary", response_model=dict)
def player_summary(email: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    player = db["player"].find_one({"email": email})
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {
        "name": player.get("name"),
        "email": player.get("email"),
        "av_coins": player.get("av_coins", 0),
        "revenue_usd": player.get("revenue_usd", 0.0),
        "completed_milestones": player.get("completed_milestones", []),
        "unlocked_worlds": player.get("unlocked_worlds", []),
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
