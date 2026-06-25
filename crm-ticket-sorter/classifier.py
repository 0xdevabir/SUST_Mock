import os
import re
from dataclasses import dataclass

from models import (
    CaseType,
    Department,
    Severity,
    TicketRequest,
    TicketResponse,
)

CASE_KEYWORDS: dict[CaseType, tuple[str, ...]] = {
    "wrong_transfer": (
        "wrong number",
        "wrong account",
        "wrong recipient",
        "sent to wrong",
        "mistaken transfer",
        "incorrect number",
        "ভুল নম্বর",
        "ভুল একাউন্ট",
        "ভুল নম্বরে",
        "ভুলে পাঠিয়েছি",
    ),
    "payment_failed": (
        "payment failed",
        "transaction failed",
        "could not pay",
        "payment not working",
        "declined",
        "টাকা যায়নি",
        "পেমেন্ট ফেইল",
        "লেনদেন ব্যর্থ",
        "ট্রানজেকশন ফেইল",
    ),
    "refund_request": (
        "refund",
        "money back",
        "return my money",
        "reverse transaction",
        "ফেরত",
        "রিফান্ড",
        "টাকা ফেরত",
        "রিফান্ড চাই",
    ),
    "phishing_or_social_engineering": (
        "otp",
        "one time password",
        "verify account",
        "click this link",
        "suspicious call",
        "scam",
        "phishing",
        "fake sms",
        "পাসওয়ার্ড",
        "ওটিপি",
        "ভুয়া",
        "প্রতারণা",
        "স্ক্যাম",
    ),
}

CASE_DEPARTMENT: dict[CaseType, Department] = {
    "wrong_transfer": "dispute_resolution",
    "payment_failed": "payments_ops",
    "refund_request": "dispute_resolution",
    "phishing_or_social_engineering": "fraud_risk",
    "other": "customer_support",
}

CASE_SEVERITY: dict[CaseType, Severity] = {
    "wrong_transfer": "high",
    "payment_failed": "medium",
    "refund_request": "medium",
    "phishing_or_social_engineering": "critical",
    "other": "low",
}


@dataclass(frozen=True)
class ClassificationMatch:
    case_type: CaseType
    score: float
    matched_keywords: tuple[str, ...]


def _normalize_text(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


def _score_case_type(message: str, keywords: tuple[str, ...]) -> tuple[float, tuple[str, ...]]:
    matched = tuple(keyword for keyword in keywords if keyword in message)
    if not matched:
        return 0.0, ()

    longest_match = max(len(keyword) for keyword in matched)
    coverage = min(1.0, longest_match / max(len(message), 1))
    score = min(1.0, 0.55 + (0.15 * len(matched)) + (0.3 * coverage))
    return score, matched


def _classify_with_rules(request: TicketRequest) -> ClassificationMatch:
    normalized_message = _normalize_text(request.message)
    best_match = ClassificationMatch(case_type="other", score=0.35, matched_keywords=())

    for case_type, keywords in CASE_KEYWORDS.items():
        score, matched_keywords = _score_case_type(normalized_message, keywords)
        if score > best_match.score:
            best_match = ClassificationMatch(
                case_type=case_type,
                score=score,
                matched_keywords=matched_keywords,
            )

    return best_match


def _build_summary(request: TicketRequest, match: ClassificationMatch) -> str:
    channel = request.channel or "unknown channel"
    locale = request.locale or "unknown locale"
    keyword_hint = (
        f" Matched signals: {', '.join(match.matched_keywords)}."
        if match.matched_keywords
        else " No strong keyword match; routed as general inquiry."
    )
    return (
        f"Ticket {request.ticket_id} from {channel} ({locale}) classified as "
        f"{match.case_type.replace('_', ' ')}.{keyword_hint}"
    )


def _human_review_required(case_type: CaseType, severity: Severity, confidence: float) -> bool:
    if case_type == "phishing_or_social_engineering":
        return True
    if severity in {"critical", "high"}:
        return True
    return confidence < 0.6


def classify_ticket(request: TicketRequest) -> TicketResponse:
    use_llm = os.getenv("USE_LLM_CLASSIFIER", "false").lower() == "true"
    if use_llm and os.getenv("OPENAI_API_KEY"):
        return _classify_with_llm(request)

    match = _classify_with_rules(request)
    case_type = match.case_type
    severity = CASE_SEVERITY[case_type]
    department = CASE_DEPARTMENT[case_type]
    confidence = round(match.score, 2)

    return TicketResponse(
        ticket_id=request.ticket_id,
        case_type=case_type,
        severity=severity,
        department=department,
        agent_summary=_build_summary(request, match),
        human_review_required=_human_review_required(case_type, severity, confidence),
        confidence=confidence,
    )


def _classify_with_llm(request: TicketRequest) -> TicketResponse:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "USE_LLM_CLASSIFIER is enabled but openai is not installed."
        ) from exc

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    prompt = (
        "Classify this CRM support ticket for a mobile financial service.\n"
        f"Ticket ID: {request.ticket_id}\n"
        f"Channel: {request.channel or 'unknown'}\n"
        f"Locale: {request.locale or 'unknown'}\n"
        f"Message: {request.message}\n\n"
        "Return JSON with keys: case_type, severity, department, agent_summary, "
        "human_review_required, confidence."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a ticket triage assistant. "
                    "case_type must be one of: wrong_transfer, payment_failed, "
                    "refund_request, phishing_or_social_engineering, other. "
                    "severity must be one of: low, medium, high, critical. "
                    "department must be one of: customer_support, dispute_resolution, "
                    "payments_ops, fraud_risk. confidence must be between 0 and 1."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    content = response.choices[0].message.content or "{}"
    payload = TicketResponse.model_validate_json(
        content,
        strict=False,
    )
    return payload.model_copy(update={"ticket_id": request.ticket_id})
