# keyboards.py
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CopyTextButton, InlineKeyboardButton

import database as db


MAIN_MENU_LABELS = {
    "services": "🎇 Xizmatlar",
    "topup": "💰 Pul kiritish",
    "account": "💸 Hisobim",
    "top": "🏆 Top",
    "settings": "⚙️ Sozlamalar",
    "support": "☎️ Qo'llab-quvvatlash",
    "prices": "💰 Narxlar",
}


def language_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    b.button(text="🇷🇺 Русский", callback_data="lang_ru")
    b.button(text="🇬🇧 English", callback_data="lang_en")
    b.adjust(1)
    return b.as_markup()


def rules_kb():
    b = InlineKeyboardBuilder()
    b.button(text="✅ Roziman", callback_data="agree_rules")
    return b.as_markup()


def subscribe_kb(channel_link):
    b = InlineKeyboardBuilder()
    b.button(text="📢 Kanalga obuna bo'lish", url=channel_link)
    b.button(text="✅ Tekshirish", callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()


def main_menu_kb():
    """Pastki (reply) klaviatura — asosiy menyu doim ekran ostida turadi."""
    rows = [
        [KeyboardButton(text=MAIN_MENU_LABELS["services"]), KeyboardButton(text=MAIN_MENU_LABELS["topup"])],
        [KeyboardButton(text=MAIN_MENU_LABELS["account"]), KeyboardButton(text=MAIN_MENU_LABELS["top"])],
        [KeyboardButton(text=MAIN_MENU_LABELS["settings"]), KeyboardButton(text=MAIN_MENU_LABELS["support"])],
        [KeyboardButton(text=MAIN_MENU_LABELS["prices"])],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def back_kb(target="menu_main"):
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Ortga", callback_data=target)
    return b.as_markup()


def categories_kb(categories):
    b = InlineKeyboardBuilder()
    for c in categories:
        b.button(text=c["name"], callback_data=f"cat_{c['id']}")
    b.button(text="◀️ Ortga", callback_data="menu_main")
    b.adjust(2)
    return b.as_markup()


def products_kb(products, cat_id):
    b = InlineKeyboardBuilder()
    for p in products:
        label = f"{p['name']}" + (f" — {p['price']:,} so'm".replace(",", " ") if p["price"] else "")
        b.button(text=label, callback_data=f"prod_{p['id']}")
    b.button(text="◀️ Ortga", callback_data="menu_services")
    b.adjust(1)
    return b.as_markup()


def topup_methods_kb():
    b = InlineKeyboardBuilder()
    b.button(text="💳 Karta orqali", callback_data="topup_karta")
    b.button(text="🏧 Bankomat", callback_data="topup_bankomat")
    b.button(text="🅿️ Payme", callback_data="topup_payme")
    b.button(text="◀️ Ortga", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


def topup_created_kb(order_code, amount):
    """Nusxalash tugmalari (Telegram'ning copy_text funksiyasi orqali)."""
    b = InlineKeyboardBuilder()
    card = db.get_setting("card_number") or ""
    b.row(
        InlineKeyboardButton(text="📋 Kartani nusxalash", copy_text=CopyTextButton(text=card.replace(" ", ""))),
        InlineKeyboardButton(text="📋 Summani nusxalash", copy_text=CopyTextButton(text=str(amount))),
    )
    b.button(text="❌ Bekor qilish", callback_data=f"cancel_topup_{order_code}")
    b.adjust(2, 1)
    return b.as_markup()


def bankomat_paid_kb(order_code):
    b = InlineKeyboardBuilder()
    b.button(text="✅ To'lov qildim", callback_data=f"bankomat_paid_{order_code}")
    b.button(text="❌ Bekor qilish", callback_data=f"cancel_topup_{order_code}")
    b.adjust(1)
    return b.as_markup()


def admin_topup_confirm_kb(order_code):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=f"admin_topup_ok_{order_code}")
    b.button(text="❌ Rad etish", callback_data=f"admin_topup_no_{order_code}")
    b.adjust(2)
    return b.as_markup()


def admin_order_confirm_kb(order_code):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=f"admin_order_ok_{order_code}")
    b.button(text="❌ Rad etish", callback_data=f"admin_order_no_{order_code}")
    b.adjust(2)
    return b.as_markup()


def account_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📈 To'ldirish tarixi", callback_data="topup_history")
    b.button(text="📉 Sarf tarixi", callback_data="spend_history")
    b.button(text="◀️ Ortga", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


def top_filters_kb():
    b = InlineKeyboardBuilder()
    b.button(text="✅ Bugun", callback_data="top_today")
    b.button(text="Kecha", callback_data="top_yesterday")
    b.button(text="Shu hafta", callback_data="top_week")
    b.button(text="Shu oy", callback_data="top_month")
    b.button(text="Hammasi", callback_data="top_all")
    b.button(text="◀️ Ortga", callback_data="menu_main")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def settings_kb():
    b = InlineKeyboardBuilder()
    b.button(text="🇺🇿 O'zbekcha", callback_data="setlang_uz")
    b.button(text="🇷🇺 Русский", callback_data="setlang_ru")
    b.button(text="🇬🇧 English", callback_data="setlang_en")
    b.button(text="◀️ Ortga", callback_data="menu_main")
    b.adjust(3, 1)
    return b.as_markup()


def support_kb():
    b = InlineKeyboardBuilder()
    b.button(text="❓ Tez-tez so'raladigan savollar", callback_data="faq_list")
    b.button(text="✍️ Adminga yozish", callback_data="support_write")
    b.button(text="◀️ Ortga", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()


def insufficient_balance_kb():
    b = InlineKeyboardBuilder()
    b.button(text="💰 Hisobni to'ldirish", callback_data="menu_topup")
    b.button(text="◀️ Ortga", callback_data="menu_services")
    b.adjust(1)
    return b.as_markup()
