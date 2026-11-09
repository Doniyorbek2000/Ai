"""AI natijalarini Telegram HTML matniga aylantirish (sof funksiyalar)."""

from __future__ import annotations

from html import escape

from .ai.schemas import LookProfile, MakeupPlan, PerfumePicks, RoutineStep, SkinAnalysis
from .catalog import Catalog, Product
from .texts import fmt_price, t

TELEGRAM_LIMIT = 4000


def _e(s: str) -> str:
    return escape(s.strip(), quote=False)


def _routine(title: str, steps: list[RoutineStep], catalog: Catalog, lang: str) -> list[str]:
    if not steps:
        return []
    out = [f"\n<b>{title}</b>"]
    for i, s in enumerate(steps, 1):
        line = f"{i}. <b>{_e(s.step)}</b>"
        product = catalog.get(s.product_id) if s.product_id else None
        if product and product.in_stock:
            line += f" — {_e(product.title(lang))}"
        out.append(line)
        if s.how.strip():
            out.append(f"   {_e(s.how)}")
    return out


def render_skin(r: SkinAnalysis, catalog: Catalog, lang: str) -> str:
    parts = [t("skin_title", lang), ""]
    if r.urgent:
        reason = r.urgent_reason or r.dermatologist_reason
        parts += [t("urgent_warning", lang, reason=_e(reason)), ""]
    if not r.photo_usable and r.photo_tip.strip():
        parts += [f"📷 {_e(r.photo_tip)}", ""]
    parts.append(f"<b>{t('skin_type', lang)}:</b> {_e(r.skin_type_label)}")
    if r.summary.strip():
        parts.append(_e(r.summary))
    if r.observations:
        parts.append(f"\n<b>{t('observations', lang)}:</b>")
        for o in r.observations:
            likely = t(f"likelihood_{o.likelihood}", lang)
            parts.append(f"• <b>{_e(o.name)}</b> ({_e(o.area)}, {likely}) — {_e(o.note)}")
    parts += _routine(t("morning", lang), r.morning_routine, catalog, lang)
    parts += _routine(t("evening", lang), r.evening_routine, catalog, lang)
    if r.tips:
        parts.append(f"\n<b>{t('tips', lang)}</b>")
        parts += [f"• {_e(tip)}" for tip in r.tips if tip.strip()]
    if r.see_dermatologist and not r.urgent and r.dermatologist_reason.strip():
        parts += ["", t("derm_warning", lang, reason=_e(r.dermatologist_reason))]
    parts += ["", t("medical_disclaimer", lang)]
    return "\n".join(parts)


def render_look(r: LookProfile, lang: str) -> str:
    parts = [
        t("look_title", lang),
        "",
        _e(r.summary),
        "",
        f"<b>{t('face_shape', lang)}:</b> {_e(r.face_shape)}",
        f"<b>{t('undertone', lang)}:</b> {_e(r.undertone)}",
        f"<b>{t('color_type', lang)}:</b> {_e(r.color_type)}",
    ]
    if r.best_colors:
        parts.append(f"\n<b>{t('best_colors', lang)}:</b> " + ", ".join(_e(c) for c in r.best_colors))
    if r.avoid_colors:
        parts.append(f"<b>{t('avoid_colors', lang)}:</b> " + ", ".join(_e(c) for c in r.avoid_colors))
    parts += [
        f"\n<b>{t('brows', lang)}:</b> {_e(r.brows)}",
        f"\n<b>{t('hair', lang)}:</b> {_e(r.hair)}",
        f"\n<b>{t('makeup_advice', lang)}:</b> {_e(r.makeup)}",
    ]
    return "\n".join(parts)


def render_makeup_plan(r: MakeupPlan, lang: str) -> str:
    parts = [t("makeup_plan_title", lang)]
    if r.summary.strip():
        parts += ["", _e(r.summary)]
    parts.append("")
    parts += [f"{i}. {_e(s)}" for i, s in enumerate(r.steps, 1) if s.strip()]
    return "\n".join(parts)


def render_perfume(r: PerfumePicks, catalog: Catalog, lang: str) -> tuple[str, list[Product]]:
    products: list[Product] = []
    parts = [t("perfume_title", lang)]
    if r.intro.strip():
        parts += ["", _e(r.intro)]
    for pick in r.picks:
        p = catalog.get(pick.product_id)
        if not p or not p.in_stock or p.category != "perfume" or p in products:
            continue
        products.append(p)
        parts += ["", f"🌸 <b>{_e(p.title(lang))}</b> — {fmt_price(p.price, lang)}", _e(pick.why)]
    if not products:
        return t("no_perfume_match", lang), []
    return "\n".join(parts), products


def render_products(products: list[Product], lang: str) -> str:
    lines = [t("recommended", lang)]
    lines += [f"• {_e(p.title(lang))} — {fmt_price(p.price, lang)}" for p in products]
    return "\n".join(lines)


def render_product_card(p: Product, catalog: Catalog, lang: str) -> str:
    text = (
        f"<b>{_e(p.title(lang))}</b>\n"
        f"<i>{_e(catalog.category_title(p.category, lang))}</i>\n\n"
        f"{_e(p.desc(lang))}\n\n"
        f"<b>{t('price', lang)}:</b> {fmt_price(p.price, lang)}"
    )
    if not p.in_stock:
        text += f"\n❗️ {t('out_of_stock', lang)}"
    return text


def cart_lines(items: list[tuple[str, int]], catalog: Catalog) -> list[tuple[Product, int]]:
    """Savatdagi mavjud mahsulotlar (katalogdan o'chirilganlari tashlab yuboriladi)."""
    out = []
    for pid, qty in items:
        p = catalog.get(pid)
        if p and p.in_stock and qty > 0:
            out.append((p, qty))
    return out


def render_cart(lines: list[tuple[Product, int]], lang: str) -> tuple[str, int]:
    if not lines:
        return t("cart_empty", lang), 0
    total = sum(p.price * q for p, q in lines)
    parts = [t("cart_title", lang), ""]
    for p, q in lines:
        parts.append(f"• {_e(p.title(lang))}\n   {q} × {fmt_price(p.price, lang)} = {fmt_price(p.price * q, lang)}")
    parts += ["", f"<b>{t('total', lang)}: {fmt_price(total, lang)}</b>"]
    return "\n".join(parts), total


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Uzun matnni paragraf chegaralarida bo'ladi (HTML teglari qator ichida yopiq)."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:  # juda uzun qator (kamdan-kam)
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
