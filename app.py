import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, ContentType, CallbackQuery, FSInputFile
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from db.service.orders import parse_order, create_order, update_order, get_order, delete_order
from utils import format_for_admin, format_for_client, convert_date
from keyboards import get_main_keyboard, get_price_accept_buttons, get_admin_buttons

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class PriceStates(StatesGroup):
    waiting_for_price = State()

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
        price = int(message.text.strip())
    except ValueError:
        await message.answer("❌  Некорректная цена\n\n⌨️  Попробуйте ещё раз:")
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    admin_message_id = data.get("admin_message_id")

    order = await update_order(order_id, {"price": price})
    if order is None:
        await message.answer("🔍  Упс! Заказ не найден в системе")
        return
    
    await bot.send_message(
        order.tg_id,
        f"💎  Цена рассчитана! <b>#{order.public_id}</b>\n\n━━━━━━━━━━━━━━━━\n💰 <b>{price}€</b>\n━━━━━━━━━━━━━━━━\n\n💡  <b>Подтвердите заказ</b>, после чего наш водитель свяжется с вами в течение 15 минут для уточнения деталей",
        reply_markup=get_price_accept_buttons(order_id)
    )

    if admin_message_id:
        try:
            formatted_admin = format_for_admin(
                order, 
                extra_info=f"\n\n⏳  Ожидание ответа..."
            )
            await bot.edit_message_text(
                chat_id=os.getenv("ADMIN_ID"),
                message_id=admin_message_id,
                text=f"🎉  ЗАКАЗ <b>#{order.public_id}</b> • ЦЕНА НАЗНАЧЕНА\n\n{formatted_admin}",
                reply_markup=None
            )
        except Exception as e:
            logging.warning(f"Не удалось изменить сообщение: {e}")

    await message.answer(f"✅  Цена {price}€ отправлена клиенту!")
    await state.clear()

@dp.callback_query(F.data.startswith("accept_price:"))
async def handle_accept_price(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]

    order = await update_order(order_id, {"accepted": True})
    if order is None:
        await callback.message.answer("🔍  Упс! Заказ не найден в системе")
        await callback.answer()
        return

    await callback.message.edit_reply_markup()

    # Клиенту
    await callback.message.answer("🎉  Отлично! Ваша поездка забронирована\n\n⏰  Водитель свяжется с вами в течение 15 минут\n\n🚗  Приятного путешествия!")

    # Админу
    formatted_admin = format_for_admin(order)
    await bot.send_message(
        os.getenv("ADMIN_ID"),
        f"🎊  ПОДТВЕРЖДЁН! <b>#{order.public_id}</b>\n\n✅  Клиент @{order.username} принял цену {order.price}€\n\n"
        f"{formatted_admin}\n\n#подтверждённые_заказы"
    )

    await callback.answer()

@dp.callback_query(F.data.startswith("decline_price:"))
async def handle_decline_price(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]

    order = await get_order(order_id)
    if not order:
        logging.warning(f"Order not found: {order_id}")
        await callback.message.answer("🔍  Упс! Заказ не найден в системе")
        await callback.answer()
        return

    await delete_order(order_id)
    await callback.message.edit_reply_markup()
    await callback.message.answer("😔  Очень жаль! Возвращайтесь в любое время, мы будем ждать вас снова.")
    await bot.send_message(os.getenv("ADMIN_ID"), f"💔  Отказ от <b>#TR001</b>\n\n❌  @{order.username} не подтвердил цену {order.price}€")
    await callback.answer()

@dp.callback_query(F.data.startswith("set_price:"))
async def set_price_callback(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.split(":")[1]

    order = await get_order(order_id)
    if not order:
        await callback.message.answer("🔍  Упс! Заказ не найден в системе")
        await callback.answer()
        return

    if order.price:
        await callback.message.answer(f"💰  Цена уже назначена!\n\nДля заказа <b>{order.public_id}</b> установлена цена {order.price}€")
        await callback.answer()
        return
    
    await state.update_data(order_id=order_id, admin_message_id=callback.message.message_id)
    await callback.message.answer(f"💸  Назначение цены для <b>#{order.public_id}</b>\n\n⌨️  Введите цену в евро:")
    await state.set_state(PriceStates.waiting_for_price)
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_decline:"))
async def handle_admin_decline(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]
    
    order = await get_order(order_id)
    if not order:
        await callback.message.answer("🔍  Упс! Заказ не найден в системе")
        await callback.answer()
        return

    await delete_order(order_id)

    try:
        formatted_admin = format_for_admin(order)
        await bot.edit_message_text(
            chat_id=os.getenv("ADMIN_ID"),
            message_id=callback.message.message_id,
            text=f"🚫  ЗАКАЗ <b>#{order.public_id}</b> • ВЫ ОТКЛОНИЛИ\n\n{formatted_admin}",
            reply_markup=None
        )
    except Exception as e:
        logging.warning(f"Не удалось изменить сообщение: {e}")

    await callback.message.answer(f"✅  Заказ <b>#{order.public_id}</b> отклонён")

    await bot.send_message(
        order.tg_id,
        f"🚫  Заказ <b>#{order.public_id}</b>\n\n😔  К сожалению, на <b>{convert_date(order.date)} • {order.time}</b> все автомобили заняты"
    )

    await callback.answer()

@dp.message(F.content_type == ContentType.WEB_APP_DATA)
async def web_app_handler(message: Message):
    data = message.web_app_data.data
    parsed_order = parse_order(data, message.from_user.id, message.from_user.username)
    order_id = await create_order(parsed_order)
    formatted_client = format_for_client(parsed_order)
    await message.answer(f"🎯  Заказ <b>#{parsed_order.public_id}</b> принят!\n\n{formatted_client}\n\n⏰  Рассчитываем стоимость...\nОтветим в течение 5 минут")
    formatted_admin = format_for_admin(parsed_order)
    logging.info(f"New order {order_id}")
    await bot.send_message(os.getenv("ADMIN_ID"), f"🔥  НОВЫЙ ЗАКАЗ <b>#{parsed_order.public_id}</b>\n\n{formatted_admin}", reply_markup=get_admin_buttons(order_id=str(order_id)))

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")