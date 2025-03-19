import re
import os
from datetime import datetime, timedelta
import dateparser

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain

from src.db import (
    insert_appointment,
    fetch_appointments,
    appointment_exists,
    fetch_table_columns,
    setup_database
)

def setup_llm_chain():
    """
    Initializes the LLM chain with the Gemini API key and a conversation prompt.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Google API key not found. Please set GEMINI_API_KEY in your environment.")
    
    llm = ChatGoogleGenerativeAI(api_key=api_key, model="gemini-2.0-flash")
    
    system_instructions = """
    You are an appointment booking assistant. Your tasks include:
      1. Greeting the user and asking for their name.
      2. Requesting an email address (mandatory).
      3. Asking for the appointment date.
      4. Asking for the appointment time.
      5. Asking for the appointment_reason.
      6. Assisting users in retrieving their appointment details if needed.
    
    Note:
      - Only use information provided explicitly by the user.
      - If any required information (name, email, date, time, or appointment_reason) is missing, clearly indicate what’s needed.
      - Validate all details before confirming appointments.
      - Format appointment details using JSON-like tags as follows:
    
    <APPOINTMENT_DETAILS>
    name: [extracted name]
    email: [extracted email]
    date: [extracted date in DD-MM-YYYY format]
    time: [extracted time in HH:MM format]
    appointment_reason: [extracted appointment_reason]
    action: [book/retrieve]
    </APPOINTMENT_DETAILS>
    
    If required details are missing, do not use the JSON format but instead ask clarifying questions.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instructions),
        MessagesPlaceholder(variable_name="conversation_history"),
        ("human", "{input}")
    ])
    
    memory = ConversationBufferMemory(return_messages=True, input_key="input", memory_key="conversation_history")
    
    chain = LLMChain(llm=llm, prompt=prompt, memory=memory)
    return chain, llm

def fetch_response_from_llm(llm, prompt_text: str) -> str:
    """
    Gets a response from the LLM using the provided prompt text.
    """
    try:
        response = llm.invoke(prompt_text)
        return response.content
    except Exception as ex:
        print(f"Error generating LLM response: {ex}")
        return None

def extract_appointment_details(response_text: str):
    """
    Extracts appointment details from the LLM response.
    Returns a tuple: (details_dict, cleaned_response_text).
    """
    details_pattern = r'<APPOINTMENT_DETAILS>(.*?)</APPOINTMENT_DETAILS>'
    match = re.search(details_pattern, response_text, re.DOTALL)
    if not match:
        return None, response_text.strip()
    
    raw_details = match.group(1).strip()
    details = {}
    
    for key in ["name", "email", "date", "time", "appointment_reason", "action"]:
        regex = rf'{key}:\s*(.*)'
        found = re.search(regex, raw_details)
        if found:
            value = found.group(1).strip()
            if key == "date":
                parsed = dateparser.parse(value)
                details["date"] = parsed.strftime('%Y-%m-%d') if parsed else value
            elif key == "time":
                
                if ':' not in value:
                    try:
                        hour = int(value)
                        value = f"{hour:02d}:00"
                    except ValueError:
                        pass
                details["time"] = value
            else:
                details[key] = value
    
    cleaned_text = re.sub(details_pattern, '', response_text, flags=re.DOTALL).strip()
    return details, cleaned_text

def is_valid_email(email: str) -> bool:
    """
    Checks whether the provided email matches the standard email format.
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def handle_chat_message(user_input: str, llm_chain, llm, session_context: dict = None) -> str:
    """
    Processes the user message, handling both appointment booking and retrieval.
    """
    current_name = session_context.get("current_name") if session_context else ""
    current_email = session_context.get("current_email") if session_context else ""
    
    llm_output = llm_chain.invoke({"input": user_input})
    response_text = llm_output.get("text", "")
    
    details, cleaned_response = extract_appointment_details(response_text)
    if not details:
        return cleaned_response
    
    if details.get("action") == "book":
        details.setdefault("name", current_name)
        details.setdefault("email", current_email)
        
        missing_fields = []
        for field in ["name", "email", "date", "time"]:
            if not details.get(field):
                missing_fields.append(field)
        
        if details.get("email") and not is_valid_email(details["email"]):
            return f"{cleaned_response}\n\nThe email provided is invalid. Please enter a valid email address."
        
        if missing_fields:
            return f"{cleaned_response}\n\nI still need the following details: {', '.join(missing_fields)}."
        
        if appointment_exists(details["name"], details["email"], details["date"], details["time"]):
            return f"You already have an appointment on {details['date']} at {details['time']}. Would you like to choose another time?"
        
        reason = details.get("appointment_reason", "General appointment")
        insert_appointment(details["name"], details["email"], details["date"], details["time"], reason)
        
        confirmation_prompt = f"""
        I have booked an appointment with these details:
        - Name: {details['name']}
        - Email: {details['email']}
        - Date: {details['date']}
        - Time: {details['time']}
        - Reason: {reason}
        
        Please format this information in a friendly, clear manner for the user.
        """
        confirmation = fetch_response_from_llm(llm, confirmation_prompt)
        if confirmation:
            return f"{cleaned_response}\n\n{confirmation}"
        return f"{cleaned_response}\n\nYour appointment is confirmed for {details['date']} at {details['time']}."
    
    elif details.get("action") == "retrieve":
        name = details.get("name") or current_name
        email = details.get("email") or current_email
        date_filter = details.get("date")
        
        if not name and not email:
            return f"{cleaned_response}\n\nPlease provide your name or email so I can retrieve your appointments."
        
        appointments = fetch_appointments(name, email, date_filter)
        return format_appointment_display(appointments, cleaned_response, llm)
    
    return cleaned_response

def format_appointment_display(appointments, cleaned_response: str, llm) -> str:
    """
    Formats and returns appointment information for the user.
    """
    if not appointments:
        return f"{cleaned_response}\n\nNo appointments found."
    
    columns = fetch_table_columns()
    formatted_entries = []
    for idx, appt in enumerate(appointments):
        record = {columns[i]: appt[i] for i in range(len(appt)) if i < len(columns)}
        formatted_entries.append(
            f"Appointment {idx + 1}:\n"
            f" - Date: {record.get('date', 'N/A')}\n"
            f" - Time: {record.get('time', 'N/A')}\n"
            f" - Name: {record.get('name', 'N/A')}\n"
            f" - Email: {record.get('email', 'N/A')}\n"
            f" - Reason: {record.get('appointment_reason', 'N/A')}"
        )
    appointments_text = "\n".join(formatted_entries)
    
    display_prompt = f"""
    The user requested their appointment details. Here are the retrieved appointments:
    
    {appointments_text}
    
    Please reformat this information into a clear and friendly message.
    """
    formatted_output = fetch_response_from_llm(llm, display_prompt)
    if formatted_output:
        return f"{cleaned_response}\n\n{formatted_output}"
    return f"{cleaned_response}\n\n{appointments_text}"

if __name__ == "__main__":
    
    setup_database()
   
    llm_chain, llm = setup_llm_chain()
   
