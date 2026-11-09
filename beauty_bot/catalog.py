"""Mahsulot katalogi (data/products.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from .texts import fmt_price, norm_lang, to_cyrillic


@dataclass(frozen=True)
class Product:
    id: str
    category: str
    price: int
    name: dict[str, str]
    description: dict[str, str]
    in_stock: bool = True
    image_url: str | None = None
    skin_types: tuple[str, ...] = ()
    concerns: tuple[str, ...] = ()
    ingredients: tuple[str, ...] = ()
    cautions: tuple[str, ...] = ()
    makeup_styles: tuple[str, ...] = ()
    families: tuple[str, ...] = ()
    seasons: tuple[str, ...] = ()
    occasions: tuple[str, ...] = ()

    def title(self, lang: str | None) -> str:
        return _localized(self.name, lang)

    def desc(self, lang: str | None) -> str:
        return _localized(self.description, lang)

    def short(self, lang: str | None) -> str:
        return f"{self.title(lang)} — {fmt_price(self.price, lang)}"


def _localized(d: dict[str, str], lang: str | None) -> str:
    lang = norm_lang(lang)
    if lang == "uz_cyrl":
        return to_cyrillic(d.get("uz", ""))
    return d.get(lang) or d.get("uz", "")


@dataclass
class Catalog:
    categories: dict[str, dict[str, str]]
    products: list[Product] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_id = {p.id: p for p in self.products}

    @classmethod
    def load(cls, path: str | Path) -> "Catalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        tuple_fields = {
            "skin_types", "concerns", "ingredients", "cautions",
            "makeup_styles", "families", "seasons", "occasions",
        }
        products = []
        for item in raw["products"]:
            kwargs = {k: (tuple(v) if k in tuple_fields else v) for k, v in item.items()}
            products.append(Product(**kwargs))
        ids = [p.id for p in products]
        if len(ids) != len(set(ids)):
            raise ValueError("Katalogda takroriy mahsulot ID lari bor")
        return cls(categories=raw["categories"], products=products)

    def update(self, product_id: str, **changes: object) -> Product | None:
        """Mahsulot narxi yoki mavjudligini joyida o'zgartiradi (admin buyruqlari uchun)."""
        old = self._by_id.get(product_id)
        if old is None:
            return None
        new = replace(old, **changes)
        self.products[self.products.index(old)] = new
        self._by_id[product_id] = new
        return new

    def apply_overrides(self, overrides: dict[str, dict]) -> None:
        for product_id, changes in overrides.items():
            if changes:
                self.update(product_id, **changes)

    def reload_from(self, other: "Catalog") -> None:
        """Fayldan qayta o'qilgan katalogni joriy obyektga ko'chiradi (havolalar o'zgarmaydi)."""
        self.categories = other.categories
        self.products = other.products
        self._by_id = {p.id: p for p in self.products}

    def get(self, product_id: str) -> Product | None:
        return self._by_id.get(product_id)

    def category_title(self, category: str, lang: str | None) -> str:
        return _localized(self.categories.get(category, {"uz": category}), lang)

    def by_category(self, category: str) -> list[Product]:
        return [p for p in self.products if p.category == category]

    def available(self, category: str | None = None) -> list[Product]:
        return [p for p in self.products if p.in_stock and (category is None or p.category == category)]

    def valid_ids(self, ids: list[str], limit: int = 6) -> list[Product]:
        """AI qaytargan ID larni tekshiradi: faqat mavjud va sotuvdagi mahsulotlar."""
        out: list[Product] = []
        for pid in ids:
            p = self.get(pid)
            if p and p.in_stock and p not in out:
                out.append(p)
            if len(out) >= limit:
                break
        return out

    def ai_context(self, categories: tuple[str, ...]) -> str:
        """AI uchun ixcham katalog (faqat sotuvdagi mahsulotlar)."""
        rows = []
        for p in self.products:
            if not p.in_stock or p.category not in categories:
                continue
            row: dict[str, object] = {
                "id": p.id,
                "category": p.category,
                "name": p.name.get("ru") or p.name.get("uz"),
                "price_uzs": p.price,
                "about": p.description.get("ru") or p.description.get("uz"),
            }
            for key in ("skin_types", "concerns", "ingredients", "cautions",
                        "makeup_styles", "families", "seasons", "occasions"):
                val = getattr(p, key)
                if val:
                    row[key] = list(val)
            rows.append(row)
        return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
