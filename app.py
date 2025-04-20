from flask import Flask, render_template, request
from src.db import setup_database, store_appointment, get_appointments_by_email
from src.helper_func import validate_booking_info, standardize_time

app = Flask(__name__)
setup_database()

@app.route('/', methods=['GET'])
def index():
    action = request.args.get('action')
    return render_template('index.html', action=action)

@app.route('/book', methods=['POST'])
def book():
    name = request.form.get('name')
    email = request.form.get('email')
    date = request.form.get('date')
    time = request.form.get('time')
    purpose = request.form.get('purpose')

    booking_info = {"name": name, "email": email, "date": date, "time": time, "purpose": purpose}
    missing_fields, invalid_fields = validate_booking_info(booking_info)
    if missing_fields or invalid_fields:
        return render_template('index.html', action='book', booking_info=booking_info,
                               missing=missing_fields, invalid=invalid_fields)

    time_std = standardize_time(time)
    success, msg = store_appointment(name, email, date, time_std, purpose)
    if not success:
        error_msg = "You already have an appointment at that date and time." if msg == 'duplicate' else msg
        return render_template('index.html', action='book', booking_info=booking_info, error=error_msg)

    booking_info['time'] = time_std
    return render_template('index.html', action='book', confirmation=booking_info)

@app.route('/check', methods=['POST'])
def check():
    email = request.form.get('check_email')
    appointments = get_appointments_by_email(email)
    not_found = not appointments
    return render_template('index.html', action='check', appointments=appointments,
                           check_email=email, not_found=not_found)

if __name__ == '__main__':
    app.run(debug=True)