from flask import Flask, render_template, request, jsonify, session
import os
from datetime import datetime
from src.helper_func import (
    setup_database, initialize_llm_chain, process_chat_message
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

try:
    llm_chain, llm = initialize_llm_chain()
except Exception as e:
    print(f"Error initializing LLM: {str(e)}")
    print("Please make sure you have set the GEMINI_API_KEY environment variable.")

try:
    setup_database()
except Exception as e:
    print(f"Database initialization error: {str(e)}")
    if os.path.exists('booking.db'):
        print("The database file exists but there might be a schema issue. You may need to delete the file and restart.")

@app.route('/')
def index():
    if 'messages' not in session:
        session['messages'] = [{"role": "assistant", "content": "Hello, I am your AI appointment automation agent. How may I assist you today? I can help you book or check your appointments."}]
    
    if 'current_name' not in session:
        session['current_name'] = None
        
    if 'current_email' not in session:
        session['current_email'] = None
    
    return render_template('index.html', messages=session['messages'], now=datetime.now())

@app.route('/send_message', methods=['POST'])
def send_message():
    user_input = request.form.get('user_input', '')
    
    if user_input:
        if 'messages' not in session:
            session['messages'] = []
        
        session_messages = session.get('messages', [])
        session_messages.append({"role": "user", "content": user_input})
        session['messages'] = session_messages
        
        response = process_chat_message(
            user_input, 
            llm_chain, 
            llm, 
            session_data={
                'current_name': session.get('current_name'),
                'current_email': session.get('current_email')
            }
        )
        
        session_messages.append({"role": "assistant", "content": response})
        session['messages'] = session_messages
     
        return jsonify({
            'user_message': user_input,
            'assistant_message': response
        })
    
    return jsonify({'error': 'No input provided'}), 400

@app.template_filter('nl2br')
def nl2br(value):
    return value.replace('\n', '<br>')

if __name__ == "__main__":
    app.run(debug=True)