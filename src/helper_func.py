import sqlite3
import re
import os
import datetime
from datetime import datetime, timedelta
import dateparser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.schema import HumanMessage, AIMessage
from langchain.chains import LLMChain
from src.db import (
    insert_appointment,
    fetch_appointments,
    appointment_exists,
    fetch_table_columns,
    setup_database
)

def initialize_llm_chain():
    api_key = os.environ.get('GEMINI_API_KEY', '')
    
    if not api_key:
        raise ValueError("Google API key not found. Please set it in your environment variables.")
    
    llm = ChatGoogleGenerativeAI(
        api_key=api_key,
        model="gemini-2.0-flash"
    )
    
    prompt = ChatPromptTemplate.from_messages([
       ("system", """
        You are an appointment booking assistant. Your task is to:
        1. Help users book appointments by collecting information step-by-step.
        2. Begin by greeting the user and asking for their name.
        3. Once the name is provided, ask for their email address (this is required).
        4. After obtaining the email, ask for the appointment date.
        5. Then, ask for the appointment time.
        6. Finally, ask for the appointment_reason.
        7. Additionally, assist users in retrieving their appointment information if needed.
        8. Respond in a friendly and helpful way.

        Important: Ensure you always ask for an email address if it's not provided, as it is required for all appointments.

        - Only use information explicitly provided by the user. Do not add or assume any details that have not been given.
        - If any required information (such as name, email, date, time, or appointment_reason) is missing or ambiguous, clearly state which details are needed and ask clarifying questions.
        - Verify the validity of provided details before generating appointment records.
        - When retrieving appointment information, only reference data that has been confirmed by the user.
        - Refrain from generating extraneous or fictional details.

        When you identify appointment details, format your response with JSON-like tags:
         
        <APPOINTMENT_DETAILS>
        name: [extracted name]
        email: [extracted email]
        date: [extracted date in DD-MM-YYYY format]
        time: [extracted time in HH:MM format]
        appointment_reason: [extracted appointment_reason]
        action: [book/retrieve]
        </APPOINTMENT_DETAILS>
        
        If any required information is missing, clearly state which details are needed and do not use the JSON-like format."""),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])
    
    memory = ConversationBufferMemory(return_messages=True, input_key="input", memory_key="history")
    
    chain = LLMChain(
        llm=llm,
        prompt=prompt,
        memory=memory
    )
    
    return chain, llm

# Gets a response from the language model based on a given prompt.
def get_llm_response(llm, prompt_text):
    try:
        return llm.invoke(prompt_text).content
    except Exception as e:
        print(f"Failed to generate message with LLM: {str(e)}")
        return None

# Extracts appointment details from the model's response.
def parse_appointment_details(response_text):
    details_pattern = r'<APPOINTMENT_DETAILS>(.*?)</APPOINTMENT_DETAILS>'
    match = re.search(details_pattern, response_text, re.DOTALL)
    
    if not match:
        return None, response_text.strip()
    
    details_text = match.group(1).strip()
    details = {}
    
    name_extraction = re.search(r'name:\s*(.*)', details_text)
    email_extraction = re.search(r'email:\s*(.*)', details_text)
    date_extraction = re.search(r'date:\s*(.*)', details_text)
    time_extraction = re.search(r'time:\s*(.*)', details_text)
    reason_extraction = re.search(r'appointment_reason:\s*(.*)', details_text)
    action_extraction = re.search(r'action:\s*(.*)', details_text)
    
    if name_extraction:
        details['name'] = name_extraction.group(1).strip()
    if email_extraction:
        details['email'] = email_extraction.group(1).strip()
    if date_extraction:
        date_str = date_extraction.group(1).strip()
        parsed_date = dateparser.parse(date_str)
        if parsed_date:
            details['date'] = parsed_date.strftime('%Y-%m-%d')
        else:
            details['date'] = date_str
    if time_extraction:
        time_str = time_extraction.group(1).strip()
        if ':' not in time_str:
            try:
                hour = int(time_str)
                time_str = f"{hour:02d}:00"
            except ValueError:
                pass
        details['time'] = time_str
    if reason_extraction:
        details['appointment_reason'] = reason_extraction.group(1).strip()
    if action_extraction:
        details['action'] = action_extraction.group(1).strip()

    clean_response = re.sub(details_pattern, '', response_text, flags=re.DOTALL).strip()
    
    return details, clean_response

def validate_email_format(email):
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))

# Handles user input and manages the appointment booking process.
def process_chat_message(user_input, llm_chain, llm, session_data=None):
    try:
        current_name = None
        current_email = None
        
        if session_data:
            current_name = session_data.get('current_name')
            current_email = session_data.get('current_email')
        
        llm_response = llm_chain.invoke({"input": user_input})
        response_text = llm_response["text"]
        
        details, clean_response = parse_appointment_details(response_text)
        
        if not details:
            return clean_response
        
        if details.get('action') == 'book':
            if not details.get('name'):
                details['name'] = current_name or ''
            if not details.get('email'):
                details['email'] = current_email or ''
            
            missing = []
            if not details.get('name'):
                missing.append("name")
            if not details.get('email'):
                missing.append("email")
            elif not validate_email_format(details.get('email')):
                return f"{clean_response}\n\nThe email address provided doesn't seem to be valid. Please provide a valid email address."
            if not details.get('date'):
                missing.append("date")
            if not details.get('time'):
                missing.append("time")
                
            if missing:
                return f"{clean_response}\n\nI still need your {', '.join(missing)} to book the appointment."
            
            if appointment_exists(details['name'], details['email'], details['date'], details['time']):
                return f"You already have an appointment on {details['date']} at {details['time']}. Would you like to book a different time?"
            
            appointment_reason = details.get('appointment_reason', 'General appointment')
            insert_appointment(details['name'], details['email'], details['date'], details['time'], appointment_reason)
            
            prompt = f"""
            Based on our conversation, I've booked an appointment with the following details:
            - Name: {details['name']}
            - Email: {details['email']}
            - Date: {details['date']}
            - Time: {details['time']}
            - Appointment_reason: {details.get('appointment_reason', 'General appointment')}
            
            Please format this information in a friendly, easy-to-read way to present back to the user.
            """
            
            confirmation = get_llm_response(llm, prompt)
            if confirmation:
                return f"{clean_response}\n\n{confirmation}"
            return f"{clean_response}\n\nGreat! I've booked your appointment for {details['date']} at {details['time']}."
        
        elif details.get('action') == 'retrieve':
            name = details.get('name') or current_name or ''
            email = details.get('email') or current_email or ''
            date = details.get('date')
            
            if not name and not email:
                return f"{clean_response}\n\nPlease provide your name or email so I can check your appointments."
            
            appointments = fetch_appointments(name, email, date)
            
            return display_formatted_appointments(appointments, clean_response, llm)
            
        return clean_response
    
    except Exception as e:
        return f"Error processing message: {str(e)}\n\nPlease try again or restart the application."

def display_formatted_appointments(appointments, clean_response, llm):
    if not appointments:
        return f"{clean_response}\n\nYou don't have any appointments scheduled."
    
    appointments_info = []
    columns = fetch_table_columns()
    
    for appt in appointments:
        appt_dict = {columns[i]: appt[i] for i in range(len(appt)) if i < len(columns)}
        appointments_info.append({
            'date': appt_dict.get('date', 'N/A'),
            'time': appt_dict.get('time', 'N/A'),
            'name': appt_dict.get('name', 'N/A'),
            'email': appt_dict.get('email', 'N/A'),
            'appointment_reason': appt_dict.get('appointment_reason', 'N/A')
        })
    
    appointments_text = "\n".join([
    f"Appointment {i+1}:\n"
    f"- Date: {appt['date']}\n"
    f"- Time: {appt['time']}\n"
    f"- Name: {appt['name']}\n"
    f"- Email: {appt['email']}\n"
    f"- Reason: {appt['appointment_reason']}"
    for i, appt in enumerate(appointments_info)
])

    
    appointments_prompt = f"""
    The user has requested their appointment details.  

    Below are the appointments retrieved from our system:  

    {appointments_text}  

    Please present this information in a clear, concise, and user-friendly format.
"""

    
    formatted_appointments = get_llm_response(llm, appointments_prompt)
    
    if formatted_appointments:
        return f"{clean_response}\n\n{formatted_appointments}"
    return f"{clean_response}\n\nHere are your appointments:\n\n{appointments_text}"

# Call setup_database() at the start of your application to ensure the database is ready.
setup_database()