"""Gemini-backed finance assistant. Sends a short summary, not the full ledger."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from decimal import Decimal

from dotenv import load_dotenv

from app_paths import app_dir
from personel_finance_tracker import parse_amount_field

ROOT = app_dir()
load_dotenv(ROOT / ".env")

DEFAULT_MODEL = "gemini-3.8-flash"
# Only current Flash models — older 2.x IDs return 404 for new API keys.
FALLBACK_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
)
MAX_RECENT = 12
MAX_ATTEMPTS_PER_MODEL = 3

SYSTEM_INSTRUCTION = """
You are a personal finance assistant for a local expense tracker.
Answer in the same language the user writes in (Turkish or English).
Use only the provided summary and recent transactions. Do not invent balances.
Be concise and practical: spending patterns, category focus, and realistic tips.
Do not ask for API keys, passwords, or bank credentials.
""".strip()


def get_api_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key is None:
        return None
    key = key.strip()
    return key or None


def get_model_name() -> str:
    return (os.getenv("GEMINI_MODEL") or DEFAULT_MODEL).strip()


def candidate_models() -> list[str]:
    primary = get_model_name()
    ordered = [primary]
    for name in FALLBACK_MODELS:
        if name not in ordered:
            ordered.append(name)
    return ordered


def build_finance_context(data: list[dict], recent_limit: int = MAX_RECENT) -> str:
    """Compact text context for the model (summary + recent rows only)."""
    if not data:
        return "No transactions recorded yet."

    income = Decimal("0.00")
    expense = Decimal("0.00")
    by_category: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"Income": Decimal("0.00"), "Expense": Decimal("0.00")}
    )

    for item in data:
        amount = parse_amount_field(item["amount"])
        t_type = item["type"]
        if t_type == "Income":
            income += amount
        else:
            expense += amount
        by_category[item["category"]][t_type] += amount

    balance = income - expense
    lines = [
        f"Transaction count: {len(data)}",
        f"Total income: {income}",
        f"Total expense: {expense}",
        f"Net balance: {balance}",
        "Category nets (income - expense):",
    ]
    for cat, amounts in sorted(by_category.items(), key=lambda x: x[0].lower()):
        net = amounts["Income"] - amounts["Expense"]
        lines.append(
            f"  - {cat}: income={amounts['Income']}, expense={amounts['Expense']}, net={net}"
        )

    recent = data[-recent_limit:]
    lines.append(f"Recent transactions (last {len(recent)}):")
    for item in recent:
        lines.append(
            f"  - {item.get('date', 'N/A')} | {item['type']} | "
            f"{item['category']} | {item['amount']}"
        )
    return "\n".join(lines)


def _error_text(exc: BaseException) -> str:
    return str(exc).lower()


def _is_unavailable(exc: BaseException) -> bool:
    text = _error_text(exc)
    return "503" in text or "unavailable" in text or "high demand" in text


def _is_not_found(exc: BaseException) -> bool:
    text = _error_text(exc)
    return "404" in text or "not_found" in text or "no longer available" in text


def ask_finance_assistant(question: str, data: list[dict]) -> str:
    """Send question + compact context to Gemini. Raises ValueError if misconfigured."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Copy .env.example to .env and add your key."
        )

    question = (question or "").strip()
    if not question:
        raise ValueError("Question is empty.")

    context = build_finance_context(data)
    prompt = (
        f"Finance context:\n{context}\n\n"
        f"User question:\n{question}"
    )

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ValueError(
            "google-genai is not installed. Run: pip install -r requirements.txt"
        ) from exc

    client = genai.Client(api_key=api_key)
    last_error: BaseException | None = None
    saw_unavailable = False
    try:
        for model_name in candidate_models():
            for attempt in range(1, MAX_ATTEMPTS_PER_MODEL + 1):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            temperature=0.4,
                        ),
                    )
                    text = (response.text or "").strip()
                    if not text:
                        raise ValueError("Gemini returned an empty response.")
                    return text
                except ValueError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if _is_unavailable(exc):
                        saw_unavailable = True
                        if attempt < MAX_ATTEMPTS_PER_MODEL:
                            time.sleep(1.5 * attempt)
                            continue
                        break
                    if _is_not_found(exc):
                        break
                    raise ValueError(f"Gemini request failed: {exc}") from exc
    finally:
        client.close()

    if saw_unavailable:
        raise ValueError(
            "Gemini şu an yoğun (503). Biraz bekleyip tekrar dene; "
            "istek güncel yedek modellere de denendi."
        ) from last_error
    if last_error is not None and _is_not_found(last_error):
        raise ValueError(
            "Seçilen Gemini modeli bulunamadı. .env içinde "
            "GEMINI_MODEL=gemini-3.8-flash olduğundan emin ol."
        ) from last_error
    if last_error is not None:
        raise ValueError(f"Gemini request failed: {last_error}") from last_error
    raise ValueError("Gemini request failed.")
