"""Session state management utilities."""
import streamlit as st
import time
import datetime
import logging

LOGGER = logging.getLogger('BankingApp')

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_users_data():
    """Load and cache user data from CSV."""
    import pandas as pd
    return pd.read_csv('data/users.csv')

@st.cache_resource
def get_chatbot_instance(user_id=None, user_fullname=None):
    """Create and cache a ChatBot instance for improved performance."""
    from modules.chatbot import ChatBot
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

def set_send_input():
    """Sets the send_input session state to True."""
    st.session_state.send_input = True
    clear_input_field()

def clear_input_field():
    """Clears the user input text field."""
    st.session_state.user_question = st.session_state.user_input
    st.session_state.user_input = ""

