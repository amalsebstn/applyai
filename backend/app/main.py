"""ApplyAI API.

Run locally:  uvicorn app.main:app --reload --port 8000
"""
import io
import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader

from . import llm
from .schemas import MAX_CV_CHARS, Bullet, TailorRequest, TailorResponse
from .security import RateLimiter, detect_injection, redact_pii, ungrounded_terms, wrap_untrusted

load_dotenv()

# Log metadata only (sizes, timings, counts) - never CV or job text (LLM02).
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("applyai")

MAX_PDF_BYTES = 2 * 1024 * 1024

app = FastAPI(title="ApplyAI", docs_url="/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGIN", "http://localhost:5173")],
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)
limiter = RateLimiter(max_calls=int(os.getenv("RATE_LIMIT_PER_MINUTE", "5")))


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/extract")
async def extract_pdf(file: UploadFile = File(...)):
    """Extract text from an uploaded CV PDF. The file is processed in memory and never stored."""
    if file.content_type != "application/pdf":
        raise HTTPException(415, "Upload a PDF file.")
    data = await file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF must be under 2 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "That file isn't a valid PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:5])
    except Exception:
        raise HTTPException(422, "Couldn't read text from that PDF. Paste your CV text instead.")
    if not text.strip():
        raise HTTPException(422, "No text found in that PDF. It may be a scanned image; paste your CV text instead.")
    return {"text": text[:MAX_CV_CHARS]}


@app.post("/api/tailor", response_model=TailorResponse)
def tailor(body: TailorRequest, request: Request):
    if not limiter.allow(_client_id(request)):
        raise HTTPException(429, "Too many requests. Wait a minute and try again.")

    started = time.monotonic()
    cv_clean, cv_redacted = redact_pii(body.cv_text)
    job_clean, job_redacted = redact_pii(body.job_text)
    warnings = detect_injection(body.job_text) + detect_injection(body.cv_text)

    prompt = wrap_untrusted("cv", cv_clean) + "\n\n" + wrap_untrusted("job", job_clean)
    try:
        out = llm.call_model(prompt)
    except llm.LLMError as exc:
        log.warning("tailor failed: %s", exc)
        raise HTTPException(502, "The AI service didn't return a usable result. Try again.")

    bullets = [Bullet(text=b, unverified_terms=ungrounded_terms(b, body.cv_text)) for b in out.tailored_bullets]
    log.info(
        "tailor ok cv_chars=%d job_chars=%d pii_redacted=%d injection_flags=%d unverified=%d secs=%.1f",
        len(body.cv_text), len(body.job_text), cv_redacted + job_redacted, len(warnings),
        sum(1 for b in bullets if b.unverified_terms), time.monotonic() - started,
    )
    return TailorResponse(
        match_score=out.match_score,
        strengths=out.strengths,
        gaps=out.gaps,
        missing_keywords=out.missing_keywords,
        bullets=bullets,
        cover_letter=out.cover_letter,
        pii_redacted=cv_redacted + job_redacted,
        injection_warnings=warnings,
    )
