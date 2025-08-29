import os
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
)

def get_price_accept_buttons(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅  Подтвердить", callback_data=f"accept_price:{order_id}"),
            InlineKeyboardButton(text="❌  Отменить", callback_data=f"decline_price:{order_id}")
        ]
    ])

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚗  ЗАКАЗАТЬ ТРАНСФЕР", web_app=WebAppInfo(url="https://" + os.getenv("WEBAPP_URL")))]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_admin_buttons(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰  Назначить цену", callback_data=f"set_price:{order_id}"),
            InlineKeyboardButton(text="❌  Отклонить", callback_data=f"admin_decline:{order_id}")
        ]
    ])