from fastapi import APIRouter

public_router = APIRouter(tags=["Public"])


@public_router.get("/inventory")
async def public_inventory():
    return [
        {"vin": "WBA93HM0XP1234567", "year": 2023, "make": "BMW", "model": "M4 Competition", "status": "AVAILABLE", "price": 82500},
        {"vin": "5YJSA1E26MF123456", "year": 2022, "make": "Tesla", "model": "Model S Plaid", "status": "AVAILABLE", "price": 109900},
        {"vin": "1FTFW1E85NFA00001", "year": 2022, "make": "Ford", "model": "F-150 Raptor", "status": "SOLD", "price": 76500},
        {"vin": "WP0AB2A93NS270001", "year": 2024, "make": "Porsche", "model": "911 GT3 RS", "status": "AVAILABLE", "price": 241300},
        {"vin": "ZHWUF4ZF9LLA00001", "year": 2020, "make": "Lamborghini", "model": "Huracan EVO", "status": "IN_TRANSIT", "price": 261274},
    ]


@public_router.post("/lead")
async def submit_lead(data: dict):
    return {"status": "received", "message": "Lead submitted successfully."}
