from flask import Flask, render_template, request, jsonify
import os
from src.db import setup_database, store_appointment, get_appointments_by_email, is_duplicate_appointment
from src.helper_func import (
    extract_email, has_booking_intent, has_checking_intent,
    is_valid_date, is_valid_time, standardize_time,
    get_llm_response, format_appointment_details, validate_booking_info
)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat_api():
    data = request.json
    user_input = data.get('message', '')
    state = data.get('state', 'choosing')
    booking_info = data.get('booking_info', {})
    
    response = process_chat(user_input, state, booking_info)
    return jsonify(response)

def process_chat(user_input, state, booking_info=None):
    if booking_info is None:
        booking_info = {}
        
    result = {
        'message': '',
        'state': state,
        'booking_info': booking_info,
        'appointments': None
    }
    
    if user_input.lower() in ["exit", "quit", "bye"]:
        result['message'] = get_llm_response("farewell", user_input)
        return result
    
    # For unclear inputs or more complex cases, use the LLM
    if user_input.strip() and len(user_input.split()) > 3:
        # Check if we should use rule-based logic or LLM
        use_llm = not (
            (state == "choosing" and (has_booking_intent(user_input) or has_checking_intent(user_input))) or
            (state == "booking_email" and extract_email(user_input)) or
            (state in ["booking_name", "booking_date", "booking_time", "booking_purpose"] and user_input.strip())
        )
        
        if use_llm:
            result['message'] = get_llm_response(state, user_input, booking_info)
            # Check if we should still process with rule-based logic
            if "I'll help you book" in result['message'] and state == "choosing":
                result['state'] = "booking_name"
            elif "I'll help you check" in result['message'] and state == "choosing":
                result['state'] = "checking_email"
            return result
    
    # State machine to handle the conversation flow
    if state == "choosing":
        if has_booking_intent(user_input):
            result['state'] = "booking_name"
            result['message'] = "Let's book your appointment. What's your name?"
        elif has_checking_intent(user_input) or user_input.strip() == "2":
            result['state'] = "checking_email"
            result['message'] = "I'll help you check your appointments. Please provide your email address."
        else:
            # Use LLM for unclear intent
            result['message'] = get_llm_response("unclear_intent", user_input)
    
    elif state == "booking_name":
        if user_input.strip():
            booking_info["name"] = user_input.strip()
            result['state'] = "booking_email"
            result['booking_info'] = booking_info
            result['message'] = "Great! Now, what's your email address?"
        else:
            result['message'] = "I need your name to proceed. Please provide your name."
    
    elif state == "booking_email":
        email = extract_email(user_input)
        if email:
            booking_info["email"] = email
            result['state'] = "booking_date"
            result['booking_info'] = booking_info
            result['message'] = "Perfect! For which date would you like to book the appointment? (e.g., 25/04/2025)"
        else:
            result['message'] = "I couldn't detect a valid email address. Please provide a valid email (e.g., example@domain.com)."
    
    elif state == "booking_date":
        date_input = user_input.strip()
        if is_valid_date(date_input):
            booking_info["date"] = date_input
            result['state'] = "booking_time"
            result['booking_info'] = booking_info
            result['message'] = "What time would you prefer for your appointment? (e.g., 14:30 or 2:30 PM)"
        else:
            result['message'] = "Please provide a valid date format (e.g., 25/04/2025, 2025-04-25). Make sure the date is not in the past."
    
    elif state == "booking_time":
        time_input = user_input.strip()
        if is_valid_time(time_input):
            # Standardize time format for storage
            booking_info["time"] = standardize_time(time_input)
            result['state'] = "booking_purpose"
            result['booking_info'] = booking_info
            result['message'] = "What's the purpose of your appointment?"
        else:
            result['message'] = "Please provide a valid time format (e.g., 14:30, 2:30 PM, or 2PM)."
    
    elif state == "booking_purpose":
        if user_input.strip():
            booking_info["purpose"] = user_input.strip()
            result['booking_info'] = booking_info
            
            # Final validation of all booking info
            missing_fields, invalid_fields = validate_booking_info(booking_info)
            
            if missing_fields:
                missing_str = ", ".join(missing_fields)
                result['message'] = f"There are missing fields in your booking: {missing_str}. Let's fill these in."
                result['state'] = f"booking_{missing_fields[0]}"
                result['message'] += f" Please provide your {missing_fields[0]}:"
                return result
            
            if invalid_fields:
                invalid_str = ", ".join(invalid_fields)
                result['message'] = f"There are invalid fields in your booking: {invalid_str}. Let's correct these."
                result['state'] = f"booking_{invalid_fields[0]}"
                result['message'] += f" Please provide a valid {invalid_fields[0]}:"
                return result
            
            # Store appointment in database
            success, message = store_appointment(
                booking_info["name"],
                booking_info["email"],
                booking_info["date"],
                booking_info["time"],
                booking_info["purpose"]
            )
            
            if success:
                # Format appointment details
                details = format_appointment_details(booking_info)
                result['message'] = f"Your appointment has been successfully booked! 🎉\n{details}\n\nWhat would you like to do next?\n\n1. Book another appointment\n2. Check your appointments"
                result['state'] = "choosing"
                # Reset booking info
                result['booking_info'] = {}
            elif message == "duplicate":
                result['message'] = f"It appears you already have an appointment scheduled for {booking_info['date']} at {booking_info['time']}.\n\nWould you like to:\n1. Choose a different date or time\n2. Check your existing appointments\n3. Start over with a new booking"
                result['state'] = "handling_duplicate"
            else:
                # Use LLM for error message
                result['message'] = get_llm_response("booking_error", message, booking_info)
                result['state'] = "choosing"
                result['booking_info'] = {}
        else:
            result['message'] = "I need to know the purpose of your appointment. Please briefly describe why you're scheduling this appointment."
    
    elif state == "handling_duplicate":
        if "1" in user_input or "different" in user_input.lower():
            result['state'] = "booking_date"
            result['message'] = "Let's choose a different date. For which date would you like to book the appointment? (e.g., 25/04/2025)"
        elif "2" in user_input or "check" in user_input.lower():
            appointments = get_appointments_by_email(email)
            result['appointments'] = appointments
            result['message'] = f"Here are your existing appointments for {booking_info['email']}:"
            result['state'] = "choosing"
            result['booking_info'] = {}
        else:  # Option 3 or default
            result['booking_info'] = {}
            result['state'] = "choosing"
            result['message'] = "What would you like to do next?\n\n1. Book a new appointment\n2. Check your appointments"
    
    elif state == "checking_email":
        # Try to extract email directly or use the input as is if it looks like an email
        email = extract_email(user_input)
        if not email and '@' in user_input and '.' in user_input:
            email = user_input.strip()
            
        if email:
            # Debug print for server-side verification
            print(f"Checking appointments for email: {email}")
            
            # Get appointments from database
            appointments = get_appointments_by_email(email)
            
            # Debug print for appointments
            print(f"Found appointments: {appointments}")
            
            # Make sure to include appointments in response
            result['appointments'] = appointments
            
            if appointments:
                result['message'] = f"I found {len(appointments)} appointment(s) for {email}:"
            else:
                result['message'] = f"I couldn't find any appointments for {email}. Would you like to book a new appointment?"
            
            result['message'] += "\n\nWhat would you like to do next?\n\n1. Book a new appointment\n2. Check another email's appointments"
            result['state'] = "choosing"
        else:
            result['message'] = "I couldn't detect a valid email address. Please provide a valid email (e.g., example@domain.com)."
    
    return result

@app.route('/api/reset', methods=['POST'])
def reset():
    return jsonify({
        'message': "Hello! I'm your Appointment Booking Assistant. Please choose an option:\n\n1. Book a new appointment\n2. Check your existing appointments",
        'state': 'choosing',
        'booking_info': {}
    })

if __name__ == '__main__':
    # Set up the database
    setup_database()
    app.run(debug=True)