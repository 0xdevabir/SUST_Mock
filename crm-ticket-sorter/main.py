import asyncio

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from classifier import classify_ticket
from models import TicketRequest, TicketResponse

load_dotenv()

app = FastAPI(
    title="CRM Ticket Sorter",
    description="Classify CRM support tickets by case type, severity, and department.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "crm-ticket-sorter"}


@app.post("/sort-ticket", response_model=TicketResponse)
async def sort_ticket(request: TicketRequest) -> TicketResponse:
    try:
        result = await asyncio.wait_for(
            classify_ticket(
                ticket_id=request.ticket_id,
                message=request.message,
                channel=request.channel,
                locale=request.locale,
            ),
            timeout=30.0,
        )
        return TicketResponse(**result)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Classification timed out after 30 seconds",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
