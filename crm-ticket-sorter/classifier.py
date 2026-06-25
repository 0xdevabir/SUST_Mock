import json
import os
import re

import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a fintech customer support ticket classifier.

Return ONLY a valid JSON object. No markdown, no code fences, no explanation.

The JSON object must contain exactly these keys:
- case_type: one of wrong_transfer, payment_failed, refund_request, phishing_or_social_engineering, other
- severity: one of low, medium, high, critical
- department: one of customer_support, dispute_resolution, payments_ops, fraud_risk
- agent_summary: one or two neutral sentences describing the ticket — MUST NEVER mention PIN, OTP, password, or card number
- confidence: float between 0.0 and 1.0

Classification rules:
- wrong_transfer → severity: high, department: dispute_resolution
- payment_failed → severity: high, department: payments_ops
- phishing_or_social_engineering → severity: critical, department: fraud_risk
- refund_request → severity: low or medium, department: customer_support or dispute_resolution
- other → severity: low, department: customer_support

Do not include human_review_required in the JSON."""


def _fallback_result(ticket_id: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "case_type": "other",
        "severity": "low",
        "department": "customer_support",
        "agent_summary": "Unable to classify the ticket automatically; routed for general review.",
        "human_review_required": False,
        "confidence": 0.0,
    }


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("Claude response was not a JSON object")
    return payload


def _compute_human_review_required(case_type: str, severity: str) -> bool:
    return severity == "critical" or case_type == "phishing_or_social_engineering"


def _build_user_message(
    message: str,
    channel: str | None,
    locale: str | None,
) -> str:
    parts = [f"Message: {message}"]
    if channel:
        parts.append(f"Channel: {channel}")
    if locale:
        parts.append(f"Locale: {locale}")
    return "\n".join(parts)


async def classify_ticket(
    ticket_id: str,
    message: str,
    channel: str | None = None,
    locale: str | None = None,
) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.AsyncAnthropic(api_key=api_key)

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _build_user_message(message, channel, locale),
                }
            ],
        )
        raw_text = response.content[0].text
        parsed = _extract_json(raw_text)
    except (json.JSONDecodeError, ValueError, IndexError, KeyError, TypeError):
        return _fallback_result(ticket_id)
    except anthropic.APIError:
        return _fallback_result(ticket_id)

    case_type = parsed.get("case_type", "other")
    severity = parsed.get("severity", "low")

    return {
        "ticket_id": ticket_id,
        "case_type": case_type,
        "severity": severity,
        "department": parsed.get("department", "customer_support"),
        "agent_summary": parsed.get(
            "agent_summary",
            "Ticket received for general customer support review.",
        ),
        "human_review_required": _compute_human_review_required(case_type, severity),
        "confidence": float(parsed.get("confidence", 0.0)),
    }
