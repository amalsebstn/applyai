"""Request and response schemas.

Input limits (LLM10) and strict output validation (LLM05) are enforced here.
"""
from pydantic import BaseModel, Field

MAX_CV_CHARS = 15_000
MAX_JOB_CHARS = 10_000


class TailorRequest(BaseModel):
    cv_text: str = Field(min_length=200, max_length=MAX_CV_CHARS)
    job_text: str = Field(min_length=100, max_length=MAX_JOB_CHARS)


# --- What the model must return (validated before anything reaches the browser) ---
class ModelOutput(BaseModel):
    match_score: int = Field(ge=0, le=100)
    strengths: list[str] = Field(max_length=8)
    gaps: list[str] = Field(max_length=8)
    missing_keywords: list[str] = Field(max_length=15)
    tailored_bullets: list[str] = Field(min_length=1, max_length=10)
    cover_letter: str = Field(max_length=4000)


# --- What the API returns to the frontend ---
class Bullet(BaseModel):
    text: str
    unverified_terms: list[str]


class TailorResponse(BaseModel):
    match_score: int
    strengths: list[str]
    gaps: list[str]
    missing_keywords: list[str]
    bullets: list[Bullet]
    cover_letter: str
    pii_redacted: int
    injection_warnings: list[str]
