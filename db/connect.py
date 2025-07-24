from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

client = AsyncIOMotorClient(os.getenv("MONGO_URL"))
db = client[os.getenv("DATABASE_NAME")]

orders_collection = db["orders"]