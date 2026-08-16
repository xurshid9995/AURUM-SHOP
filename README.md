# AURUM SHOP — Telegram Top-up Bot

## 1. Sozlash (Railway'da)

**Variables** bo'limiga qo'shing:
- `BOT_TOKEN` — BotFather'dan olingan token
- `OWNER_ID` — sizning Telegram ID raqamingiz (bosh admin, avtomatik super_admin bo'ladi)

Ixtiyoriy (keyin admin panel orqali ham sozlash mumkin):
- `ORDERS_LOG_CHANNEL` — "otziv" log kanali username/ID'si
- `FINANCE_LOG_CHANNEL` — texnik jurnal kanali username/ID'si

**Start Command:** `python main.py` (yoki Procfile avtomatik aniqlaydi)

## 2. Birinchi ishga tushirish

Bot ishga tushganda `aurum_shop.db` fayli avtomatik yaratiladi, namuna toifalar
(TG Stars, Standoff 2 va h.k.) va sozlamalar bilan to'ldiriladi. `OWNER_ID`
avtomatik bosh admin (`super_admin`) qilib belgilanadi.

Botga `/admin` buyrug'ini yuborib, admin panelni oching.

## 3. Nima to'liq ishlaydi (hozir)

✅ Til tanlash (uz/ru/en, birinchi marta) → qoidalarga rozilik → majburiy obuna → menyu
✅ Xizmatlar: toifalar → mahsulotlar → (kerak bo'lsa) o'yin ID → balansdan xarid → 5 daqiqa bekor qilish oynasi → admin tasdiqlash
✅ Pul kiritish: Karta (noyob summa, nusxalash tugmalari, 5 daqiqa muddat) va Bankomat (bosqichma-bosqich) oqimlari, chek yuborish, admin tasdiqlaydi
✅ Hisobim: balans, kiritilgan/sarflangan, to'ldirish/sarf tarixi, "Yangilangan" (oldingi kirish vaqti)
✅ Top: davr bo'yicha reyting (bugun/kecha/hafta/oy/hammasi)
✅ Sozlamalar: profil + til almashtirish
✅ Qo'llab-quvvatlash: ichki chat (adminga forward) + FAQ
✅ Admin panel: statistika, broadcast, toifa/mahsulot boshqaruvi (yoqish/o'chirish/narx), matnlarni tahrirlash (+ rasm), majburiy obuna sozlash, to'lov sozlamalari (karta/bankomat/Payme toggle/P2P rejim), foydalanuvchi qidiruv+bloklash+izoh+tranzaksiyalar, admin qo'shish (super_admin), FAQ boshqaruvi

## 4. Keyingi bosqichda qo'shiladigan (tashqi infratuzilma talab qiladi)

Bular — kod arxitekturasida **joy tayyor** (baza jadvallari, sozlamalar), lekin
to'liq ishga tushirish uchun tashqi xizmatlar/qo'shimcha ishlov kerak:

- **P2P avtomatik/yarim-avtomatik tasdiqlash** — bank SMS'larini forward qiluvchi
  alohida telefon/ilova va SMS-parser handler yozish kerak
- **Payme/Click rasmiy integratsiyasi** — merchant hisob olingach ulaymiz
- **WebApp (Mini App)** — alohida veb-sahifa (HTML/JS) va uni hostlash kerak
- **Referal, kunlik bonus, promo-kod ishlatish, VIP darajalar** — baza tayyor
  (`promo_codes` jadvali va h.k.), lekin foydalanuvchi tomonidagi handler'lar
  keyingi bosqichda qo'shiladi
- **Log kanallariga to'liq integratsiya** — sozlamalar tayyor, ammo "bajarilganlik
  skrinini juftlashtirib joylash" logikasi keyingi qadamda to'ldiriladi
- **Excel/CSV eksport, avtomatik zaxira nusxa** — keyingi qadamda qo'shiladi

Bularning har birini alohida, kichik-kichik bosqichlarda so'rab, ustiga qurib
boraverish mumkin — hozirgi kod bazasi buzilmaydi, faqat kengayadi.

## 5. Fayllar tuzilishi

- `main.py` — bot ishga tushirish nuqtasi + foydalanuvchi tomoni handlerlari
- `admin.py` — admin panelning barcha handlerlari
- `database.py` — SQLite bilan ishlash (barcha jadvallar shu yerda)
- `keyboards.py` — foydalanuvchi tomoni tugmalari
- `config.py` — environment variables orqali sozlamalar
- `assets/` — welcome.jpg, prices.jpg rasmlari
