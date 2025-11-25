"""UI utilities for styling and image handling."""
import streamlit as st
import base64
import logging

LOGGER = logging.getLogger('BankingApp')

def load_css():
    """Load and inject custom CSS files."""
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

def get_image_base64(image_path):
    """Get base64 encoding of an image."""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def display_image_html(image_path, width="200px", class_name=""):
    """Display an image with HTML."""
    img_base64 = get_image_base64(image_path)
    img_html = f'<img src="data:image/png;base64,{img_base64}" width="{width}" class="{class_name}">'
    return img_html

