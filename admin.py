# admin.py
# Admin panelning barcha handlerlari shu yerda. main.py ichida register() orqali ulanadi.

import asyncio
from aiogram import F
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command

import database as db
from keyboards import admin_order_confirm_kb, admin_topup_confirm_kb


class AdminFlow(StatesGroup):
    broadcast_text = State()
    edit_price = State()
    edit_text_value = State()
    edit_card_number = State()
    edit_card_owner = State()
    edit_bankomat_phone = State()
    edit_sub_channel = State()
    add_admin_id = State()
    search_user = State()
    edit_user_note = State()
    add_faq_question = State()
    add_faq_answer = State()
    new_category_name = State()
    new_product_name = State()


# ---------------------------------------------------------------------
# KLAVIATURALAR
# ---------------------------------------------------------------------

def admin_main_kb():
    b = InlineKeyboardBuilder()
    b.button(text="📊 Statistika", callback_data="adm_stats")
    b.button(text="📋 Kutilayotganlar", callback_data="adm_pending")
    b.button(text="📢 Xabar yuborish", callback_data="adm_broadcast")
    b.button(text="🗂 Toifa/Mahsulot", callback_data="adm_catalog")
    b.button(text="📝 Matnlar", callback_data="adm_texts")
    b.button(text="🔔 Majburiy obuna", callback_data="adm_sub")
    b.button(text="💳 To'lov sozlamalari", callback_data="adm_payment")
    b.button(text="👥 Foydalanuvchilar", callback_data="adm_users")
    b.button(text="🛡 Adminlar", callback_data="adm_admins")
    b.button(text="❓ FAQ", callback_data="adm_faq")
    b.adjust(2)
    return b.as_markup()


def back_admin_kb(target="adm_main"):
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Ortga", callback_data=target)
    return b.as_markup()


def toggle_kb(key, current_value, target_cb, back_cb):
    b = InlineKeyboardBuilder()
    label = "🔴 O'chirish" if current_value == "1" else "🟢 Yoqish"
    b.button(text=label, callback_data=target_cb)
    b.button(text="◀️ Ortga", callback_data=back_cb)
    b.adjust(1)
    return b.as_markup()


# ---------------------------------------------------------------------
# ASOSIY REGISTER FUNKSIYASI
# ---------------------------------------------------------------------

def register(dp, bot, is_admin, is_super_admin, safe_edit):

    async def guard(callback: CallbackQuery) -> bool:
        if not is_admin(callback.from_user.id):
            await callback.answer("Ruxsat yo'q.", show_alert=True)
            return False
        return True

    # ------------------ /admin ------------------

    @dp.message(Command("admin"))
    async def cmd_admin(message: Message):
        if not is_admin(message.from_user.id):
            return
        await message.answer("🔧 Admin panel", reply_markup=admin_main_kb())

    @dp.callback_query(F.data == "adm_main")
    async def adm_main(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        await state.clear()
        await safe_edit(callback, "🔧 Admin panel", reply_markup=admin_main_kb())
        await callback.answer()

    # ------------------ Statistika ------------------

    @dp.callback_query(F.data == "adm_stats")
    async def adm_stats(callback: CallbackQuery):
        if not await guard(callback):
            return
        conn = db.get_conn()
        users_count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        orders_count = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='delivered'").fetchone()["c"]
        revenue = conn.execute("SELECT COALESCE(SUM(price),0) s FROM orders WHERE status='delivered'").fetchone()["s"]
        topup_sum = conn.execute("SELECT COALESCE(SUM(unique_amount),0) s FROM topups WHERE status='approved'").fetchone()["s"]
        pending_orders = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='pending'").fetchone()["c"]
        pending_topups = conn.execute("SELECT COUNT(*) c FROM topups WHERE status='pending'").fetchone()["c"]
        conn.close()

        text = (
            f"📊 Statistika\n\n"
            f"👥 Foydalanuvchilar: {users_count}\n"
            f"✅ Bajarilgan buyurtmalar: {orders_count}\n"
            f"💰 Umumiy tushum (xizmatlar): {revenue:,} so'm\n".replace(",", " ")
            + f"💳 Umumiy to'ldirishlar: {topup_sum:,} so'm\n\n".replace(",", " ")
            + f"⏳ Kutilayotgan buyurtmalar: {pending_orders}\n"
            f"⏳ Kutilayotgan to'ldirishlar: {pending_topups}"
        )
        await safe_edit(callback, text, reply_markup=back_admin_kb())
        await callback.answer()

    # ------------------ Kutilayotganlar ------------------

    @dp.callback_query(F.data == "adm_pending")
    async def adm_pending(callback: CallbackQuery):
        if not await guard(callback):
            return
        orders = db.get_pending_orders()
        topups = db.get_pending_topups()

        if not orders and not topups:
            await safe_edit(callback, "📋 Hozircha kutilayotgan buyurtma yoki to'ldirish yo'q.", reply_markup=back_admin_kb())
            await callback.answer()
            return

        await safe_edit(
            callback,
            f"📋 Kutilayotgan buyurtmalar: {len(orders)} ta\n📋 Kutilayotgan to'ldirishlar: {len(topups)} ta\n\nHar biri quyida alohida chiqariladi 👇",
            reply_markup=back_admin_kb(),
        )
        await callback.answer()

        for order in orders:
            user = db.get_user(order["user_id"])
            text = (
                f"🆕 Buyurtma #{order['order_code']}\n\n"
                f"Foydalanuvchi: {user['full_name']} (@{user['username']})\n"
                f"Mahsulot: {order['product_name']}\n"
                f"Narx: {order['price']:,} so'm".replace(",", " ")
            )
            if order["game_uid"]:
                text += f"\nO'yin ID: {order['game_uid']}"
            await callback.message.answer(text, reply_markup=admin_order_confirm_kb(order["order_code"]))

        for topup in topups:
            user = db.get_user(topup["user_id"])
            method_label = "💳 Karta" if topup["method"] == "karta" else "🏧 Bankomat"
            caption = (
                f"💰 To'ldirish #{topup['order_code']}\n\n"
                f"Foydalanuvchi: {user['full_name']} (@{user['username']})\n"
                f"Summa: {topup['unique_amount']:,} so'm\n".replace(",", " ")
                + f"Usul: {method_label}"
            )
            if topup["receipt_file_id"]:
                try:
                    await bot.send_photo(
                        callback.from_user.id,
                        topup["receipt_file_id"],
                        caption=caption,
                        reply_markup=admin_topup_confirm_kb(topup["order_code"]),
                    )
                    continue
                except Exception:
                    pass
            caption += "\n\n⚠️ Chek rasmi hali yuborilmagan."
            await callback.message.answer(caption, reply_markup=admin_topup_confirm_kb(topup["order_code"]))

    # ------------------ Broadcast ------------------

    @dp.callback_query(F.data == "adm_broadcast")
    async def adm_broadcast(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        await state.set_state(AdminFlow.broadcast_text)
        await safe_edit(callback, "📢 Hammaga yuboriladigan xabar matnini yozing:", reply_markup=back_admin_kb())
        await callback.answer()

    @dp.message(AdminFlow.broadcast_text)
    async def broadcast_send(message: Message, state: FSMContext):
        await state.clear()
        user_ids = db.get_all_user_ids()
        sent, blocked, failed = 0, 0, 0
        status_msg = await message.answer(f"Yuborilmoqda... 0/{len(user_ids)}")
        for i, uid in enumerate(user_ids):
            try:
                if message.photo:
                    await bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
                else:
                    await bot.send_message(uid, message.text)
                sent += 1
            except TelegramForbiddenError:
                db.mark_blocked_bot(uid)
                blocked += 1
            except Exception:
                failed += 1
            if i % 20 == 0:
                try:
                    await status_msg.edit_text(f"Yuborilmoqda... {i}/{len(user_ids)}")
                except Exception:
                    pass
            await asyncio.sleep(0.05)
        await status_msg.edit_text(
            f"✅ Yuborildi: {sent} ta\n🚫 Botni bloklagan: {blocked} ta\n⚠️ Boshqa xato: {failed} ta"
        )

    # ------------------ Toifa/Mahsulot boshqaruvi ------------------

    @dp.callback_query(F.data == "adm_catalog")
    async def adm_catalog(callback: CallbackQuery):
        if not await guard(callback):
            return
        cats = db.get_categories(only_active=False)
        b = InlineKeyboardBuilder()
        for c in cats:
            mark = "🟢" if c["active"] else "🔴"
            b.button(text=f"{mark} {c['name']}", callback_data=f"adm_cat_{c['id']}")
        b.button(text="➕ Yangi toifa", callback_data="adm_new_cat")
        b.button(text="◀️ Ortga", callback_data="adm_main")
        b.adjust(1)
        await safe_edit(callback, "🗂 Toifalar (🟢 yoqilgan / 🔴 o'chirilgan):", reply_markup=b.as_markup())
        await callback.answer()

    @dp.callback_query(F.data == "adm_new_cat")
    async def adm_new_cat(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        await state.set_state(AdminFlow.new_category_name)
        await safe_edit(callback, "Yangi toifa nomini yozing:", reply_markup=back_admin_kb("adm_catalog"))
        await callback.answer()

    @dp.message(AdminFlow.new_category_name)
    async def new_cat_name(message: Message, state: FSMContext):
        db.add_category(message.text.strip())
        await state.clear()
        await message.answer("✅ Toifa qo'shildi.", reply_markup=back_admin_kb("adm_catalog"))

    @dp.callback_query(F.data.startswith("adm_cat_"))
    async def adm_cat_detail(callback: CallbackQuery):
        if not await guard(callback):
            return
        cat_id = int(callback.data.split("_")[2])
        cat = db.get_category(cat_id)
        products = db.get_products(cat_id, only_active=False)
        b = InlineKeyboardBuilder()
        toggle_label = "🔴 O'chirish" if cat["active"] else "🟢 Yoqish"
        b.button(text=f"{toggle_label} (toifa)", callback_data=f"adm_toggle_cat_{cat_id}")
        for p in products:
            mark = "🟢" if p["active"] else "🔴"
            price = f" — {p['price']:,} so'm".replace(",", " ") if p["price"] else ""
            b.button(text=f"{mark} {p['name']}{price}", callback_data=f"adm_prod_{p['id']}")
        b.button(text="➕ Yangi mahsulot", callback_data=f"adm_new_prod_{cat_id}")
        b.button(text="◀️ Ortga", callback_data="adm_catalog")
        b.adjust(1)
        await safe_edit(callback, f"📦 {cat['name']}", reply_markup=b.as_markup())
        await callback.answer()

    @dp.callback_query(F.data.startswith("adm_toggle_cat_"))
    async def adm_toggle_cat(callback: CallbackQuery):
        if not await guard(callback):
            return
        cat_id = int(callback.data.split("_")[3])
        cat = db.get_category(cat_id)
        db.set_category_active(cat_id, 0 if cat["active"] else 1)
        await callback.answer("Yangilandi ✅")
        await adm_cat_detail(callback)

    @dp.callback_query(F.data.startswith("adm_new_prod_"))
    async def adm_new_prod(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        cat_id = int(callback.data.split("_")[3])
        await state.update_data(new_prod_cat_id=cat_id)
        await state.set_state(AdminFlow.new_product_name)
        await safe_edit(callback, "Yangi mahsulot nomini yozing:", reply_markup=back_admin_kb("adm_catalog"))
        await callback.answer()

    @dp.message(AdminFlow.new_product_name)
    async def new_prod_name(message: Message, state: FSMContext):
        data = await state.get_data()
        db.add_product(data["new_prod_cat_id"], message.text.strip())
        await state.clear()
        await message.answer(
            "✅ Mahsulot qo'shildi (nofaol holatda, narxi 0). Avval narxni belgilang, so'ng yoqing.",
            reply_markup=back_admin_kb("adm_catalog"),
        )

    @dp.callback_query(F.data.startswith("adm_prod_"))
    async def adm_prod_detail(callback: CallbackQuery):
        if not await guard(callback):
            return
        product_id = int(callback.data.split("_")[2])
        p = db.get_product(product_id)
        b = InlineKeyboardBuilder()
        toggle_label = "🔴 O'chirish" if p["active"] else "🟢 Yoqish"
        b.button(text=toggle_label, callback_data=f"adm_toggle_prod_{product_id}")
        b.button(text="💰 Narxni o'zgartirish", callback_data=f"adm_setprice_{product_id}")
        b.button(text="◀️ Ortga", callback_data=f"adm_cat_{p['category_id']}")
        b.adjust(1)
        text = f"📦 {p['name']}\n💰 Narx: {p['price']:,} so'm".replace(",", " ")
        await safe_edit(callback, text, reply_markup=b.as_markup())
        await callback.answer()

    @dp.callback_query(F.data.startswith("adm_toggle_prod_"))
    async def adm_toggle_prod(callback: CallbackQuery):
        if not await guard(callback):
            return
        product_id = int(callback.data.split("_")[3])
        p = db.get_product(product_id)
        db.set_product_active(product_id, 0 if p["active"] else 1)
        await callback.answer("Yangilandi ✅")
        await adm_prod_detail(callback)

    @dp.callback_query(F.data.startswith("adm_setprice_"))
    async def adm_setprice(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        product_id = int(callback.data.split("_")[2])
        await state.update_data(price_product_id=product_id)
        await state.set_state(AdminFlow.edit_price)
        await safe_edit(callback, "Yangi narxni kiriting (so'mda, faqat son):")
        await callback.answer()

    @dp.message(AdminFlow.edit_price)
    async def edit_price_value(message: Message, state: FSMContext):
        if not message.text.strip().isdigit():
            await message.answer("❗ Faqat son kiriting.")
            return
        data = await state.get_data()
        db.set_product_price(data["price_product_id"], int(message.text.strip()))
        await state.clear()
        await message.answer("✅ Narx yangilandi.", reply_markup=back_admin_kb("adm_catalog"))

    # ------------------ Matnlar (texts) ------------------

    TEXT_KEYS = [
        ("welcome", "Salomlashuv xabari"),
        ("rules", "Foydalanish qoidalari"),
        ("mandatory_sub", "Majburiy obuna xabari"),
        ("topup_created", "To'ldirish buyurtmasi xabari"),
        ("topup_expired", "Muddati tugagan xabar"),
        ("insufficient_balance", "Balans yetarli emas xabari"),
        ("section_disabled", "Texnik nosozlik xabari"),
    ]

    @dp.callback_query(F.data == "adm_texts")
    async def adm_texts(callback: CallbackQuery):
        if not await guard(callback):
            return
        b = InlineKeyboardBuilder()
        for key, label in TEXT_KEYS:
            b.button(text=label, callback_data=f"adm_text_{key}")
        b.button(text="◀️ Ortga", callback_data="adm_main")
        b.adjust(1)
        await safe_edit(callback, "📝 Tahrirlanadigan matnlar:", reply_markup=b.as_markup())
        await callback.answer()

    @dp.callback_query(F.data.startswith("adm_text_"))
    async def adm_text_detail(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        key = callback.data.replace("adm_text_", "")
        current = db.get_text(key)
        await state.update_data(editing_text_key=key)
        await state.set_state(AdminFlow.edit_text_value)
        await safe_edit(
            callback,
            f"Joriy matn:\n\n{current}\n\n---\nYangi matnni yuboring (rasm bilan yuborsangiz, rasm ham saqlanadi):",
            reply_markup=back_admin_kb("adm_texts"),
        )
        await callback.answer()

    @dp.message(AdminFlow.edit_text_value)
    async def edit_text_value(message: Message, state: FSMContext):
        data = await state.get_data()
        key = data["editing_text_key"]
        new_text = message.text or message.caption or ""
        image_path = None
        if message.photo:
            file_id = message.photo[-1].file_id
            dest = f"assets/custom_{key}.jpg"
            try:
                await message.bot.download(file_id, destination=dest)
                image_path = dest
            except Exception:
                image_path = None
        db.set_text(key, content=new_text if new_text else None, image_path=image_path)
        await state.clear()
        await message.answer("✅ Matn yangilandi.", reply_markup=back_admin_kb("adm_texts"))

    # ------------------ Majburiy obuna ------------------

    @dp.callback_query(F.data == "adm_sub")
    async def adm_sub(callback: CallbackQuery):
        if not await guard(callback):
            return
        enabled = db.get_setting("mandatory_sub_enabled")
        channel = db.get_setting("mandatory_sub_channel") or "(kiritilmagan)"
        b = InlineKeyboardBuilder()
        label = "🔴 O'chirish" if enabled == "1" else "🟢 Yoqish"
        b.button(text=label, callback_data="adm_sub_toggle")
        b.button(text="🔗 Kanal ssilkasini o'zgartirish", callback_data="adm_sub_setlink")
        b.button(text="◀️ Ortga", callback_data="adm_main")
        b.adjust(1)
        text = f"🔔 Majburiy obuna\n\nHolat: {'🟢 Yoqilgan' if enabled == '1' else '🔴 O''chirilgan'}\nKanal: {channel}"
        await safe_edit(callback, text, reply_markup=b.as_markup())
        await callback.answer()

    @dp.callback_query(F.data == "adm_sub_toggle")
    async def adm_sub_toggle(callback: CallbackQuery):
        if not await guard(callback):
            return
        current = db.get_setting("mandatory_sub_enabled")
        db.set_setting("mandatory_sub_enabled", "0" if current == "1" else "1")
        await callback.answer("Yangilandi ✅")
        await adm_sub(callback)

    @dp.callback_query(F.data == "adm_sub_setlink")
    async def adm_sub_setlink(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        await state.set_state(AdminFlow.edit_sub_channel)
        await safe_edit(callback, "Kanal username'ini yuboring (masalan @mychannel):")
        await callback.answer()

    @dp.message(AdminFlow.edit_sub_channel)
    async def edit_sub_channel(message: Message, state: FSMContext):
        db.set_setting("mandatory_sub_channel", message.text.strip())
        await state.clear()
        await message.answer("✅ Kanal saqlandi.", reply_markup=back_admin_kb("adm_sub"))

    # ------------------ To'lov sozlamalari ------------------

    @dp.callback_query(F.data == "adm_payment")
    async def adm_payment(callback: CallbackQuery):
        if not await guard(callback):
            return
        card = db.get_setting("card_number")
        owner = db.get_setting("card_owner")
        phone = db.get_setting("bankomat_phone")
        payme = db.get_setting("payme_enabled") == "1"
        p2p_mode = db.get_setting("p2p_mode")

        b = InlineKeyboardBuilder()
        b.button(text="💳 Karta raqamini o'zgartirish", callback_data="adm_edit_card")
        b.button(text="👤 Karta egasini o'zgartirish", callback_data="adm_edit_owner")
        b.button(text="📱 Bankomat raqamini o'zgartirish", callback_data="adm_edit_phone")
        b.button(text=("🔴 Payme o'chirish" if payme else "🟢 Payme yoqish"), callback_data="adm_toggle_payme")
        b.button(text=f"🔄 P2P rejimi: {p2p_mode}", callback_data="adm_cycle_p2p")
        b.button(text="◀️ Ortga", callback_data="adm_main")
        b.adjust(1)

        text = (
            f"💳 To'lov sozlamalari\n\n"
            f"Karta: {card}\nEgasi: {owner}\nBankomat tel: {phone}\n"
            f"Payme: {'🟢 Yoqilgan' if payme else '🔴 O''chirilgan'}\n"
            f"P2P tasdiqlash rejimi: {p2p_mode} (manual/semi_auto/full_auto)"
        )
        await safe_edit(callback, text, reply_markup=b.as_markup())
        await callback.answer()

    @dp.callback_query(F.data == "adm_edit_card")
    async def adm_edit_card(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        await state.set_state(AdminFlow.edit_card_number)
        await safe_edit(callback, "Yangi karta raqamini kiriting:")
        await callback.answer()

    @dp.message(AdminFlow.edit_card_number)
    async def save_card_number(message: Message, state: FSMContext):
        db.set_setting("card_number", message.text.strip())
        await state.clear()
        await message.answer("✅ Saqlandi.", reply_markup=back_admin_kb("adm_payment"))

    @dp.callback_query(F.data == "adm_edit_owner")
    async def adm_edit_owner(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        await state.set_state(AdminFlow.edit_card_owner)
        await safe_edit(callback, "Yangi karta egasi ismini kiriting:")
        await callback.answer()

    @dp.message(AdminFlow.edit_card_owner)
    async def save_card_owner(message: Message, state: FSMContext):
        db.set_setting("card_owner", message.text.strip())
        await state.clear()
        await message.answer("✅ Saqlandi.", reply_markup=back_admin_kb("adm_payment"))

    @dp.callback_query(F.data == "adm_edit_phone")
    async def adm_edit_phone(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        await state.set_state(AdminFlow.edit_bankomat_phone)
        await safe_edit(callback, "Yangi telefon raqamini kiriting:")
        await callback.answer()

    @dp.message(AdminFlow.edit_bankomat_phone)
    async def save_bankomat_phone(message: Message, state: FSMContext):
        db.set_setting("bankomat_phone", message.text.strip())
        await state.clear()
        await message.answer("✅ Saqlandi.", reply_markup=back_admin_kb("adm_payment"))

    @dp.callback_query(F.data == "adm_toggle_payme")
    async def adm_toggle_payme(callback: CallbackQuery):
        if not await guard(callback):
            return
        current = db.get_setting("payme_enabled")
        db.set_setting("payme_enabled", "0" if current == "1" else "1")
        await callback.answer("Yangilandi ✅")
        await adm_payment(callback)

    @dp.callback_query(F.data == "adm_cycle_p2p")
    async def adm_cycle_p2p(callback: CallbackQuery):
        if not await guard(callback):
            return
        order = ["manual", "semi_auto", "full_auto"]
        current = db.get_setting("p2p_mode")
        next_mode = order[(order.index(current) + 1) % len(order)]
        db.set_setting("p2p_mode", next_mode)
        await callback.answer(f"P2P rejimi: {next_mode}")
        await adm_payment(callback)

    # ------------------ Foydalanuvchilar ------------------

    @dp.callback_query(F.data == "adm_users")
    async def adm_users(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        await state.set_state(AdminFlow.search_user)
        await safe_edit(callback, "🔍 Foydalanuvchi ID yoki username yuboring:", reply_markup=back_admin_kb())
        await callback.answer()

    @dp.message(AdminFlow.search_user)
    async def do_search_user(message: Message, state: FSMContext):
        user = db.search_user(message.text.strip())
        await state.clear()
        if not user:
            await message.answer("Topilmadi.", reply_markup=back_admin_kb())
            return

        txs = db.get_transactions(user["user_id"], limit=10)
        tx_lines = "\n".join([f"• {t['type']} {t['amount']:+,} so'm — {t['created_at'][:16]}".replace(",", " ") for t in txs]) or "—"

        text = (
            f"👤 {user['full_name']} (@{user['username']})\n"
            f"ID: {user['user_id']}\n"
            f"Balans: {user['balance']:,} so'm\n".replace(",", " ")
            + f"Bloklangan: {'Ha' if user['banned'] else 'Yoq'}\n"
            f"Rol: {user['role']}\n"
            f"Izoh: {user['admin_note'] or '—'}\n\n"
            f"Oxirgi tranzaksiyalar:\n{tx_lines}"
        )
        b = InlineKeyboardBuilder()
        b.button(text=("🔓 Blokdan chiqarish" if user["banned"] else "🚫 Bloklash"), callback_data=f"adm_ban_{user['user_id']}")
        b.button(text="📝 Izoh yozish", callback_data=f"adm_note_{user['user_id']}")
        b.button(text="◀️ Ortga", callback_data="adm_main")
        b.adjust(1)
        await message.answer(text, reply_markup=b.as_markup())

    @dp.callback_query(F.data.startswith("adm_ban_"))
    async def adm_ban(callback: CallbackQuery):
        if not await guard(callback):
            return
        user_id = int(callback.data.split("_")[2])
        user = db.get_user(user_id)
        db.ban_user(user_id, 0 if user["banned"] else 1)
        await callback.answer("Yangilandi ✅")

    @dp.callback_query(F.data.startswith("adm_note_"))
    async def adm_note_start(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        user_id = int(callback.data.split("_")[2])
        await state.update_data(note_user_id=user_id)
        await state.set_state(AdminFlow.edit_user_note)
        await safe_edit(callback, "Izohni yozing:")
        await callback.answer()

    @dp.message(AdminFlow.edit_user_note)
    async def save_user_note(message: Message, state: FSMContext):
        data = await state.get_data()
        db.set_admin_note(data["note_user_id"], message.text.strip())
        await state.clear()
        await message.answer("✅ Izoh saqlandi.", reply_markup=back_admin_kb())

    # ------------------ Adminlar (faqat super admin) ------------------

    @dp.callback_query(F.data == "adm_admins")
    async def adm_admins(callback: CallbackQuery):
        if not await guard(callback):
            return
        if not is_super_admin(callback.from_user.id):
            await callback.answer("Faqat bosh admin uchun.", show_alert=True)
            return
        admins = db.get_all_admins()
        lines = ["🛡 Adminlar ro'yxati:\n"]
        for a in admins:
            lines.append(f"• {a['full_name']} (ID: {a['user_id']}) — {a['role']}")
        b = InlineKeyboardBuilder()
        b.button(text="➕ Admin qo'shish", callback_data="adm_add_admin")
        b.button(text="◀️ Ortga", callback_data="adm_main")
        b.adjust(1)
        await safe_edit(callback, "\n".join(lines), reply_markup=b.as_markup())
        await callback.answer()

    @dp.callback_query(F.data == "adm_add_admin")
    async def adm_add_admin(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        if not is_super_admin(callback.from_user.id):
            await callback.answer("Faqat bosh admin uchun.", show_alert=True)
            return
        await state.set_state(AdminFlow.add_admin_id)
        await safe_edit(callback, "Yangi admin qilinadigan foydalanuvchi ID'sini yuboring:")
        await callback.answer()

    @dp.message(AdminFlow.add_admin_id)
    async def save_new_admin(message: Message, state: FSMContext):
        if not message.text.strip().isdigit():
            await message.answer("❗ Faqat raqam (ID) kiriting.")
            return
        uid = int(message.text.strip())
        target = db.get_user(uid)
        if not target:
            await message.answer("Bu ID bo'yicha foydalanuvchi topilmadi (u avval botga /start bergan bo'lishi kerak).")
            return
        db.set_role(uid, "admin")
        await state.clear()
        await message.answer(f"✅ {uid} endi admin.", reply_markup=back_admin_kb())

    # ------------------ FAQ ------------------

    @dp.callback_query(F.data == "adm_faq")
    async def adm_faq(callback: CallbackQuery):
        if not await guard(callback):
            return
        rows = db.get_faq_list()
        b = InlineKeyboardBuilder()
        for r in rows:
            b.button(text=f"❌ {r['question'][:30]}", callback_data=f"adm_faq_del_{r['id']}")
        b.button(text="➕ Yangi savol-javob", callback_data="adm_faq_add")
        b.button(text="◀️ Ortga", callback_data="adm_main")
        b.adjust(1)
        await safe_edit(callback, "❓ FAQ boshqaruvi (bosilsa o'chadi):", reply_markup=b.as_markup())
        await callback.answer()

    @dp.callback_query(F.data.startswith("adm_faq_del_"))
    async def adm_faq_del(callback: CallbackQuery):
        if not await guard(callback):
            return
        faq_id = int(callback.data.split("_")[3])
        db.delete_faq(faq_id)
        await callback.answer("O'chirildi ✅")
        await adm_faq(callback)

    @dp.callback_query(F.data == "adm_faq_add")
    async def adm_faq_add(callback: CallbackQuery, state: FSMContext):
        if not await guard(callback):
            return
        await state.set_state(AdminFlow.add_faq_question)
        await safe_edit(callback, "Savolni yozing:")
        await callback.answer()

    @dp.message(AdminFlow.add_faq_question)
    async def faq_question_entered(message: Message, state: FSMContext):
        await state.update_data(faq_question=message.text.strip())
        await state.set_state(AdminFlow.add_faq_answer)
        await message.answer("Endi javobni yozing:")

    @dp.message(AdminFlow.add_faq_answer)
    async def faq_answer_entered(message: Message, state: FSMContext):
        data = await state.get_data()
        db.add_faq(data["faq_question"], message.text.strip())
        await state.clear()
        await message.answer("✅ FAQ qo'shildi.", reply_markup=back_admin_kb())
