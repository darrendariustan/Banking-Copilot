import streamlit as st
from streamlit_mic_recorder import mic_recorder
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
from chatbot import ChatBot
from audio_utils import *
import os
import pandas as pd
from dotenv import load_dotenv
import datetime
import time
import re
from money_transfer import MoneyTransfer, get_user_select_options, get_account_select_options, validate_transfer_input
# Import the new account dashboard module
from account_dashboard import display_account_dashboard
from cryptography.fernet import Fernet
import logging
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger('BankingApp')

# Load environment variables from .env file
load_dotenv()

# Configure Streamlit for longer session duration
st.set_page_config(
    page_title="AletaBanc Copilot",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Function to load and inject custom CSS
def load_css():
    # Load the main CSS file
    try:
        with open("static/css/login.css", "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception as e:
        LOGGER.warning(f"Could not load login.css: {str(e)}")
    
    # Load and encode background image
    try:
        image_path = "static/assets/background.jpg"
        with open(image_path, "rb") as img_file:
            bg_img_base64 = base64.b64encode(img_file.read()).decode()
        
        # Apply background image directly
        background_style = f"""
        <style>
        .stApp {{
            background-image: linear-gradient(135deg, rgba(0, 0, 10, 0.85), rgba(15, 23, 42, 0.9)), url("data:image/jpeg;base64,{bg_img_base64}") !important;
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
            background-attachment: fixed !important;
        }}
        
        @media (prefers-color-scheme: light) {{
            .stApp {{
                background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.85)), url("data:image/jpeg;base64,{bg_img_base64}") !important;
            }}
        }}
        </style>
        """
        st.markdown(background_style, unsafe_allow_html=True)
    except Exception as e:
        LOGGER.warning(f"Error loading background: {str(e)}")
    
    # Now load the theme CSS (without background image handling)
    try:
        with open("static/css/theme.css", "r") as f:
            theme_css = f.read()
            st.markdown(f"<style>{theme_css}</style>", unsafe_allow_html=True)
    except Exception as e:
        LOGGER.warning(f"Could not load theme.css: {str(e)}")
        
    # Additional JavaScript for custom styling
    st.markdown("""
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        // Add classes to financial elements
        document.querySelectorAll('td:nth-child(7)').forEach(cell => {
            if(cell.textContent.trim().toLowerCase() === 'active') {
                cell.classList.add('status-active');
            }
        });
        
        // Add money formatting classes
        document.querySelectorAll('td:nth-child(4), td:nth-child(5)').forEach(cell => {
            cell.classList.add('money-value');
        });
        
        // Ensure theme is applied
        const isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.body.classList.add(isDarkMode ? 'force-dark' : 'force-light');
    });
    </script>
    """, unsafe_allow_html=True)

# Function to get base64 encoding of an image
def get_image_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# Function to display an image with HTML
def display_image_html(image_path, width="200px", class_name=""):
    img_base64 = get_image_base64(image_path)
    img_html = f'<img src="data:image/png;base64,{img_base64}" width="{width}" class="{class_name}">'
    return img_html

# Apply CSS at the start
load_css()

# Extend session state expiration (by default it's 60 minutes)
if "session_start_time" not in st.session_state:
    st.session_state.session_start_time = time.time()

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_users_data():
    """Load and cache user data from CSV."""
    return pd.read_csv('data/users.csv')

@st.cache_resource
def get_chatbot_instance(user_id=None, user_fullname=None):
    """Create and cache a ChatBot instance for improved performance."""
    try:
        chatbot = ChatBot()
        if user_fullname:
            chatbot.user_fullname = user_fullname
        if user_id:
            chatbot.user_id = user_id
        return chatbot
    except Exception as e:
        st.error(f"Error initializing ChatBot: {str(e)}")
        return None

def set_send_input():
    """Sets the send_input session state to True."""
    st.session_state.send_input = True
    clear_input_field()

def clear_input_field():
    """Clears the user input text field."""
    st.session_state.user_question = st.session_state.user_input
    st.session_state.user_input = ""

def authenticate_user(user_id, password):
    """Authenticate a user by ID and password."""
    try:
        # Load users data from cached function
        users_df = load_users_data()
        
        # Check if user exists
        if user_id in users_df['user_id'].values:
            # Get user data
            user_row = users_df[users_df['user_id'] == user_id]
            user_data = user_row.iloc[0]
            
            # Compare passwords
            stored_password = user_data['password']
            
            if password.strip() == stored_password:
                # Set the last login timestamp
                st.session_state.last_login_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                return True, user_data
            else:
                # Track failed attempts for rate limiting
                if "failed_attempts" not in st.session_state:
                    st.session_state.failed_attempts = 1
                else:
                    st.session_state.failed_attempts += 1
                    
                # Limit login attempts (optional security feature)
                if st.session_state.failed_attempts >= 5:
                    time.sleep(2)  # Add delay after multiple failed attempts
                    
                return False, None
        else:
            return False, None
    
    except Exception as e:
        logging.error(f"Authentication error: {str(e)}")
        return False, None

def display_auth_sidebar():
    """Display authentication sidebar and handle authentication logic."""
    with st.sidebar:
        # Add logo to the top of the sidebar
        st.markdown(f'<div class="login-container login-animation">{display_image_html("static/assets/Aletabank.png", class_name="login-logo")}</div>', unsafe_allow_html=True)
        
        # Styled title
        st.markdown('<h2 class="sidebar-title">Account Access</h2>', unsafe_allow_html=True)
        
        # If user is already authenticated
        if "authenticated" in st.session_state and st.session_state.authenticated:
            st.success(f"Logged in as: {st.session_state.user_fullname}")
            
            # Show last login time if available
            if "last_login_time" in st.session_state:
                st.markdown(f"<p style='font-size: 0.8rem; color: #666;'>Last login: {st.session_state.last_login_time}</p>", unsafe_allow_html=True)
            
            if st.button("Logout"):
                # Capture current user ID before clearing state
                current_user = None
                if 'current_user_id' in st.session_state:
                    current_user = st.session_state.current_user_id
                
                # Clear authentication state
                for key in ['authenticated', 'current_user_id', 'user_fullname', 'last_login_time']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                # Clear user-specific history if we have a user ID
                if current_user:
                    user_history_key = f'history_{current_user}'
                    backup_key = f'chat_history_backup_{current_user}'
                    display_key = f'displayed_messages_{current_user}'
                    
                    # Don't delete the history keys as they should persist between sessions
                    # Just don't display them for the logged out state
                    
                    # Clear display tracking for this user
                    if display_key in st.session_state:
                        st.session_state[display_key] = {}
                
                # Clear generic display tracking
                if 'displayed_messages' in st.session_state:
                    st.session_state.displayed_messages = {}
                
                # Clear audio-related state
                if 'audio_file' in st.session_state:
                    st.session_state.audio_file = None
                if 'last_intent' in st.session_state:
                    st.session_state.last_intent = None
                if 'last_processed_message' in st.session_state:
                    st.session_state.last_processed_message = ""
                
                # Clear the cached resources to ensure a fresh start
                st.cache_resource.clear()
                
                st.rerun()
        else:
            # Display styled login form
            st.markdown('<div class="login-form">', unsafe_allow_html=True)
            
            # Subheader for login
            st.subheader("Login")
            
            # Check if there's a remembered user
            default_index = 0
            if "remember_user" in st.session_state:
                remembered_user = st.session_state.remember_user
                user_options = ["USR001", "USR002", "USR003", "USR004", "USR005"]
                if remembered_user in user_options:
                    default_index = user_options.index(remembered_user)
            
            # User ID selection with default if remembered
            user_id = st.selectbox("Select User ID", 
                               ["USR001", "USR002", "USR003", "USR004", "USR005"],
                               index=default_index,
                               format_func=lambda x: f"{x} - {'Darren Smith' if x == 'USR001' else 'Maria Smith' if x == 'USR002' else 'Enric Smith' if x == 'USR003' else 'Randy Smith' if x == 'USR004' else 'Victor Smith' if x == 'USR005' else x}")
            
            # Get user first name for password hint
            user_name_map = {
                "USR001": "darren", 
                "USR002": "maria", 
                "USR003": "enric", 
                "USR004": "randy", 
                "USR005": "victor"
            }
            selected_name = user_name_map.get(user_id, "")
            id_digits = user_id[-3:] if user_id else ""
            password_hint = f"{selected_name}{id_digits}" if selected_name else "firstname001"
            
            # Password field without the toggle button (removing the eye icon)
            password = st.text_input(f"Password (e.g., {password_hint})", type="password", key="password_input")
            
            # Remember me checkbox - checked by default if user is remembered
            remember_me = st.checkbox("Remember me", key="remember_me", value="remember_user" in st.session_state)
            
            # Form validation
            form_valid = True
            error_message = ""
            
            if "login_attempted" in st.session_state and st.session_state.login_attempted:
                if not password:
                    form_valid = False
                    error_message = "Please enter your password"
            
            # Display validation error if exists
            if not form_valid:
                st.markdown(f'<div class="login-error">{error_message}</div>', unsafe_allow_html=True)
            
            # Login button with styling
            if st.button("Login", key="login_button", use_container_width=True):
                # Set login attempted flag for validation
                st.session_state.login_attempted = True
                
                if not password:
                    st.markdown('<div class="login-error">Please enter your password</div>', unsafe_allow_html=True)
                else:
                    authenticated, user_data = authenticate_user(user_id, password)
                    if authenticated:
                        # Set authentication data first (before clearing anything)
                        st.session_state.authenticated = True
                        st.session_state.current_user_id = user_id
                        st.session_state.user_fullname = f"{user_data['first_name']} {user_data['last_name']}"
                        
                        # Remember me functionality
                        if remember_me:
                            st.session_state.remember_user = user_id
                        elif "remember_user" in st.session_state:
                            del st.session_state.remember_user
                        
                        # Clear login attempt state
                        if "login_attempted" in st.session_state:
                            del st.session_state.login_attempted
                        
                        # Clear any previous user's data
                        initialize_session_state()
                        
                        # Initialize user-specific display tracking
                        display_key = f'displayed_messages_{user_id}'
                        st.session_state[display_key] = {}
                        
                        # Clear cache to ensure fresh chatbot instance with updated code
                        st.cache_resource.clear()
                        
                        st.markdown(f'<div class="login-success">Welcome, {st.session_state.user_fullname}!</div>', unsafe_allow_html=True)
                        st.rerun()
                    else:
                        # Clear any previous failed attempts message
                        failed_count = st.session_state.get("failed_attempts", 0)
                        if failed_count > 3:
                            st.markdown('<div class="login-error">Too many incorrect attempts. Please try again after a short delay.</div>', unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="login-error">Authentication failed. Please check your credentials.</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
def clear_chat_history():
    """Clear the chat history."""
    if 'current_user_id' in st.session_state:
        # Clear user-specific history
        user_history_key = f'history_{st.session_state.current_user_id}'
        backup_key = f'chat_history_backup_{st.session_state.current_user_id}'
        display_key = f'displayed_messages_{st.session_state.current_user_id}'
        
        if user_history_key in st.session_state:
            del st.session_state[user_history_key]
        if backup_key in st.session_state:
            st.session_state[backup_key] = []
        if display_key in st.session_state:
            st.session_state[display_key] = {}
    
    # Also clean up the old generic keys if they exist
    if 'history' in st.session_state:
        del st.session_state['history']
    if 'chat_history_backup' in st.session_state:
        st.session_state.chat_history_backup = []
    if 'displayed_messages' in st.session_state:
        st.session_state.displayed_messages = {}
        
    # Reset message processing state
    st.session_state.last_processed_message = ""
    st.session_state.audio_file = None
    st.session_state.last_intent = None
    
    # Clear processed messages to allow fresh interactions
    if 'processed_messages' in st.session_state:
        st.session_state.processed_messages = set()
        
    # Clear the cached ChatBot instance to ensure updates are applied
    st.cache_resource.clear()
    
    # Use timestamp to prevent rapid reruns
    current_time = datetime.datetime.now().timestamp()
    st.session_state.last_rerun = current_time
    st.rerun()

def initialize_session_state():
    """Initialize all session state variables only once."""
    # List of all session state vars with their default values
    default_vars = {
        "message_ids": set(),
        "last_run_timestamp": time.time(),
        "processing_message": False,
        "chat_history_backup": [],
        "send_input": False,
        "user_question": "",
        "last_processed_message": "",
        "audio_file": None,
        "last_intent": None,
        "last_rerun": 0,
        "debug_audio": "",
        "debug_transcription": "",
        "processed_messages": set()  # Track already processed messages to prevent loops
    }
    
    # Set default values for any missing session state variables
    for var, default in default_vars.items():
        if var not in st.session_state:
            st.session_state[var] = default

def main():
    # Set app title
    st.title("AletaBanc Copilot")
    
    # Initialize session state once
    initialize_session_state()
    
    # Display authentication sidebar
    display_auth_sidebar()
    
    # Check if user is authenticated
    if "authenticated" not in st.session_state or not st.session_state.authenticated:
        st.info("Please log in to access the banking assistant.")
        st.markdown("""
        ### Welcome to AletaBanc Copilot
        
        Your personal AI-powered financial assistant, designed to help you manage your finances efficiently.
        
        Access your accounts securely through the login panel on the left. AletaBanc Copilot helps you:
        
        - Monitor account balances and transactions
        - Analyze spending patterns and set budgets
        - Get personalized financial insights
        - Transfer funds between accounts
        - Receive answers to your banking questions
        
        """)
        return
    
    # Container for chat history
    chat_container = st.container()
    
    # Audio container for voice responses
    audio_container = st.container()
    
    # Initializing chat history with enhanced persistence and user-specific key
    user_history_key = f'history_{st.session_state.current_user_id}'
    chat_history = StreamlitChatMessageHistory(key=user_history_key)
    
    # If chat history is empty but we have a backup, restore it
    backup_key = f'chat_history_backup_{st.session_state.current_user_id}'
    if not chat_history.messages and backup_key in st.session_state:
        for msg in st.session_state[backup_key]:
            if msg['type'] == 'human':
                chat_history.add_user_message(msg['content'])
            elif msg['type'] == 'ai':
                chat_history.add_ai_message(msg['content'])
    
    # Ensure we have a user-specific backup list
    if backup_key not in st.session_state:
        st.session_state[backup_key] = []
    
    # Initialize ChatBot instance with current user ID using cached function
    chatbot = get_chatbot_instance(user_id=st.session_state.current_user_id, user_fullname=st.session_state.user_fullname)
    
    # After user is authenticated, add sidebar menu
    if "authenticated" in st.session_state and st.session_state.authenticated:
        st.sidebar.subheader("Navigation")
        
        # Menu options - Removed Transaction History and Spending Analytics as they're now part of Account Overview
        menu_options = [
            "Account Overview",  
            "Money Transfer",
            "Financial Advice"
        ]
        
        selected_menu = st.sidebar.radio("Select a feature", menu_options)
        
        # Store the menu selection in session state to preserve it during reruns
        st.session_state.selected_menu = selected_menu
        
        # Add a button to clear chat history
        if st.sidebar.button("Clear Chat History"):
            clear_chat_history()

        # Only show chat input, recording, and chat history in Account Overview
        voice_recording = None
        if selected_menu != "Money Transfer" and selected_menu != "Financial Advice":
            # Text input field for user questions/messages with automatic submission
            user_input = st.text_input("Type your message", key="user_input", on_change=set_send_input)
            
            # Create column for voice recording
            col1 = st.columns([1])[0]
            
            # Voice recording in column
            with col1:
                voice_recording = mic_recorder(start_prompt="Start Recording", stop_prompt="Stop Recording", key="voice_recording")
        
            # Display chat history with deduplication tracking
            if chat_history.messages:
                with chat_container:
                    st.subheader("Chat History:")
                    
                    # Use user-specific display tracking key
                    display_key = f"displayed_messages_{st.session_state.current_user_id}"
                    
                    # Initialize display tracking if not exists
                    if display_key not in st.session_state:
                        st.session_state[display_key] = {}
                    
                    # Reset displayed messages for fresh display
                    st.session_state[display_key] = {}
                    
                    # Display all messages in the chat history
                    for i, message in enumerate(chat_history.messages):
                        st.chat_message(message.type).write(message.content)
                        
                        # Create a unique key for this message for tracking
                        message_key = f"{message.type}_{i}_{message.content[:50]}"
                        st.session_state[display_key][message_key] = True
        
            # Display audio player if an audio file is available
            with audio_container:
                if st.session_state.audio_file:
                    st.write("🔊 Voice Response:")
                    col_intent, col_player = st.columns([1, 3])
                    with col_intent:
                        if st.session_state.last_intent:
                            st.info(f"Intent: {st.session_state.last_intent}")
                    with col_player:
                        st.audio(st.session_state.audio_file)
            
            # Add this function to handle money transfer intents from voice commands
            def process_money_transfer_intent(chatbot, user_input, user_id):
                """
                Process a voice command for transferring money between accounts.
                
                Args:
                    chatbot: Instance of ChatBot
                    user_input: The transcribed voice command
                    user_id: The current user ID
                
                Returns:
                    tuple: (bool success, str message)
                """
                try:
                    # Use the intent analyzer to extract parameters
                    intent_analysis = chatbot.intent_analyzer.analyze(user_input)
                    
                    # Extract parameters for the transfer
                    params = intent_analysis.get("parameters", {})
                    source_account_type = params.get("source_account_type")
                    target_account_type = params.get("target_account_type")
                    amount = params.get("amount")
                    description = params.get("description", "Voice Transfer")
                    
                    # Validate we have the necessary parameters
                    if not source_account_type or not target_account_type:
                        return False, "I need to know which accounts to transfer between. Please specify your source and target accounts."
                    
                    if not amount:
                        return False, "I need to know how much money to transfer. Please specify an amount."
                    
                    # Initialize MoneyTransfer class
                    money_transfer = MoneyTransfer()
                    
                    # Execute the transfer
                    result = money_transfer.transfer_money(
                        source_user_id=user_id,
                        target_user_id=user_id,  # Same user for both accounts
                        amount=amount,
                        source_account_type=source_account_type,
                        target_account_type=target_account_type,
                        description=description
                    )
                    
                    # Check result and format response
                    if result["status"] == "success":
                        return True, f"I've successfully transferred ${amount:.2f} from your {source_account_type.replace('_', ' ').lower()} " \
                              f"to your {target_account_type.replace('_', ' ').lower()}. " \
                              f"Your new balance in the source account is ${result['source_balance']:.2f}."
                    else:
                        return False, f"I couldn't complete the transfer: {result['message']}. Please try again."
                    
                except Exception as e:
                    LOGGER.error(f"Error in voice money transfer: {e}")
                    return False, "I encountered an error while trying to process the transfer. Please try again or use the transfer form instead."

            # Update the voice recording handling code to process money transfer intents
            # Handling voice recording input
            if voice_recording:
                try:
                    # Prevent multiple runs of the same message
                    current_time = time.time()
                    if current_time - st.session_state.last_run_timestamp < 0.5:
                        return
                        
                    st.session_state.last_run_timestamp = current_time
                    
                    # Log the voice recording received
                    st.session_state.debug_audio = "Voice recording received"
                    
                    # Directly use voice_recording with our improved transcribe_audio function
                    transcribed_text = transcribe_audio(voice_recording)
                    
                    # Add debug info
                    if transcribed_text:
                        st.session_state.debug_transcription = f"Transcribed text: {transcribed_text}"
                    else:
                        st.session_state.debug_transcription = "Transcription failed or returned empty"
                        st.rerun()
                        return
                        
                    # Create a hash of the message to track if it's been processed
                    message_hash = f"{transcribed_text}:{st.session_state.current_user_id}"
                    
                    # Skip if this exact message has already been processed recently
                    if message_hash in st.session_state.processed_messages:
                        st.session_state.debug_transcription += " (Skipped - duplicate message)"
                        st.rerun()
                        return
                        
                    # Add to processed messages to prevent looping
                    st.session_state.processed_messages.add(message_hash)
                    
                    # Limit size of processed messages set
                    if len(st.session_state.processed_messages) > 20:
                        # Keep only the 10 most recent messages
                        st.session_state.processed_messages = set(list(st.session_state.processed_messages)[-10:])
                    
                    st.session_state.processing_message = True
                    
                    # Generate timestamp for this interaction
                    timestamp = datetime.datetime.now().isoformat()
                    
                    # Add user message to chat history
                    chat_history.add_user_message(transcribed_text)
                    
                    # Update chat history backup
                    st.session_state[backup_key].append({"type": "human", "content": transcribed_text})
                    
                    # Get intent classification with fallback to _classify_intent if classify_text fails
                    try:
                        # Use standard classification first (embedding-based similarity)
                        intent = chatbot.classify_text(transcribed_text)
                        st.session_state.debug_intent = f"Classified intent: {intent}"
                        
                        # Format intent for display (replace underscores with spaces)
                        if "_" in intent:
                            intent = intent.replace("_", " ")
                        
                        # Only use pattern matching as fallback if embedding classification returned "default"
                        if intent == "default":
                            # Get all account types and names from user accounts if available
                            account_types = []
                            account_names = []
                            
                            if hasattr(st, 'session_state') and 'dashboard_context' in st.session_state:
                                try:
                                    # Extract accounts from dashboard context
                                    if 'accounts' in st.session_state.dashboard_context:
                                        accounts = st.session_state.dashboard_context.get('accounts', [])
                                        # Extract all account types and names
                                        for account in accounts:
                                            if 'account_type' in account:
                                                account_type = account['account_type'].lower().replace('_', ' ')
                                                account_types.append(account_type)
                                            if 'account_name' in account:
                                                account_name = account['account_name'].lower()
                                                account_names.append(account_name)
                                except Exception as e:
                                    # Log but don't break if error occurs
                                    logging.error(f"Error extracting account types: {str(e)}")
                            
                            # If no account types found, fallback to standard types
                            if not account_types:
                                account_types = ['savings', 'checking', 'account']
                            
                            # Combine account names and types for pattern matching
                            account_identifiers = account_types + account_names
                            account_pattern = '|'.join(account_identifiers)
                            
                            # Check for account balance query patterns as fallback
                            account_balance_patterns = [
                                rf"how much (do|have) i (have )?in my ({account_pattern})",
                                rf"what('s| is) my ({account_pattern}) (account )?balance",
                                rf"balance in (my )?({account_pattern})",
                                rf"how much money (do|have) i (have )?in (my )?({account_pattern})",
                            ]
                            
                            # Check for spending patterns as fallback
                            spending_patterns = [
                                r"(which|what) category should i cut back",
                                r"spending analytics",
                                r"where (am i|are my) (over)?spending",
                                r"category.*spend",
                                r"spend.*category"
                            ]
                            
                            # Direct pattern match only as fallback
                            if any(re.search(pattern, transcribed_text.lower()) for pattern in account_balance_patterns):
                                intent = "Account Inquiries"
                                st.session_state.debug_intent += " (Fallback: Account Inquiries pattern match)"
                            elif any(re.search(pattern, transcribed_text.lower()) for pattern in spending_patterns):
                                intent = "Spending Analysis"
                                st.session_state.debug_intent += " (Fallback: Spending Analysis pattern match)"
                    except AttributeError:
                        # Fallback if classify_text is not available
                        try:
                            intent = chatbot._classify_intent(transcribed_text)
                            st.session_state.debug_intent = f"Fallback intent: {intent}"
                            
                            # Format intent for display
                            if "_" in intent:
                                intent = intent.replace("_", " ")
                        except Exception as e:
                            st.session_state.debug_intent = f"Error in intent classification: {str(e)}"
                            intent = "default"
                    
                    # Check for money transfer intent
                    if intent == "Money_Transfer" or intent == "Money Transfer":
                        # Process as money transfer
                        try:
                            success, response = process_money_transfer_intent(chatbot, transcribed_text, st.session_state.current_user_id)
                        except Exception as e:
                            # If there's an error processing the money transfer, provide a helpful message
                            response = f"I encountered an issue processing your money transfer request. Could you please rephrase it with the amount and accounts you want to transfer between?"
                            logging.error(f"Error in money transfer processing: {str(e)}")
                    else:
                        # Get standard response with error handling
                        try:
                            response = chatbot.get_response(transcribed_text)
                        except Exception as e:
                            # Provide a helpful response if there's an error
                            logging.error(f"Error getting chatbot response: {str(e)}")
                            response = "I'm sorry, I couldn't process that request. Could you please rephrase your question?"
                    
                    # Add AI response to chat history
                    chat_history.add_ai_message(response)
                    
                    # Update chat history backup
                    st.session_state[backup_key].append({"type": "ai", "content": response})
                    
                    # Convert to speech
                    text_to_speech(response)
                    
                    # Store audio file in session state
                    st.session_state.audio_file = "response.wav"
                    st.session_state.last_intent = intent
                    
                    # Force refresh to update chat history
                    current_time = datetime.datetime.now().timestamp()
                    st.session_state.last_rerun = current_time
                    
                    # Store the current menu selection before rerun
                    st.session_state.selected_menu = selected_menu
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing audio: {e}")
                finally:
                    # Always ensure processing_message is reset
                    st.session_state.processing_message = False
            
            # Display debug info if it exists
            if st.session_state.get('debug_audio') or st.session_state.get('debug_transcription'):
                with st.expander("Voice Recording Debug Info (Click to hide)"):
                    if st.session_state.get('debug_audio'):
                        st.write(st.session_state.get('debug_audio'))
                    if st.session_state.get('debug_transcription'):
                        st.write(st.session_state.get('debug_transcription'))
            
            # Handling text input
            if st.session_state.send_input and st.session_state.user_question:
                try:
                    # Prevent multiple runs of the same message
                    current_time = time.time()
                    if current_time - st.session_state.last_run_timestamp < 0.5:
                        return
                        
                    st.session_state.last_run_timestamp = current_time
                    
                    current_message = st.session_state.user_question
                    
                    # Create a hash of the message to track if it's been processed
                    message_hash = f"{current_message}:{st.session_state.current_user_id}"
                    
                    # Skip if this exact message has already been processed recently
                    if message_hash in st.session_state.processed_messages:
                        st.session_state.user_question = ""  # Still clear the input
                        return
                        
                    # Add to processed messages to prevent looping
                    st.session_state.processed_messages.add(message_hash)
                    
                    # Limit size of processed messages set
                    if len(st.session_state.processed_messages) > 20:
                        # Keep only the 10 most recent messages
                        st.session_state.processed_messages = set(list(st.session_state.processed_messages)[-10:])
                    
                    st.session_state.processing_message = True
                    
                    # Generate timestamp for this interaction
                    timestamp = datetime.datetime.now().isoformat()
                    
                    # Add user message to chat history
                    chat_history.add_user_message(current_message)
                    
                    # Update chat history backup
                    st.session_state[backup_key].append({"type": "human", "content": current_message})
                    
                    # Get chatbot response
                    # Check if we're on the Account Overview page and have chart data
                    chart_context = None
                    if selected_menu == "Account Overview" and "chart_data" in st.session_state:
                        try:
                            # Convert chart data to a readable format for the chatbot
                            chart_data = st.session_state.chart_data
                            
                            # Ensure all required keys exist
                            required_keys = ['checking_balance', 'savings_balance', 'credit_balance', 
                                            'avg_income', 'avg_expenses', 'savings_rate',
                                            'highest_expense_month', 'highest_expense_amount',
                                            'lowest_expense_month', 'lowest_expense_amount',
                                            'current_balance', 'balance_90day_high', 'balance_90day_high_date',
                                            'balance_90day_low', 'balance_90day_low_date', 
                                            'balance_monthly_trend_pct', 'spending_distribution', 'mortgage']
                            
                            # Check if all required keys exist
                            missing_keys = [key for key in required_keys if key not in chart_data]
                            
                            if not missing_keys:
                                chart_context = f"""
                                Current account balances:
                                - Checking: ${chart_data['checking_balance']:,.2f}
                                - Savings: ${chart_data['savings_balance']:,.2f}
                                - Credit Card: ${chart_data['credit_balance']:,.2f}
                                
                                Income vs Expenses:
                                - Average monthly income: ${chart_data['avg_income']:,}
                                - Average monthly expenses: ${chart_data['avg_expenses']:,}
                                - Current savings rate: {chart_data['savings_rate']}%
                                - Highest expense month: {chart_data['highest_expense_month']} (${chart_data['highest_expense_amount']:,})
                                - Lowest expense month: {chart_data['lowest_expense_month']} (${chart_data['lowest_expense_amount']:,})
                                
                                Account Balance Trend:
                                - Current balance: ${chart_data['current_balance']:,}
                                - 90-day high: ${chart_data['balance_90day_high']:,} on {chart_data['balance_90day_high_date']}
                                - 90-day low: ${chart_data['balance_90day_low']:,} on {chart_data['balance_90day_low_date']}
                                - Monthly trend: {chart_data['balance_monthly_trend_pct']}% growth
                                
                                Spending Distribution:
                                {'; '.join([f"{category}: {details['percentage']}% (${details['amount']:,})" 
                                            for category, details in chart_data['spending_distribution'].items()])}
                                
                                Mortgage:
                                - Original amount: ${chart_data['mortgage']['original_amount']:,}
                                - Current balance: ${chart_data['mortgage']['current_balance']:,}
                                - Paid off: ${chart_data['mortgage']['paid_off']:,} ({chart_data['mortgage']['paid_off_percentage']}%)
                                - Monthly payment: ${chart_data['mortgage']['monthly_payment']:,}
                                - Interest rate: {chart_data['mortgage']['interest_rate']}%
                                """
                            else:
                                # Fall back to a simpler context if keys are missing
                                chart_context = f"User is viewing their account dashboard with financial information."
                        except Exception as e:
                            # Log the error but continue without chart context
                            logging.error(f"Error generating chart context: {str(e)}")
                            chart_context = None
                        
                        # Pass chart context to chatbot
                        try:
                            response = chatbot.get_response(current_message, chart_context=chart_context)
                        except Exception as e:
                            # Provide a helpful response if there's an error
                            logging.error(f"Error getting chatbot response with chart context: {str(e)}")
                            response = "I'm sorry, I couldn't process that request. Could you please rephrase your question?"
                    else:
                        # Standard response without chart context
                        try:
                            response = chatbot.get_response(current_message)
                        except Exception as e:
                            # Provide a helpful response if there's an error
                            logging.error(f"Error getting chatbot response: {str(e)}")
                            response = "I'm sorry, I couldn't process that request. Could you please rephrase your question?"
                    
                    # Add AI response to chat history
                    chat_history.add_ai_message(response)
                    
                    # Update chat history backup
                    st.session_state[backup_key].append({"type": "ai", "content": response})
                    
                    # Get intent with fallback to _classify_intent if classify_text fails
                    try:
                        # Use standard classification first (embedding-based similarity)
                        intent = chatbot.classify_text(current_message)
                        st.session_state.debug_intent = f"Classified intent: {intent}"
                        
                        # Format intent for display (replace underscores with spaces)
                        if "_" in intent:
                            intent = intent.replace("_", " ")
                        
                        # Only use pattern matching as fallback if embedding classification returned "default"
                        if intent == "default":
                            # Get all account types and names from user accounts if available
                            account_types = []
                            account_names = []
                            
                            if hasattr(st, 'session_state') and 'dashboard_context' in st.session_state:
                                try:
                                    # Extract accounts from dashboard context
                                    if 'accounts' in st.session_state.dashboard_context:
                                        accounts = st.session_state.dashboard_context.get('accounts', [])
                                        # Extract all account types and names
                                        for account in accounts:
                                            if 'account_type' in account:
                                                account_type = account['account_type'].lower().replace('_', ' ')
                                                account_types.append(account_type)
                                            if 'account_name' in account:
                                                account_name = account['account_name'].lower()
                                                account_names.append(account_name)
                                except Exception as e:
                                    # Log but don't break if error occurs
                                    logging.error(f"Error extracting account types: {str(e)}")
                            
                            # If no account types found, fallback to standard types
                            if not account_types:
                                account_types = ['savings', 'checking', 'account']
                            
                            # Combine account names and types for pattern matching
                            account_identifiers = account_types + account_names
                            account_pattern = '|'.join(account_identifiers)
                            
                            # Check for account balance query patterns as fallback
                            account_balance_patterns = [
                                rf"how much (do|have) i (have )?in my ({account_pattern})",
                                rf"what('s| is) my ({account_pattern}) (account )?balance",
                                rf"balance in (my )?({account_pattern})",
                                rf"how much money (do|have) i (have )?in (my )?({account_pattern})",
                            ]
                            
                            # Check for spending patterns as fallback
                            spending_patterns = [
                                r"(which|what) category should i cut back",
                                r"spending analytics",
                                r"where (am i|are my) (over)?spending",
                                r"category.*spend",
                                r"spend.*category"
                            ]
                            
                            # Direct pattern match only as fallback
                            if any(re.search(pattern, current_message.lower()) for pattern in account_balance_patterns):
                                intent = "Account Inquiries"
                                st.session_state.debug_intent += " (Fallback: Account Inquiries pattern match)"
                            elif any(re.search(pattern, current_message.lower()) for pattern in spending_patterns):
                                intent = "Spending Analysis"
                                st.session_state.debug_intent += " (Fallback: Spending Analysis pattern match)"
                    except AttributeError:
                        # Fallback if classify_text is not available
                        try:
                            intent = chatbot._classify_intent(current_message)
                            st.session_state.debug_intent = f"Fallback intent: {intent}"
                            
                            # Format intent for display
                            if "_" in intent:
                                intent = intent.replace("_", " ")
                        except Exception as e:
                            st.session_state.debug_intent = f"Error in intent classification: {str(e)}"
                            intent = "default"
                    
                    # Convert to speech
                    text_to_speech(response)
                    
                    # Store audio file in session state
                    st.session_state.audio_file = "response.wav"
                    st.session_state.last_intent = intent
                    
                    # Force refresh to update chat history
                    current_time = datetime.datetime.now().timestamp()
                    st.session_state.last_rerun = current_time
                    
                    # Store the current menu selection before rerun
                    st.session_state.selected_menu = selected_menu
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing message: {e}")
                finally:
                    # Always ensure processing_message is reset
                    st.session_state.processing_message = False

        # Get the selected menu from session state if available (to preserve during reruns)
        if "selected_menu" in st.session_state:
            selected_menu = st.session_state.selected_menu
            
        # Handle different menu options (moved from earlier in the code)
        if selected_menu == "Account Overview":
            # Create a container for the dashboard to ensure it's always rendered
            dashboard_container = st.container()
            
            with dashboard_container:
                # Use the new account dashboard functionality
                # Ensure dashboard is displayed regardless of chat interactions
                dashboard_data = display_account_dashboard(
                    user_id=st.session_state.current_user_id,
                    user_fullname=st.session_state.user_fullname
                )
                
                # Store dashboard context in session state for the chatbot to use
                if dashboard_data:
                    st.session_state.dashboard_context = {
                        'user_fullname': st.session_state.user_fullname,
                        'user_id': st.session_state.current_user_id,
                        'total_accounts': dashboard_data.get('total_accounts', 0),
                        'total_assets': dashboard_data.get('total_assets', 0),
                        'total_liabilities': dashboard_data.get('total_liabilities', 0),
                        'selected_account': dashboard_data.get('selected_account', 'All Accounts'),
                        'selected_time_period': dashboard_data.get('selected_time_period', 'Last 30 days'),
                        'chart_data': dashboard_data.get('chart_data', {})
                    }
                    
                    # Store chart_data directly for easier access, preserving existing data
                    chart_data = dashboard_data.get('chart_data', {})
                    if "chart_data" in st.session_state:
                        # Merge new chart data with existing data
                        st.session_state.chart_data.update(chart_data)
                    else:
                        # First time setting chart data
                        st.session_state.chart_data = chart_data
        
        elif selected_menu == "Money Transfer":
            st.header("Money Transfer")
            
            # Initialize money transfer module
            money_transfer = MoneyTransfer()
            
            # Check for redirects from previous actions
            if 'redirect_to_overview' in st.session_state and st.session_state.redirect_to_overview:
                # Clear the redirect flag
                st.session_state.redirect_to_overview = False
                # Set the selected menu to Account Overview
                st.session_state.previous_menu = selected_menu
                selected_menu = "Account Overview"
                st.rerun()
            
            st.subheader("Transfer Money Between Accounts")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### From")
                # Source user selection (default to current user)
                users = get_user_select_options(money_transfer)
                source_user_id = st.selectbox(
                    "Source User", 
                    options=[user['value'] for user in users],
                    format_func=lambda x: next((user['label'] for user in users if user['value'] == x), x),
                    index=[i for i, user in enumerate(users) if user['value'] == st.session_state.current_user_id][0] if 'current_user_id' in st.session_state else 0,
                    key="source_user"
                )
                
                # Source account selection
                source_accounts = get_account_select_options(money_transfer, source_user_id)
                if not source_accounts:
                    st.warning(f"No accounts found for selected user.")
                    source_account_type = None
                else:
                    source_account_type = st.selectbox(
                        "Source Account",
                        options=[account['value'] for account in source_accounts],
                        format_func=lambda x: next((account['label'] for account in source_accounts if account['value'] == x), x),
                        key="source_account"
                    )
            
            with col2:
                st.markdown("### To")
                # Target user selection
                target_user_id = st.selectbox(
                    "Target User", 
                    options=[user['value'] for user in users],
                    format_func=lambda x: next((user['label'] for user in users if user['value'] == x), x),
                    key="target_user"
                )
                
                # Target account selection
                target_accounts = get_account_select_options(money_transfer, target_user_id)
                if not target_accounts:
                    st.warning(f"No accounts found for selected user.")
                    target_account_type = None
                else:
                    target_account_type = st.selectbox(
                        "Target Account",
                        options=[account['value'] for account in target_accounts],
                        format_func=lambda x: next((account['label'] for account in target_accounts if account['value'] == x), x),
                        key="target_account"
                    )
            
            # Amount and description
            amount_str = st.text_input("Amount ($)", placeholder="Enter amount e.g. 100.00")
            description = st.text_input("Description (Optional)", placeholder="Enter description")
            
            # Show validation information to guide users
            if amount_str:
                amount_valid, amount_result = validate_transfer_input(amount_str)
                if not amount_valid:
                    st.warning(amount_result)
                elif float(amount_result) > 1000:
                    st.info("Note: Large transfers may require additional verification.")
            
            # Check if both source and target accounts are selected before showing the transfer button
            transfer_disabled = (source_account_type is None or target_account_type is None or 
                               source_user_id == target_user_id and source_account_type == target_account_type)
            
            # Transfer button with helpful tooltip
            transfer_btn = st.button(
                "Transfer Money", 
                disabled=transfer_disabled,
                help="Transfer funds between accounts. Both source and target accounts must be selected."
            )
            
            if transfer_disabled and source_user_id == target_user_id and source_account_type == target_account_type:
                st.warning("Cannot transfer money to the same account")
                
            # Process transfer
            if transfer_btn:
                # Validate amount
                amount_valid, amount_result = validate_transfer_input(amount_str)
                
                if not amount_valid:
                    st.error(amount_result)
                else:
                    # Show progress indicator during processing
                    with st.spinner("Processing transfer..."):
                        # Process transfer
                        result = money_transfer.transfer_money(
                            source_user_id,
                            target_user_id,
                            amount_result,
                            source_account_type,
                            target_account_type,
                            description
                        )
                    
                    if result["status"] == "success":
                        # Success feedback with better formatting
                        st.success(result["message"])
                        
                        # Create a container for the transfer details
                        with st.container():
                            st.markdown("### Transfer Details")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.info(f"💰 Source Balance: ${result['source_balance']:.2f}")
                            with col2:
                                st.info(f"💰 Target Balance: ${result['target_balance']:.2f}")
                            
                            st.markdown(f"Transaction ID: `{result['transaction_id']}`")
                            st.markdown(f"Date: `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
                            
                            # Add options to view updated accounts or make another transfer
                            st.markdown("### What's next?")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("View Account Overview"):
                                    # Set session state to redirect to account overview
                                    st.session_state.redirect_to_overview = True
                                    st.rerun()
                            with col2:
                                if st.button("Make Another Transfer"):
                                    # Clear form fields for a new transfer
                                    st.session_state.pop('source_account', None)
                                    st.session_state.pop('target_user', None)
                                    st.session_state.pop('target_account', None)
                                    st.rerun()
                    else:
                        # More detailed error feedback
                        st.error(result["message"])
                        if "code" in result and result["code"] == "INSUFFICIENT_FUNDS":
                            # Show accounts with sufficient funds if available
                            sufficient_accounts = money_transfer.get_accounts_with_sufficient_funds(
                                source_user_id, amount_result)
                            if sufficient_accounts:
                                st.markdown("#### Accounts with sufficient funds:")
                                for acct in sufficient_accounts:
                                    st.info(
                                        f"• {acct['account_name']} ({acct['account_type']}): " + 
                                        f"${acct['balance']:.2f} {acct['currency']}"
                                    )
                        elif "code" in result and result["code"] == "SYSTEM_ERROR":
                            st.warning("A system error occurred. Please try again later or contact support.")
            
            # Transfer History with better formatting
            st.markdown("---")
            st.subheader("Recent Transfers")
            history_tab1, history_tab2 = st.tabs(["Sent", "Received"])
            
            # Helper function to format the transfer history
            def display_transfer_history(transfers_df, direction):
                if not transfers_df.empty:
                    # Create a more user-friendly display
                    for index, row in transfers_df.iterrows():
                        with st.container():
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.markdown(f"**{row['date']}**")
                                amount_str = row['amount']
                                if direction == "sent":
                                    st.markdown(f"📤 `{amount_str}`")
                                else:
                                    st.markdown(f"📥 `{amount_str}`")
                            with col2:
                                st.markdown(f"**{row['description']}**")
                                if 'balance_after' in row:
                                    st.markdown(f"Balance after: ${row['balance_after']:.2f}")
                                st.markdown(f"ID: {row['transaction_id']}")
                            st.markdown("---")
                else:
                    if direction == "sent":
                        st.info("No outgoing transfers found")
                    else:
                        st.info("No incoming transfers found")
            
            # Get user's transfer history
            transfer_history = money_transfer.get_transfer_history(st.session_state.current_user_id)
            
            # Display sent transfers
            with history_tab1:
                if transfer_history["status"] == "success" and "transfers" in transfer_history and len(transfer_history["transfers"]) > 0:
                    try:
                        transfers_df = pd.DataFrame(transfer_history["transfers"])
                        # Filter only outgoing transfers (negative amounts)
                        outgoing = transfers_df[transfers_df["amount"].str.contains("-")]
                        # Sort by date, most recent first
                        if not outgoing.empty and 'date' in outgoing.columns:
                            try:
                                # Sort if possible
                                outgoing = outgoing.sort_values('date', ascending=False)
                            except Exception as e:
                                LOGGER.warning(f"Could not sort by date: {e}")
                        display_transfer_history(outgoing, "sent")
                    except Exception as e:
                        LOGGER.warning(f"Unable to display transfer history: {str(e)}")
                        st.info("No outgoing transfers found")
                else:
                    status_message = transfer_history.get("message", "No transfer history available")
                    st.info(status_message)
            
            # Display received transfers
            with history_tab2:
                if transfer_history["status"] == "success" and "transfers" in transfer_history and len(transfer_history["transfers"]) > 0:
                    try:
                        transfers_df = pd.DataFrame(transfer_history["transfers"])
                        # Filter only incoming transfers (positive amounts)
                        incoming = transfers_df[~transfers_df["amount"].str.contains("-")]
                        # Sort by date, most recent first
                        if not incoming.empty and 'date' in incoming.columns:
                            try:
                                # Sort if possible
                                incoming = incoming.sort_values('date', ascending=False)
                            except Exception as e:
                                LOGGER.warning(f"Could not sort by date: {e}")
                        display_transfer_history(incoming, "received")
                    except Exception as e:
                        LOGGER.warning(f"Unable to display transfer history: {str(e)}")
                        st.info("No incoming transfers found")
                else:
                    status_message = transfer_history.get("message", "No transfer history available")
                    st.info(status_message)
        
        elif selected_menu == "Financial Advice":
            # Import the financial advice implementation
            from financial_advice import render_financial_advice_page
            
            # Render the financial advice page with the current user's ID and name
            render_financial_advice_page(
                user_id=st.session_state.current_user_id,
                user_fullname=st.session_state.user_fullname
            )

if __name__ == "__main__":
    main()