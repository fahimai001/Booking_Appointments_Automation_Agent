from flask import Flask, render_template, request, jsonify, session
import os
from datetime import datetime
from src.helper_func import setup_database, setup_llm_chain, handle_chat_message

app = Flask(__name__)
app.secret_key = os.urandom(24)

def initialize_services():
    """
    Initializes the LLM chain and sets up the database.
    """
    try:
        llm_chain, llm = setup_llm_chain()
    except Exception as err:
        print(f"Error initializing LLM: {err}")
        print("Please ensure GEMINI_API_KEY is set in your environment.")
        llm_chain, llm = None, None

    try:
        setup_database()
    except Exception as err:
        print(f"Database initialization error: {err}")
        if os.path.exists('database/booking.db'):
            print("Database file exists but there might be a schema issue. Consider deleting the file and restarting.")
    return llm_chain, llm

llm_chain, llm = initialize_services()

@app.before_request
def ensure_session_keys():
    if 'messages' not in session:
        session['messages'] = [{
            "role": "assistant",
            "content": ("Hello, I am your AI appointment automation agent. "
                        "How may I assist you today? I can help you book or check your appointments.")
        }]
    if 'current_name' not in session:
        session['current_name'] = None
    if 'current_email' not in session:
        session['current_email'] = None

@app.route('/')
def index():
    return render_template('index.html', messages=session['messages'], now=datetime.now())

@app.route('/send_message', methods=['POST'])
def send_message():
    user_input = request.form.get('user_input', '')
    if not user_input:
        return jsonify({'error': 'No input provided'}), 400

    session_messages = session.get('messages', [])
    session_messages.append({"role": "user", "content": user_input})
    session['messages'] = session_messages

    # Change from process_chat_message to handle_chat_message
    response = handle_chat_message(
        user_input,
        llm_chain,
        llm,
        session_context={  # Updated parameter name to match the function definition
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

@app.template_filter('nl2br')
def nl2br(value):
    return value.replace('\n', '<br>')

if __name__ == "__main__":
    app.run(debug=True)