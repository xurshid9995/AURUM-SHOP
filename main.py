# main.py
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile

import config
import database as db
import keyboards as kb
import admin as admin_module
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

WELCOME_IMAGE = "assets/welcome.jpg"
PRICES_IMAGE = "assets/prices.jpg"

TOPUP_METHOD_LABELS = {
    "karta": "💳 Kartadan to'ldirildi",
    "bankomat": "🏧 Bankomatdan to'ldirildi",
}


class Flow(StatesGroup):
    entering_game_id = State()
    entering_topup_amount = State()
    entering_bankomat_amount = State()
    waiting_receipt = State()
    writing_support = State()# ======================================================================
# YORDAMCHI FUNKSIYALAR
# ======================================================================

async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=reply_markup)
        except Exception:
            await callback.message.answer(text, reply_markup=reply_markup)


async def send_view(target, text: str, reply_markup=None):
    """target — CallbackQuery (inline tugma bosilganda) yoki Message (pastki reply
    tugma bosilganda) bo'lishi mumkin. Har ikkalasida ham foydalanuvchiga bir xil
    ko'rinishni chiqaradi."""
    if isinstance(target, CallbackQuery):
        await safe_edit(target, text, reply_markup=reply_markup)
        await target.answer()
    else:
        await target.answer(text, reply_markup=reply_markup)


async def send_text_key(target, key, reply_markup=None, **kwargs):
    """`texts` jadvalidagi matnni chiqaradi. Agar admin panel orqali shu matnga
    rasm biriktirilgan bo'lsa (adm_texts → rasm bilan yuborish), o'sha rasm ham
    birga chiqariladi — avval faqat 'welcome' va 'prices' uchun ishlar edi."""
    text = db.get_text(key, **kwargs)
    image_path = db.get_text_image(key)
    if image_path:
        msg = target.message if isinstance(target, CallbackQuery) else target
        try:
            await msg.answer_photo(FSInputFile(image_path), caption=text, reply_markup=reply_markup)
        except Exception:
            await msg.answer(text, reply_markup=reply_markup)
        if isinstance(target, CallbackQuery):
            await target.answer()
    else:
        await send_view(target, text, reply_markup=reply_markup)


def target_user_id(target):
    return target.from_user.id


def is_admin(user_id):
    u = db.get_user(user_id)
    return bool(u and u["role"] in ("admin", "super_admin"))


def is_super_admin(user_id):
    u = db.get_user(user_id)
    return bool(u and u["role"] == "super_admin")


async def is_subscribed(user_id):
    if db.get_setting("mandatory_sub_enabled") != "1":
        return True
    channel = db.get_setting("mandatory_sub_channel")
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(channel, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        return True  # kanal noto'g'ri sozlangan bo'lsa, mijozni bloklamaymiz


async def show_main_menu(target, as_new=False):
    """target — Message yoki CallbackQuery bo'lishi mumkin. Asosiy menyu endi
    pastki (reply) klaviatura bo'lgani uchun har doim yangi xabar yuboriladi
    (mavjud xabarni tahrirlab reply-klaviatura biriktirib bo'lmaydi)."""
    text = "🏠 Asosiy menyu. Pastdagi tugmalardan birini tanlang:"
    if isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=kb.main_menu_kb())
    else:
        await target.answer(text, reply_markup=kb.main_menu_kb())


async def check_onboarding(message: Message, user_id: int) -> bool:
    """Til/qoida/obuna bosqichlarini tekshiradi. True = davom etsa bo'ladi (menyuga chiqadi)."""
    user = db.get_user(user_id)

    if not user["language"]:
        await message.answer("🌐 Tilni tanlang / Choose language / Выберите язык:", reply_markup=kb.language_kb())
        return False

    if not user["agreed_rules_at"]:
        await send_text_key(message, "rules", reply_markup=kb.rules_kb())
        return False

    if not await is_subscribed(user_id):
        channel = db.get_setting("mandatory_sub_channel")
        await send_text_key(message, "mandatory_sub", reply_markup=kb.subscribe_kb(channel))
        return False

    return True


# ======================================================================
# START / ONBOARDING
# ======================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    is_new = db.is_new_user(message.from_user.id)
    db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

    if await check_onboarding(message, message.from_user.id):
        caption = db.get_text("welcome", name=message.from_user.full_name)
        img_path = db.get_text_image("welcome") or WELCOME_IMAGE
        try:
            await message.answer_photo(FSInputFile(img_path), caption=caption, reply_markup=kb.main_menu_kb())
        except Exception:
            await message.answer(caption, reply_markup=kb.main_menu_kb())


@dp.callback_query(F.data.startswith("lang_"))
async def choose_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    db.set_user_language(callback.from_user.id, lang)
    await callback.answer()
    if await check_onboarding(callback.message, callback.from_user.id):
        await show_main_menu(callback.message)
    else:
        pass  # check_onboarding keyingi bosqich xabarini o'zi yuboradi


@dp.callback_query(F.data == "agree_rules")
async def agree_rules(callback: CallbackQuery):
    db.agree_to_rules(callback.from_user.id)
    await callback.answer("Rahmat!")
    if await is_subscribed(callback.from_user.id):
        await show_main_menu(callback.message)
    else:
        channel = db.get_setting("mandatory_sub_channel")
        await send_text_key(callback.message, "mandatory_sub", reply_markup=kb.subscribe_kb(channel))


@dp.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.answer("✅ Obuna tasdiqlandi!")
        await show_main_menu(callback.message)
    else:
        await callback.answer("❗ Hali obuna bo'lmadingiz.", show_alert=True)


@dp.callback_query(F.data == "menu_main")
async def menu_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await show_main_menu(callback)


@dp.callback_query(F.data == "show_prices")
async def show_prices(callback: CallbackQuery):
    await open_prices(callback)


@dp.message(F.text == kb.MAIN_MENU_LABELS["prices"])
async def show_prices_reply(message: Message):
    await open_prices(message)PRICE_LIST_TEXT = (
    "💎 Narxlar\n\n"
    "100💎 = 10 990 so'm 💲\n"
    "500💎 = 54 990 so'm 💲\n"
    "1000💎 = 109 990 so'm 💲\n"
    "1500💎 = 169 990 so'm 💲\n"
    "2000💎 = 219 990 so'm 💲\n"
    "3000💎 = 329 990 so'm 💲"
)


async def open_prices(target):
    img_path = db.get_text_image("prices") or PRICES_IMAGE
    msg = target.message if isinstance(target, CallbackQuery) else target
    try:
        await msg.answer_photo(FSInputFile(img_path), caption=PRICE_LIST_TEXT)
    except Exception:
        await msg.answer(PRICE_LIST_TEXT)
    if isinstance(target, CallbackQuery):
        await target.answer()


# ======================================================================
# XIZMATLAR (toifalar → mahsulotlar → xarid)
# ======================================================================

@dp.callback_query(F.data == "menu_services")
async def menu_services(callback: CallbackQuery, state: FSMContext):
    await open_services(callback, state)


@dp.message(F.text == kb.MAIN_MENU_LABELS["services"])
async def menu_services_reply(message: Message, state: FSMContext):
    await open_services(message, state)


async def open_services(target, state: FSMContext):
    await state.clear()
    cats = db.get_categories()
    await send_view(target, "🛍 Mahsulot toifasini tanlang:", reply_markup=kb.categories_kb(cats))


@dp.callback_query(F.data.startswith("cat_"))
async def choose_category(callback: CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    cat = db.get_category(cat_id)
    products = db.get_products(cat_id)
    if not products:
        await callback.answer("Bu toifada hozircha mahsulot yo'q.", show_alert=True)
        return

    lines = [f"📦 {cat['name']}", "", "Mavjud paketlar:", ""]
    for p in products:
        if p["price"]:
            lines.append(f"🔹 {p['name']} = {p['price']:,} so'm".replace(",", " "))
        else:
            lines.append(f"🔹 {p['name']} — tez orada")
    lines.append("")
    lines.append("👇 Kerakli paketni pastdagi tugmalardan tanlang:")

    await safe_edit(callback, "\n".join(lines), reply_markup=kb.products_kb(products, cat_id))
    await callback.answer()


@dp.callback_query(F.data.startswith("prod_"))
async def choose_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    product = db.get_product(product_id)
    if not product or not product["active"]:
        await send_text_key(callback, "section_disabled", reply_markup=kb.back_kb("menu_services"))
        return

    if product["requires_game_id"]:
        await state.update_data(product_id=product_id)
        await state.set_state(Flow.entering_game_id)
        await safe_edit(callback, f"🎮 {product['name']}\n\nO'yin ichidagi ID'ingizni kiriting:")
        await callback.answer()
        return

    await state.update_data(product_id=product_id, game_uid=None)
    await show_purchase_confirmation(callback, product, game_uid=None, state=state)
    await callback.answer()


@dp.message(Flow.entering_game_id)
async def entered_game_id(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("⚠️ Faqat raqam kiriting. O'yin ichidagi ID'ingizni qayta kiriting:")
        return

    data = await state.get_data()
    product = db.get_product(data["product_id"])
    await state.update_data(game_uid=text)
    await show_purchase_confirmation(message, product, game_uid=text, state=state)


async def show_purchase_confirmation(target, product, game_uid, state: FSMContext):
    if not product["price"] or product["price"] <= 0:
        await state.clear()
        await send_text_key(target, "section_disabled", reply_markup=kb.back_kb("menu_services"))
        return

    user = db.get_user(target_user_id(target))
    if user["balance"] < product["price"]:
        await state.clear()
        await send_text_key(target, "insufficient_balance", reply_markup=kb.insufficient_balance_kb())
        return

    text = (
        f"🛒 Buyurtmani tasdiqlang\n\n"
        f"📦 Mahsulot: {product['name']}\n"
        f"💰 Narx: {product['price']:,} so'm".replace(",", " ")
    )
    if game_uid:
        text += f"\n🎮 O'yin ID: {game_uid}"
    text += "\n\nXaridni tasdiqlaysizmi? Balansingizdan yechib olinadi."

    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data="confirm_purchase")
    b.button(text="❌ Bekor qilish", callback_data="cancel_purchase")
    b.adjust(2)
    await send_view(target, text, reply_markup=b.as_markup())


@dp.callback_query(F.data == "confirm_purchase")
async def confirm_purchase(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data.get("product_id")
    if not product_id:
        await callback.answer("❗ Buyurtma topilmadi, qaytadan urinib ko'ring.", show_alert=True)
        await state.clear()
        return
    product = db.get_product(product_id)
    game_uid = data.get("game_uid")
    await state.clear()
    await finalize_purchase(callback.message, callback.from_user.id, product, game_uid=game_uid)
    await callback.answer()


@dp.callback_query(F.data == "cancel_purchase")
async def cancel_purchase(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(callback, "❌ Xarid bekor qilindi.", reply_markup=kb.back_kb("menu_services"))
    await callback.answer()


async def finalize_purchase(message: Message, user_id: int, product, game_uid):
    if not product["price"] or product["price"] <= 0:
        await send_text_key(message, "section_disabled", reply_markup=kb.back_kb("menu_services"))
        return

    user = db.get_user(user_id)
    if user["balance"] < product["price"]:
        await send_text_key(message, "insufficient_balance", reply_markup=kb.insufficient_balance_kb())
        return

    code = db.create_order(user_id, product["id"], product["name"], product["price"], game_uid)
    db.adjust_balance(user_id, -product["price"], "purchase", note=f"Buyurtma #{code}")

    text = (
        f"✅ Buyurtma yaratildi!\n\n"
        f"🆔 Buyurtma: {code}\n"
        f"📦 Mahsulot: {product['name']}\n"
        f"💰 Narx: {product['price']:,} so'm".replace(",", " ")
    )
    if game_uid:
        text += f"\n🎮 O'yin ID: {game_uid}"
    text += "\n\n5 daqiqa ichida bekor qilishingiz mumkin."

    from keyboards import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data=f"cancel_order_{code}")
    await message.answer(text, reply_markup=b.as_markup())

    asyncio.create_task(schedule_order_forward(code))


async def schedule_order_forward(code, delay_seconds=300):
    await asyncio.sleep(delay_seconds)
    order = db.get_order_by_code(code)
    if not order or order["status"] != "pending":
        return
    await forward_order_to_admins(order)


async def forward_order_to_admins(order):
    user = db.get_user(order["user_id"])
    text = (
        f"🆕 Yangi buyurtma #{order['order_code']}\n\n"
        f"Foydalanuvchi: {user['full_name']} (@{user['username']})\n"
        f"Mahsulot: {order['product_name']}\n"
        f"Narx: {order['price']:,} so'm".replace(",", " ")
    )
    if order["game_uid"]:
        text += f"\nO'yin ID: {order['game_uid']}"
    for admin_row in db.get_all_admins():
        try:
            await bot.send_message(admin_row["user_id"], text, reply_markup=kb.admin_order_confirm_kb(order["order_code"]))
        except Exception:
            pass


@dp.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order(callback: CallbackQuery):
    code = callback.data.replace("cancel_order_", "")
    order = db.get_order_by_code(code)
    if not order or order["status"] != "pending":
        await callback.answer("Bu buyurtma allaqachon qayta ishlangan.", show_alert=True)
        return
    db.set_order_status(code, "cancelled")
    db.adjust_balance(order["user_id"], order["price"], "refund", note=f"Bekor qilindi #{code}")
    await safe_edit(callback, f"❌ Buyurtma #{code} bekor qilindi, mablag' balansga qaytarildi.")
    await callback.answer()


# ======================================================================
# PUL KIRITISH
# ======================================================================

@dp.callback_query(F.data == "menu_topup")
async def menu_topup(callback: CallbackQuery, state: FSMContext):
    await open_topup(callback, state)


@dp.message(F.text == kb.MAIN_MENU_LABELS["topup"])
async def menu_topup_reply(message: Message, state: FSMContext):
    await open_topup(message, state)


async def open_topup(target, state: FSMContext):
    await state.clear()
    await send_view(target, "💰 To'lov usulini tanlang:", reply_markup=kb.topup_methods_kb())


@dp.callback_query(F.data == "topup_payme")
async def topup_payme(callback: CallbackQuery):
    if db.get_setting("payme_enabled") != "1":
        await send_text_key(callback, "section_disabled", reply_markup=kb.back_kb("menu_topup"))
    else:
        await callback.answer()


@dp.callback_query(F.data == "topup_karta")
async def topup_karta(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.entering_topup_amount)
    await safe_edit(callback, db.get_text("topup_amount_prompt"), reply_markup=kb.back_kb("menu_topup"))
    await callback.answer()


@dp.message(Flow.entering_topup_amount)
async def entered_topup_amount(message: Message, state: FSMContext):
    await handle_topup_amount(message, state, @dp.callback_query(F.data == "topup_bankomat")
async def topup_bankomat(callback: CallbackQuery, state: FSMContext):
    text = (
        f"✍️ To'lov turi: 📱 Bankomat\n\n"
        f"✍️ Karta: {db.get_setting('card_number')}\n"
        f"👤 Karta egasi: {db.get_setting('card_owner')}\n"
        f"👤 Ulangan raqam: {db.get_setting('bankomat_phone')}\n\n"
        f"📌 Qo'llanma:\n\n"
        f"1️⃣ Bankomat orqali yuqoridagi kartaga to'lovni amalga oshiring\n"
        f"2️⃣ «✅ To'lov qildim» tugmasini bosing\n"
        f"3️⃣ Bankomat kvitansiyasidagi summani kiriting\n"
        f"4️⃣ Kvitansiya rasmini (screenshot yoki foto) yuboring"
    )
    code = db.generate_order_code()
    await state.update_data(bankomat_code=code)
    await safe_edit(callback, text, reply_markup=kb.bankomat_paid_kb(code))
    await callback.answer()


@dp.callback_query(F.data.startswith("bankomat_paid_"))
async def bankomat_paid(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Flow.entering_bankomat_amount)
    await safe_edit(callback, "To'lagan summangizni kiriting:")
    await callback.answer()


@dp.message(Flow.entering_bankomat_amount)
async def entered_bankomat_amount(message: Message, state: FSMContext):
    await handle_topup_amount(message, state, method="bankomat")


async def handle_topup_amount(message: Message, state: FSMContext, method: str):
    text = message.text.strip().replace(" ", "")
    if not text.isdigit():
        await message.answer(db.get_text("topup_invalid_amount"))
        return
    amount = int(text)
    if amount < 1000:
        await message.answer(db.get_text("topup_min_amount"))
        return

    code, unique_amount, created, expires = db.create_topup(message.from_user.id, method, amount)
    await state.set_state(Flow.waiting_receipt)
    await state.update_data(topup_code=code)

    if method == "karta":
        text = db.get_text(
            "topup_created",
            order_code=code,
            amount=f"{unique_amount:,}".replace(",", " "),
            card_number=db.get_setting("card_number"),
            card_owner=db.get_setting("card_owner"),
            created=created.strftime("%H:%M"),
            expires=expires.strftime("%H:%M"),
        )
        image_path = db.get_text_image("topup_created")
        if image_path:
            try:
                await message.answer_photo(FSInputFile(image_path), caption=text, reply_markup=kb.topup_created_kb(code, unique_amount))
            except Exception:
                await message.answer(text, reply_markup=kb.topup_created_kb(code, unique_amount))
        else:
            await message.answer(text, reply_markup=kb.topup_created_kb(code, unique_amount))
    else:
        await message.answer(
            f"To'lov qabul qilindi: {amount:,} so'm.\n\nEndi to'lov chekini (rasm) yuboring 📸".replace(",", " ")
        )

    asyncio.create_task(schedule_topup_expiry(code))


async def schedule_topup_expiry(code, delay_seconds=None):
    minutes = int(db.get_setting("topup_expiry_minutes") or 5)
    await asyncio.sleep(delay_seconds if delay_seconds is not None else minutes * 60)
    topup = db.get_topup_by_code(code)
    if not topup or topup["status"] != "awaiting_receipt":
        return
    db.set_topup_status(code, "expired")
    try:
        text = db.get_text("topup_expired", admin_contact="@admin_username")
        image_path = db.get_text_image("topup_expired")
        if image_path:
            await bot.send_photo(topup["user_id"], FSInputFile(image_path), caption=text)
        else:
            await bot.send_message(topup["user_id"], text)
    except Exception:
        pass


@dp.message(Flow.waiting_receipt, F.photo)
async def receive_topup_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("topup_code")
    if not code:
        return
    file_id = message.photo[-1].file_id
    db.attach_topup_receipt(code, file_id)
    await state.clear()

    topup = db.get_topup_by_code(code)
    await message.answer(f"✅ Chek qabul qilindi! Buyurtma #{code}. Admin tez orada tekshiradi.")

    user = db.get_user(message.from_user.id)
    caption = (
        f"💳 Yangi to'ldirish so'rovi\n\n"
        f"🆔 {code}\n"
        f"👤 {user['full_name']} (@{user['username']})\n"
        f"💰 Summa: {topup['unique_amount']:,} so'm".replace(",", " ") + f"\n"
        f"Usul: {TOPUP_METHOD_LABELS.get(topup['method'], topup['method'])}"
    )
    for admin_row in db.get_all_admins():
        try:
            await bot.send_photo(admin_row["user_id"], file_id, caption=caption, reply_markup=kb.admin_topup_confirm_kb(code))
        except Exception:
            pass

    log_channel = db.get_setting("finance_log_channel")
    if log_channel:
        try:
            await bot.send_message(log_channel, f"💰 To'lov keldi: #{code} — {topup['unique_amount']:,} so'm".replace(",", " "))
        except Exception:
            pass


@dp.callback_query(F.data.startswith("cancel_topup_"))
async def cancel_topup(callback: CallbackQuery, state: FSMContext):
    code = callback.data.replace("cancel_topup_", "")
    topup = db.get_topup_by_code(code)
    if topup and topup["status"] == "awaiting_receipt":
        db.set_topup_status(code, "rejected")
    await state.clear()
    await safe_edit(callback, "❌ Bekor qilindi.", reply_markup=kb.back_kb("menu_topup"))
    await callback.answer()


# ======================================================================
# HISOBIM
# ======================================================================

@dp.callback_query(F.data == "menu_account")
async def menu_account(callback: CallbackQuery):
    await open_account(callback)


@dp.message(F.text == kb.MAIN_MENU_LABELS["account"])
async def menu_account_reply(message: Message):
    await open_account(message)


async def open_account(target):
    user_id = target_user_id(target)
    previous_seen = db.touch_last_seen(user_id)
    user = db.get_user(user_id)

    updated_str = "—"
    if previous_seen:
        try:
            dt = datetime.fromisoformat(previous_seen)
            updated_str = dt.strftime("%d-%B %Y, %H:%M")
        except Exception:
            updated_str = previous_seen

    text = (
        f"ℹ️ Ma'lumotlaringiz\n\n"
        f"💰 Balans: {user['balance']:,} so'm\n".replace(",", " ")
        + f"➕ Kiritilgan: {user['total_topup']:,} so'm\n".replace(",", " ")
        + f"➖ Sarflangan: {user['total_spent']:,} so'm\n\n".replace(",", " ")
        + f"📅 Yangilangan: {updated_str}"
    )
    await send_view(target, text, reply_markup=kb.account_kb())


@dp.callback_query(F.data == "topup_history")
async def topup_history(callback: CallbackQuery):
    rows = db.get_user_topups(callback.from_user.id, limit=10)
    if not rows:
        text = "To'ldirish tarixi bo'sh."
    else:
        lines = ["📈 To'ldirish tarixi:\n"]
        for r in rows:
            method_label = TOPUP_METHOD_LABELS.get(r["method"], r["method"])
            lines.append(f"#{r['order_code']} — {r['unique_amount']:,} so'm".replace(",", " ") + f" — {method_label} — {r['status']}")
        text = "\n".join(lines)
    await safe_edit(callback, text, reply_markup=kb.back_kb("menu_account"))
    await callback.answer()


@dp.callback_query(F.data == "spend_history")
async def spend_history(callback: CallbackQuery):
    rows = db.get_user_orders(callback.from_user.id, limit=10)
    if not rows:
        text = "Sarf tarixi bo'sh."
    else:
        lines = ["📉 Sarf tarixi:\n"]
        for r in rows:
            lines.append(f"#{r['order_code']} — {r['product_name']} — {r['price']:,} so'm".replace(",", " ") + f" — {r['status']}")
        text = "\n".join(lines)
    await safe_edit(callback, text, reply_markup=kb.back_kb("menu_account"))
    await callback.answer()


# ======================================================================
# TOP
# ======================================================================

PERIOD_MAP = {
    "top_week": lambda: datetime.now() - timedelta(days=7),
    "top_month": lambda: datetime.now() - timedelta(days=30),
    "top_year": lambda: datetime.now() - timedelta(days=365),
    "top_all": lambda: None,
}


@dp.callback_query(F.data == "menu_top")
async def menu_top(callback: CallbackQuery):
    await render_top(callback, "top_week")


@dp.message(F.text == kb.MAIN_MENU_LABELS["top"])
async def menu_top_reply(message: Message):
    await render_top(message, "top_week")


@dp.callback_query(F.data.startswith("top_"))
async def filter_top(callback: CallbackQuery):
    await render_top(callback, callback.data)


async def render_top(target, period_key):
    since_fn = PERIOD_MAP.get(period_key, PERIOD_MAP["top_week"])
    since_dt = since_fn()
    since_iso = since_dt.isoformat(timespec="seconds") if since_dt else None

    rows = db.get_top_spenders(since_iso, limit=10)
    medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]
    period_labels = {
        "top_week": "1 haftalik",
        "top_month": "1 oylik",
        "top_year": "1 yillik",
        "top_all": "Hammasi",
    }
    lines = [
        f"🏆 Faollik reytingi (TOP-10) — {period_labels.get(period_key, '1 haftalik')}",
        "",
        "Ushbu ro'yxatda tanlangan davr ichida eng ko'p xarid qilgan mijozlar aks etadi",
        "",
    ]
    if not rows:
        lines.append("Hozircha ma'lumot yo'q.")
    for i, r in enumerate(rows):
        uname = f"@{r['username']}" if r["username"] else f"ID{r['user_id']}"
        lines.append(f"{medals[i]} {uname} — {r['total']:,} so'm • {r['cnt']} ta buyurtma".replace(",", " "))

    my_rank = "—"
    my = db.get_user(target_user_id(target))
    lines.append("")
    lines.append("─────────────")
    lines.append(f"👤 Sizning reytingdagi o'rningiz: {my_rank}")
    lines.append(f"   {my['total_spent']:,} so'm".replace(",", " "))

    await send_view(target, "\n".join(lines), reply_markup=kb.top_filters_kb())
