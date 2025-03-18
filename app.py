from flask import Flask, render_template, request, jsonify, session
import os
from datetime import datetime
from src.helper_func import setup_database, initialize_llm_chain, process_chat_message

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global variables for the language model chain and instance.
llm_chain = None
llm = None

@app.before_first_request
def initialize_services():
    """
    Initialize the LLM chain and set up the database before handling any requests.
    """
    global llm_chain, llm
    try:
        llm_chain, llm = initialize_llm_chain()
    except Exception as err:
        app.logger.error("Error initializing LLM: %s", err)
        raise err  # Halt the app if LLM initialization fails.

    try:
        setup_database()
    except Exception as err:
        app.logger.error("Database initialization error: %s", err)
        if os.path.exists('database/booking.db'):
            app.logger.error("Database file exists but may have a schema issue. Consider deleting the file and restarting.")
        raise err

@app.route('/')
def index():
    """
    Render the main index page and initialize session variables if they are not set.
    """
    session.setdefault('messages', [{
        "role": "assistant",
        "content": ("Hello, I am your AI appointment automation agent. "
                    "How may I assist you today? I can help you book or check your appointments.")
    }])
    session.setdefault('current_name', None)
    session.setdefault('current_email', None)
    
    return render_template('index.html', messages=session['messages'], now=datetime.now())

@app.route('/send_message', methods=['POST'])
def send_message():
    """
    Process the user message and return the assistant's response in JSON format.
    """
    user_input = request.form.get('user_input', '').strip()
    
    if not user_input:
        return jsonify({'error': 'No input provided'}), 400
    
    # Append the user's message to the session history.
    session_messages = session.get('messages', [])
    session_messages.append({"role": "user", "content": user_input})
    session['messages'] = session_messages

    # Process the input and generate a response.
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

@app.template_filter('nl2br')
def nl2br(text):
    """
    Convert newline characters in text to HTML <br> tags.
    """
    return text.replace('\n', '<br>')

if __name__ == "__main__":
    app.run(debug=True)
