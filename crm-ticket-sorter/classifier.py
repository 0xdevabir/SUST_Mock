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
        "agent_summary": "Unable to classify ticket automatically. Please review manually.",
        "human_review_required": True,
        "confidence": 0.0,
    }


def _strip_markdown_fences(text: str) -> str:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    return cleaned.strip()


def _parse_response_json(raw_text: str) -> dict:
    cleaned = _strip_markdown_fences(raw_text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"Failed to parse Claude response:\n{raw_text}")
        raise

    if not isinstance(payload, dict):
        print(f"Failed to parse Claude response:\n{raw_text}")
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
        parsed = _parse_response_json(raw_text)
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
