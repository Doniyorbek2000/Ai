# AI Beauty — Telegram bot

Qizlar va ayollar uchun sun'iy intellektga asoslangan go'zallik yordamchisi va kosmetika do'koni.
Bot uchta tilda ishlaydi: o'zbek (lotin), o'zbek (kirill) va rus.

## Imkoniyatlar

| Bo'lim | Nima qiladi |
|---|---|
| 🔬 **Teri tahlili** (AI Skin Doctor) | Ayol 4 ta savolga javob beradi va yuz rasmini yuboradi. AI teri turini, toshma, dog', qizarish kabi belgilarni (ehtimol darajasi bilan) aniqlaydi. Ertalabki va kechki parvarish rejasini tuzadi va katalogdan mos mahsulotlarni taklif qiladi. Xavfli belgilar bo'lsa, dermatologga yo'naltiradi. |
| 💋 **AI makiyaj** | 6 ta obrazdan biri tanlanadi: kundalik, tabiiy, kechki, to'y, Reels, glam. Bot rasmga makiyaj qo'yib qaytaradi, yuz tuzilishi o'zgarmaydi. Shu obrazni o'zi qilish uchun qadamlar va kerakli mahsulotlarni ham yuboradi. |
| ✨ **Ideal obraz** | Yuz shakli, teri ohangi, rang tipi, yarashadigan ranglar, qosh, soch va makiyaj bo'yicha maslahat beradi. |
| 🌸 **Atir tanlash** | 5 ta savoldan keyin katalogdan 1–3 ta atirni tushuntirish bilan taklif qiladi. |
| 🎬 **Reels va maslahat** (Beauty Academy) | Professional vizajist kabi suhbatlashadi: Reels uchun makiyaj, yorug'lik, burchak va kadrni baholash. |
| 🛍 **Do'kon** | Katalog, savat va buyurtma berish (telefon, manzil yoki lokatsiya, izoh). Buyurtma admin guruhiga tugmalar bilan keladi. |
| 💎 **Beauty Club** | Har bir xariddan bonus beriladi. Bonus buyurtma yetkazilgandan keyin hisoblanadi va keyingi xaridda ishlatiladi. |

### Xavfsizlik va qonuniylik
- **AI tashxis qo'ymaydi va dori yozmaydi.** U faqat kosmetik vositalarni (niatsinamid, salitsil kislotasi, SPF va hokazo) tavsiya qiladi. Retsept bilan beriladigan dorilar (antibiotik, gormonal, izotretinoin) taqiqlangan. Xavfli belgilar bo'lsa (xolning o'zgarishi, shish, infeksiya), shifokorga darhol murojaat qilish so'raladi. Har bir natija ostida "bu tibbiy tashxis emas" degan ogohlantirish bor.
- 18 yoshgacha bo'lganlar, homiladorlar va emizikli onalarga retinol va kuchli kislotalar tavsiya qilinmaydi.
- **Yuz rasmlari saqlanmaydi.** Birinchi rasmdan oldin rozilik so'raladi. `/delete_me` buyrug'i foydalanuvchining barcha ma'lumotlarini o'chiradi.
- AI faqat katalogdagi mahsulotlarni tavsiya qila oladi. Katalogda yo'q ID lar avtomatik tashlab yuboriladi.
- Har bir foydalanuvchi uchun kunlik AI so'rovlar limiti bor (`DAILY_AI_LIMIT`), bu xarajatni nazorat qiladi.

## Texnologiyalar
- Python 3.11+, [aiogram 3](https://docs.aiogram.dev/) (Telegram), SQLite.
- **Gemini API** (Google) — bitta kalit hamma ishni bajaradi:
  - `GEMINI_MODEL` (standart: `gemini-3.5-flash`) — teri tahlili, stilist, makiyaj rejasi, atir va Academy. Javoblar qat'iy JSON formatida keladi.
  - `GEMINI_IMAGE_MODEL` (standart: `gemini-3.1-flash-image`, "Nano Banana") — rasmga makiyaj qo'yish. `MAKEUP_IMAGES=0` bo'lsa, bot faqat matnli makiyaj rejasini yuboradi.
- Google model nomlarini vaqti-vaqti bilan yangilab turadi. Bot ishga tushganda modellar mavjudligini tekshiradi. Model topilmasa, logda xato chiqaradi va mavjud modellar ro'yxatini ko'rsatadi: kerakli nomni `.env` ga yozasiz.

## O'rnatish

1. [@BotFather](https://t.me/BotFather) da bot yarating va tokenni oling.
2. [aistudio.google.com/apikey](https://aistudio.google.com/apikey) da Gemini API kalitini oling va loyihada **billing'ni yoqing**. Bepul tarifda yuborilgan ma'lumotlar Google mahsulotlarini yaxshilashda ishlatilishi mumkin. Mijozlarning yuz rasmlari uchun bu yaramaydi, shuning uchun pullik tarif kerak. Shartlarni Google sahifasida tekshiring.
3. Buyurtmalar uchun Telegram guruh yarating va botni unga qo'shing. Guruh ID sini `ADMIN_CHAT_ID` ga yozing (masalan, `-100...`). Adminlarning Telegram ID larini `ADMIN_IDS` ga yozing: faqat ular buyurtma holatini o'zgartira oladi.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # .env ichini to'ldiring
python -m beauty_bot
```

Docker orqali ishga tushirish:

```bash
docker build -t ai-beauty-bot .
docker run -d --env-file .env -v $(pwd)/data:/app/data -v beauty-db:/app/db -e DB_PATH=/app/db/beauty_bot.db ai-beauty-bot
```

## Katalogni to'ldirish

`data/products.json` faylida hozircha **namuna** mahsulotlar turibdi. Ularni o'zingizning haqiqiy mahsulotlaringiz bilan almashtiring. Har bir mahsulotda quyidagilar bo'ladi:

- `id`, `category` (`skincare`, `makeup`, `perfume`, `hair_body`), `price` (so'mda), `name` va `description` (`uz` va `ru` tillarida);
- `image_url` (ixtiyoriy), `in_stock` (`false` bo'lsa sotuvda ko'rinmaydi);
- AI to'g'ri tanlashi uchun teglar:
  - parvarish vositalari: `skin_types`, `concerns`, `ingredients`, `cautions`;
  - makiyaj: `makeup_styles`;
  - atirlar: `families`, `seasons`, `occasions`.

Kirill yozuvi lotin matnidan avtomatik yasaladi.

## Admin buyruqlari
- Yangi buyurtma admin guruhiga keladi. Ostidagi tugmalar: ✅ Tasdiqlash / 📦 Yetkazildi / ❌ Bekor. Mijozga holat haqida avtomatik xabar boradi.
- `/orders [new|confirmed|delivered|cancelled]` — buyurtmalar ro'yxati.

## Testlar

```bash
pip install -r requirements-dev.txt
pytest
```

Testlar haqiqiy dispatcher orqali to'liq ssenariylarni tekshiradi: start va til tanlash, teri tahlili, makiyaj, atir, Academy, savat, buyurtma, admin va bonuslar. Telegram va AI o'rniga soxta (fake) obyektlar ishlatiladi. Gemini so'rovlarining tuzilishi va bloklangan javoblarni qayta ishlash haqiqiy SDK orqali, soxta HTTP javoblar bilan alohida tekshiriladi.

## Loyiha tuzilishi

```
beauty_bot/
  __main__.py       ishga tushirish, routerlar
  config.py         .env sozlamalari
  texts.py          3 tildagi matnlar va lotin→kirill transliteratsiya
  catalog.py        mahsulot katalogi
  db.py             SQLite: foydalanuvchi, savat, buyurtma, bonus, AI limiti
  render.py         AI natijalarini Telegram matniga aylantirish
  keyboards.py      tugmalar
  ai/gemini.py      Gemini so'rovlari
  ai/prompts.py     AI ko'rsatmalari (xavfsizlik qoidalari shu yerda)
  ai/schemas.py     javob formatlari
  ai/makeup.py      makiyajli rasm (Gemini Nano Banana)
  ai/errors.py      AI xatolari
  handlers/         bo'limlar: menu, skin, makeup, look, perfume, academy, shop, club, admin
data/products.json  katalog
tests/              testlar
```

## Keyingi qadamlar
- Haqiqiy katalog, narxlar va mahsulot rasmlari.
- Click / Payme orqali onlayn to'lov (hozir to'lov kuryerga naqd yoki karta orqali).
- Dermatolog bilan hamkorlikda pullik onlayn konsultatsiya tugmasi.
- Statistika: qaysi tavsiyalar sotuvga aylanmoqda.
