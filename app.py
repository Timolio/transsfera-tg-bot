import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, ContentType
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚗 Заказать трансфер", web_app=WebAppInfo(url="https://" + os.getenv("WEBAPP_URL")))]],
        resize_keyboard=True,
    )

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Welcome to the Transsfera Bot!", reply_markup=get_main_keyboard())

@dp.message(F.content_type == ContentType.WEB_APP_DATA)
async def web_app_handler(message: Message):
    data = message.web_app_data.data
    await message.answer(f"Received data from web app: {data}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")