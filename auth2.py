import streamlit as st

def is_authenticated():
    """Check if user is authenticated."""
    return st.user.is_logged_in