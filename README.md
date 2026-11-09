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
| 🛍 **Do'kon** | Katalog, savat va buyurtma berish (telefon, manzil yoki lokatsiya, izoh). Yetkazib berish narxi hisoblanadi, ma'lum summadan boshlab bepul. To'lov **Click / Payme** orqali onlayn yoki kuryerga. Buyurtma admin guruhiga tugmalar bilan keladi. |
| 💎 **Beauty Club** | Har bir xariddan bonus beriladi: bonus buyurtma yetkazilgandan keyin hisoblanadi va keyingi xaridda ishlatiladi. Bundan tashqari, shaxsiy taklif havolasi bor: dugona birinchi xaridini olganda taklif qilganga bonus beriladi. |
| 🔔 **Eslatma** | Teri tahlilidan 14 kun o'tgach bot "teringiz qanday?" deb yozadi va qayta tahlilga taklif qiladi. Bu mijozni qaytaradi va yangi sotuvga olib keladi. |
| 📊 **Admin panel** | Bot ichida: statistika, narx o'zgartirish, mahsulotni sotuvdan olish, hammaga xabar yuborish, blogerlar samaradorligi. |

### Xavfsizlik va qonuniylik
- **AI tashxis qo'ymaydi va dori yozmaydi.** U faqat kosmetik vositalarni (niatsinamid, salitsil kislotasi, SPF va hokazo) tavsiya qiladi. Retsept bilan beriladigan dorilar (antibiotik, gormonal, izotretinoin) taqiqlangan. Xavfli belgilar bo'lsa (xolning o'zgarishi, shish, infeksiya), shifokorga darhol murojaat qilish so'raladi. Har bir natija ostida "bu tibbiy tashxis emas" degan ogohlantirish bor.
- 18 yoshgacha bo'lganlar, homiladorlar va emizikli onalarga retinol va kuchli kislotalar tavsiya qilinmaydi.
- **Yuz rasmlari saqlanmaydi.** Birinchi rasmdan oldin rozilik so'raladi. `/delete_me` buyrug'i foydalanuvchining barcha ma'lumotlarini o'chiradi.
- AI faqat katalogdagi mahsulotlarni tavsiya qila oladi. Katalogda yo'q ID lar avtomatik tashlab yuboriladi.
- Har bir foydalanuvchi uchun kunlik AI so'rovlar limiti bor (`DAILY_AI_LIMIT`), bu xarajatni nazorat qiladi. Bir vaqtda faqat bitta AI so'rovi ishlaydi. Albom bo'lib kelgan rasmlardan faqat birinchisi tahlil qilinadi. Spam (juda ko'p xabar) avtomatik e'tiborsiz qoldiriladi.
- To'lovda karta ma'lumotlari Click/Payme tomonida qoladi. Bot har bir to'lovdan oldin buyurtma summasi va egasini tekshiradi. To'lanmagan buyurtma 24 soatdan keyin bekor qilinadi va ishlatilgan bonus qaytariladi.
- Bot qayta ishga tushsa ham foydalanuvchining qaysi qadamda turgani (FSM) bazada saqlanib qoladi. Kutilmagan xatolar logga yoziladi, foydalanuvchiga esa tushunarli xabar boradi.

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

Serverda Docker orqali ishga tushirish (tavsiya etiladi; bot qulasa ham avtomatik qayta yonadi):

```bash
docker compose up -d --build
docker compose logs -f bot      # loglarni ko'rish
```

Ma'lumotlar bazasi `beauty-db` nomli Docker volume'da saqlanadi. Undan muntazam zaxira nusxa oling.

### Onlayn to'lovni ulash (Click / Payme)
1. Click yoki Payme bilan merchant shartnoma tuzing (bu kod bilan bo'lmaydi).
2. @BotFather → `/mybots` → botingiz → **Payments** → Click yoki Payme ni tanlang va token oling.
3. Tokenni `.env` ichidagi `PAYMENT_PROVIDER_TOKEN=` qatoriga yozing. Bo'sh qolsa, faqat kuryerga to'lov ishlaydi.

Avval provayderning **test** tokeni bilan sinab ko'ring.

### Blogerlar va reklama havolalari
Har bir bloger yoki reklamaga alohida havola bering: `https://t.me/BOTINGIZ?start=aziza`. Qaysi manbadan qancha yangi mijoz kelgani `/stats` buyrug'ida ko'rinadi. Dugonani taklif qilish havolasi (`?start=ref_...`) har bir mijozga "Beauty Club" bo'limida avtomatik beriladi.

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
Bu buyruqlar faqat `ADMIN_IDS` dagi odamlar uchun ishlaydi, boshqalar uchun bot jim turadi.

| Buyruq | Nima qiladi |
|---|---|
| (tugmalar) | Yangi buyurtma admin guruhiga ✅ Tasdiqlash / 📦 Yetkazildi / ❌ Bekor tugmalari bilan keladi. Mijozga holat haqida avtomatik xabar boradi. |
| `/admin` | Buyruqlar ro'yxati |
| `/orders [new\|confirmed\|delivered\|cancelled\|awaiting_payment]` | Buyurtmalar ro'yxati |
| `/stats [kunlar]` | Statistika: foydalanuvchilar, tushum, AI dan xaridga konversiya, eng ko'p sotilgan AI tavsiyalari, bloger manbalari |
| `/products [kategoriya]` | Mahsulotlar, narx va mavjudlik |
| `/price sk-spf50 145000` | Narxni o'zgartirish (darhol, faylni tahrirlamasdan) |
| `/stock sk-spf50 off` / `on` | Sotuvdan olish yoki qaytarish. AI ham bu mahsulotni tavsiya qilmaydi |
| `/reload` | `data/products.json` ni qayta o'qish (botni to'xtatmasdan) |
| `/broadcast` | Chatga xabar (matn, rasm yoki video) yozing, so'ng unga **javob (reply)** qilib `/broadcast` deb yozing. Tasdiqlagandan keyin xabar hammaga yuboriladi |

## Testlar

```bash
pip install -r requirements-dev.txt
ruff check beauty_bot tests
pytest
```

GitHub'ga har safar push qilinganda testlar avtomatik ishlaydi (`.github/workflows/tests.yml`).

61 ta test haqiqiy dispatcher orqali to'liq ssenariylarni tekshiradi: start va til tanlash, teri tahlili, makiyaj, atir, Academy, savat, buyurtma, Click/Payme to'lovi, referal, eslatmalar, admin panel, bot qayta ishga tushgandan keyin holat saqlanishi va spamdan himoya. Telegram va AI o'rniga soxta (fake) obyektlar ishlatiladi. Gemini so'rovlarining tuzilishi va bloklangan javoblarni qayta ishlash haqiqiy SDK orqali, soxta HTTP javoblar bilan alohida tekshiriladi.

## Loyiha tuzilishi

```
beauty_bot/
  __main__.py       ishga tushirish, routerlar
  config.py         .env sozlamalari
  texts.py          3 tildagi matnlar va lotin→kirill transliteratsiya
  catalog.py        mahsulot katalogi
  db.py             SQLite: foydalanuvchi, savat, buyurtma, bonus, AI limiti, statistika, eslatmalar
  storage.py        FSM holatini bazada saqlash
  middlewares.py    til, spamdan himoya, albomlar
  scheduler.py      fon vazifalari: eslatmalar, to'lanmagan buyurtmalar
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

## Ishga tushirishdan oldin (kod bilan bo'lmaydigan ishlar)
- **Katalog:** haqiqiy mahsulotlar, narxlar, rasmlar va har biriga to'g'ri teglar (teri turi, muammo, tarkib, ehtiyot choralari).
- **Click / Payme bilan shartnoma** va BotFather'dan to'lov tokeni.
- **Gemini'da billing'ni yoqish** (pullik tarif).
- **Yuristga ko'rsatish:** maxfiylik siyosati, ommaviy oferta, shaxsiy ma'lumotlar qonuni. O'zbekistonda fuqarolarning shaxsiy ma'lumotlarini mamlakat ichidagi serverda saqlash talabi bor, shuning uchun serverni shunga qarab tanlang.
- **Mahsulot sertifikatlari** va originalligini tasdiqlovchi hujjatlar.
- **Dermatolog hamkor:** "shifokorga murojaat qiling" degan joyda aniq kontakt bo'lishi yaxshi.
- **Sinov:** 20–30 ta haqiqiy rasm bilan AI javoblarini tekshirish va promptlarni sozlash.
- **Bot ko'rinishi:** avatar, tavsif va BotFather'dagi "About" matni.
