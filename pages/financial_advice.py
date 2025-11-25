"""Financial Advice page."""
import streamlit as st
from modules.financial_advice import render_financial_advice_page

def render_financial_advice(user_id, user_fullname):
    """Render the Financial Advice page."""
    render_financial_advice_page(
        user_id=user_id,
        user_fullname=user_fullname
    )

