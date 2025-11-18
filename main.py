import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="PC Builder Simulator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility to convert Mongo document to JSON-serializable dict

def serialize_doc(doc):
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# Compatibility engine
class CompatibilityResult(BaseModel):
    is_valid: bool
    issues: List[str]
    estimated_power_w: int


def estimate_power_and_validate(components: Dict[str, dict]) -> CompatibilityResult:
    issues: List[str] = []
    total_tdp = 0

    cpu = components.get("CPU")
    gpu = components.get("GPU")
    mb = components.get("Motherboard")
    ram = components.get("RAM")
    storage = components.get("Storage")
    psu = components.get("PSU")
    case = components.get("Case")
    cooler = components.get("Cooler")

    # Sum TDP from CPU and GPU; add headroom for other parts
    if cpu and cpu.get("tdp"):
        total_tdp += int(cpu["tdp"])  # CPU TDP
    if gpu and gpu.get("tdp"):
        total_tdp += int(gpu["tdp"])  # Approx GPU power

    # Add baseline 75W for other parts if we have a CPU
    if cpu:
        total_tdp += 75

    # Socket match CPU <-> Motherboard
    if cpu and mb:
        if cpu.get("socket") and mb.get("socket") and cpu["socket"] != mb["socket"]:
            issues.append("CPU and Motherboard sockets do not match")

    # RAM type match with Motherboard
    if mb and ram:
        if mb.get("ram_type") and ram.get("ram_type") and mb["ram_type"] != ram["ram_type"]:
            issues.append("RAM type incompatible with Motherboard")

    # RAM speed not exceeding motherboard max
    if mb and ram:
        if mb.get("ram_speed") and ram.get("ram_speed") and int(ram["ram_speed"]) > int(mb["ram_speed"]):
            issues.append("RAM speed exceeds motherboard maximum")

    # PSU wattage sufficient
    if psu and psu.get("psu_wattage"):
        required = int(total_tdp * 1.5)  # 50% headroom recommendation
        if int(psu["psu_wattage"]) < required:
            issues.append(f"PSU wattage may be insufficient (needs ~{required}W)")

    # Case GPU length
    if case and gpu:
        if case.get("case_gpu_max_length_mm") and gpu.get("gpu_length_mm"):
            if int(gpu["gpu_length_mm"]) > int(case["case_gpu_max_length_mm"]):
                issues.append("GPU may not fit in the case (length)")

    # Cooler height
    if case and cooler:
        if case.get("case_cooler_max_height_mm") and cooler.get("cooler_height_mm"):
            if int(cooler["cooler_height_mm"]) > int(case["case_cooler_max_height_mm"]):
                issues.append("Cooler may be too tall for the case")

    # Cooler capacity for CPU TDP
    if cooler and cpu and cooler.get("cooler_tdp_rating") and cpu.get("tdp"):
        if int(cooler["cooler_tdp_rating"]) < int(cpu["tdp"]):
            issues.append("Cooler TDP rating may be insufficient for CPU")

    return CompatibilityResult(
        is_valid=len(issues) == 0,
        issues=issues,
        estimated_power_w=total_tdp,
    )


# Request/Response models
class BuildRequest(BaseModel):
    selections: Dict[str, str]  # type -> component id


class BuildResponse(BaseModel):
    total_price: float
    estimated_power_w: int
    is_valid: bool
    issues: List[str]


@app.get("/")
def root():
    return {"message": "PC Builder Simulator API"}


@app.get("/api/components")
def list_components(type: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    query = {"type": type} if type else {}
    items = db["component"].find(query).limit(200)
    return [serialize_doc(x) for x in items]


@app.post("/api/seed")
def seed_components():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Simple seed data (small curated set)
    seed = [
        {"name": "AMD Ryzen 5 5600", "type": "CPU", "brand": "AMD", "price": 139.0, "socket": "AM4", "tdp": 65},
        {"name": "Intel Core i5-12400F", "type": "CPU", "brand": "Intel", "price": 170.0, "socket": "LGA1700", "tdp": 65},

        {"name": "MSI B550-A Pro", "type": "Motherboard", "brand": "MSI", "price": 119.0, "socket": "AM4", "ram_type": "DDR4", "ram_speed": 4400, "ram_slots": 4, "form_factor": "ATX"},
        {"name": "ASUS PRIME B660M-A", "type": "Motherboard", "brand": "ASUS", "price": 129.0, "socket": "LGA1700", "ram_type": "DDR4", "ram_speed": 5066, "ram_slots": 4, "form_factor": "mATX"},

        {"name": "Corsair Vengeance 16GB (2x8) 3200", "type": "RAM", "brand": "Corsair", "price": 45.0, "ram_type": "DDR4", "ram_speed": 3200},
        {"name": "G.SKILL Ripjaws S5 32GB (2x16) 5600", "type": "RAM", "brand": "G.SKILL", "price": 99.0, "ram_type": "DDR5", "ram_speed": 5600},

        {"name": "NVIDIA RTX 3060", "type": "GPU", "brand": "NVIDIA", "price": 299.0, "tdp": 170, "gpu_length_mm": 242},
        {"name": "AMD Radeon RX 6700 XT", "type": "GPU", "brand": "AMD", "price": 329.0, "tdp": 230, "gpu_length_mm": 267},

        {"name": "Samsung 970 EVO Plus 1TB", "type": "Storage", "brand": "Samsung", "price": 79.0},
        {"name": "Seagate Barracuda 2TB", "type": "Storage", "brand": "Seagate", "price": 49.0},

        {"name": "Corsair 4000D Airflow", "type": "Case", "brand": "Corsair", "price": 94.0, "form_factor": "ATX", "case_gpu_max_length_mm": 360, "case_cooler_max_height_mm": 170},
        {"name": "NZXT H210", "type": "Case", "brand": "NZXT", "price": 79.0, "form_factor": "ITX", "case_gpu_max_length_mm": 325, "case_cooler_max_height_mm": 165},

        {"name": "Cooler Master Hyper 212", "type": "Cooler", "brand": "Cooler Master", "price": 39.0, "cooler_tdp_rating": 150, "cooler_height_mm": 159},
        {"name": "Noctua NH-D15", "type": "Cooler", "brand": "Noctua", "price": 99.0, "cooler_tdp_rating": 220, "cooler_height_mm": 165},

        {"name": "Corsair RM650x", "type": "PSU", "brand": "Corsair", "price": 99.0, "psu_wattage": 650, "psu_type": "ATX"},
        {"name": "Seasonic Focus 750W", "type": "PSU", "brand": "Seasonic", "price": 119.0, "psu_wattage": 750, "psu_type": "ATX"},
    ]

    # Only seed if empty
    count = db["component"].count_documents({})
    if count == 0:
        db["component"].insert_many(seed)
        return {"inserted": len(seed)}
    else:
        return {"message": "Components already seeded", "count": count}


@app.post("/api/evaluate", response_model=BuildResponse)
def evaluate_build(req: BuildRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Fetch selected components by ids
    components: Dict[str, dict] = {}
    total_price = 0.0

    for ctype, id_str in req.selections.items():
        try:
            obj_id = ObjectId(id_str)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid id for {ctype}")
        doc = db["component"].find_one({"_id": obj_id})
        if not doc:
            raise HTTPException(status_code=404, detail=f"Component not found: {ctype}")
        doc = serialize_doc(doc)
        components[ctype] = doc
        total_price += float(doc.get("price", 0.0))

    result = estimate_power_and_validate(components)

    return BuildResponse(
        total_price=round(total_price, 2),
        estimated_power_w=result.estimated_power_w,
        is_valid=result.is_valid,
        issues=result.issues,
    )


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
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
