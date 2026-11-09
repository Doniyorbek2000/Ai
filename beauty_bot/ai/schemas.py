"""AI javoblari uchun tuzilgan (structured) formatlar.

Field tavsiflari ingliz tilida: ular model uchun, foydalanuvchiga ko'rinmaydi."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Likelihood = Literal["low", "medium", "high"]


class Observation(BaseModel):
    name: str = Field(description="Visible sign in plain words (e.g. inflamed breakouts)")
    area: str = Field(description="Where on the face (forehead, cheeks, chin...)")
    likelihood: Likelihood
    note: str = Field(description="Short note: what it may mean and what to watch")


class RoutineStep(BaseModel):
    step: str = Field(description="Step name (cleanse, serum, moisturize, SPF...)")
    product_id: Optional[str] = Field(description="Matching catalog product id, or null")
    how: str = Field(description="How and how often to use it")


class SkinAnalysis(BaseModel):
    is_face_photo: bool
    photo_usable: bool = Field(description="Is the photo good enough to judge the skin")
    photo_tip: str = Field(description="If the photo is poor, how to retake it; otherwise empty")
    skin_type: Literal["oily", "dry", "combination", "normal", "sensitive", "unclear"]
    skin_type_label: str = Field(description="Skin type in the user's language")
    summary: str = Field(description="2-3 sentence summary, warm and encouraging")
    observations: list[Observation]
    morning_routine: list[RoutineStep]
    evening_routine: list[RoutineStep]
    tips: list[str] = Field(description="3-6 practical habits (sleep, pillowcase, not touching or squeezing...)")
    see_dermatologist: bool
    dermatologist_reason: str
    urgent: bool = Field(description="Are there warning signs that need a doctor soon")
    urgent_reason: str
    product_ids: list[str] = Field(description="Recommended catalog product ids, most important first, up to 6")


class LookProfile(BaseModel):
    is_face_photo: bool
    face_shape: str
    undertone: str = Field(description="Warm / cool / neutral, with a short note")
    color_type: str = Field(description="Color type (spring, summer, autumn, winter) with a short note")
    best_colors: list[str]
    avoid_colors: list[str]
    brows: str = Field(description="Brow shape and color advice")
    hair: str = Field(description="Hairstyle and length advice")
    makeup: str = Field(description="Key everyday and evening makeup advice")
    summary: str
    product_ids: list[str]


class MakeupPlan(BaseModel):
    is_face_photo: bool
    summary: str = Field(description="Why this look suits this face, 1-2 sentences")
    steps: list[str] = Field(description="Short steps to recreate the look herself, 5-9")
    product_ids: list[str]


class PerfumePick(BaseModel):
    product_id: str
    why: str


class PerfumePicks(BaseModel):
    intro: str
    picks: list[PerfumePick]
