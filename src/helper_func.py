import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_message_histories import ChatMessageHistory
import dateparser
from src.db_manager import DatabaseManager

db = DatabaseManager()

def load_api_key():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not found. Please set it in your .env file.")
    return api_key

def get_llm(api_key):
    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model="gemini-2.0-flash",
        convert_system_message_to_human=True
    )

def get_appointment_patterns():
    return {
        "user_name": r"(?:name[:\s]+)([A-Za-z\s]+)|(?:my name is\s+)([A-Za-z\s]+)|(?:i am\s+)([A-Za-z\s]+)|(?:This is\s+)([A-Za-z\s]+)",
        "date": r"(?:date[:\s]+)([A-Za-z0-9\s,]+)|(?:on\s+)([A-Za-z0-9\s,]+)|(?:for\s+)([A-Za-z0-9\s,]+\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b[A-Za-z0-9\s,]+)",
        "time": r"(?:time[:\s]+)([0-9:]+\s*(?:AM|PM|am|pm)?)|(?:at\s+)([0-9:]+\s*(?:AM|PM|am|pm)?)",
        "email": r"(?:email[:\s]+)([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)|([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
        "appointment_type": r"(?:appointment_type[:\s]+)(Data Science|AI\/ML|Application Development|Database Development)|(?:for\s+)(Data Science|AI\/ML|Application Development|Database Development)|(?:regarding\s+)(Data Science|AI\/ML|Application Development|Database Development)"
    }

def get_system_prompt():
    return """
You are an expert and helpful appointment booking assistant. Your responsibility is to Book Appointment with "Sabir".

Extract relevant details from the user's prompt. You should collect information sequentially if not provided all at once:
1. user_name - Ask for their name if not provided
2. date - Ask for their preferred date if not provided
3. time - Ask for their preferred time if not provided
4. email - Ask for their email address if not provided
5. appointment_type - Ask them to choose from: Data Science, AI/ML, Application Development, Database Development

Once all details are collected, confirm the appointment details with the user and respond with a nice confirmation message.

If a user asks about their appointment, provide details from the database in a friendly manner.

Remember to only book appointments with Sabir who specializes in Data Science, AI/ML, Application Development, and Database Development.

Be conversational and friendly. If the user asks questions about Sabir's expertise, offer brief information about the services.
"""

def create_prompt_template():
    return ChatPromptTemplate.from_messages([
        ("system", get_system_prompt()),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

def extract_appointment_details(user_input):
    appointment_details = {}
    appointment_pattern = get_appointment_patterns()
    
    for field, pattern in appointment_pattern.items():
        match = re.search(pattern, user_input, re.IGNORECASE)
        if match:
            caught_group = next((g for g in match.groups() if g is not None), None)
            if caught_group:
                appointment_details[field] = caught_group.strip()
    
    if "date" not in appointment_details:
        try:
            parsed_date = dateparser.parse(user_input, settings={'PREFER_DATES_FROM': 'future'})
            if parsed_date:
                appointment_details["date"] = parsed_date.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"Date parsing error: {e}")
    
    return appointment_details

def extract_date_reference(user_input):
    today = datetime.now()
    
    if "today" in user_input.lower():
        return today.strftime("%Y-%m-%d")
    elif "tomorrow" in user_input.lower():
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "next week" in user_input.lower():
        return (today + timedelta(days=7)).strftime("%Y-%m-%d")
    elif "day after tomorrow" in user_input.lower():
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")
    
    try:
        parsed_date = dateparser.parse(user_input, settings={'PREFER_DATES_FROM': 'future'})
        if parsed_date:
            return parsed_date.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Date reference extraction error: {e}")
    
    return None

def format_time(time_str):
    try:
        time_str = time_str.strip().lower()
        
        formats = [
            "%I:%M %p",
            "%I:%M%p",
            "%H:%M",
            "%I %p"
        ]
        
        for fmt in formats:
            try:
                time_obj = datetime.strptime(time_str, fmt)
                return time_obj.strftime("%H:%M")
            except ValueError:
                continue
        
        if ":" not in time_str:
            match = re.match(r"(\d+)\s*(am|pm)", time_str)
            if match:
                hour, meridiem = match.groups()
                hour = int(hour)
                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
                return f"{hour:02d}:00"
        
        parsed_time = dateparser.parse(time_str)
        if parsed_time:
            return parsed_time.strftime("%H:%M")
            
        return time_str
    except Exception as e:
        print(f"Error formatting time: {e}")
        return time_str

def save_appointment(details, message_history):
    if not details:
        return None, "No appointment details found to save."
    
    print(f"Saving appointment with details: {details}")
    
    required_fields = ["user_name", "date", "time", "email", "appointment_type"]
    missing = [f for f in required_fields if f not in details]
    if missing:
        return None, f"Missing required fields: {', '.join(missing)}"
    
    if 'time' in details:
        try:
            details['time'] = format_time(details['time'])
        except Exception as e:
            print(f"Error formatting time: {e}")
    
    if 'date' in details:
        try:
            if not re.match(r'\d{4}-\d{2}-\d{2}', details['date']):
                parsed_date = dateparser.parse(details['date'], settings={'PREFER_DATES_FROM': 'future'})
                if parsed_date:
                    details['date'] = parsed_date.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"Error formatting date: {e}")
    
    try:
        if db.conn is None or db.cursor is None:
            db.connect()
            
        success, message = db.save_appointment(details)
        
        if success:
            appointment_str = "APPOINTMENT_DETAILS: " + ", ".join([f"{k}: {v}" for k, v in details.items()])
            message_history.add_user_message("Save my appointment")
            message_history.add_ai_message(appointment_str)
            saved_appts = db.get_appointments(email=details['email'])
            print(f"After save: Found {len(saved_appts)} appointments for {details['email']}")
            return details, message
        else:
            print(f"Database error: {message}")
            return None, message
    except Exception as e:
        error_msg = f"Exception during appointment save: {str(e)}"
        print(error_msg)
        return None, error_msg

def has_all_required_details(details):
    required_fields = ["user_name", "date", "time", "email", "appointment_type"]
    return all(field in details for field in required_fields)

def retrieve_appointments(message_history, query=None):
    def extract_email_from_text(text):
        if not text:
            return None
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        match = re.search(email_pattern, text)
        if match:
            return match.group(0)
        return None
    
    email = extract_email_from_text(query) if query else None
    date_ref = extract_date_reference(query) if query else None
    
    is_next_appointment_query = query and any(word in query.lower() for word in ["next", "upcoming"])
    
    if is_next_appointment_query:
        next_appointment = db.get_next_appointment(email)
        if next_appointment:
            return f"""Your next appointment is:
- Name: {next_appointment['user_name']}
- Date: {next_appointment['date']}
- Time: {next_appointment['time']}
- Type: {next_appointment['appointment_type']}"""
        else:
            return "You don't have any upcoming appointments."
    
    elif date_ref:
        appointments = db.get_appointments(email=email, date=date_ref)
        if appointments:
            result = f"Here are your appointments for {date_ref}:\n"
            for i, appointment in enumerate(appointments, 1):
                result += f"""
{i}. Appointment with Sabir:
   - Name: {appointment['user_name']}
   - Time: {appointment['time']}
   - Type: {appointment['appointment_type']}"""
            return result
        else:
            return f"You don't have any appointments scheduled for {date_ref}."
    
    else:
        appointments = db.get_appointments(email=email)
        if appointments:
            result = "Here are all your appointments:\n"
            for i, appointment in enumerate(appointments, 1):
                result += f"""
{i}. Appointment on {appointment['date']} at {appointment['time']}:
   - Name: {appointment['user_name']}
   - Type: {appointment['appointment_type']}"""
            return result
        else:
            friendly_message = "I couldn't find any appointments for you. Would you like to schedule one now?"
            return friendly_message
    
    appointments = []
    messages = message_history.messages
    
    for message in messages:
        if hasattr(message, 'content') and "APPOINTMENT_DETAILS:" in message.content:
            appointment_info = message.content.split("APPOINTMENT_DETAILS:")[1].strip()
            appointments.append(appointment_info)
    
    if not appointments:
        return "No appointments found."
    
    return "Here are your appointments from history:\n" + "\n".join(appointments)

def is_booking_request(user_input):
    booking_keywords = ["book", "schedule", "make", "set", "create", "arrange", "appointment", "new appointment"]
    return any(keyword in user_input.lower() for keyword in booking_keywords)

def is_retrieval_request(user_input):
    retrieval_keywords = ["show", "get", "find", "view", "check", "see", "tell", "when is", "do i have", "my appointment"]
    appointment_keywords = ["appointment", "schedule", "booking"]
    
    has_retrieval = any(keyword in user_input.lower() for keyword in retrieval_keywords)
    has_appointment = any(keyword in user_input.lower() for keyword in appointment_keywords)
    
    return has_retrieval and has_appointment or "next appointment" in user_input.lower()

def get_next_question(details):
    if "user_name" not in details:
        return "Could you please tell me your name?"
    elif "date" not in details:
        return "On what date would you like to schedule your appointment with Sabir?"
    elif "time" not in details:
        return "What time would work best for you? Sabir is available from 9 AM to 5 PM."
    elif "email" not in details:
        return "Please provide your email address for the appointment confirmation."
    elif "appointment_type" not in details:
        return "What type of service are you interested in? Sabir specializes in: Data Science, AI/ML, Application Development, or Database Development."
    else:
        return None

def process_user_input(user_input, message_history, current_details, collecting_info, llm):
    new_details = extract_appointment_details(user_input)
    
    current_details.update(new_details)
    
    print(f"Current appointment details: {current_details}")
    
    if is_booking_request(user_input) or collecting_info:
        collecting_info = True
        
        if has_all_required_details(current_details):
            print("All required details collected, saving appointment...")
            
            if 'date' in current_details and not re.match(r'\d{4}-\d{2}-\d{2}', current_details['date']):
                try:
                    parsed_date = dateparser.parse(current_details['date'], settings={'PREFER_DATES_FROM': 'future'})
                    if parsed_date:
                        current_details['date'] = parsed_date.strftime("%Y-%m-%d")
                        print(f"Formatted date: {current_details['date']}")
                except Exception as e:
                    print(f"Error formatting date: {e}")
            
            if 'time' in current_details:
                try:
                    current_details['time'] = format_time(current_details['time'])
                    print(f"Formatted time: {current_details['time']}")
                except Exception as e:
                    print(f"Error formatting time: {e}")
            
            saved_details, message = save_appointment(current_details, message_history)
            
            if saved_details:
                confirmation = f"""
Great! I've booked your appointment with Sabir.

Appointment Details:
- Name: {current_details['user_name']}
- Date: {current_details['date']}
- Time: {current_details['time']}
- Email: {current_details['email']}
- Service: {current_details['appointment_type']}

Thank you for scheduling with us. You will receive a confirmation email shortly.
Is there anything else I can help you with?
"""
                message_history.add_user_message(user_input)
                message_history.add_ai_message(confirmation)
                
                return confirmation, {}, False
            else:
                error_msg = f"I'm sorry, there was an issue saving your appointment: {message}. Please try again."
                message_history.add_user_message(user_input)
                message_history.add_ai_message(error_msg)
                return error_msg, current_details, False
        else:
            next_question = get_next_question(current_details)
            message_history.add_user_message(user_input)
            message_history.add_ai_message(next_question)
            return next_question, current_details, True
    
    elif is_retrieval_request(user_input):
        response = retrieve_appointments(message_history, user_input)
        message_history.add_user_message(user_input)
        message_history.add_ai_message(response)
        return response, current_details, collecting_info
    
    else:
        chain = create_prompt_template() | llm | StrOutputParser()
        chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: message_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        
        response = chain_with_history.invoke(
            {"input": user_input},
            config={"configurable": {"session_id": "streamlit_session"}}
        )
        
        return response, current_details, collecting_info