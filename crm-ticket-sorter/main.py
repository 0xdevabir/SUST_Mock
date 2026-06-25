from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from classifier import classify_ticket
from models import TicketRequest, TicketResponse

load_dotenv()

app = FastAPI(
    title="CRM Ticket Sorter",
    description="Classify CRM support tickets by case type, severity, and department.",
    version="1.0.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/classify", response_model=TicketResponse)
async def classify(request: TicketRequest) -> TicketResponse:
    try:
        return classify_ticket(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
