from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.database import get_database_connection


app = FastAPI(title="Bundle Data Assistant")


# Allow our SvelteKit frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


# Structure of incoming chat messages
class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


# Database reporting function
def get_total_orders():

    with get_database_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT COUNT(*) FROM orders;"
            )

            result = cursor.fetchone()

            return result[0]


# Chat endpoint
@app.post("/api/chat")
def chat(request: ChatRequest):

    question = request.message.lower()

    if "order" in question:

        try:

            total = get_total_orders()

            return {
                "answer": f"There are {total} orders in the database.",
                "rows": []
            }

        except Exception as error:
            print("DATABASE ERROR:", type(error).__name__, str(error))
            return {
                "answer": "Sorry, I could not retrieve the order data.",
                "rows": []
                }

    return {
        "answer": "I can help you with questions about orders.",
        "rows": []
    }