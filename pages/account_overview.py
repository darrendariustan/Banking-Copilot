"""Account Overview page."""
import streamlit as st
from modules.account_dashboard import display_account_dashboard

def render_account_overview(user_id, user_fullname):
    """Render the Account Overview page."""
    # Create a container for the dashboard to ensure it's always rendered
    dashboard_container = st.container()
    
    with dashboard_container:
        # Use the new account dashboard functionality
        # Ensure dashboard is displayed regardless of chat interactions
        dashboard_data = display_account_dashboard(
            user_id=user_id,
            user_fullname=user_fullname
        )
        
        # Store dashboard context in session state for the chatbot to use
        if dashboard_data:
            st.session_state.dashboard_context = {
                'user_fullname': user_fullname,
                'user_id': user_id,
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

