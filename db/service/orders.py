from ..connect import orders_collection
from typing_extensions import Optional
import json
from datetime import datetime, timezone
from pydantic import BaseModel, ValidationError

class OrderModel(BaseModel):
    tg_id: Optional[int] = None
    name: str
    phone: str
    date: str
    time: str
    from_location: str
    to_location: str
    adults: int
    children: int
    created_at: Optional[datetime] = None

def parse_order(json_string: str, tg_id: int) -> OrderModel:
    try:
        data = json.loads(json_string)
        data["tg_id"] = tg_id
        data["created_at"] = datetime.now(timezone.utc)
        return OrderModel(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Invalid order data: {e}")

async def create_order(order: OrderModel) -> None:
    result = await orders_collection.insert_one(order.model_dump())
    return str(result.inserted_id)