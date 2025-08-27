from db.service.orders import OrderModel
from datetime import datetime

def convert_date(date_string):
    months_ru = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    
    date_obj = datetime.strptime(date_string, "%Y-%m-%d")
    
    day = date_obj.day
    month = months_ru[date_obj.month]
    year = date_obj.year
    
    return f"{day} {month} {year}"

def format_messengers(order: OrderModel) -> str:
    messengers = []
    if order.hasViber:
        messengers.append("Viber")
    if order.hasTelegram:
        messengers.append("Telegram")
    if order.hasWhatsApp:
        messengers.append("WhatsApp")
    return f" ({', '.join(messengers)})" if messengers else ""

def format_user_link(order: OrderModel) -> str:
    if order.username:
        return f"@{order.username}"
    
def format_for_client(order: OrderModel, include_confirmation: bool = False) -> str:
    messengers_str = format_messengers(order)
    
    formatted = (
        f"<b>📅  {convert_date(order.date)} • {order.time}</b>\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📍  Откуда: <blockquote>{order.from_location}</blockquote>\n"
        f"📍  Куда: <blockquote>{order.to_location}</blockquote>\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"👤  Имя: {order.name}\n"
        f"📞  Телефон: {order.phone}{messengers_str}\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"👨‍👩‍👧‍👦  Всего пассажиров: <b>{order.adults + order.children}</b>\n"
        f"(из них до 12 лет: <b>{order.children}</b>)\n"
        f"🧳  Багажа: <b>{order.baggage}</b>\n\n"
    )

    if order.comment:
        formatted += f'💬  Комментарий:\n   "{order.comment}"\n\n'

    if order.price:
        formatted += f"━━━━━━━━━━━━━━━━\n💰  <b>Стоимость: {order.price}€</b>"
    
    if include_confirmation and order.price:
        formatted += "\n\n💡  <i>После подтверждения водитель свяжется с вами для уточнения деталей.</i>\n\n<b>Подтверждаете поездку?</b>"
    
    return formatted

def format_for_admin(order: OrderModel, extra_info: str = None) -> str:
    messengers_str = format_messengers(order)
    user_link = format_user_link(order)
    
    formatted = (
        f"<b>📅  {convert_date(order.date)} • {order.time}</b>\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📍  Откуда: <blockquote>{order.from_location}</blockquote>\n"
        f"📍  Куда: <blockquote>{order.to_location}</blockquote>\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"👤  {user_link}\n"
        f"📝  Имя: {order.name}\n"
        f"📞  Телефон: {order.phone}{messengers_str}\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"👨‍👩‍👧‍👦  Всего пассажиров: <b>{order.adults + order.children}</b>\n"
        f"(из них до 12 лет: <b>{order.children}</b>)\n"
        f"🧳  Багажа: <b>{order.baggage}</b>\n\n"
        
    )

    if order.comment:
        formatted += f'💬  Комментарий:\n   "{order.comment}"\n\n'

    if order.price:
        formatted += f"━━━━━━━━━━━━━━━━\n💰  <b>Стоимость: {order.price}€</b>"

    if extra_info:
        formatted += f"{extra_info}"
    
    return formatted