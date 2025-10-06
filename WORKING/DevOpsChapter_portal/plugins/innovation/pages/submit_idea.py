import streamlit as st


def render(user):
    st.title("💡 Submit Your Idea")

    with st.form("idea_form"):
        idea_title = st.text_input("Idea Title")
        idea_description = st.text_area("Describe your idea in detail")
        submitted = st.form_submit_button("Submit Idea")

        if submitted:
            if idea_title and idea_description:
                st.success("✅ Idea submitted successfully!")
                st.balloons()
                # Here you would normally save to database
                st.write(f"**Title:** {idea_title}")
                st.write(f"**Description:** {idea_description[:100]}...")  # Preview
            else:
                st.error("Please fill in both title and description.")