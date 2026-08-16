# config.py
# Barcha maxfiy ma'lumotlar Railway'ning "Variables" bo'limidan o'qiladi.
# Bu fayl xavfsiz — hech qanday haqiqiy token o'zida saqlamaydi,
# shuning uchun ochiq (public) repo'ga yuklash ham xavfsiz.

import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Bosh admin (Owner) — botni birinchi ishga tushirganda shu ID avtomatik
# "super_admin" bo'lib bazaga yoziladi. Boshqa adminlarni keyin shu odam qo'shadi.
_owner_raw = os.getenv("OWNER_ID", "0")
OWNER_ID = int(_owner_raw) if _owner_raw.strip().isdigit() else 0

# Ixtiyoriy: log kanallari (agar kiritilmasa, bot shunchaki log yubormaydi,
# xato bermaydi — keyin istalgan vaqt Sozlamalar > Kanallar orqali ham
# admin panelidan kiritish mumkin bo'ladi)
ORDERS_LOG_CHANNEL = os.getenv("ORDERS_LOG_CHANNEL", "")   # "Otziv" kanali (bajarilgan buyurtmalar)
FINANCE_LOG_CHANNEL = os.getenv("FINANCE_LOG_CHANNEL", "")  # texnik jurnal (barcha pul harakati)

DB_PATH = "aurum_shop.db"
