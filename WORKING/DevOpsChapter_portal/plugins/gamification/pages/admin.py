import streamlit as st


def render(user):
    st.title("Quest Admin Panel")
    st.write("This is where admins can manage quests and milestones.")

    if user.get('role') != 'admin':
        st.warning("Admin access required.")
        return

    st.success("Welcome, Admin!")
    # Add admin functionality here later