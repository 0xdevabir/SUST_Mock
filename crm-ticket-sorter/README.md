# CRM Ticket Sorter

FastAPI service that classifies CRM support tickets by case type, severity, and routing department.

## Project structure

```
crm-ticket-sorter/
├── main.py
├── classifier.py
├── models.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Setup

```bash
cd crm-ticket-sorter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

## API

### `GET /health`

Health check.

### `POST /classify`

Request body (`TicketRequest`):

```json
{
  "ticket_id": "TKT-1001",
  "channel": "app",
  "locale": "bn",
  "message": "ভুল নম্বরে টাকা পাঠিয়ে ফেলেছি"
}
```

Response (`TicketResponse`):

```json
{
  "ticket_id": "TKT-1001",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Ticket TKT-1001 from app (bn) classified as wrong transfer. Matched signals: ভুল নম্বর.",
  "human_review_required": true,
  "confidence": 0.82
}
```

## Classification

Tickets are classified via the Anthropic API (`claude-sonnet-4-6`). Set `ANTHROPIC_API_KEY` in `.env`.

## Supported values

| Field | Values |
|-------|--------|
| `channel` | `app`, `sms`, `call_center`, `merchant_portal` |
| `locale` | `bn`, `en`, `mixed` |
| `case_type` | `wrong_transfer`, `payment_failed`, `refund_request`, `phishing_or_social_engineering`, `other` |
| `severity` | `low`, `medium`, `high`, `critical` |
| `department` | `customer_support`, `dispute_resolution`, `payments_ops`, `fraud_risk` |
