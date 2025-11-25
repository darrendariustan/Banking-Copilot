"""Main Streamlit application for Banking Copilot."""
import streamlit as st
from streamlit_mic_recorder import mic_recorder
from langchain_community.chat_message_histories import StreamlitChatMessageHistory
import time
import logging

# Import core modules
from core import (
    authenticate_user,
    display_auth_sidebar,
    load_css,
    initialize_session_state,
    clear_chat_history,
    set_send_input,
)
from core.session_utils import get_chatbot_instance

# Import handlers
from handlers import process_text_message, process_voice_message

# Import pages
from pages import render_account_overview, render_money_transfer, render_financial_advice

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger('BankingApp')

# Configure Streamlit
st.set_page_config(
    page_title="AletaBanc Copilot",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply CSS at the start
load_css()

# Extend session state expiration (by default it's 60 minutes)
if "session_start_time" not in st.session_state:
    st.session_state.session_start_time = time.time()

def main():
    """Main application entry point."""
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
    chatbot = get_chatbot_instance(
        user_id=st.session_state.current_user_id,
        user_fullname=st.session_state.user_fullname
    )
    
    # After user is authenticated, add sidebar menu
    if "authenticated" in st.session_state and st.session_state.authenticated:
        st.sidebar.subheader("Navigation")
        
        # Menu options
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
                voice_recording = mic_recorder(
                    start_prompt="Start Recording",
                    stop_prompt="Stop Recording",
                    key="voice_recording"
                )
        
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
            
            # Handle voice recording input
            if voice_recording:
                process_voice_message(
                    voice_recording=voice_recording,
                    chatbot=chatbot,
                    chat_history=chat_history,
                    backup_key=backup_key,
                    selected_menu=selected_menu,
                    user_id=st.session_state.current_user_id
                )
            
            # Display debug info if it exists
            if st.session_state.get('debug_audio') or st.session_state.get('debug_transcription'):
                with st.expander("Voice Recording Debug Info (Click to hide)"):
                    if st.session_state.get('debug_audio'):
                        st.write(st.session_state.get('debug_audio'))
                    if st.session_state.get('debug_transcription'):
                        st.write(st.session_state.get('debug_transcription'))
            
            # Handle text input
            if st.session_state.send_input and st.session_state.user_question:
                process_text_message(
                    chatbot=chatbot,
                    chat_history=chat_history,
                    backup_key=backup_key,
                    selected_menu=selected_menu
                )

        # Get the selected menu from session state if available (to preserve during reruns)
        if "selected_menu" in st.session_state:
            selected_menu = st.session_state.selected_menu
            
        # Handle different menu options
        if selected_menu == "Account Overview":
            render_account_overview(
                    user_id=st.session_state.current_user_id,
                    user_fullname=st.session_state.user_fullname
                )
        
        elif selected_menu == "Money Transfer":
            render_money_transfer(user_id=st.session_state.current_user_id)
        
        elif selected_menu == "Financial Advice":
            render_financial_advice(
                user_id=st.session_state.current_user_id,
                user_fullname=st.session_state.user_fullname
            )

if __name__ == "__main__":
    main()
