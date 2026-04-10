import streamlit as st
from plugins.gamification.models.db_utils import db_manager as db


def get_user():
    """Get current user from session state"""
    return st.session_state.get('user')


def login():
    """Login form"""
    st.title("🔐 Login to DevOps Portal")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            if not username or not password:
                st.error("Please enter both username and password")
                return

            user = db.get_user(username, password)
            if user:
                # user is now a dictionary, not a tuple
                st.session_state.user = user
                st.success(f"Welcome back, {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid username or password")

    # Registration section (optional)
    with st.expander("Don't have an account? Register here"):
        with st.form("register_form"):
            new_username = st.text_input("Choose username")
            new_password = st.text_input("Choose password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            register = st.form_submit_button("Register")

            if register:
                if not new_username or not new_password:
                    st.error("Please enter both username and password")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                elif db.user_exists(new_username):
                    st.error("Username already exists")
                else:
                    if db.create_user(new_username, new_password):
                        st.success("Account created successfully! Please login.")
                    else:
                        st.error("Failed to create account")