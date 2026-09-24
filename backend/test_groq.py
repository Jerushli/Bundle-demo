import os

from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


# Locate our backend folder
BASE_DIR = Path(__file__).resolve().parent


# Load API credentials from backend/.env
load_dotenv(BASE_DIR / ".env")


# Retrieve Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def test_groq_connection():

    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY is missing.")
        return

    try:

        # Create Groq client
        client = Groq(
            api_key=GROQ_API_KEY,
            timeout=30.0
        )

        print("Sending request to Groq...")

        # Send a message to the AI model
        response = client.chat.completions.create(

            model="openai/gpt-oss-20b",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant. "
                        "Keep your answers short and clear."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        "Reply with: Groq connection successful."
                    )
                }
            ]

        )

        # Retrieve generated response
        answer = response.choices[0].message.content

        print("\nGroq API connected successfully!")

        print("\nAI Response:")

        print(answer)

    except Exception as error:

        print("\nGroq API connection failed!")

        print("Error type:", type(error).__name__)

        print("Error:", str(error))


if __name__ == "__main__":

    test_groq_connection()