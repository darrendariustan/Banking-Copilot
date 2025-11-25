"""Authentication utilities."""
import streamlit as st
import datetime
import time
import logging
from .session_utils import load_users_data, initialize_session_state
from .ui_utils import display_image_html

LOGGER = logging.getLogger('BankingApp')

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

