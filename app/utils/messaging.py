import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()


account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_NUMBER")

client = Client(account_sid, auth_token)


def send_whatsapp_message(to: str, message: str):
    """Send a WhatsApp message using the Twilio API.

    Args:
        to (str): The recipient's WhatsApp number (e.g., 'whatsapp:+521234567890').
        message (str): The content of the message to be sent.
    """
    client.messages.create(from_=whatsapp_from, to=to, body=message)
