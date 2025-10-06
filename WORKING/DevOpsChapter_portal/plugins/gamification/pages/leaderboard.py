import streamlit as st
from plugins.gamification.models.db_utils import db_manager


def render(user):
    # Check if user is admin
    if user.get('role') != 'admin':
        st.warning("🚫 Access Denied: Leaderboard is only available for administrators.")
        return

    st.title("👑 Leaderboard")
    st.write("Track user progress and achievements across all quest categories")

    # Get database connection
    conn = db_manager.get_connection()

    try:
        # Get leaderboard data
        leaderboard_data = get_leaderboard_data(conn)

        if leaderboard_data:
            # Display leaderboard
            display_leaderboard(leaderboard_data)
        else:
            st.info("No leaderboard data available yet. Complete some quests to appear here!")

    except Exception as e:
        st.error(f"Error loading Leaderboard: {e}")
        st.info("No leaderboard data available yet. Complete some quests to appear here!")
    finally:
        conn.close()


def get_leaderboard_data(conn):
    """Get leaderboard data with correct column handling"""
    c = conn.cursor()

    # Query that returns all needed columns
    c.execute('''
    SELECT 
        u.username,
        u.role,
        u.points,
        u.level,
        COUNT(um.milestone_id) as completed_milestones,
        (SELECT COUNT(*) FROM milestones) as total_milestones
    FROM users u
    LEFT JOIN user_milestones um ON u.id = um.user_id
    GROUP BY u.id, u.username, u.role, u.points, u.level
    ORDER BY u.points DESC, completed_milestones DESC, u.level DESC
    ''')

    return c.fetchall()


def display_leaderboard(leaderboard_data):
    """Display the leaderboard in a nice format"""
    st.subheader("🏆 Top Performers")

    # Create columns for header
    col1, col2, col3, col4 = st.columns([3, 2, 2, 3])

    with col1:
        st.write("**User**")
    with col2:
        st.write("**Points**")
    with col3:
        st.write("**Level**")
    with col4:
        st.write("**Progress**")

    st.markdown("---")

    for i, row in enumerate(leaderboard_data):
        # Unpack all 6 values from the row
        username, role, points, level, completed, total = row

        # Determine medal emoji based on rank
        if i == 0:
            medal = "🥇"
        elif i == 1:
            medal = "🥈"
        elif i == 2:
            medal = "🥉"
        else:
            medal = f"**#{i + 1}**"

        # Calculate progress percentage
        progress_percent = (completed / total * 100) if total > 0 else 0

        # Create columns for each user
        col1, col2, col3, col4 = st.columns([1, 3, 2, 4])

        with col1:
            st.write(medal)

        with col2:
            st.write(f"**{username}**")
            if role == 'admin':
                st.caption("👑 Admin")
            else:
                st.caption("User")

        with col3:
            st.write(f"**{points}**")
            st.caption(f"Level {level}")

        with col4:
            st.progress(progress_percent / 100)
            st.caption(f"{completed}/{total} milestones")

    # Additional statistics
    st.subheader("📊 Statistics")
    total_users = len(leaderboard_data)
    total_points = sum(row[2] for row in leaderboard_data)  # points is at index 2
    avg_points = total_points / total_users if total_users > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Users", total_users)
    with col2:
        st.metric("Total Points", total_points)
    with col3:
        st.metric("Average Points", f"{avg_points:.1f}")