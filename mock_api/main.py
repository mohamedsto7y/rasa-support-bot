"""Stand-in for the client's order / CRM system that the custom actions integrate with.

Run: uvicorn mock_api.main:app --port 8000
"""
from itertools import count
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock Orders API")

ORDERS = {
    "ORD-48213": {"status": "shipped", "eta": "tomorrow"},
    "ORD-10001": {"status": "processing", "eta": "in 3 days"},
    "ORD-55555": {"status": "delivered", "eta": None},
    "ORD-77777": {"status": "out_for_delivery", "eta": "today"},
    "ORD-12345": {"status": "cancelled", "eta": None},
}
TICKETS: dict = {}
_ticket_seq = count(1001)


class TicketIn(BaseModel):
    issue_type: str
    phone_number: str
    order_id: Optional[str] = None
    lang: str = "en"
    conversation_id: Optional[str] = None


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = ORDERS.get(order_id.upper())
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return {"order_id": order_id.upper(), **order}


@app.post("/tickets", status_code=201)
def create_ticket(ticket: TicketIn):
    ticket_id = f"TCK-{next(_ticket_seq)}"
    TICKETS[ticket_id] = ticket.model_dump() if hasattr(ticket, "model_dump") else ticket.dict()
    return {"ticket_id": ticket_id}
