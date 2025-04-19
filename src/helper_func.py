import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

# Load environment variables
load_dotenv()

# Initialize the Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.environ["GEMINI_API_KEY"],
    temperature=0.1
)

# Define a prompt template for the appointment assistant
appointment_prompt_template = """
You are an AI Appointment Booking Assistant designed to help users schedule and manage their appointments.

CONTEXT:
The user is interacting with you through a chat interface. Your primary functions are:

Helping users book new appointments
Retrieving information about existing appointments
CURRENT STATE: {current_state}
USER INFORMATION: {user_info}

USER INPUT: {user_input}

Your task is to respond helpfully and naturally while guiding the user through the appointment booking or retrieval process.
If the user provides unclear or incomplete information, politely ask for clarification.

FORMATTING GUIDELINES:

Present appointment details in a clean, organized format using clear headings and sections.
Use bullet points or numbered lists where appropriate.
For appointment confirmations, create a visually distinct "Appointment Confirmation" section.
For appointment listings, format each appointment in a way that's easy to scan quickly.
Add emoji for relevant concepts (📅 for dates, ⏰ for time, 📝 for purpose, etc.)
Keep your responses concise, friendly, and focused on the appointment booking task.

RESPONSE:
"""

# Create the prompt template object
prompt = PromptTemplate(
    input_variables=["current_state", "user_info", "user_input"],
    template=appointment_prompt_template
)

# Create the LLM chain
appointment_chain = LLMChain(llm=llm, prompt=prompt)

def extract_email(text: str) -> str:
    """Extract email from user input."""
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    if email_match:
        return email_match.group(0)
    return ""

def has_booking_intent(text: str) -> bool:
    """Check if input contains booking intent."""
    booking_indicators = [
        "book", "schedule", "make", "set", "create", "arrange", "new appointment",
        "fix", "plan", "reserve", "want appointment", "need appointment", "1", "option 1",
        "first option", "booking"
    ]
    return any(indicator.lower() in text.lower() for indicator in booking_indicators)

def has_checking_intent(text: str) -> bool:
    """Check if input contains checking/retrieval intent."""
    checking_indicators = [
        "check", "get", "show", "list", "find", "view", "see", "retrieve", "tell",
        "what", "when", "my appointment", "appointment detail", "status", "2", "option 2",
        "second option", "checking"
    ]
    return any(indicator.lower() in text.lower() for indicator in checking_indicators)

def is_valid_date(date_str: str) -> bool:
    """Validate date format."""
    # Check common date formats: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD
    date_patterns = [
        re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$"),  # DD/MM/YYYY or MM/DD/YYYY
        re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"),  # YYYY-MM-DD
        re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")   # DD-MM-YYYY or MM-DD-YYYY
    ]

    # Check if date matches any of the patterns
    if not any(pattern.match(date_str) for pattern in date_patterns):
        return False

    # Try to parse the date
    try:
        # First try with common formats
        formats = ["%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"]
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # Check if date is in the future (or today)
                if parsed_date.date() >= datetime.now().date():
                    return True
            except ValueError:
                continue
        return False
    except Exception:
        return False

def is_valid_time(time_str: str) -> bool:
    """Validate time format."""
    # Check multiple time formats: 14:30, 2:30 PM, 2PM, etc.
    time_patterns = [
        re.compile(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$"),  # 24-hour format like 14:30
        re.compile(r"^(1[0-2]|0?[1-9]):([0-5][0-9])\s?(AM|PM|am|pm)$"),  # 12-hour with minutes
        re.compile(r"^(1[0-2]|0?[1-9])\s?(AM|PM|am|pm)$")  # 12-hour without minutes
    ]

    return any(pattern.match(time_str) for pattern in time_patterns)

def standardize_time(time_str: str) -> str:
    """Standardize time format."""
    # If already in 24-hour format like 14:30
    if re.match(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$", time_str):
        return time_str

    # If in 12-hour format with minutes like 2:30 PM
    match = re.match(r"^(1[0-2]|0?[1-9]):([0-5][0-9])\s?(AM|PM|am|pm)$", time_str)
    if match:
        hour, minute, period = match.groups()
        hour = int(hour)
        if period.lower() == "pm" and hour < 12:
            hour += 12
        elif period.lower() == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute}"

    # If in 12-hour format without minutes like 2PM
    match = re.match(r"^(1[0-2]|0?[1-9])\s?(AM|PM|am|pm)$", time_str)
    if match:
        hour, period = match.groups()
        hour = int(hour)
        if period.lower() == "pm" and hour < 12:
            hour += 12
        elif period.lower() == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:00"

    return time_str  # Return original if no pattern matches

def get_llm_response(state, user_input, booking_info=None):
    """For more complex responses, use the LLM."""
    # Prepare user info summary
    if booking_info:
        user_info = ", ".join([f"{k}: {v}" for k, v in booking_info.items() if v])
    else:
        user_info = "No booking information available yet"

    # Use the LLM chain to generate a response
    response = appointment_chain.run(
        current_state=state,
        user_info=user_info,
        user_input=user_input
    )

    return response.strip()

def format_appointment_details(booking_info):
    """Format appointment details in a clear, readable way."""
    return f"""
📋 APPOINTMENT DETAILS 📋
👤 Name: {booking_info["name"]}
📧 Email: {booking_info["email"]}
📅 Date: {booking_info["date"]}
⏰ Time: {booking_info["time"]}
📝 Purpose: {booking_info["purpose"]}
"""

def validate_booking_info(booking_info):
    """Validate booking information."""
    missing_fields = []
    invalid_fields = []

    # Check required fields
    for field in ["name", "email", "date", "time", "purpose"]:
        if field not in booking_info or not booking_info[field].strip():
            missing_fields.append(field)

    # Validate fields if present
    if "email" in booking_info and booking_info["email"]:
        if not re.match(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", booking_info["email"]):
            invalid_fields.append("email")

    if "date" in booking_info and booking_info["date"]:
        if not is_valid_date(booking_info["date"]):
            invalid_fields.append("date")

    if "time" in booking_info and booking_info["time"]:
        if not is_valid_time(booking_info["time"]):
            invalid_fields.append("time")

    return missing_fields, invalid_fields