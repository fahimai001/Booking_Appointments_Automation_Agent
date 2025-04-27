import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")


def has_booking_intent(text: str) -> bool:
    booking_indicators = ["book", "schedule", "make", "set", "create", "arrange", "new appointment"]
    return any(indicator.lower() in text.lower() for indicator in booking_indicators)


def has_checking_intent(text: str) -> bool:
    checking_indicators = ["check", "get", "show", "list", "find", "view", "see", "retrieve"]
    return any(indicator.lower() in text.lower() for indicator in checking_indicators)


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", email))


def is_valid_date(date_str: str) -> bool:
    date_patterns = [r"^(\d{1,2})/(\d{1,2})/(\d{4})$"]
    if not any(re.match(pattern, date_str) for pattern in date_patterns):
        return False
    try:
        parsed_date = datetime.strptime(date_str, "%d/%m/%Y")
        return parsed_date.date() >= datetime.now().date()
    except ValueError:
        return False


def is_valid_time(time_str: str) -> bool:
    time_patterns = [
        r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$",
        r"^(1[0-2]|0?[1-9]):([0-5][0-9])\s?(AM|PM|am|pm)$",
        r"^(1[0-2]|0?[1-9])\s?(AM|PM|am|pm)$"
    ]
    return any(re.match(pattern, time_str) for pattern in time_patterns)


def standardize_time(time_str: str) -> str:
    if re.match(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$", time_str):
        return time_str
    match = re.match(r"^(1[0-2]|0?[1-9]):([0-5][0-9])\s?(AM|PM|am|pm)$", time_str)
    if match:
        hour, minute, period = match.groups()
        hour = int(hour)
        if period.lower() == "pm" and hour < 12:
            hour += 12
        elif period.lower() == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute}"
    
    match = re.match(r"^(1[0-2]|0?[1-9])\s?(AM|PM|am|pm)$", time_str)
    if match:
        hour, period = match.groups()
        hour = int(hour)
        if period.lower() == "pm" and hour < 12:
            hour += 12
        elif period.lower() == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:00"
    return time_str


def send_email(to_address: str, subject: str, body: str) -> None:
    """
    Send an email via SMTP using credentials from your .env.
    Raises exception if sending fails.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = to_address
    msg.set_content(body)


    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_USER, EMAIL_PASS)
        smtp.send_message(msg)


def make_confirmation_message(name: str, date: str, time: str, purpose: str) -> str:
    """Builds the plain-text body for the confirmation email."""
    return (
        f"Hi {name},\n\n"
        f"Your appointment has been booked successfully! 📅⏰\n\n"
        f"— Date: {date}\n"
        f"— Time: {time}\n"
        f"— Purpose: {purpose}\n\n"
        "If you need to reschedule or cancel, just reply to this email.\n\n"
        "Thank you and have a great day!\n"
    )

def make_cancellation_message(email: str, count: int) -> str:
    """Builds the plain-text body for the cancellation email."""
    return (
        f"Hi there,\n\n"
        f"Your {count} appointment{'s' if count > 1 else ''} linked to {email} "
        f"{'have' if count > 1 else 'has'} been successfully cancelled. ❌📅\n\n"
        "If this was done in error or you wish to book new appointments, "
        "please contact us or use our booking system again.\n\n"
        "Thank you for using our service!\n"
    )