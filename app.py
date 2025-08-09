import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, ContentType, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
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

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class PriceStates(StatesGroup):
    waiting_for_price = State()

def format_order(order: OrderModel, has_price_question: bool = False) -> str:
    messengers = []
    if order.hasViber:
        messengers.append("Viber")
    if order.hasTelegram:
        messengers.append("Telegram")
    if order.hasWhatsApp:
        messengers.append("WhatsApp")
    messengers_str = f" ({', '.join(messengers)})" if messengers else ""

    formatted = (
        f"<b>📅 Дата и время: {order.date}, {order.time}</b>\n\n"
        f"📍 Откуда: <blockquote>{order.from_location}</blockquote>\n"
        f"📍 Куда: <blockquote>{order.to_location}</blockquote>\n\n"
        f"👤 Имя: {order.name}\n"
        # f"<a href='tg://user?id={order.tg_id}'>🤖 Telegram-профиль заказчика</a>\n\n"
        f"📞 Телефон: {order.phone}{messengers_str}\n\n"
        f"👨‍👩‍👧‍👦 Всего пассажиров: <b>{order.adults + order.children}</b>\n"
        f"(из них до 12 лет: <b>{order.children}</b>)\n\n"
        f"🧳 Багажа: <b>{order.baggage}</b>"
    )

    if (order.price):
        formatted += f"\n\n💰 <i>Стоимость трансфера составляет <b>{order.price}€</b>.</i>"
    
    if (not has_price_question):
        formatted += " <b><i>Подтверждаете заказ?</i></b>"
    
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

def get_admin_buttons(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Дать цену", callback_data=f"set_price:{order_id}"),
            InlineKeyboardButton(text="❌ Отказаться", callback_data=f"admin_decline:{order_id}")
        ]
    ])

@dp.message(CommandStart())
async def start_handler(message: Message):
    photo_path = "assets/banner.jpg"
    caption = (
        f"👋 Добро пожаловать, @{message.from_user.username}! Это бот <b>Transsfera</b>. \n\n"
        "Здесь вы можете быстро и удобно заказать трансфер по всему побережью <i>Costa Blanca</i>, "
        "в том числе в аэропорты Аликанте, Валенсии и Барселоны ✈️\n\n"
        "Введите данные по <b>кнопке внизу</b> ⬇️⬇️⬇️, после чего бот рассчитает цену вашей поездки. "
        "Вам останется только подтвердить заказ ✅ и... Приятного пути!"
    )
    logging.info(f"User {message.from_user.id} ({message.from_user.username}) opened the bot")
    await message.answer_photo(
        photo=FSInputFile(path=photo_path),
        caption=caption,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML
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
    admin_message_id = data.get("admin_message_id")

    order = await update_order(order_id, {"price": price})
    if order is None:
        await message.answer("⚠️ Заказ не найден.")
        return

    formatted = format_order(order)
    await bot.send_message(
        order.tg_id,
        f"🚖 Ваш заказ <b>#{order.public_id}</b>\n\n{formatted}",
        reply_markup=get_price_accept_buttons(order_id)
    )

    if admin_message_id:
        try:
            await bot.edit_message_text(
                chat_id=os.getenv("ADMIN_ID"),
                message_id=admin_message_id,
                text=f"🎉 Новый заказ <b>#{order.public_id}</b>\n\n{formatted}\n\n✅ <i>Вы назначили цену в <b>{price}€</b>.</i>",
                reply_markup=None
            )
        except Exception as e:
            pass

    await message.answer("✅ Цена отправлена клиенту.")
    await state.clear()

@dp.callback_query(F.data.startswith("accept_price:"))
async def handle_accept_price(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]

    order = await update_order(order_id, {"accepted": True})
    if order is None:
        await callback.message.answer("⚠️ Заказ не найден.")
        await callback.answer()
        return

    await callback.message.edit_reply_markup()

    # Клиенту
    await callback.message.answer("✅ Отлично! Водитель свяжется с вами в течение 15 минут.")

    # Админу
    await bot.send_message(
        os.getenv("ADMIN_ID"),
        f"✅ Клиент подтвердил заказ <b>#{order.public_id}</b>\n\n"
        f"{format_order(order, True)}\n\n#подтверждённые_заказы"
    )

    await callback.answer()

@dp.callback_query(F.data.startswith("decline_price:"))
async def handle_decline_price(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]

    logging.info(f"Attempting to decline order: {order_id}")

    order = await get_order(order_id)
    if not order:
        logging.warning(f"Order not found: {order_id}")
        await callback.message.answer("⚠️ Заказ не найден.")
        await callback.answer()
        return

    await delete_order(order_id)

    await callback.message.edit_reply_markup()
    await callback.message.answer("😔 Очень жаль! Возвращайтесь в любое время, мы будем ждать вас снова.")

    await bot.send_message(os.getenv("ADMIN_ID"), f"😔 Клиент не подтвердил заказ #{order.public_id}.")

    await callback.answer()

@dp.callback_query(F.data.startswith("set_price:"))
async def set_price_callback(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.split(":")[1]

    order = await get_order(order_id)
    if not order:
        await callback.message.answer("⚠️ Заказ не найден.")
        await callback.answer()
        return

    if order.price:
        await callback.message.answer(f"❌ Вы уже определили цену в <b>{order.price}€</b> для этого заказа!")
        await callback.answer()
        return
    
    await state.update_data(order_id=order_id, admin_message_id=callback.message.message_id)
    await callback.message.answer(f"💰 Введите цену для заказа #{order.public_id}...")
    await state.set_state(PriceStates.waiting_for_price)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_decline:"))
async def handle_admin_decline(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]
    
    order = await get_order(order_id)
    if not order:
        await callback.message.answer("⚠️ Заказ не найден.")
        await callback.answer()
        return

    await delete_order(order_id)

    await callback.message.edit_reply_markup()

    await callback.message.answer(f"❌ Заказ <b>#{order.public_id}</b> отклонён.")

    await bot.send_message(
        order.tg_id,
        f"🚖 Ваш заказ <b>#{order.public_id}</b>\n\n😔 К сожалению, на дату <b>{order.date}</b> в <b>{order.time}</b> свободных машин нет."
    )

    await callback.answer()

@dp.message(F.content_type == ContentType.WEB_APP_DATA)
async def web_app_handler(message: Message):
    data = message.web_app_data.data
    parsed_order = parse_order(data, message.from_user.id)
    order_id = await create_order(parsed_order)
    await message.answer(f"✅ Ваш заказ <b>#{parsed_order.public_id}</b> принят! Обработка может занять до 5 минут.")
    formatted = format_order(parsed_order, True)
    logging.info(f"New order {order_id}")
    await bot.send_message(os.getenv("ADMIN_ID"), f"🎉 Новый заказ <b>#{parsed_order.public_id}</b>\n\n{formatted}", reply_markup=get_admin_buttons(order_id=str(order_id)), )

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")