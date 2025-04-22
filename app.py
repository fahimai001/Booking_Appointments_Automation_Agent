from flask import Flask, render_template, request, jsonify
import os
import time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from src.db import setup_database, store_appointment, get_appointments_by_email
from src.helper_func import is_valid_email, is_valid_date, is_valid_time, standardize_time

load_dotenv()

setup_database()

app = Flask(__name__)

@tool
def book_appointment(name: str, email: str, date: str, time: str, purpose: str) -> str:
    """Book an appointment with the provided details."""
    if not all([name, email, date, time, purpose]):
        return "Missing required information. Please provide all details."
    if not is_valid_email(email):
        return "Invalid email address. Please provide a valid email."
    if not is_valid_date(date):
        return "Invalid date or date is in the past. Please use DD/MM/YYYY format."
    if not is_valid_time(time):
        return "Invalid time format. Please use HH:MM or H AM/PM."
    standardized_time = standardize_time(time)
    success, msg = store_appointment(name, email, date, standardized_time, purpose)
    if success:
        return f"Appointment booked successfully for {name} on {date} at {standardized_time} for {purpose}."
    else:
        return f"Failed to book appointment: {msg}"

@tool
def check_appointments(email: str) -> str:
    """Check appointments for the given email."""
    if not is_valid_email(email):
        return "Invalid email address. Please provide a valid email."
    appointments = get_appointments_by_email(email)
    if not appointments:
        return "No appointments found for this email."
    response = "**Your Appointments:**\n\n"
    for i, app in enumerate(appointments, 1):
        response += f"**Appointment {i}:**\n"
        response += f"- **Date:** {app['date']}\n"
        response += f"- **Time:** {app['time']}\n"
        response += f"- **Purpose:** {app['purpose']}\n\n"
    return response.strip()

def get_llm():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.environ["GEMINI_API_KEY"],
        temperature=0.1
    )
    return llm.bind_tools([book_appointment, check_appointments])

llm_with_tools = get_llm()

system_message = SystemMessage(content="""
You are an AI Appointment Booking Assistant. Your task is to help users book appointments or check existing appointments.

For booking an appointment:
- Collect the user's full name, email, date (DD/MM/YYYY), time, and purpose.
- Ask for each piece of information naturally, one at a time, based on what the user has already provided.
- Once all details are collected, use the book_appointment tool to store the appointment.
- Present the details back to the user for confirmation after booking.

For checking appointments:
- Ask for the user's email.
- Use the check_appointments tool to retrieve and display the appointments.

Be concise, friendly, and use emojis (📅, ⏰, 📝) to make it engaging. If the user provides irrelevant information, gently guide them back to booking or checking appointments. Do not repeat the initial greeting unless it's the first message.
""")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/message', methods=['POST'])
def process_message():
    data = request.json
    user_input = data.get('message', '')
    conversation_history = data.get('history', [])
    
    messages = [system_message]
    
    for msg in conversation_history:
        if msg['role'] == 'user':
            messages.append(HumanMessage(content=msg['content']))
        else:
            messages.append(AIMessage(content=msg['content']))
    
    messages.append(HumanMessage(content=user_input))
    
    time.sleep(0.5)
    
    response = llm_with_tools.invoke(messages)
    
    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call['name']
            tool_args = tool_call['args']
            
            if tool_name == 'book_appointment':
                result = book_appointment.invoke(tool_args)
            elif tool_name == 'check_appointments':
                result = check_appointments.invoke(tool_args)
            else:
                result = "Unknown tool."
                
            return jsonify({'content': result})
    else:
        return jsonify({'content': response.content})

if __name__ == '__main__':
    app.run(debug=True)