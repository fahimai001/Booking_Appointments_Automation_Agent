import os
import streamlit as st
from langchain_community.chat_message_histories import ChatMessageHistory
import pandas as pd
import re
from datetime import datetime
import logging
import time

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

from src.helper_func import (
    load_api_key,
    get_llm,
    process_user_input,
    retrieve_appointments
)
from src.db_manager import DatabaseManager

def extract_email(text):
    if not text:
        return None
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    match = re.search(email_pattern, text)
    if match:
        return match.group(0)
    return None

st.set_page_config(
    page_title="Appointment Booking Assistant", 
    page_icon="📅",
    layout="wide"
)

st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .chat-message.user {
        background-color: #e6f3ff;
        border-left: 5px solid #2196F3;
    }
    .chat-message.assistant {
        background-color: #f0f0f0;
        border-left: 5px solid #9e9e9e;
    }
    .chat-header {
        margin-bottom: 10px;
        font-weight: bold;
    }
    .chat-time {
        font-size: 0.8rem;
        color: #666;
    }
    .st-emotion-cache-16txtl3 h1 {
        text-align: center;
        margin-bottom: 30px;
    }
    .appointment-card {
        background-color: #f9f9f9;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

st.title("📅 Appointment Booking Assistant")

if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()

with st.sidebar:
    debug_expander = st.expander("Debug Info (Developer Only)", expanded=False)
    with debug_expander:
        st.write("Database Status:")
        
        if st.button("Check Database Connection"):
            try:
                st.session_state.db.cursor.execute("SELECT COUNT(*) FROM appointments")
                count = st.session_state.db.cursor.fetchone()[0]
                st.success(f"Database connection successful. Found {count} appointments.")
            except Exception as e:
                st.error(f"Database error: {str(e)}")
        
        if st.button("Show Database Path"):
            st.info(f"Database path: {os.path.abspath(st.session_state.db.db_path)}")
        
        if st.button("List All Appointments (Debug)"):
            try:
                all_appointments = st.session_state.db.get_all_appointments()
                if all_appointments:
                    st.success(f"Found {len(all_appointments)} total appointments")
                    for i, appt in enumerate(all_appointments, 1):
                        st.markdown(f"""
                        **Appointment {i}:**
                        - ID: {appt['id']}
                        - Name: {appt['user_name']}
                        - Email: {appt['email']}
                        - Date: {appt['date']}
                        - Time: {appt['time']}
                        - Type: {appt['appointment_type']}
                        """)
                else:
                    st.warning("No appointments found in database")
            except Exception as e:
                st.error(f"Error listing appointments: {str(e)}")
        
        if st.button("Reset Database"):
            try:
                st.session_state.db.cursor.execute("DELETE FROM appointments")
                st.session_state.db.conn.commit()
                st.success("Database reset successfully")
            except Exception as e:
                st.error(f"Error resetting database: {str(e)}")

with st.sidebar:
    st.header("View Your Appointments")
    email_input = st.text_input("Enter your email to view appointments:", key="view_email")
    
    if st.button("View All Appointments"):
        if email_input:
            logger.info(f"Viewing appointments for email: {email_input}")
            try:
                st.session_state.db = DatabaseManager()
                appointments = st.session_state.db.get_appointments(email=email_input)
                if appointments:
                    st.success(f"Found {len(appointments)} appointment(s)")
                    for appt in appointments:
                        st.markdown(f"""
                        <div class="appointment-card">
                            <div><strong>Name:</strong> {appt['user_name']}</div>
                            <div><strong>Date:</strong> {appt['date']}</div>
                            <div><strong>Time:</strong> {appt['time']}</div>
                            <div><strong>Service:</strong> {appt['appointment_type']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("No appointments found for this email address.")
                    logger.warning(f"No appointments found for email: {email_input}")
            except Exception as e:
                st.error(f"Error retrieving appointments: {str(e)}")
                logger.error(f"Error retrieving appointments: {str(e)}", exc_info=True)
        else:
            st.warning("Please enter an email address to view appointments.")
    
    if st.button("View Next Appointment"):
        if email_input:
            logger.info(f"Viewing next appointment for email: {email_input}")
            try:
                st.session_state.db = DatabaseManager()
                next_appointment = st.session_state.db.get_next_appointment(email=email_input)
                if next_appointment:
                    st.success("Here's your next appointment:")
                    st.markdown(f"""
                    <div class="appointment-card">
                        <div><strong>Name:</strong> {next_appointment['user_name']}</div>
                        <div><strong>Date:</strong> {next_appointment['date']}</div>
                        <div><strong>Time:</strong> {next_appointment['time']}</div>
                        <div><strong>Service:</strong> {next_appointment['appointment_type']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("No upcoming appointments found.")
                    logger.warning(f"No upcoming appointments found for email: {email_input}")
            except Exception as e:
                st.error(f"Error retrieving next appointment: {str(e)}")
                logger.error(f"Error retrieving next appointment: {str(e)}", exc_info=True)
        else:
            st.warning("Please enter an email address to view appointments.")
    
    st.divider()
    st.markdown("### About Sabir's Services")
    st.markdown("""
    Sabir specializes in:
    - **Data Science**: Data analysis, visualization, and machine learning
    - **AI/ML**: Custom AI solutions and ML model development
    - **Application Development**: Web and mobile app development
    - **Database Development**: Database design, optimization, and management
    """)

if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'message_history' not in st.session_state:
    st.session_state.message_history = ChatMessageHistory()

if 'current_details' not in st.session_state:
    st.session_state.current_details = {}

if 'collecting_info' not in st.session_state:
    st.session_state.collecting_info = False

if 'api_key' not in st.session_state:
    try:
        st.session_state.api_key = load_api_key()
        logger.info("API key loaded successfully")
    except ValueError as e:
        st.error(f"API Key Error: {str(e)}")
        logger.error(f"API Key Error: {str(e)}")
        st.session_state.api_key = None

if 'llm' not in st.session_state and st.session_state.api_key:
    try:
        st.session_state.llm = get_llm(st.session_state.api_key)
        logger.info("LLM initialized successfully")
    except Exception as e:
        st.error(f"LLM Initialization Error: {str(e)}")
        logger.error(f"LLM Initialization Error: {str(e)}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

def display_welcome_message():
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.write("""
            👋 Hello! I'm your appointment booking assistant. I can help you:
            
            - Schedule an appointment with Sabir
            - Check your existing appointments
            - Answer questions about Sabir's services
            
            How can I assist you today?
            """)

display_welcome_message()

if prompt := st.chat_input("Type your message here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.write(prompt)
    
    with st.spinner("Thinking..."):
        if st.session_state.api_key:
            try:
                logger.info(f"Processing user input: {prompt}")
                
                time.sleep(0.5)
                
                response, updated_details, collecting_info = process_user_input(
                    prompt,
                    st.session_state.message_history,
                    st.session_state.current_details,
                    st.session_state.collecting_info,
                    st.session_state.llm
                )
                
                st.session_state.current_details = updated_details
                st.session_state.collecting_info = collecting_info
                
                logger.info(f"Updated appointment details: {st.session_state.current_details}")
                logger.info(f"Collecting info state: {st.session_state.collecting_info}")
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                
                with st.chat_message("assistant"):
                    st.write(response)
            except Exception as e:
                error_msg = f"An error occurred: {str(e)}"
                st.error(error_msg)
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
        else:
            st.error("API key is not set. Please check your .env file.")
            logger.error("API key is not set")
            
with st.expander("Reset Conversation"):
    if st.button("Clear Chat History"):
        logger.info("Clearing chat history")
        st.session_state.messages = []
        st.session_state.message_history = ChatMessageHistory()
        st.session_state.current_details = {}
        st.session_state.collecting_info = False
        st.rerun()

with st.sidebar:
    details_expander = st.expander("Current Appointment Details", expanded=False)
    with details_expander:
        st.write("Current appointment details being collected:")
        st.write(st.session_state.current_details)
        st.write(f"Collecting info state: {st.session_state.collecting_info}")

st.markdown("""
<div style="text-align: center; margin-top: 30px; padding: 10px; color: #666;">
    <p>© 2025 Appointment Booking Assistant | Built with Streamlit</p>
</div>
""", unsafe_allow_html=True)