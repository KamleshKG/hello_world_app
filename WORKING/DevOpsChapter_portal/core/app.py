import os
import importlib
import streamlit as st
from core.auth import get_user, login
from core.plugin_loader import load_plugins, get_plugin_pages
from plugins.gamification.models.db_utils import db_manager


def main():
    st.set_page_config(page_title="Unified DevOps Portal", layout="wide")

    # Initialize session state
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'plugins' not in st.session_state:
        st.session_state.plugins = load_plugins()
    if 'plugin_pages' not in st.session_state:
        st.session_state.plugin_pages = get_plugin_pages(st.session_state.plugins)
    if 'demo_mode' not in st.session_state:
        st.session_state.demo_mode = False
    if 'demo_step' not in st.session_state:
        st.session_state.demo_step = 0
    if 'current_page' not in st.session_state:  # Track current page
        st.session_state.current_page = "Home"

        # Load quests into database
    conn = db_manager.get_connection()
    db_manager.load_quests(conn)
    conn.close()

    # Authentication
    if not st.session_state.user:
        login()
        return

    # Sidebar
    st.sidebar.title("🚀 DevOps Portal")
    st.sidebar.write(f"Welcome, **{st.session_state.user['username']}**!")

    # Create navigation options
    nav_options = ["Home"] + [p["name"] for p in st.session_state.plugin_pages]
    selected_page = st.sidebar.selectbox("Navigate to", nav_options, key="nav_select")

    # Update current page tracking
    st.session_state.current_page = selected_page

    # Show tutorial button ONLY on Home page
    if selected_page == "Home" and not st.session_state.get('demo_mode'):
        if st.sidebar.button("🎬 Start Interactive Tutorial"):
            st.session_state.demo_mode = True
            st.session_state.demo_step = 0
            st.rerun()

    # Render selected page
    if selected_page == "Home":
        render_homepage()
    else:
        render_plugin_page(selected_page)

    # If in demo mode, show demo  regardless of current page
    # if st.session_state.get('demo_mode'):
    #     render_demo()


def render_homepage():
    st.title("🎮 Welcome to Unified DevOps Portal")

    # Animated demo section
    if st.button("🎬 Start Interactive Demo"):
        st.session_state.demo_mode = True
        st.session_state.demo_step = 0
        st.rerun()

    if st.session_state.get('demo_mode'):
        render_demo()
        return

    st.write("### Your central hub for:")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        🎯 **Gamified Learning**  
        *• Complete quests*  
        *• Earn points & badges*  
        *• Track your progress*
        """)

    with col2:
        st.markdown("""
        💡 **Innovation Hub**  
        *• Submit ideas*  
        *• Collaborate with team*  
        *• Drive innovation*
        """)

    with col3:
        st.markdown("""
        📊 **Smart Analytics**  
        *• Track performance*  
        *• Get insights*  
        *• Make data-driven decisions*
        """)

    # Animated character
    st.markdown("""
    <div style='text-align: center; margin: 20px 0;'>
        <span style='font-size: 2em;'>🚀</span>
        <p><small>Your DevOps companion is ready to guide you!</small></p>
    </div>
    """, unsafe_allow_html=True)


# def render_demo():
#     """Interactive demo/tutorial mode"""
#     demo_steps = [
#         {"title": "Welcome to the Demo!", "content": "Let me show you around your new DevOps portal...", "emoji": "👋"},
#         {"title": "Gamification Dashboard", "content": "Track your learning progress and complete quests to level up!",
#          "emoji": "🎯"},
#         {"title": "Innovation Portal",
#          "content": "Share your brilliant ideas with the team and collaborate on new solutions.", "emoji": "💡"},
#         {"title": "Leaderboard", "content": "See how you rank against your colleagues (admin access required).",
#          "emoji": "👑"},
#         {"title": "Ready to Start!", "content": "You're all set! Explore the features and start your DevOps journey.",
#          "emoji": "🚀"}
#     ]
#
#     current_step = st.session_state.get('demo_step', 0)
#
#     if current_step >= len(demo_steps):
#         st.session_state.demo_mode = False
#         st.rerun()
#         return
#
#     step = demo_steps[current_step]
#
#     # Animated header
#     st.markdown(f"""
#     <div style='text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#                 padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;'>
#         <h1 style='margin: 0;'>{step['emoji']} {step['title']}</h1>
#     </div>
#     """, unsafe_allow_html=True)
#
#     st.write(step['content'])
#
#     # Progress bar
#     progress = (current_step + 1) / len(demo_steps)
#     st.progress(progress)
#
#     # Navigation buttons
#     col1, col2, col3 = st.columns([1, 2, 1])
#
#     with col1:
#         if current_step > 0:
#             if st.button("⬅️ Previous"):
#                 st.session_state.demo_step -= 1
#                 st.rerun()
#
#     with col2:
#         st.write(f"Step {current_step + 1} of {len(demo_steps)}")
#
#     with col3:
#         if st.button("Next ➡️" if current_step < len(demo_steps) - 1 else "Finish 🎉"):
#             if current_step < len(demo_steps) - 1:
#                 st.session_state.demo_step += 1
#             else:
#                 st.session_state.demo_mode = False
#             st.rerun()
# def render_demo_overlay():
#     """Demo mode that overlays on top of any page"""
#     demo_steps = [
#         {"title": "Welcome to the Demo!", "content": "Let me show you around your new DevOps portal...", "emoji": "👋",
#          "page": "Home"},
#         {"title": "Gamification Dashboard", "content": "Track your learning progress and complete quests to level up!",
#          "emoji": "🎯", "page": "Gamification Dashboard"},
#         {"title": "Innovation Portal",
#          "content": "Share your brilliant ideas with the team and collaborate on new solutions.", "emoji": "💡",
#          "page": "Submit Idea"},
#         {"title": "Leaderboard", "content": "See how you rank against your colleagues (admin access required).",
#          "emoji": "👑", "page": "Leaderboard"},
#         {"title": "Ready to Start!", "content": "You're all set! Explore the features and start your DevOps journey.",
#          "emoji": "🚀", "page": "Home"}
#     ]
#
#     current_step = st.session_state.get('demo_step', 0)
#
#     if current_step >= len(demo_steps):
#         st.session_state.demo_mode = False
#         st.rerun()
#         return
#
#     step = demo_steps[current_step]
#
#     # Only show this step if we're on the right page
#     if st.session_state.current_page != step['page']:
#         # Auto-advance to the next step that matches current page
#         for i, demo_step in enumerate(demo_steps[current_step:]):
#             if demo_step['page'] == st.session_state.current_page:
#                 st.session_state.demo_step = current_step + i
#                 st.rerun()
#                 return
#         return
#
#     # Create overlay effect
#     st.markdown("""
#     <div style='position: fixed; top: 0; left: 0; right: 0; bottom: 0;
#                 background: rgba(0,0,0,0.5); z-index: 1000;
#                 display: flex; justify-content: center; align-items: center;'>
#     </div>
#     """, unsafe_allow_html=True)
#
#     # Demo content in a modal
#     with st.container():
#         st.markdown(f"""
#         <div style='position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
#                     background: white; padding: 20px; border-radius: 10px; z-index: 1001;
#                     box-shadow: 0 4px 20px rgba(0,0,0,0.3); min-width: 400px;'>
#             <h2 style='text-align: center; color: #667eea;'>{step['emoji']} {step['title']}</h2>
#             <p style='text-align: center;'>{step['content']}</p>
#         </div>
#         """, unsafe_allow_html=True)
#
#     # Navigation buttons at bottom
#     col1, col2, col3 = st.columns([1, 2, 1])
#
#     with col1:
#         if current_step > 0:
#             if st.button("⬅️ Previous", key="demo_prev"):
#                 st.session_state.demo_step -= 1
#                 st.rerun()
#
#     with col2:
#         st.write(f"Step {current_step + 1} of {len(demo_steps)}")
#
#     with col3:
#         next_text = "Next ➡️" if current_step < len(demo_steps) - 1 else "Finish 🎉"
#         if st.button(next_text, key="demo_next"):
#             if current_step < len(demo_steps) - 1:
#                 st.session_state.demo_step += 1
#             else:
#                 st.session_state.demo_mode = False
#             st.rerun()
def render_homepage():
    st.title("🎮 Welcome to Unified DevOps Portal")

    # Animated demo section
    if st.button("🎬 Start Interactive Demo"):
        st.session_state.demo_mode = True
        st.session_state.demo_step = 0
        st.rerun()

    if st.session_state.get('demo_mode'):
        render_demo()
        return

    st.write("### Your central hub for:")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        🎯 **Gamified Learning**  
        *• Complete quests*  
        *• Earn points & badges*  
        *• Track your progress*
        """)

    with col2:
        st.markdown("""
        💡 **Innovation Hub**  
        *• Submit ideas*  
        *• Collaborate with team*  
        *• Drive innovation*
        """)

    with col3:
        st.markdown("""
        📊 **Smart Analytics**  
        *• Track performance*  
        *• Get insights*  
        *• Make data-driven decisions*
        """)

    # Animated character
    st.markdown("""
    <div style='text-align: center; margin: 20px 0;'>
        <span style='font-size: 2em;'>🚀</span>
        <p><small>Your DevOps companion is ready to guide you!</small></p>
    </div>
    """, unsafe_allow_html=True)


def render_demo():
    """Simple demo that works alongside normal home page content"""
    demo_steps = [
        {"title": "Welcome to the Demo!", "content": "Let me show you around your new DevOps portal...", "emoji": "👋"},
        {"title": "Gamification Dashboard",
         "content": "Navigate to 'Gamification Dashboard' to track your learning progress and complete quests!",
         "emoji": "🎯"},
        {"title": "Innovation Portal", "content": "Go to 'Submit Idea' to share your brilliant ideas with the team!",
         "emoji": "💡"},
        {"title": "Leaderboard", "content": "Admins can check 'Leaderboard' to see team rankings!", "emoji": "👑"},
        {"title": "Ready to Start!", "content": "You're all set! Use the sidebar to navigate and explore.",
         "emoji": "🚀"}
    ]

    current_step = st.session_state.get('demo_step', 0)

    # Display demo content in a prominent but non-blocking way
    st.markdown("---")
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 10px; color: white; margin-bottom: 20px;'>
        <h2 style='margin: 0; text-align: center;'>{demo_steps[current_step]['emoji']} {demo_steps[current_step]['title']}</h2>
    </div>
    """, unsafe_allow_html=True)

    st.write(demo_steps[current_step]['content'])

    # Progress bar
    progress = (current_step + 1) / len(demo_steps)
    st.progress(progress)

    # Navigation buttons
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if current_step > 0:
            if st.button("⬅️ Previous", key="demo_prev"):
                st.session_state.demo_step -= 1
                st.rerun()
        else:
            st.write("")  # Empty space for layout

    with col2:
        st.write(f"**Tutorial Step {current_step + 1} of {len(demo_steps)}**")
        if st.button("❌ Exit Tutorial", key="demo_exit"):
            st.session_state.demo_mode = False
            st.session_state.demo_step = 0
            st.rerun()

    with col3:
        if current_step < len(demo_steps) - 1:
            if st.button("Next ➡️", key="demo_next"):
                st.session_state.demo_step += 1
                st.rerun()
        else:
            if st.button("Finish 🎉", key="demo_finish"):
                st.session_state.demo_mode = False
                st.session_state.demo_step = 0
                st.rerun()

    st.markdown("---")


def render_plugin_page(selected_page):
    # Find the selected page info
    page_info = None
    for p in st.session_state.plugin_pages:
        if p['name'] == selected_page:
            page_info = p
            break

    if not page_info:
        st.error(f"Page '{selected_page}' not found.")
        return

    # SIMPLE FIX: Map plugin names to folder names
    plugin_folder_map = {
        "Gamification Portal": "gamification",
        "Innovation Portal": "innovation"
    }

    folder_name = plugin_folder_map.get(page_info['plugin_name'])
    if not folder_name:
        st.error(f"Unknown plugin: {page_info['plugin_name']}")
        return

    module_path = f"plugins.{folder_name}.{page_info['module']}"

    st.sidebar.write(f"Debug: Trying to load {module_path}")

    try:
        module = importlib.import_module(module_path)
        render_func = getattr(module, page_info['function'])
        render_func(st.session_state.user)
    except Exception as e:
        st.error(f"Error loading {selected_page}: {e}")


if __name__ == "__main__":
    main()