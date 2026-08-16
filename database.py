# database.py
# SQLite — faylga asoslangan, alohida o'rnatish talab qilmaydigan ma'lumotlar bazasi.
# Bot birinchi marta ishga tushganda barcha jadvallar avtomatik yaratiladi.

import sqlite3
import random
import string
from datetime import datetime, timedelta

from config import DB_PATH, OWNER_ID


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


# ======================================================================
# JADVALLARNI YARATISH
# ======================================================================

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            language TEXT,                 -- 'uz' | 'ru' | 'en'
            agreed_rules_at TEXT,          -- foydalanish qoidalariga rozilik vaqti
            balance INTEGER DEFAULT 0,
            total_topup INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            role TEXT DEFAULT 'user',      -- 'user' | 'admin' | 'super_admin'
            permissions TEXT DEFAULT '',   -- vergul bilan: "approve,broadcast,edit_prices"
            referrer_id INTEGER,
            admin_note TEXT DEFAULT '',    -- faqat adminlar ko'radigan shaxsiy izoh
            last_seen_at TEXT,             -- "Hisobim"da ko'rsatiladigan OLDINGI kirish vaqti
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price INTEGER DEFAULT 0,
            requires_game_id INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT UNIQUE,        -- mijozga ko'rinadigan noyob buyurtma ID
            user_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT,
            game_uid TEXT,
            price INTEGER,
            status TEXT DEFAULT 'pending', -- pending | delivered | cancelled | rejected
            created_at TEXT,
            fulfilled_at TEXT,
            admin_receipt_file_id TEXT     -- admin yuborgan "bajarildi" skrini
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS topups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT UNIQUE,
            user_id INTEGER NOT NULL,
            method TEXT,                   -- karta | bankomat | payme
            base_amount INTEGER,
            unique_amount INTEGER,         -- to'lanishi kerak bo'lgan aniq summa
            card_number TEXT,
            card_owner TEXT,
            phone_number TEXT,
            receipt_file_id TEXT,
            status TEXT DEFAULT 'awaiting_receipt',  -- awaiting_receipt | pending | approved | rejected | expired
            late_penalty INTEGER DEFAULT 0,
            created_at TEXT,
            expires_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT,                     -- topup | purchase | refund | bonus
            amount INTEGER,
            note TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS texts (
            key TEXT PRIMARY KEY,
            content TEXT,
            image_path TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sender TEXT,                   -- 'user' | 'admin'
            text TEXT,
            photo_file_id TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS faq (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            answer TEXT,
            sort_order INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            percent_off INTEGER DEFAULT 0,
            amount_off INTEGER DEFAULT 0,
            uses_left INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    """)

    conn.commit()

    # ---- eski bazalarga yangi ustunlarni qo'shish (migratsiya) ----
    try:
        cur.execute("ALTER TABLE users ADD COLUMN blocked_bot INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    _seed_defaults(conn)
    conn.close()


def _seed_defaults(conn):
    cur = conn.cursor()

    # ---- boshlang'ich sozlamalar ----
    defaults = {
        "mandatory_sub_enabled": "0",
        "mandatory_sub_channel": "",
        "webapp_enabled": "0",
        "webapp_url": "",
        "card_number": "8600 0000 0000 0000",
        "card_owner": "F.M",
        "bankomat_phone": "+998 00 000 00 00",
        "payme_enabled": "0",
        "click_enabled": "0",
        "p2p_mode": "manual",          # manual | semi_auto | full_auto
        "orders_log_channel": "",
        "finance_log_channel": "",
        "topup_expiry_minutes": "5",
        "late_penalty_percent": "20",
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # ---- tahrirlanadigan matnlar ----
    default_texts = {
        "welcome": (
            "👋 Assalomu alaykum, {name}!\n\n"
            "🛒 AURUM SHOP botida quyidagilarni xarid qilishingiz mumkin:\n\n"
            "⭐ Telegram Stars\n"
            "💎 O'yinlar uchun donat\n\n"
            "👇 Quyidagi menyudan kerakli bo'limni tanlang:"
        ),
        "rules": (
            "📜 Foydalanish qoidalari\n\n"
            "1. Barcha to'lovlar qaytarilmaydi.\n"
            "2. Noto'g'ri ID/ma'lumot kiritilsa, admin javobgar emas.\n"
            "3. Buyurtma ko'rsatilgan aniq summada to'lanishi shart.\n\n"
            "Davom etish uchun qoidalarga rozilik bildiring."
        ),
        "mandatory_sub": "⚠️ Botdan foydalanish uchun avval kanalimizga obuna bo'ling:",
        "topup_amount_prompt": "💳 To'ldirmoqchi bo'lgan summangizni kiriting:\n\nMinimal: 1 000 so'm",
        "topup_invalid_amount": "❗ Faqat raqam kiriting.",
        "topup_min_amount": "❗ Minimal summa: 1 000 so'm",
        "topup_created": (
            "✅ To'lov buyurtmasi yaratildi!\n\n"
            "🆔 Buyurtma: {order_code}\n"
            "💰 To'lanishi kerak: {amount} so'm\n"
            "💳 Karta: {card_number}\n"
            "👤 Ism: {card_owner}\n\n"
            "⚠️ Aynan {amount} so'm o'tkazing! Kam yoki ko'p pul tashlasangiz, "
            "pulingiz balansga tushmay qoladi va bu holatda admin javobgar emas!\n\n"
            "📸 To'lovni amalga oshirgach, chek (screenshot yoki foto) rasmini shu yerga yuboring.\n\n"
            "⏱️ Yaratildi: {created} — Tugaydi: {expires}"
        ),
        "topup_expired": (
            "Hurmatli mijoz, buyurtma bekor qilindi. Agar pul tashlab qo'ygan "
            "bo'lsangiz, adminga murojaat qiling: {admin_contact}"
        ),
        "insufficient_balance": "❗ Balansingiz yetarli emas. Hisobingizni to'ldiring.",
        "section_disabled": "⚠️ Bu bo'lim hozircha texnik nosozlik tufayli ishlamayapti. Birozdan so'ng qayta urinib ko'ring.",
    }
    for k, v in default_texts.items():
        cur.execute("INSERT OR IGNORE INTO texts (key, content, image_path) VALUES (?, ?, NULL)", (k, v))

    conn.commit()

    # ---- namuna toifalar/mahsulotlar (birinchi ishga tushirishda) ----
    cur.execute("SELECT COUNT(*) c FROM categories")
    if cur.fetchone()["c"] == 0:
        cats = ["TG Stars", "TG Premium", "Standoff 2", "Roblox", "Steam", "Free Fire"]
        for i, name in enumerate(cats):
            cur.execute("INSERT INTO categories (name, active, sort_order) VALUES (?,1,?)", (name, i))
            cat_id = cur.lastrowid
            requires_id = 1 if name in ("Standoff 2", "Free Fire") else 0
            cur.execute(
                "INSERT INTO products (category_id, name, price, requires_game_id, active, sort_order) VALUES (?,?,?,?,1,0)",
                (cat_id, f"{name} — namuna paket", 0, requires_id),
            )
        conn.commit()

    # ---- bosh admin ----
    if OWNER_ID:
        cur.execute("SELECT user_id FROM users WHERE user_id=?", (OWNER_ID,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users (user_id, role, created_at) VALUES (?, 'super_admin', ?)",
                (OWNER_ID, now_iso()),
            )
        else:
            cur.execute("UPDATE users SET role='super_admin' WHERE user_id=?", (OWNER_ID,))
        conn.commit()


# ======================================================================
# TEXTS / SETTINGS (admin panel orqali tahrirlanadigan)
# ======================================================================

def get_text(key, **kwargs):
    conn = get_conn()
    row = conn.execute("SELECT content FROM texts WHERE key=?", (key,)).fetchone()
    conn.close()
    content = row["content"] if row else key
    try:
        return content.format(**kwargs)
    except Exception:
        return content


def get_text_image(key):
    conn = get_conn()
    row = conn.execute("SELECT image_path FROM texts WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["image_path"] if row else None


def set_text(key, content=None, image_path=None):
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT content, image_path FROM texts WHERE key=?", (key,)).fetchone()
    if row:
        new_content = content if content is not None else row["content"]
        new_image = image_path if image_path is not None else row["image_path"]
        cur.execute("UPDATE texts SET content=?, image_path=? WHERE key=?", (new_content, new_image, key))
    else:
        cur.execute("INSERT INTO texts (key, content, image_path) VALUES (?,?,?)", (key, content or "", image_path))
    conn.commit()
    conn.close()


def get_setting(key):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


# ======================================================================
# FOYDALANUVCHILAR
# ======================================================================

def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row


def is_new_user(user_id):
    return get_user(user_id) is None


def upsert_user(user_id, username, full_name):
    conn = get_conn()
    cur = conn.cursor()
    existing = cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
    if existing:
        cur.execute(
            "UPDATE users SET username=?, full_name=?, blocked_bot=0 WHERE user_id=?",
            (username, full_name, user_id),
        )
    else:
        cur.execute(
            """INSERT INTO users (user_id, username, full_name, balance, created_at)
               VALUES (?,?,?,0,?)""",
            (user_id, username, full_name, now_iso()),
        )
    conn.commit()
    conn.close()


def set_user_language(user_id, lang):
    conn = get_conn()
    conn.execute("UPDATE users SET language=? WHERE user_id=?", (lang, user_id))
    conn.commit()
    conn.close()


def agree_to_rules(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET agreed_rules_at=? WHERE user_id=?", (now_iso(), user_id))
    conn.commit()
    conn.close()


def touch_last_seen(user_id):
    """'Hisobim' ochilganda chaqiriladi: eski qiymatni qaytaradi, so'ng yangilaydi."""
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT last_seen_at FROM users WHERE user_id=?", (user_id,)).fetchone()
    previous = row["last_seen_at"] if row else None
    cur.execute("UPDATE users SET last_seen_at=? WHERE user_id=?", (now_iso(), user_id))
    conn.commit()
    conn.close()
    return previous


def adjust_balance(user_id, delta, kind, note=""):
    """delta musbat bo'lsa balans oshadi (topup/bonus), manfiy bo'lsa kamayadi (purchase)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, user_id))
    if kind == "topup":
        cur.execute("UPDATE users SET total_topup = total_topup + ? WHERE user_id=?", (delta, user_id))
    elif kind == "purchase":
        cur.execute("UPDATE users SET total_spent = total_spent + ? WHERE user_id=?", (abs(delta), user_id))
    cur.execute(
        "INSERT INTO transactions (user_id, type, amount, note, created_at) VALUES (?,?,?,?,?)",
        (user_id, kind, delta, note, now_iso()),
    )
    conn.commit()
    conn.close()


def get_transactions(user_id, limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


def ban_user(user_id, banned=1):
    conn = get_conn()
    conn.execute("UPDATE users SET banned=? WHERE user_id=?", (banned, user_id))
    conn.commit()
    conn.close()


def set_admin_note(user_id, note):
    conn = get_conn()
    conn.execute("UPDATE users SET admin_note=? WHERE user_id=?", (note, user_id))
    conn.commit()
    conn.close()


def set_role(user_id, role, permissions=""):
    conn = get_conn()
    conn.execute("UPDATE users SET role=?, permissions=? WHERE user_id=?", (role, permissions, user_id))
    conn.commit()
    conn.close()


def get_all_admins():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users WHERE role IN ('admin','super_admin')").fetchall()
    conn.close()
    return rows


def get_all_user_ids():
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users WHERE banned=0 AND blocked_bot=0").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]


def mark_blocked_bot(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET blocked_bot=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def search_user(query):
    """ID yoki username bo'yicha qidiradi."""
    conn = get_conn()
    if query.isdigit():
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (int(query),)).fetchone()
    else:
        q = query.lstrip("@")
        row = conn.execute("SELECT * FROM users WHERE username LIKE ?", (q,)).fetchone()
    conn.close()
    return row


# ======================================================================
# TOIFALAR / MAHSULOTLAR
# ======================================================================

def get_categories(only_active=True):
    conn = get_conn()
    q = "SELECT * FROM categories"
    if only_active:
        q += " WHERE active=1"
    q += " ORDER BY sort_order"
    rows = conn.execute(q).fetchall()
    conn.close()
    return rows


def get_category(cat_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    conn.close()
    return row


def get_products(cat_id, only_active=True):
    conn = get_conn()
    q = "SELECT * FROM products WHERE category_id=?"
    if only_active:
        q += " AND active=1"
    q += " ORDER BY sort_order"
    rows = conn.execute(q, (cat_id,)).fetchall()
    conn.close()
    return rows


def get_product(product_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    return row


def set_category_active(cat_id, active):
    conn = get_conn()
    conn.execute("UPDATE categories SET active=? WHERE id=?", (active, cat_id))
    conn.commit()
    conn.close()


def set_product_active(product_id, active):
    conn = get_conn()
    conn.execute("UPDATE products SET active=? WHERE id=?", (active, product_id))
    conn.commit()
    conn.close()


def set_product_price(product_id, price):
    conn = get_conn()
    conn.execute("UPDATE products SET price=? WHERE id=?", (price, product_id))
    conn.commit()
    conn.close()


def add_category(name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO categories (name, active, sort_order) VALUES (?,1,999)", (name,))
    conn.commit()
    conn.close()


def add_product(cat_id, name, price=0, requires_game_id=0):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (category_id, name, price, requires_game_id, active, sort_order) VALUES (?,?,?,?,0,999)",
        (cat_id, name, price, requires_game_id),
    )
    conn.commit()
    conn.close()


# ======================================================================
# NOYOB KODLAR
# ======================================================================

def generate_order_code():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=10))


def generate_unique_amount(base_amount):
    """Bazaviy summaga 1-99 orasidagi tasodifiy raqam qo'shib, band bo'lmagan summani qaytaradi."""
    conn = get_conn()
    cur = conn.cursor()
    for _ in range(50):
        candidate = base_amount + random.randint(1, 99)
        exists = cur.execute(
            "SELECT id FROM topups WHERE unique_amount=? AND status IN ('awaiting_receipt','pending')",
            (candidate,),
        ).fetchone()
        if not exists:
            conn.close()
            return candidate
    conn.close()
    return base_amount + random.randint(100, 999)


# ======================================================================
# BUYURTMALAR (Xizmatlar — balansdan xarid)
# ======================================================================

def create_order(user_id, product_id, product_name, price, game_uid=None):
    conn = get_conn()
    cur = conn.cursor()
    code = generate_order_code()
    cur.execute(
        """INSERT INTO orders (order_code, user_id, product_id, product_name, game_uid, price, status, created_at)
           VALUES (?,?,?,?,?,?, 'pending', ?)""",
        (code, user_id, product_id, product_name, game_uid, price, now_iso()),
    )
    conn.commit()
    conn.close()
    return code


def get_order_by_code(code):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE order_code=?", (code,)).fetchone()
    conn.close()
    return row


def set_order_status(code, status, admin_receipt_file_id=None):
    conn = get_conn()
    cur = conn.cursor()
    if admin_receipt_file_id:
        cur.execute(
            "UPDATE orders SET status=?, fulfilled_at=?, admin_receipt_file_id=? WHERE order_code=?",
            (status, now_iso(), admin_receipt_file_id, code),
        )
    else:
        cur.execute("UPDATE orders SET status=? WHERE order_code=?", (status, code))
    conn.commit()
    conn.close()


def get_pending_orders():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM orders WHERE status='pending' ORDER BY created_at").fetchall()
    conn.close()
    return rows


def get_user_orders(user_id, limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
    ).fetchall()
    conn.close()
    return rows


# ======================================================================
# TO'LDIRISH BUYURTMALARI (Pul kiritish)
# ======================================================================

def create_topup(user_id, method, base_amount):
    unique_amount = generate_unique_amount(base_amount)
    code = generate_order_code()
    minutes = int(get_setting("topup_expiry_minutes") or 5)
    created = datetime.now()
    expires = created + timedelta(minutes=minutes)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO topups (order_code, user_id, method, base_amount, unique_amount,
           card_number, card_owner, phone_number, status, created_at, expires_at)
           VALUES (?,?,?,?,?,?,?,?, 'awaiting_receipt', ?, ?)""",
        (
            code, user_id, method, base_amount, unique_amount,
            get_setting("card_number"), get_setting("card_owner"), get_setting("bankomat_phone"),
            created.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()
    return code, unique_amount, created, expires


def get_topup_by_code(code):
    conn = get_conn()
    row = conn.execute("SELECT * FROM topups WHERE order_code=?", (code,)).fetchone()
    conn.close()
    return row


def attach_topup_receipt(code, file_id):
    conn = get_conn()
    conn.execute(
        "UPDATE topups SET receipt_file_id=?, status='pending' WHERE order_code=?", (file_id, code)
    )
    conn.commit()
    conn.close()


def set_topup_status(code, status):
    conn = get_conn()
    conn.execute("UPDATE topups SET status=? WHERE order_code=?", (status, code))
    conn.commit()
    conn.close()


def get_pending_topups():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM topups WHERE status='pending' ORDER BY created_at"
    ).fetchall()
    conn.close()
    return rows


def get_expired_topups():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM topups WHERE status='awaiting_receipt' AND expires_at < ?",
        (now_iso(),),
    ).fetchall()
    conn.close()
    return rows


def get_user_topups(user_id, limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM topups WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
    ).fetchall()
    conn.close()
    return rows


# ======================================================================
# TOP / REYTING
# ======================================================================

def get_top_spenders(since_iso=None, limit=5):
    conn = get_conn()
    if since_iso:
        rows = conn.execute(
            """SELECT user_id, username, SUM(amount) as total, COUNT(*) as cnt
               FROM transactions WHERE type='purchase' AND created_at >= ?
               GROUP BY user_id ORDER BY total DESC LIMIT ?""",
            (since_iso, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT user_id, SUM(amount) as total, COUNT(*) as cnt
               FROM transactions WHERE type='purchase'
               GROUP BY user_id ORDER BY total DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    conn.close()
    return rows


# ======================================================================
# QO'LLAB-QUVVATLASH (ichki chat)
# ======================================================================

def add_support_message(user_id, sender, text=None, photo_file_id=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO support_messages (user_id, sender, text, photo_file_id, created_at) VALUES (?,?,?,?,?)",
        (user_id, sender, text, photo_file_id, now_iso()),
    )
    conn.commit()
    conn.close()


def get_support_history(user_id, limit=50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM support_messages WHERE user_id=? ORDER BY created_at LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


# ======================================================================
# FAQ
# ======================================================================

def get_faq_list():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM faq ORDER BY sort_order").fetchall()
    conn.close()
    return rows


def add_faq(question, answer):
    conn = get_conn()
    conn.execute("INSERT INTO faq (question, answer, sort_order) VALUES (?,?,999)", (question, answer))
    conn.commit()
    conn.close()


def delete_faq(faq_id):
    conn = get_conn()
    conn.execute("DELETE FROM faq WHERE id=?", (faq_id,))
    conn.commit()
    conn.close()
