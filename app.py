from flask import Flask, render_template, request, jsonify
import os
import time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.db import setup_database, store_appointment, get_appointments_by_email, delete_appointments_by_email
from src.helper_func import (
    is_valid_email, is_valid_date, is_valid_time, standardize_time,
    send_email, make_confirmation_message, make_cancellation_message
)

load_dotenv()

setup_database()

app = Flask(__name__)

@tool
def book_appointment(name: str, email: str, date: str, time: str, purpose: str) -> str:
    """Book an appointment and email the user a confirmation."""

    if not all([name, email, date, time, purpose]):
        return "Missing required information. Please provide all details."
    
    if not is_valid_email(email):
        return "Invalid email address. Please provide a valid email."
    
    if not is_valid_date(date):
        return "Invalid date or date is in the past. Please use DD/MM/YYYY format."
    
    if not is_valid_time(time):
        return "Invalid time format. Please use HH:MM or H AM/PM."
    
    std_time = standardize_time(time)

    success, msg = store_appointment(name, email, date, std_time, purpose)
    if not success:
        return f"Failed to book appointment: {msg}"

    try:
        subject = "Your Appointment Confirmation"
        body = make_confirmation_message(name, date, std_time, purpose)
        send_email(to_address=email, subject=subject, body=body)
    except Exception as e:

        app.logger.error(f"Email send error for {email}: {e}")

    return (
        f"✅ Appointment booked for **{name}** on **{date}** at **{std_time}** "
        f"for **{purpose}**. A confirmation email has been sent to {email}."
    )


@tool
def check_appointments(email: str) -> str:
    """Check appointments for the given email."""


    if not is_valid_email(email):
        return "Invalid email address. Please provide a valid email."
    

    appointments = get_appointments_by_email(email)
    if not appointments:
        return "No appointments found for this email."
    

    response = "**Your Appointments:**\n\n"
    for i, appnt in enumerate(appointments, 1):
        response += f"**Appointment {i}:**\n"
        response += f"- **Date:** {appnt['date']}\n"
        response += f"- **Time:** {appnt['time']}\n"
        response += f"- **Purpose:** {appnt['purpose']}\n\n"
    return response.strip()

@tool
def cancel_appointment(email: str) -> str:
    """Cancel all appointments for the given email."""
    
    if not is_valid_email(email):
        return "Invalid email address. Please provide a valid email."
    
    appointments = get_appointments_by_email(email)
    if not appointments:
        return "No appointments found for this email. Nothing to cancel."
    
    success, count = delete_appointments_by_email(email)
    if not success:
        return "Failed to cancel appointments. Please try again."
    
    try:
        subject = "Your Appointment Cancellation"
        body = make_cancellation_message(email, count)
        send_email(to_address=email, subject=subject, body=body)
    except Exception as e:
        app.logger.error(f"Email send error for {email}: {e}")
    
    return (
        f"❌ Successfully cancelled {count} appointment{'s' if count > 1 else ''} "
        f"for **{email}**. A cancellation confirmation email has been sent."
    )


def get_llm():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.environ["GEMINI_API_KEY"],
        temperature=0.1
    )
    return llm.bind_tools([book_appointment, check_appointments, cancel_appointment])


llm_with_tools = get_llm()

system_message = SystemMessage(content="""
You are an AI Appointment Booking Assistant. Your task is to help users book appointments, check existing appointments, or cancel appointments.

# NEW: handle user greetings
At the very start of the conversation, if the user only greets you, respond with a friendly greeting and ask how you can help.

For booking an appointment:
- Collect name, email, date (DD/MM/YYYY), time, and purpose.
- Ask one at a time, then call the book_appointment tool.
- After booking, the user gets both a chat confirmation and an email.

For checking appointments:
- Ask for email and call the check_appointments tool.

For cancelling appointments:
- Ask for email only and call the cancel_appointment tool.
- All appointments for that email will be cancelled.
- After cancellation, the user gets both a chat confirmation and an email.

Be concise, friendly, and use emojis to keep it engaging.
""")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/message', methods=['POST'])
def process_message():
    data = request.json
    user_input = data.get('message', '')
    history = data.get('history', [])


    messages = [system_message]
    for msg in history:
        messages.append(AIMessage(content=msg['content']) if msg['role']=='assistant'
                        else HumanMessage(content=msg['content']))
    messages.append(HumanMessage(content=user_input))


    time.sleep(0.5)
    response = llm_with_tools.invoke(messages)


    if response.tool_calls:
        for call in response.tool_calls:
            if call['name']=='book_appointment':
                result = book_appointment.invoke(call['args'])
            elif call['name']=='check_appointments':
                result = check_appointments.invoke(call['args'])
            elif call['name']=='cancel_appointment':
                result = cancel_appointment.invoke(call['args'])
            else:
                result = "Unknown tool."
            return jsonify({'content': result})
    return jsonify({'content': response.content})

if __name__ == '__main__':
    app.run(debug=True)