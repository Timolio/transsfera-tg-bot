from ..connect import orders_collection
from typing_extensions import Optional
import json
import random
import string
from datetime import datetime, timezone
from pydantic import BaseModel, ValidationError
from bson import ObjectId

class OrderModel(BaseModel):
    tg_id: Optional[int] = None
    username: Optional[str] = None
    public_id: str
    name: str
    phone: str
    date: str
    time: str
    from_location: str
    to_location: str
    adults: int
    children: int
    baggage: int
    hasWhatsApp: bool
    hasTelegram: bool
    hasViber: bool
    comment: str = ""
    price: Optional[int] = None
    created_at: Optional[datetime] = None
    accepted: bool = False

def generate_public_id(length: int = 6) -> str:
    first_char = random.choice(string.ascii_uppercase)
    rest = ''.join(random.choices('0123456789', k=length))
    return first_char + rest

def parse_order(json_string: str, tg_id: int, username: str) -> OrderModel:
    try:
        data = json.loads(json_string)
        data["tg_id"] = tg_id
        data["created_at"] = datetime.now(timezone.utc)
        data["public_id"] = generate_public_id()
        data["username"] = username
        return OrderModel(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Invalid order data: {e}")

async def create_order(order: OrderModel) -> None:
    result = await orders_collection.insert_one(order.model_dump())
    return str(result.inserted_id)

async def get_order(order_id: str) -> OrderModel:
    result = await orders_collection.find_one({"_id": ObjectId(order_id)})
    if result is None:
        return None
    return OrderModel(**result)

async def update_order(order_id: str, update_data: dict) -> OrderModel | None:
    result = await orders_collection.find_one_and_update(
        {"_id": ObjectId(order_id)},
        {"$set": update_data},
        return_document=True,
    )
    if result is None:
        return None
    return OrderModel(**result)

async def delete_order(order_id: str) -> bool:
    result = await orders_collection.delete_one({"_id": ObjectId(order_id)})
    return result.deleted_count == 1