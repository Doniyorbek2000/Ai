"""Bot matnlari: o'zbek (lotin), o'zbek (kirill) va rus tillarida.

O'zbek kirill matnlari lotin matnidan avtomatik transliteratsiya qilinadi,
shuning uchun faqat ``uz`` va ``ru`` yoziladi.
"""

from __future__ import annotations

import re
from functools import lru_cache

LANGS = ("uz", "uz_cyrl", "ru")
DEFAULT_LANG = "uz"

# AI javobi qaysi tilda yozilishi kerak
AI_LANGUAGE_NAME = {
    "uz": "Uzbek (Latin script)",
    "uz_cyrl": "Uzbek (Cyrillic script)",
    "ru": "Russian",
}

# ---------------------------------------------------------------------------
# Lotin -> kirill transliteratsiyasi
# ---------------------------------------------------------------------------

# Bu so'zlar o'zgarmaydi (brend va texnik so'zlar)
_PROTECTED = {
    "AI", "Beauty", "Club", "Academy", "Shop", "Reels", "SPF", "Instagram",
    "Telegram", "Skin", "Doctor", "Makeup", "Look", "Ideal", "Perfume", "ml", "BHA",
    "AHA", "PHA",
}

_APOSTROPHES = "'ʻʼ`’‘"
_DIGRAPHS = [
    ("o'", "ў"), ("g'", "ғ"), ("sh", "ш"), ("ch", "ч"),
    ("yo", "ё"), ("yu", "ю"), ("ya", "я"), ("ye", "е"),
]
_SINGLE = {
    "a": "а", "b": "б", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "x": "х", "y": "й", "z": "з", "c": "с", "w": "в",
}


def _match_case(src: str, dst: str) -> str:
    if src.isupper() and (len(src) > 1 or len(dst) == 1):
        return dst.upper()
    if src[0].isupper():
        return dst[0].upper() + dst[1:]
    return dst


def _translit_word(word: str) -> str:
    if word in _PROTECTED:
        return word
    w = word
    for ch in _APOSTROPHES:
        w = w.replace(ch, "'")
    out: list[str] = []
    i = 0
    low = w.lower()
    while i < len(w):
        two = low[i : i + 2]
        if two == "yo" and low[i + 2 : i + 3] == "'":  # yo'q -> йўқ
            out.append(_match_case(w[i], "й"))
            i += 1
            continue
        hit = next((dst for src, dst in _DIGRAPHS if two == src), None)
        if hit:
            out.append(_match_case(w[i : i + 2], hit))
            i += 2
            continue
        c = low[i]
        if c == "'":
            # tutuq belgisi (ma'lumot, sun'iy) -> ъ; so'z boshi/oxiridagi qo'shtirnoq tashlanadi
            out.append("ъ" if 0 < i < len(w) - 1 else "")
            i += 1
            continue
        if c == "e" and i == 0:
            out.append(_match_case(w[i], "э"))
        elif c in _SINGLE:
            out.append(_match_case(w[i], _SINGLE[c]))
        else:
            out.append(w[i])
        i += 1
    return "".join(out)


# HTML teglari, {placeholder} lar va so'zlar alohida ishlanadi
_TOKEN = re.compile(r"(<[^>]+>|\{[^}]*\}|&[a-z]+;|/[a-z_]+|[A-Za-z" + _APOSTROPHES + r"]+)")


@lru_cache(maxsize=2048)
def to_cyrillic(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        tok = m.group(0)
        if tok[0] in "<{&/":
            return tok
        return _translit_word(tok)

    return _TOKEN.sub(repl, text)


# ---------------------------------------------------------------------------
# Matnlar
# ---------------------------------------------------------------------------

T: dict[str, dict[str, str]] = {
    "choose_lang": {
        "uz": "Tilni tanlang / Тилни танланг / Выберите язык:",
        "ru": "Tilni tanlang / Тилни танланг / Выберите язык:",
    },
    "welcome": {
        "uz": (
            "💄 <b>AI Beauty</b> ga xush kelibsiz, {name}!\n\n"
            "Men sizning shaxsiy go'zallik yordamchingizman:\n"
            "• 🔬 yuz terisini tahlil qilaman va parvarish rejasini tuzaman\n"
            "• 💋 rasmingizga chiroyli makiyaj qo'yib ko'rsataman\n"
            "• ✨ sizga mos ranglar, qosh va makiyajni aytaman\n"
            "• 🌸 atir tanlashga yordam beraman\n"
            "• 🎬 Reels va suratga tushish uchun maslahat beraman\n"
            "• 🛍 original mahsulotlarni yetkazib beramiz\n\n"
            "Quyidagi menyudan tanlang 👇"
        ),
        "ru": (
            "💄 Добро пожаловать в <b>AI Beauty</b>, {name}!\n\n"
            "Я ваш персональный beauty-помощник:\n"
            "• 🔬 анализирую кожу лица и составляю план ухода\n"
            "• 💋 показываю, как на вас будет смотреться макияж\n"
            "• ✨ подсказываю подходящие цвета, форму бровей и макияж\n"
            "• 🌸 помогаю выбрать аромат\n"
            "• 🎬 даю советы для Reels и фотосъёмки\n"
            "• 🛍 доставляем оригинальную косметику\n\n"
            "Выберите в меню ниже 👇"
        ),
    },
    "menu": {"uz": "Asosiy menyu 👇", "ru": "Главное меню 👇"},
    "btn_skin": {"uz": "🔬 Teri tahlili", "ru": "🔬 Анализ кожи"},
    "btn_makeup": {"uz": "💋 AI makiyaj", "ru": "💋 AI макияж"},
    "btn_look": {"uz": "✨ Ideal obraz", "ru": "✨ Идеальный образ"},
    "btn_perfume": {"uz": "🌸 Atir tanlash", "ru": "🌸 Подбор аромата"},
    "btn_academy": {"uz": "🎬 Reels va maslahat", "ru": "🎬 Reels и советы"},
    "btn_shop": {"uz": "🛍 Do'kon", "ru": "🛍 Магазин"},
    "btn_cart": {"uz": "🧺 Savat", "ru": "🧺 Корзина"},
    "btn_club": {"uz": "💎 Beauty Club", "ru": "💎 Beauty Club"},
    "btn_settings": {"uz": "⚙️ Til / Maxfiylik", "ru": "⚙️ Язык / Конфиденциальность"},
    "btn_cancel": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена"},
    "btn_back": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад"},
    "btn_skip": {"uz": "➡️ O'tkazib yuborish", "ru": "➡️ Пропустить"},
    "btn_menu": {"uz": "🏠 Menyu", "ru": "🏠 Меню"},
    "cancelled": {"uz": "Bekor qilindi.", "ru": "Отменено."},
    # --- Rozilik va maxfiylik ---
    "consent": {
        "uz": (
            "📸 <b>Rasmingiz haqida</b>\n\n"
            "Tahlil uchun yuz rasmingiz sun'iy intellekt xizmatlariga yuboriladi. "
            "Biz rasmlaringizni <b>saqlamaymiz</b>: ular faqat javob tayyorlash uchun ishlatiladi.\n\n"
            "Istalgan vaqtda /delete_me buyrug'i bilan ma'lumotlaringizni o'chirishingiz mumkin.\n\n"
            "Rozimisiz?"
        ),
        "ru": (
            "📸 <b>О вашем фото</b>\n\n"
            "Для анализа фото лица передаётся сервисам искусственного интеллекта. "
            "Мы <b>не храним</b> ваши фотографии: они используются только для подготовки ответа.\n\n"
            "Вы можете удалить свои данные командой /delete_me в любой момент.\n\n"
            "Вы согласны?"
        ),
    },
    "consent_yes": {"uz": "✅ Roziman", "ru": "✅ Согласна"},
    "consent_no": {"uz": "Yo'q", "ru": "Нет"},
    "consent_declined": {
        "uz": "Tushunarli. Rasmsiz ham do'kon va maslahatlardan foydalanishingiz mumkin.",
        "ru": "Понятно. Без фото вы можете пользоваться магазином и советами.",
    },
    "privacy": {
        "uz": (
            "🔒 <b>Maxfiylik</b>\n\n"
            "• Yuz rasmlari saqlanmaydi, faqat tahlil vaqtida AI xizmatiga yuboriladi.\n"
            "• Biz faqat tilingiz, savatingiz, buyurtmalaringiz va bonuslaringizni saqlaymiz.\n"
            "• Onlayn to'lovda karta ma'lumotlari Click/Payme tomonida qayta ishlanadi, bizga kelmaydi.\n"
            "• /delete_me — barcha ma'lumotlaringizni o'chirish.\n\n"
            "Tilni o'zgartirish uchun quyidagi tugmani bosing."
        ),
        "ru": (
            "🔒 <b>Конфиденциальность</b>\n\n"
            "• Фото лица не сохраняются, они передаются AI-сервису только на время анализа.\n"
            "• Мы храним только язык, корзину, заказы и бонусы.\n"
            "• При онлайн-оплате данные карты обрабатывает Click/Payme, к нам они не попадают.\n"
            "• /delete_me — удалить все ваши данные.\n\n"
            "Чтобы сменить язык, нажмите кнопку ниже."
        ),
    },
    "btn_change_lang": {"uz": "🌐 Tilni o'zgartirish", "ru": "🌐 Сменить язык"},
    "deleted": {
        "uz": "🗑 Ma'lumotlaringiz o'chirildi. Qaytadan boshlash uchun /start bosing.",
        "ru": "🗑 Ваши данные удалены. Чтобы начать заново, нажмите /start.",
    },
    # --- Umumiy AI ---
    "send_photo": {
        "uz": (
            "📷 Endi yuzingiz rasmini yuboring.\n\n"
            "Yaxshi natija uchun: kunduzgi yorug'lik, makiyajsiz, yuz to'g'ridan, "
            "filtrsiz va aniq rasm."
        ),
        "ru": (
            "📷 Теперь отправьте фото лица.\n\n"
            "Для лучшего результата: дневной свет, без макияжа, лицо анфас, "
            "без фильтров, чёткое фото."
        ),
    },
    "send_photo_not_file": {
        "uz": "Iltimos, rasmni oddiy rasm (photo) sifatida yuboring.",
        "ru": "Пожалуйста, отправьте изображение как обычное фото.",
    },
    "analyzing": {"uz": "⏳ Tahlil qilyapman, 20–60 soniya kuting...", "ru": "⏳ Анализирую, подождите 20–60 секунд..."},
    "ai_error": {
        "uz": "😔 Hozir javob tayyorlay olmadim. Birozdan keyin qayta urinib ko'ring.",
        "ru": "😔 Сейчас не получилось подготовить ответ. Попробуйте чуть позже.",
    },
    "ai_refused": {
        "uz": "Bu so'rov bo'yicha javob bera olmayman. Iltimos, boshqacha so'rab ko'ring.",
        "ru": "На этот запрос я не могу ответить. Пожалуйста, сформулируйте иначе.",
    },
    "limit_reached": {
        "uz": "Bugungi bepul AI so'rovlar limiti tugadi ({limit} ta). Ertaga yana kutamiz! 💖",
        "ru": "Дневной лимит бесплатных AI-запросов исчерпан ({limit}). Ждём вас завтра! 💖",
    },
    "not_face": {
        "uz": "Rasmda yuz aniq ko'rinmadi. Iltimos, yuzingiz to'liq ko'rinadigan rasm yuboring.",
        "ru": "На фото не видно лица. Пожалуйста, отправьте фото, где лицо видно полностью.",
    },
    # --- Teri tahlili ---
    "skin_intro": {
        "uz": (
            "🔬 <b>AI Skin Doctor</b>\n\n"
            "Bir nechta savol beraman, keyin rasmingizni tahlil qilaman.\n\n"
            "Yoshingiz?"
        ),
        "ru": (
            "🔬 <b>AI Skin Doctor</b>\n\n"
            "Задам несколько вопросов, затем проанализирую фото.\n\n"
            "Ваш возраст?"
        ),
    },
    "ask_skin_feel": {
        "uz": "Kun davomida teringiz qanday his qilinadi?",
        "ru": "Как ощущается ваша кожа в течение дня?",
    },
    "ask_concern": {"uz": "Sizni eng ko'p nima bezovta qiladi?", "ru": "Что беспокоит больше всего?"},
    "ask_extra": {
        "uz": (
            "Qo'shimcha ma'lumot bormi? Masalan: homiladorlik, emizish, allergiya, "
            "hozir ishlatayotgan vositalar, toshma qachondan beri borligi.\n\n"
            "Yozing yoki «O'tkazib yuborish» ni bosing."
        ),
        "ru": (
            "Есть дополнительная информация? Например: беременность, кормление грудью, "
            "аллергия, средства, которыми пользуетесь, как давно появились высыпания.\n\n"
            "Напишите или нажмите «Пропустить»."
        ),
    },
    "skin_title": {"uz": "🔬 <b>Teri tahlili natijasi</b>", "ru": "🔬 <b>Результат анализа кожи</b>"},
    "skin_type": {"uz": "Teri turi", "ru": "Тип кожи"},
    "observations": {"uz": "Ko'rinayotgan belgilar", "ru": "Заметные признаки"},
    "morning": {"uz": "☀️ Ertalabki parvarish", "ru": "☀️ Утренний уход"},
    "evening": {"uz": "🌙 Kechki parvarish", "ru": "🌙 Вечерний уход"},
    "tips": {"uz": "💡 Maslahatlar", "ru": "💡 Советы"},
    "derm_warning": {
        "uz": "🩺 <b>Dermatologga uchrashishni tavsiya qilamiz:</b> {reason}",
        "ru": "🩺 <b>Рекомендуем обратиться к дерматологу:</b> {reason}",
    },
    "urgent_warning": {
        "uz": "🚨 <b>Iltimos, kechiktirmasdan shifokorga murojaat qiling:</b> {reason}",
        "ru": "🚨 <b>Пожалуйста, обратитесь к врачу без промедления:</b> {reason}",
    },
    "medical_disclaimer": {
        "uz": (
            "<i>⚠️ Bu tibbiy tashxis emas. AI faqat rasmdagi tashqi belgilarni baholaydi "
            "va kosmetik parvarish bo'yicha maslahat beradi. Dori-darmonni faqat shifokor tayinlaydi.</i>"
        ),
        "ru": (
            "<i>⚠️ Это не медицинский диагноз. AI оценивает только внешние признаки на фото "
            "и даёт советы по косметическому уходу. Лекарства назначает только врач.</i>"
        ),
    },
    "likelihood_low": {"uz": "ehtimoli past", "ru": "вероятность низкая"},
    "likelihood_medium": {"uz": "ehtimoli o'rtacha", "ru": "вероятность средняя"},
    "likelihood_high": {"uz": "ehtimoli yuqori", "ru": "вероятность высокая"},
    "recommended": {"uz": "🛍 <b>Sizga mos mahsulotlar:</b>", "ru": "🛍 <b>Подходящие вам средства:</b>"},
    # --- Makiyaj ---
    "makeup_intro": {
        "uz": "💋 <b>AI makiyaj</b>\n\nQaysi obrazni sinab ko'ramiz?",
        "ru": "💋 <b>AI макияж</b>\n\nКакой образ примерим?",
    },
    "makeup_generating": {
        "uz": "🎨 Makiyaj qo'yyapman, 30–90 soniya kuting...",
        "ru": "🎨 Наношу макияж, подождите 30–90 секунд...",
    },
    "makeup_caption": {
        "uz": "💋 Sizning «{style}» obrazingiz. Yuz tuzilishingiz o'zgartirilmagan, faqat makiyaj qo'shildi.",
        "ru": "💋 Ваш образ «{style}». Черты лица не изменены, добавлен только макияж.",
    },
    "makeup_image_failed": {
        "uz": "Rasm tayyorlashning iloji bo'lmadi, lekin makiyaj rejasini yozib berdim 👇",
        "ru": "Не удалось подготовить изображение, но я расписала план макияжа 👇",
    },
    "makeup_plan_title": {"uz": "📝 <b>Makiyaj rejasi</b>", "ru": "📝 <b>План макияжа</b>"},
    "makeup_again": {"uz": "🔁 Boshqa obraz", "ru": "🔁 Другой образ"},
    # --- Ideal obraz ---
    "look_intro": {
        "uz": (
            "✨ <b>Ideal obraz</b>\n\n"
            "Yuz shaklingiz, rang tipingiz va sizga yarashadigan ranglarni aniqlayman. "
            "Yuzingiz va sochingiz ko'rinadigan rasm yuboring."
        ),
        "ru": (
            "✨ <b>Идеальный образ</b>\n\n"
            "Определю форму лица, цветотип и подходящие вам цвета. "
            "Отправьте фото, где видно лицо и волосы."
        ),
    },
    "look_title": {"uz": "✨ <b>Sizning go'zallik profilingiz</b>", "ru": "✨ <b>Ваш beauty-профиль</b>"},
    "face_shape": {"uz": "Yuz shakli", "ru": "Форма лица"},
    "undertone": {"uz": "Teri ohangi", "ru": "Подтон кожи"},
    "color_type": {"uz": "Rang tipi", "ru": "Цветотип"},
    "best_colors": {"uz": "🎨 Sizga yarashadigan ranglar", "ru": "🎨 Вам идут цвета"},
    "avoid_colors": {"uz": "🚫 Ehtiyot bo'ling", "ru": "🚫 Осторожнее с"},
    "brows": {"uz": "Qosh", "ru": "Брови"},
    "hair": {"uz": "Soch turmagi", "ru": "Причёска"},
    "makeup_advice": {"uz": "Makiyaj", "ru": "Макияж"},
    # --- Atir ---
    "perfume_intro": {"uz": "🌸 <b>Atir tanlash</b>\n\nAtir kim uchun?", "ru": "🌸 <b>Подбор аромата</b>\n\nДля кого аромат?"},
    "ask_occasion": {"uz": "Qaysi vaziyat uchun?", "ru": "Для какого случая?"},
    "ask_family": {"uz": "Qanday hidlar yoqadi?", "ru": "Какие ароматы нравятся?"},
    "ask_season": {"uz": "Qaysi fasl uchun?", "ru": "Для какого сезона?"},
    "ask_budget": {"uz": "Byudjet?", "ru": "Бюджет?"},
    "picking": {"uz": "⏳ Siz uchun atir tanlayapman...", "ru": "⏳ Подбираю аромат..."},
    "perfume_title": {"uz": "🌸 <b>Siz uchun tanlangan atirlar</b>", "ru": "🌸 <b>Ароматы для вас</b>"},
    "no_perfume_match": {
        "uz": "Hozir katalogda bu talablarga mos atir topilmadi. Menejerimiz siz bilan bog'lanishi mumkin.",
        "ru": "Сейчас в каталоге нет подходящего аромата. Наш менеджер может с вами связаться.",
    },
    # --- Academy / Reels ---
    "academy_intro": {
        "uz": (
            "🎬 <b>Beauty Academy</b>\n\n"
            "Professional vizajist va kontent-maslahatchi sifatida javob beraman. Masalan:\n"
            "• Reels uchun qanday makiyaj kamerada chiroyli chiqadi?\n"
            "• Halqa lampa bilan qanday yoritish kerak?\n"
            "• Kechki tadbirga qanday tayyorlanay?\n\n"
            "Savolingizni yozing yoki rasm yuboring (masalan, kadrni baholash uchun). "
            "Chiqish uchun menyudagi istalgan bo'limni tanlang."
        ),
        "ru": (
            "🎬 <b>Beauty Academy</b>\n\n"
            "Отвечаю как профессиональный визажист и контент-консультант. Например:\n"
            "• Какой макияж хорошо смотрится в Reels?\n"
            "• Как правильно ставить кольцевую лампу?\n"
            "• Как подготовиться к вечернему мероприятию?\n\n"
            "Напишите вопрос или отправьте фото (например, чтобы оценить кадр). "
            "Чтобы выйти, выберите любой раздел меню."
        ),
    },
    "thinking": {"uz": "✍️ Javob yozyapman...", "ru": "✍️ Пишу ответ..."},
    # --- Do'kon ---
    "shop_title": {"uz": "🛍 <b>Do'kon</b> — bo'limni tanlang:", "ru": "🛍 <b>Магазин</b> — выберите раздел:"},
    "category_empty": {"uz": "Bu bo'limda hozircha mahsulot yo'q.", "ru": "В этом разделе пока нет товаров."},
    "price": {"uz": "Narxi", "ru": "Цена"},
    "sum": {"uz": "so'm", "ru": "сум"},
    "btn_add": {"uz": "🧺 Savatga qo'shish", "ru": "🧺 В корзину"},
    "added": {"uz": "✅ Savatga qo'shildi", "ru": "✅ Добавлено в корзину"},
    "not_found": {"uz": "Mahsulot topilmadi", "ru": "Товар не найден"},
    "out_of_stock": {"uz": "Hozir mavjud emas", "ru": "Нет в наличии"},
    "cart_empty": {"uz": "🧺 Savatingiz bo'sh.", "ru": "🧺 Ваша корзина пуста."},
    "cart_title": {"uz": "🧺 <b>Savat</b>", "ru": "🧺 <b>Корзина</b>"},
    "total": {"uz": "Jami", "ru": "Итого"},
    "btn_checkout": {"uz": "✅ Buyurtma berish", "ru": "✅ Оформить заказ"},
    "btn_clear": {"uz": "🗑 Tozalash", "ru": "🗑 Очистить"},
    "ask_phone": {
        "uz": "📞 Telefon raqamingizni yuboring (pastdagi tugma orqali yoki +998... ko'rinishida yozing):",
        "ru": "📞 Отправьте номер телефона (кнопкой ниже или в формате +998...):",
    },
    "btn_share_phone": {"uz": "📱 Raqamni yuborish", "ru": "📱 Отправить номер"},
    "bad_phone": {"uz": "Raqam noto'g'ri. Masalan: +998901234567", "ru": "Неверный номер. Например: +998901234567"},
    "ask_address": {
        "uz": "📍 Yetkazib berish manzilini yozing (shahar, ko'cha, uy) yoki lokatsiya yuboring:",
        "ru": "📍 Напишите адрес доставки (город, улица, дом) или отправьте геолокацию:",
    },
    "ask_comment": {"uz": "Izoh (ixtiyoriy):", "ru": "Комментарий (необязательно):"},
    "confirm_order": {
        "uz": "{cart}\n\n📞 {phone}\n📍 {address}\n💬 {comment}\n\n{payment}\nTasdiqlaysizmi?",
        "ru": "{cart}\n\n📞 {phone}\n📍 {address}\n💬 {comment}\n\n{payment}\nПодтверждаете?",
    },
    "btn_confirm": {"uz": "✅ Tasdiqlash", "ru": "✅ Подтвердить"},
    "order_placed": {
        "uz": "🎉 Buyurtma №{id} qabul qilindi! Menejerimiz tez orada bog'lanadi.\nYetkazilgandan so'ng {bonus} so'm bonus olasiz 💎",
        "ru": "🎉 Заказ №{id} принят! Менеджер скоро свяжется с вами.\nПосле доставки вы получите {bonus} сум бонусов 💎",
    },
    "use_bonus": {"uz": "💎 Bonus ishlatildi: −{amount} so'm", "ru": "💎 Списано бонусов: −{amount} сум"},
    "btn_use_bonus": {"uz": "💎 Bonusni ishlatish ({amount} so'm)", "ru": "💎 Списать бонусы ({amount} сум)"},
    # --- Club ---
    "club": {
        "uz": (
            "💎 <b>Beauty Club</b>\n\n"
            "Bonus balansingiz: <b>{balance} so'm</b>\n"
            "Har bir xariddan {percent}% bonus qaytadi. Bonusni keyingi buyurtmada ishlatishingiz mumkin.\n\n"
            "<b>Buyurtmalaringiz:</b>\n{orders}"
        ),
        "ru": (
            "💎 <b>Beauty Club</b>\n\n"
            "Ваш бонусный баланс: <b>{balance} сум</b>\n"
            "С каждой покупки возвращается {percent}% бонусами. Их можно использовать в следующем заказе.\n\n"
            "<b>Ваши заказы:</b>\n{orders}"
        ),
    },
    "no_orders": {"uz": "Hali buyurtma yo'q.", "ru": "Заказов пока нет."},
    "status_new": {"uz": "yangi", "ru": "новый"},
    "status_confirmed": {"uz": "tasdiqlangan", "ru": "подтверждён"},
    "status_delivered": {"uz": "yetkazilgan", "ru": "доставлен"},
    "status_cancelled": {"uz": "bekor qilingan", "ru": "отменён"},
    "order_status_changed": {
        "uz": "📦 Buyurtma №{id} holati: <b>{status}</b>",
        "ru": "📦 Статус заказа №{id}: <b>{status}</b>",
    },
    # --- Umumiy xatolar va navbat ---
    "error_generic": {
        "uz": "😔 Kutilmagan xatolik yuz berdi. Iltimos, qayta urinib ko'ring yoki /menu bosing.",
        "ru": "😔 Произошла непредвиденная ошибка. Попробуйте ещё раз или нажмите /menu.",
    },
    "busy": {
        "uz": "⏳ Oldingi so'rovingiz hali tayyorlanmoqda, biroz kuting.",
        "ru": "⏳ Предыдущий запрос ещё обрабатывается, подождите немного.",
    },
    # --- Yetkazib berish va to'lov ---
    "delivery": {"uz": "🚚 Yetkazib berish", "ru": "🚚 Доставка"},
    "delivery_free": {"uz": "bepul", "ru": "бесплатно"},
    "free_delivery_hint": {
        "uz": "💡 {amount} dan ortiq xaridda yetkazib berish bepul.",
        "ru": "💡 При заказе от {amount} доставка бесплатная.",
    },
    "choose_payment": {"uz": "To'lov usulini tanlang:", "ru": "Выберите способ оплаты:"},
    "btn_pay_online": {"uz": "💳 Onlayn: Click / Payme", "ru": "💳 Онлайн: Click / Payme"},
    "btn_pay_cash": {"uz": "💵 Kuryerga (naqd yoki karta)", "ru": "💵 Курьеру (наличные или карта)"},
    "payment_cash_note": {"uz": "To'lov: kuryerga naqd yoki karta orqali.", "ru": "Оплата: курьеру наличными или картой."},
    "invoice_title": {"uz": "AI Beauty buyurtma №{id}", "ru": "Заказ AI Beauty №{id}"},
    "invoice_description": {
        "uz": "{count} ta mahsulot, yetkazib berish bilan. Buyurtma to'lovdan keyin tasdiqlanadi.",
        "ru": "{count} товар(ов), с доставкой. Заказ подтверждается после оплаты.",
    },
    "invoice_sent": {
        "uz": "💳 Quyidagi tugma orqali to'lang. To'lov {hours} soat ichida qilinmasa, buyurtma bekor qilinadi.",
        "ru": "💳 Оплатите кнопкой ниже. Если оплата не поступит в течение {hours} ч, заказ будет отменён.",
    },
    "payment_received": {
        "uz": "✅ To'lov qabul qilindi! Buyurtma №{id} rasmiylashtirildi, menejerimiz tez orada bog'lanadi.\nYetkazilgandan so'ng {bonus} so'm bonus olasiz 💎",
        "ru": "✅ Оплата получена! Заказ №{id} оформлен, менеджер скоро свяжется с вами.\nПосле доставки вы получите {bonus} сум бонусов 💎",
    },
    "payment_problem": {
        "uz": "Bu buyurtmani to'lab bo'lmaydi: u bekor qilingan yoki allaqachon to'langan. Savatdan qaytadan buyurtma bering.",
        "ru": "Этот заказ нельзя оплатить: он отменён или уже оплачен. Оформите заказ заново из корзины.",
    },
    "order_expired": {
        "uz": "⌛️ Buyurtma №{id} to'lanmagani uchun bekor qilindi. Mahsulotlar savatingizda qoldi.",
        "ru": "⌛️ Заказ №{id} отменён, так как не был оплачен. Товары остались в корзине.",
    },
    "status_awaiting_payment": {"uz": "to'lov kutilmoqda", "ru": "ожидает оплаты"},
    # --- Taklif (referal) ---
    "invite": {
        "uz": "👭 <b>Dugonangizni taklif qiling!</b>\nShu havolani yuboring:\n{link}\n\nU birinchi xaridini olganda sizga {bonus} so'm bonus beriladi. Taklif qilganlaringiz: {count}",
        "ru": "👭 <b>Пригласите подругу!</b>\nОтправьте ей ссылку:\n{link}\n\nКогда она получит первый заказ, вам начислим {bonus} сум бонусов. Приглашено: {count}",
    },
    "referral_reward": {
        "uz": "🎁 Siz taklif qilgan dugonangiz birinchi xaridini oldi! Sizga {bonus} so'm bonus berildi.",
        "ru": "🎁 Ваша подруга получила первый заказ! Вам начислено {bonus} сум бонусов.",
    },
    # --- Eslatma ---
    "reminder_skin": {
        "uz": "🌸 Salom! {days} kun oldin teringizni tahlil qilgan edik. Parvarish qanday ketyapti?\n\nYangi rasm yuborsangiz, o'zgarishlarni ko'rib, rejani yangilab beraman.",
        "ru": "🌸 Здравствуйте! {days} дней назад мы анализировали вашу кожу. Как проходит уход?\n\nОтправьте новое фото — я оценю изменения и обновлю план.",
    },
    "btn_reanalyze": {"uz": "🔬 Qayta tahlil qilish", "ru": "🔬 Повторный анализ"},
}

# Tanlov variantlari: kod -> matn
OPTIONS: dict[str, dict[str, dict[str, str]]] = {
    "age": {
        "u18": {"uz": "18 gacha", "ru": "До 18"},
        "18_24": {"uz": "18–24", "ru": "18–24"},
        "25_34": {"uz": "25–34", "ru": "25–34"},
        "35_44": {"uz": "35–44", "ru": "35–44"},
        "45p": {"uz": "45+", "ru": "45+"},
    },
    "skin_feel": {
        "oily": {"uz": "Yog'li, yaltiraydi", "ru": "Жирная, блестит"},
        "dry": {"uz": "Quruq, tortishadi", "ru": "Сухая, стягивает"},
        "combination": {"uz": "T-zona yog'li, yonoqlar quruq", "ru": "Т-зона жирная, щёки сухие"},
        "normal": {"uz": "Normal", "ru": "Нормальная"},
        "sensitive": {"uz": "Sezgir, tez qizaradi", "ru": "Чувствительная, краснеет"},
        "unknown": {"uz": "Bilmayman", "ru": "Не знаю"},
    },
    "concern": {
        "acne": {"uz": "Toshma / husnbuzar", "ru": "Высыпания / акне"},
        "spots": {"uz": "Dog'lar, pigmentatsiya", "ru": "Пятна, пигментация"},
        "redness": {"uz": "Qizarish", "ru": "Покраснения"},
        "dryness": {"uz": "Quruqlik, po'st tashlash", "ru": "Сухость, шелушение"},
        "pores": {"uz": "Kengaygan teshikchalar", "ru": "Расширенные поры"},
        "aging": {"uz": "Ajinlar", "ru": "Морщины"},
        "dullness": {"uz": "Xira rang", "ru": "Тусклый цвет лица"},
    },
    "makeup_style": {
        "daily": {"uz": "☀️ Kundalik", "ru": "☀️ Повседневный"},
        "natural": {"uz": "🌿 Tabiiy (nude)", "ru": "🌿 Натуральный (nude)"},
        "evening": {"uz": "🌙 Kechki", "ru": "🌙 Вечерний"},
        "wedding": {"uz": "👰 To'y / bayram", "ru": "👰 Свадебный / праздничный"},
        "reels": {"uz": "🎬 Reels / foto uchun", "ru": "🎬 Для Reels / фото"},
        "glam": {"uz": "💎 Premium glam", "ru": "💎 Premium glam"},
    },
    "perfume_for": {
        "self": {"uz": "O'zim uchun", "ru": "Для себя"},
        "gift": {"uz": "Sovg'a uchun", "ru": "В подарок"},
    },
    "occasion": {
        "daily": {"uz": "Har kungi", "ru": "На каждый день"},
        "work": {"uz": "Ish / o'qish", "ru": "Работа / учёба"},
        "date": {"uz": "Romantik uchrashuv", "ru": "Романтическое свидание"},
        "evening": {"uz": "Kechki tadbir, to'y", "ru": "Вечернее мероприятие, свадьба"},
    },
    "family": {
        "floral": {"uz": "🌹 Gulli", "ru": "🌹 Цветочные"},
        "fruity": {"uz": "🍑 Mevali, shirin", "ru": "🍑 Фруктовые, сладкие"},
        "fresh": {"uz": "🍋 Yangi, sitrus", "ru": "🍋 Свежие, цитрусовые"},
        "oriental": {"uz": "🕌 Sharqona, iliq", "ru": "🕌 Восточные, тёплые"},
        "woody": {"uz": "🌲 Yog'ochli", "ru": "🌲 Древесные"},
        "gourmand": {"uz": "🍰 Vanil, shirinlik", "ru": "🍰 Ваниль, сладости"},
    },
    "season": {
        "spring_summer": {"uz": "Bahor–yoz", "ru": "Весна–лето"},
        "autumn_winter": {"uz": "Kuz–qish", "ru": "Осень–зима"},
        "all": {"uz": "Butun yil", "ru": "Круглый год"},
    },
    "budget": {
        "low": {"uz": "300 ming so'mgacha", "ru": "До 300 тыс. сум"},
        "mid": {"uz": "300–700 ming", "ru": "300–700 тыс."},
        "high": {"uz": "700 ming+", "ru": "700 тыс.+"},
    },
}

BUDGET_RANGES = {"low": (0, 300_000), "mid": (300_000, 700_000), "high": (700_000, 10**12)}


def norm_lang(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT_LANG


def _pick(entry: dict[str, str], lang: str) -> str:
    lang = norm_lang(lang)
    if lang == "uz_cyrl":
        return to_cyrillic(entry["uz"])
    return entry.get(lang) or entry["uz"]


def t(key: str, lang: str | None, **kwargs: object) -> str:
    text = _pick(T[key], lang or DEFAULT_LANG)
    return text.format(**kwargs) if kwargs else text


def opt(group: str, code: str, lang: str | None) -> str:
    return _pick(OPTIONS[group][code], lang or DEFAULT_LANG)


def options(group: str, lang: str | None) -> list[tuple[str, str]]:
    return [(code, opt(group, code, lang)) for code in OPTIONS[group]]


def all_variants(key: str) -> set[str]:
    """Tugma matnining barcha tillardagi variantlari (handler filtrlari uchun)."""
    return {t(key, lang) for lang in LANGS}


def fmt_price(amount: int, lang: str | None) -> str:
    return f"{amount:,}".replace(",", " ") + " " + t("sum", lang)
