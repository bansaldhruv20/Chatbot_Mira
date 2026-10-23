import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

try:
    from . import dp_helper as db
    from . import generic_helper as helper
except ImportError:
    # Support running from inside the backend directory too.
    import dp_helper as db
    import generic_helper as helper


@asynccontextmanager
async def lifespan(app):
    db.initialize()
    yield


app = FastAPI(
    title="Mira food ordering prototype",
    lifespan=lifespan,
)

frontend = Path(__file__).resolve().parents[1] / "frontend"


class Action(BaseModel):
    session: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    action: Literal[
        "new",
        "add",
        "remove",
        "cart",
        "complete",
        "track",
    ]
    items: list[str] = Field(
        default_factory=list,
        max_length=30,
    )
    quantities: list[Any] = Field(
        default_factory=list,
        max_length=30,
    )
    order_id: Any = None


def perform(action: Action):
    if action.action == "track":
        result = db.track(action.order_id)

        message = (
            f"Order #{result['order_id']} is "
            f"{result['status']}. Total: {result['total']}."
        )

    else:
        result = db.cart_action(
            action.session,
            action.action,
            action.items,
            action.quantities,
        )

        if action.action == "complete":
            message = (
                "Order placed! "
                f"Your order ID is #{result['order_id']}. "
                f"Total: {result['total']}, payable on delivery."
            )
        else:
            cart_text = helper.get_str_from_food_dict(
                result["items"]
            )

            message = (
                f"Your cart: {cart_text}. "
                "Add items or confirm your order."
            )

    return {
        **result,
        "fulfillmentText": message,
    }


def audit(source, action_name, success):
    try:
        db.record_interaction(
            source,
            action_name,
            success,
        )
    except SQLAlchemyError:
        # Logging failure must not turn a saved order into an error.
        logging.exception("Could not record interaction")


def execute(payload, source):
    try:
        result = perform(payload)
        audit(source, payload.action, True)
        return result

    except ValueError as error:
        audit(source, payload.action, False)
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except SQLAlchemyError:
        logging.exception("Database operation failed")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Please retry.",
        ) from None


@app.get("/health")
def health():
    with db.engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"status": "ok"}


@app.get("/api/menu")
def menu():
    return db.menu()


@app.post("/api/action")
def action(payload: Action):
    return execute(payload, "local_controls")


# Accept the corrected agent names and the original export's names.
INTENTS = {
    "new.order": "new",
    "order.add - context: ongoing-order": "add",
    "order.add - context: ongoing": "add",
    "order.remove - context: ongoing-order": "remove",
    "order.remove - context: ongoing": "remove",
    "order.complete - context: ongoing-order": "complete",
    "order.complete - context: ongoing": "complete",
    "track.order - context: ongoing-tracking": "track",
    "track.order - context:on-goingtracking": "track",
}


def as_list(value):
    if isinstance(value, list):
        return value

    if value is None:
        return []

    return [value]


@app.post("/")
@app.post("/webhook")
async def webhook(request: Request):
    token = os.getenv("WEBHOOK_TOKEN")

    if token and not secrets.compare_digest(
        request.headers.get("X-Webhook-Token", ""),
        token,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook token",
        )

    try:
        payload = await request.json()

        query = payload["queryResult"]
        intent = query["intent"]["displayName"]

        if intent not in INTENTS:
            return {
                "fulfillmentText": (
                    "Please start a new order "
                    "or ask to track an order."
                )
            }

        parameters = query.get("parameters") or {}

        session = helper.extract_session_id(
            payload.get("session", "")
        )

        # Older payloads may identify the session through a context.
        if not session:
            contexts = query.get("outputContexts") or []

            session = (
                helper.extract_session_id(
                    contexts[0].get("name", "")
                )
                if contexts
                else ""
            )

        names = next(
            (
                parameters[key]
                for key in [
                    "food-item",
                    "Food-Items",
                    "food-items",
                ]
                if key in parameters
            ),
            [],
        )

        result = execute(
            Action(
                session=session,
                action=INTENTS[intent],
                items=as_list(names),
                quantities=as_list(
                    parameters.get("number")
                ),
                order_id=parameters.get("order_id"),
            ),
            "webhook",
        )

        return {
            "fulfillmentText": result["fulfillmentText"]
        }

    except HTTPException as error:
        if error.status_code == 400:
            return {
                "fulfillmentText": error.detail
            }
        raise

    except (
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        AttributeError,
    ):
        return {
            "fulfillmentText": (
                "Please provide a valid session, "
                "food items and quantities, or an order ID."
            )
        }


@app.get("/")
def home():
    return FileResponse(frontend / "home.html")


app.mount(
    "/static",
    StaticFiles(directory=frontend),
    name="static",
)
