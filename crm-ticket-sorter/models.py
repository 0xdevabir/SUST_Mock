from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Channel = Literal["app", "sms", "call_center", "merchant_portal"]
Locale = Literal["bn", "en", "mixed"]
CaseType = Literal[
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "phishing_or_social_engineering",
    "other",
]
Severity = Literal["low", "medium", "high", "critical"]
Department = Literal[
    "customer_support",
    "dispute_resolution",
    "payments_ops",
    "fraud_risk",
]

CHANNEL_VALUES = frozenset({"app", "sms", "call_center", "merchant_portal"})
LOCALE_VALUES = frozenset({"bn", "en", "mixed"})
CASE_TYPE_VALUES = frozenset(
    {
        "wrong_transfer",
        "payment_failed",
        "refund_request",
        "phishing_or_social_engineering",
        "other",
    }
)
SEVERITY_VALUES = frozenset({"low", "medium", "high", "critical"})
DEPARTMENT_VALUES = frozenset(
    {"customer_support", "dispute_resolution", "payments_ops", "fraud_risk"}
)


class TicketRequest(BaseModel):
    ticket_id: str
    channel: Optional[Channel] = None
    locale: Optional[Locale] = None
    message: str

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in CHANNEL_VALUES:
            raise ValueError(
                f"channel must be one of: {', '.join(sorted(CHANNEL_VALUES))}"
            )
        return value

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in LOCALE_VALUES:
            raise ValueError(
                f"locale must be one of: {', '.join(sorted(LOCALE_VALUES))}"
            )
        return value


class TicketResponse(BaseModel):
    ticket_id: str
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    human_review_required: bool
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("case_type")
    @classmethod
    def validate_case_type(cls, value: str) -> str:
        if value not in CASE_TYPE_VALUES:
            raise ValueError(
                f"case_type must be one of: {', '.join(sorted(CASE_TYPE_VALUES))}"
            )
        return value

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: str) -> str:
        if value not in SEVERITY_VALUES:
            raise ValueError(
                f"severity must be one of: {', '.join(sorted(SEVERITY_VALUES))}"
            )
        return value

    @field_validator("department")
    @classmethod
    def validate_department(cls, value: str) -> str:
        if value not in DEPARTMENT_VALUES:
            raise ValueError(
                f"department must be one of: {', '.join(sorted(DEPARTMENT_VALUES))}"
            )
        return value
