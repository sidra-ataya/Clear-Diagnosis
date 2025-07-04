from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_migrate import Migrate
from openai import OpenAI
from livereload import Server
from config import Config
from models import *  # Import All models here
import os
from flask_mail import Mail, Message #add email and environment variables libraries
from dotenv import load_dotenv


app = Flask(__name__)
app.config.from_object(Config)

### ---Flask-Mail --- ###
# Get email configuration from environment variables
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS')
app.config['ADMIN_EMAIL'] = os.environ.get('ADMIN_EMAIL')

# Flask-Mail
mail = Mail(app)

db.init_app(app)
migrate = Migrate(app, db)  # Initialize Flask-Migrate for database migrations

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key="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",
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login page if not authenticated
# Define a user class that extends UserMixin for Flask-Login compatibility
class UserLogin(UserMixin, User):
    pass

@login_manager.user_loader
def load_user(user_id):
    """Load a user by their ID."""
    return UserLogin.query.get(int(user_id))

@app.before_request
def create_tables():
    """Create database tables before the first request."""
    db.create_all()

@app.route("/")
def home():
    return render_template("index.html", user=current_user)

@app.route("/login" , methods=["GET", "POST"])
def login():
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password_hash == password:  # Assuming password is stored in plain text for simplicity
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid username or password.')
    return render_template("login.html")

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('new_username')
        email = request.form.get('new_email')
        password = request.form.get('new_password')
        if User.query.filter_by(username=username).first():
            flash('Username already taken.')
        else:
            user = User(username=username, email=email, password_hash=password)
            #user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('chat', Conversation_id=0), user=current_user)
    return render_template('signup.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


### --- Medical Consultation Form Routes --- ###

# 1. Display the medical consultation form (questions.html)
@app.route('/consultation')
def consultation_form():
    """Renders the medical consultation form page."""
    return render_template('questions.html')

# 2. Get the form data and send it via email
@app.route('/submit-consultation', methods=['POST'])
def submit_consultation():
    """Handles form submission and sends the data via email."""
    if request.method == 'POST':
        # To ensure the form data is processed correctly
        form_data = request.form

        # Create the email subject and body
        # Using get() to avoid KeyError if a field is missing
        subject = f"Consultation Request from: {form_data.get('full_name', 'N/A')}"

        email_body = f"""
        Consultation Request Submission, 
        --- 1. Personal Information and Main Complaint ---
        - Full Name: {form_data.get('full_name')}
        - Age: {form_data.get('age')}
        - Gender: {form_data.get('gender')}
        - Main Complaint: {form_data.get('main_complaint')}

        --- 2. Current Symptoms Details ---
        - Onset: {form_data.get('onset')}
        - Location: {form_data.get('location')}
        - Character: {form_data.get('character')}
        - Duration: {form_data.get('duration')}
        - Aggravating Factors: {form_data.get('aggravating')}
        - Alleviating Factors: {form_data.get('alleviating')}
        - Related Symptoms: {form_data.get('related_symptoms')}
        - Severity (1-10): {form_data.get('severity')}

        --- 3. Medical History ---
        - Chronic Diseases: {", ".join(form_data.getlist('chronic_diseases'))}
        - Current Medications: {form_data.get('medications')}
        - Allergies: {form_data.get('allergies')}
        - Previous Surgeries: {form_data.get('surgeries')}

        --- 4. Lifestyle ---
        - Smoking Status: {form_data.get('smoking')}

        --- End of Report ---
        """

        # Create the email message
        # Using Flask-Mail to send the email
        msg = Message(
            subject,
            sender=('Clear Diagnosis System', app.config['MAIL_USERNAME']),
            recipients=[app.config['ADMIN_EMAIL']] # Send to admin email
        )
        msg.body = email_body
        
        try:
            mail.send(msg)
            flash('Form submitted successfully!', 'success')
            return redirect(url_for('thank_you'))
        except Exception as e:
            flash(f'Error occurred while sending the form: {e}', 'danger')
            return redirect(url_for('consultation_form'))

    return redirect(url_for('consultation_form'))

# 3. Route for the thank you page after successful submission
@app.route('/thank-you')
def thank_you():
    """Displays a thank you page after successful form submission."""
    return render_template('thank_you.html') # It's better to create a simple thank you page

### ----------------------------------------------------------------- ###

# --- Chat Routes ---
@app.route("/dashboard")
def dashboard():
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.timestamp.desc()).all()
    return render_template('dashboard.html', conversations=conversations)

@app.route('/new_chat', methods=['GET', 'POST'])
@login_required
def new_chat():
    if request.method == 'POST':
        # Create a new conversation for the current userm
        new_message = request.form.get('message')

        
        # Create a new conversation with the current user
        new_subject = new_message[:50]  # Use the first 50 characters of the message as the subject
        new_conv = Conversation(user_id=current_user.id, subject=new_subject, role='User', timestamp=datetime.now())
        db.session.add(new_conv)
        db.session.commit()
        msg = Message( conversation_id=new_conv.id, sender_id=current_user.id, role='User', content=new_message, timestamp=datetime.now())
        db.session.add(msg)
        db.session.commit()

    # Redirect to the new conversation page
    return redirect(url_for('chat', conversation_id=new_conv.id))


@app.route('/chat/<int:conversation_id>', methods=['GET', 'POST'])
@login_required
def chat(conversation_id):
    
    conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.timestamp.desc()).all()
    
    # If conversation_id is 0, redirect to the Show new chat dialog
    if conversation_id == 0:
        # Fetch the conversation and its messages

        return render_template('chat.html', conversations=conversations, new_chat=True)
    
    convo = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST' :
        user_input  = request.form.get('message')
        if user_input:
            msg = Message(
                conversation_id=convo.id,
                sender_id=current_user.id,
                content=user_input,
                role='User',
                timestamp=datetime.now()
            )
            db.session.add(msg)
            db.session.commit()

            # Call the Online medical bot API
            #bot_response = ask_medical_bot(user_input)
            #bot_response = ask_local_bot(user_input)
            bot_response = "test response"  # Placeholder for actual bot response

            bot_msg = Message(
                conversation_id=convo.id,
                sender_id=0,  # Assuming 0 is the bot's ID
                content=bot_response,
                role='Bot',
                timestamp=datetime.now()
            )
            db.session.add(bot_msg)
            db.session.commit()
        return redirect(url_for('chat', conversation_id=conversation_id, new_chat=False))
    
    return render_template('chat.html', conversations=conversations, conversation=convo, new_chat=False)
    
@app.route('/chatt/<int:conversation_id>/delete', methods=['POST'])
@login_required
def delete_conversation(conversation_id):
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first_or_404()

    # Delete all messages in the conversation
    Message.query.filter_by(conversation_id=conversation.id).delete()

    # Then delete the conversation itself
    db.session.delete(conversation)
    db.session.commit()

    flash("Conversation deleted successfully.", "success")
    return redirect(url_for('chat', conversation_id=0)) 

"""
gpt_model = GPT4All("Mistral-7B-Instruct-v0.3.IQ1_M.gguf", model_path=".", allow_download=False)

def ask_local_bot(prompt):
    system_prompt = (
        "You are a cautious and helpful medical assistant. "
        "Based on the user's symptoms, suggest possible causes and remind them to consult a doctor. "
        "Make your answers as short as possible. "
        "Ask for more information if needed, untillyou narrow down the possibilities. "
        "you can ask personal questions like age and gender to narrow down the possibilities. "
        "If the user asks about a specific disease, provide a brief description. "
        "If the user asks about a specific symptom, provide a brief description. "
        "Only return the final reply, not internal thoughts or reasoning."
    )
    response = gpt_model.chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200
    )
    return response['choices'][0]['message']['content']
"""
MODEL = "mistralai/mistral-small-3.2-24b-instruct:free"

def ask_medical_bot(user_input):
    system_prompt = (
        "You are a cautious and helpful medical assistant. "
        "Based on the user's symptoms, suggest possible causes and remind them to consult a doctor. "
        "Make your answers as short as possible. "
        "Ask for more information if needed, untillyou narrow down the possibilities. "
        "you can ask personal questions like age and gender to narrow down the possibilities. "
        "If the user asks about a specific disease, provide a brief description. "
        "If the user asks about a specific symptom, provide a brief description. "
        "Only return the final reply, not internal thoughts or reasoning."

    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
    )

    try:
        return response.choices[0].message.content
    except Exception as e:
        print(f"[GPT Error] {e}")
        return "Sorry, something went wrong while generating a response. Please try again."


if __name__ == "__main__":
    # Ensure the instance folder exists
    with app.app_context():  # Needed for DB operations
        db.create_all()      # Creates the database and tables
    server = Server(app.wsgi_app)
    server.watch("**/*.py")  # Watch Python files for changes
    server.watch("templates/*.html")
    server.watch("static/*.*")
    server.serve(host="0.0.0.0", port=5000, debug=True) 
