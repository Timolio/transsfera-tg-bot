import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, ContentType, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from db.service.orders import parse_order, create_order, update_order, get_order, delete_order, OrderModel

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")

bot = Bot(token=os.getenv("DEV_BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class PriceStates(StatesGroup):
    waiting_for_price = State()

def format_order(order: OrderModel, has_price_question: bool = False) -> str:
    formatted = (
        f"<b>📅 Дата и время: {order.date}, {order.time}</b>\n\n"
        f"📍 Откуда: <blockquote>{order.from_location}</blockquote>\n"
        f"📍 Куда: <blockquote>{order.to_location}</blockquote>\n\n"
        f"👤 Имя: {order.name}\n"
        f"<a href='tg://user?id={order.tg_id}'>🤖 Telegram-профиль заказчика</a>\n\n"
        f"📞 Телефон: {order.phone}\n\n"
        f"👨‍👩‍👧‍👦 Всего пассажиров: <b>{order.adults + order.children}</b>\n"
        f"(из них до 12 лет: <b>{order.children}</b>)"
    )

    if (order.price):
        formatted += f"\n\n💰 Стоимость трансфера составляет <b>{order.price}€</b>."
    
    if (not has_price_question):
        formatted += " Подходит ли вам эта цена?"
    
    return formatted

def get_price_accept_buttons(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"accept_price:{order_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"decline_price:{order_id}")
        ]
    ])

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚗 Заказать трансфер", web_app=WebAppInfo(url="https://" + os.getenv("WEBAPP_URL")))]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_price_button(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Дать цену", callback_data=f"set_price:{order_id}")]
    ])

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "👋 Добро пожаловать!\n\nЭто бот трансферной компании Transsfera. Мы работаем в Испании: Аликанте, Барселона, Валенсия.\n\nЗдесь вы можете быстро заказать трансфер.",
        reply_markup=get_main_keyboard()
    )

@dp.message(PriceStates.waiting_for_price)
async def receive_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную цену.")
        return

    data = await state.get_data()
    order_id = data["order_id"]

    order = await update_order(order_id, {"price": price})

    formatted = format_order(order)
    await bot.send_message(
        order.tg_id,
        f"🚖 Ваш заказ <b>№{order.public_id}</b>\n\n{formatted}",
        reply_markup=get_price_accept_buttons(order_id)
    )

    await message.answer("✅ Цена отправлена клиенту.")
    await state.clear()

@dp.callback_query(F.data.startswith("accept_price:"))
async def handle_accept_price(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]

    order = await update_order(order_id, {"accepted": True})
    if not order:
        await callback.message.answer("⚠️ Заказ не найден.")
        return

    await callback.message.edit_reply_markup()

    # Клиенту
    await callback.message.answer("✅ Отлично! Водитель свяжется с вами в течение 5 минут для подтверждения.")

    # Админу
    await bot.send_message(
        os.getenv("ADMIN_ID"),
        f"✅ Клиент подтвердил заказ <b>№{order.public_id}</b>.\n\n"
        f"{format_order(order, True)}\n\n#подтверждённые_заказы"
    )

    await callback.answer()

@dp.callback_query(F.data.startswith("decline_price:"))
async def handle_decline_price(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]

    await delete_order(order_id)

    await callback.message.edit_reply_markup()
    await callback.message.answer("😔 Спасибо! Вы можете снова отправить заказ в любое время.")
    await callback.answer()

@dp.callback_query(F.data.startswith("set_price:"))
async def set_price_callback(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.split(":")[1]
    order = await get_order(order_id)
    if order.price:
        await callback.message.answer(f"❌ Вы уже определили цену в <b>{order.price}€</b> для этого заказа!")
        await callback.answer()
        return
    await state.update_data(order_id=order_id)
    await callback.message.answer("Введите цену для этого заказа:")
    await state.set_state(PriceStates.waiting_for_price)
    await callback.answer()

@dp.message(F.content_type == ContentType.WEB_APP_DATA)
async def web_app_handler(message: Message):
    data = message.web_app_data.data
    parsed_order = parse_order(data, message.from_user.id)
    order_id = await create_order(parsed_order)
    await message.answer(f"✅ Ваш заказ <b>№{parsed_order.public_id}</b> принят! Обработка может занять до 5 минут.")
    formatted = format_order(parsed_order, True)
    await bot.send_message(os.getenv("ADMIN_ID"), f"🎉 Новый заказ <b>№{parsed_order.public_id}</b>:\n\n{formatted}", reply_markup=get_price_button(order_id=str(order_id)), )

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")