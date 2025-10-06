import streamlit as st
import time
import json  # Add this import
from plugins.gamification.models.db_utils import db_manager


def render(user):
    st.title("🎯 Your Learning Dashboard")

    # Welcome animation
    if 'first_visit' not in st.session_state:
        st.balloons()
        st.session_state.first_visit = True

    # Get database connection
    conn = db_manager.get_connection()

    # Get available categories
    categories = db_manager.get_quest_categories(conn)

    # Get user progress across all categories
    progress = db_manager.get_user_progress(conn, user['id'])

    # Calculate total points and milestones
    total_points = db_manager.get_user_points(conn, user['id'])
    total_milestones = sum(total for _, _, total in progress) if progress else 0
    completed_milestones = sum(completed for _, completed, _ in progress) if progress else 0

    # Animated points counter
    points_placeholder = st.empty()
    points_placeholder.metric("✨ Total Points", total_points)

    # Overall progress section
    st.subheader("📊 Overall Progress")

    if total_milestones > 0:
        progress_percent = (completed_milestones / total_milestones) * 100
        st.progress(progress_percent / 100)
        st.write(f"**Overall Completion:** {completed_milestones}/{total_milestones} milestones completed")

        # Celebration animation when progress is made
        if progress_percent == 100:
            st.balloons()
            st.success("🎉 Amazing! You've completed all milestones!")
        elif progress_percent >= 75:
            st.snow()
            st.info("🔥 You're almost there! Keep going!")
    else:
        st.info("No milestones available yet. Check back soon!")

    # Category selector
    st.subheader("🎯 Browse Quests by Category")

    if categories:
        selected_category = st.selectbox("Choose a category", ["All Categories"] + categories)

        # Display milestones based on selected category
        if selected_category == "All Categories":
            # Show progress by category
            if progress:
                st.write("### 📈 Progress by Category")
                for category, completed, total in progress:
                    if total > 0:
                        col1, col2, col3 = st.columns([2, 5, 1])
                        with col1:
                            st.write(f"**{category}**")
                        with col2:
                            category_progress = (completed / total) * 100
                            st.progress(category_progress / 100)
                        with col3:
                            st.write(f"{completed}/{total}")

            # Show all milestones
            st.write("### 🎯 All Available Milestones")
            milestones_exist = False
            for category in categories:
                milestones = db_manager.get_milestones_by_category(conn, category)
                if milestones:
                    milestones_exist = True
                    st.write(f"#### {category}")
                    display_milestones(conn, user, milestones)

            if not milestones_exist:
                st.info("No milestones available in any category.")
        else:
            # Show selected category milestones
            st.write(f"### 🎯 {selected_category} Milestones")
            milestones = db_manager.get_milestones_by_category(conn, selected_category)
            if milestones:
                display_milestones(conn, user, milestones)
            else:
                st.info(f"No milestones available in {selected_category} category.")
    else:
        st.info("No quest categories available yet. Please check if quest files are properly configured.")

    # User badges section
    st.subheader("🏆 Your Badges")
    user_badges = db_manager.get_user_badges(conn, user['id'])

    if user_badges:
        cols = st.columns(3)
        for i, (badge_id, name, description, earned_at) in enumerate(user_badges):
            with cols[i % 3]:
                st.success(f"**{name}**")
                st.write(description)
                st.caption(f"Earned: {earned_at}")
    else:
        st.info("You haven't earned any badges yet. Complete milestones to earn badges!")

    conn.close()


def display_milestones(conn, user, milestones):
    """Helper function to display milestones with completion status"""
    for milestone in milestones:
        mid, name, desc, points, difficulty, prerequisites_json, tags_json = milestone

        # Parse JSON fields with error handling
        try:
            prerequisites = json.loads(prerequisites_json) if prerequisites_json else []
        except:
            prerequisites = []

        try:
            tags = json.loads(tags_json) if tags_json else []
        except:
            tags = []

        # Check if milestone is completed
        completed = db_manager.is_milestone_completed(conn, user['id'], mid)

        # Check if prerequisites are met
        prerequisites_met = all(db_manager.is_milestone_completed(conn, user['id'], prereq) for prereq in prerequisites)

        if completed:
            with st.container():
                st.success(f"✅ **{name}** - {desc}")
                st.write(f"🎯 Earned: **{points} points** | Difficulty: {difficulty}")
                if tags:
                    st.write(f"🏷️ Tags: {', '.join(tags)}")
        else:
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    if prerequisites and not prerequisites_met:
                        st.warning(f"🔒 **{name}** - {desc}")
                        st.write(f"📋 Prerequisites: {', '.join(prerequisites)}")
                    else:
                        st.info(f"🎯 **{name}** - {desc}")

                    st.write(f"🏆 Potential: {points} points | Difficulty: {difficulty}")
                    if tags:
                        st.write(f"🏷️ Tags: {', '.join(tags)}")

                with col2:
                    if prerequisites and not prerequisites_met:
                        st.button("🔒 Locked", key=f"locked_{mid}", disabled=True)
                    else:
                        if st.button("Complete", key=f"complete_{mid}"):
                            # Complete the milestone
                            db_manager.complete_milestone(conn, user['id'], mid)

                            # Check if user earns a badge
                            badge_id = db_manager.get_milestone_badge(conn, mid)
                            if badge_id:
                                db_manager.award_badge(conn, user['id'], badge_id)

                            # Success animation
                            st.success("🎉 Milestone completed!")
                            time.sleep(1)  # Small delay for animation effect
                            st.rerun()

                st.markdown("---")