import os
from twilio.rest import Client
import dotenv

dotenv.load_dotenv()


account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_NUMBER")

client = Client(account_sid, auth_token)

def send_whatsapp_message(to: str, message: str):
    client.messages.create(
        from_=whatsapp_from,
        to=to,
        body=message
    )