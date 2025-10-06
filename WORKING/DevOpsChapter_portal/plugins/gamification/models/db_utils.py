import json
import sqlite3
import hashlib
from pathlib import Path


class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = self.get_connection()
        c = conn.cursor()

        # Create tables if they don't exist
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS milestones (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            points INTEGER DEFAULT 0,
            quest_category TEXT,
            difficulty TEXT,
            prerequisites TEXT,
            tags TEXT,
            badge TEXT
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS user_milestones (
            user_id INTEGER,
            milestone_id TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, milestone_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (milestone_id) REFERENCES milestones (id)
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS badges (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS user_badges (
            user_id INTEGER,
            badge_id TEXT,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, badge_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (badge_id) REFERENCES badges (id)
        )
        ''')

        # Create default admin user if not exists
        admin_password = hashlib.sha256("adminpass".encode()).hexdigest()
        c.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, role, points, level)
        VALUES (?, ?, ?, ?, ?)
        ''', ('admin', admin_password, 'admin', 0, 1))

        # Create test user if not exists
        test_password = hashlib.sha256("testpass".encode()).hexdigest()
        c.execute('''
        INSERT OR IGNORE INTO users (username, password_hash, role, points, level)
        VALUES (?, ?, ?, ?, ?)
        ''', ('testuser', test_password, 'user', 0, 1))

        # Debug quest file structures
        self.debug_quest_files()

        # Load quests
        self.load_quests(conn)

        conn.commit()
        conn.close()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def get_user(self, username, password):
        """Authenticate user with hashed password"""
        conn = self.get_connection()
        c = conn.cursor()

        # First get the user by username only
        c.execute('''
        SELECT id, username, password_hash, role, points, level 
        FROM users 
        WHERE username = ?
        ''', (username,))

        user = c.fetchone()
        conn.close()

        if not user:
            return None  # User not found

        # Hash the input password for comparison
        hashed_input_password = hashlib.sha256(password.encode()).hexdigest()

        # Compare the hashed input with stored hash
        if hashed_input_password == user[2]:  # user[2] is password_hash
            return {
                'id': user[0],
                'username': user[1],
                'role': user[3],
                'points': user[4],
                'level': user[5]
            }

        return None  # Password doesn't match

    def create_user(self, username, password, role='user'):
        """Create a new user"""
        conn = self.get_connection()
        c = conn.cursor()

        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            c.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            ''', (username, hashed_password, role))

            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # Username already exists
            conn.close()
            return False

    def user_exists(self, username):
        """Check if a username already exists"""
        conn = self.get_connection()
        c = conn.cursor()

        c.execute('SELECT COUNT(*) FROM users WHERE username = ?', (username,))
        count = c.fetchone()[0]

        conn.close()
        return count > 0

    def load_quests(self, conn):
        c = conn.cursor()
        quests_path = Path(__file__).parent.parent / 'quests'

        # List of all quest files to load
        quest_files = [
            'copilot_quests.json',
            'onboarding_quests.json',
            'iac_quests.json',
            'cicd_quests.json',
            'deployment_quests.json'
        ]

        all_milestones = []

        for quest_file in quest_files:
            file_path = quests_path / quest_file

            # Skip if file doesn't exist
            if not file_path.exists():
                print(f"Quest file {quest_file} not found, skipping...")
                continue

            try:
                with open(file_path, 'r') as f:
                    quest_data = json.load(f)

                # Handle different JSON structures
                if 'quest_lines' in quest_data:
                    # Original format with quest_lines
                    for quest_line in quest_data['quest_lines']:
                        for milestone in quest_line['milestones']:
                            milestone['quest_category'] = quest_data.get('quest_category', 'General')
                            all_milestones.append(milestone)

                elif 'quests' in quest_data:
                    # New format with quests array
                    for milestone in quest_data['quests']:
                        milestone['quest_category'] = quest_data.get('quest_category', 'General')
                        all_milestones.append(milestone)

                elif 'milestones' in quest_data:
                    # Direct milestones format
                    for milestone in quest_data['milestones']:
                        milestone['quest_category'] = quest_data.get('quest_category', 'General')
                        all_milestones.append(milestone)

                print(f"Loaded items from {quest_file}")

            except Exception as e:
                print(f"Error loading quests from {quest_file}: {e}")
                continue

        # Insert all milestones into database
        for milestone in all_milestones:
            # Convert lists to strings for database storage
            prerequisites = json.dumps(milestone.get('prerequisites', [])) if isinstance(milestone.get('prerequisites'),
                                                                                         list) else milestone.get(
                'prerequisites', '[]')
            tags = json.dumps(milestone.get('tags', [])) if isinstance(milestone.get('tags'), list) else milestone.get(
                'tags', '[]')

            # Insert or ignore if milestone already exists
            c.execute('''
            INSERT OR IGNORE INTO milestones 
            (id, name, description, points, quest_category, difficulty, prerequisites, tags, badge)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                milestone['id'],
                milestone['name'],
                milestone.get('description', ''),
                milestone.get('points', 0),
                milestone.get('quest_category', 'General'),
                milestone.get('difficulty', 'beginner'),
                prerequisites,
                tags,
                milestone.get('badge', '')
            ))

            # Also ensure badges are created
            badge_id = milestone.get('badge')
            if badge_id:
                c.execute('''
                INSERT OR IGNORE INTO badges (id, name, description, icon)
                VALUES (?, ?, ?, ?)
                ''', (
                    badge_id,
                    milestone.get('name', ''),
                    milestone.get('description', ''),
                    f"badge_{badge_id}.png"
                ))

        conn.commit()
        print(f"Loaded {len(all_milestones)} milestones from all quest files")

    def get_quest_categories(self, conn):
        c = conn.cursor()
        c.execute(
            'SELECT DISTINCT quest_category FROM milestones WHERE quest_category IS NOT NULL ORDER BY quest_category')
        return [row[0] for row in c.fetchall()]

    def get_milestones_by_category(self, conn, category):
        c = conn.cursor()
        c.execute('''
        SELECT id, name, description, points, difficulty, prerequisites, tags 
        FROM milestones 
        WHERE quest_category = ?
        ORDER BY difficulty, name
        ''', (category,))
        return c.fetchall()

    def get_user_progress(self, conn, user_id):
        c = conn.cursor()
        c.execute('''
        SELECT m.quest_category, COUNT(um.milestone_id), COUNT(m.id)
        FROM milestones m
        LEFT JOIN user_milestones um ON m.id = um.milestone_id AND um.user_id = ?
        GROUP BY m.quest_category
        ''', (user_id,))
        return c.fetchall()

    def get_user_points(self, conn, user_id):
        c = conn.cursor()
        c.execute('''
        SELECT COALESCE(SUM(m.points), 0)
        FROM user_milestones um
        JOIN milestones m ON um.milestone_id = m.id
        WHERE um.user_id = ?
        ''', (user_id,))
        return c.fetchone()[0]

    def is_milestone_completed(self, conn, user_id, milestone_id):
        c = conn.cursor()
        c.execute('''
        SELECT COUNT(*) FROM user_milestones 
        WHERE user_id = ? AND milestone_id = ?
        ''', (user_id, milestone_id))
        return c.fetchone()[0] > 0

    def complete_milestone(self, conn, user_id, milestone_id):
        c = conn.cursor()
        try:
            c.execute('''
            INSERT OR IGNORE INTO user_milestones (user_id, milestone_id)
            VALUES (?, ?)
            ''', (user_id, milestone_id))

            # Update user points
            c.execute('''
            UPDATE users 
            SET points = points + (SELECT points FROM milestones WHERE id = ?)
            WHERE id = ?
            ''', (milestone_id, user_id))

            conn.commit()
            return True
        except:
            conn.rollback()
            return False

    def get_milestone_badge(self, conn, milestone_id):
        c = conn.cursor()
        c.execute('SELECT badge FROM milestones WHERE id = ?', (milestone_id,))
        result = c.fetchone()
        return result[0] if result else None

    def award_badge(self, conn, user_id, badge_id):
        c = conn.cursor()
        c.execute('''
        INSERT OR IGNORE INTO user_badges (user_id, badge_id)
        VALUES (?, ?)
        ''', (user_id, badge_id))
        conn.commit()

    def get_user_badges(self, conn, user_id):
        c = conn.cursor()
        c.execute('''
        SELECT b.id, b.name, b.description, ub.earned_at
        FROM user_badges ub
        JOIN badges b ON ub.badge_id = b.id
        WHERE ub.user_id = ?
        ORDER BY ub.earned_at DESC
        ''', (user_id,))
        return c.fetchall()

    # Backward compatibility methods
    def get_user_progress_old(self, user_id):
        """Old method signature for backward compatibility"""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''
        SELECT m.id, m.name, m.description, m.points, 
               CASE WHEN um.milestone_id IS NOT NULL THEN 1 ELSE 0 END as achieved,
               um.completed_at
        FROM milestones m
        LEFT JOIN user_milestones um ON m.id = um.milestone_id AND um.user_id = ?
        ORDER BY m.id
        ''', (user_id,))
        result = c.fetchall()
        conn.close()
        return result

    def set_milestone(self, user_id, milestone_id):
        """Old method signature for backward compatibility"""
        conn = self.get_connection()
        self.complete_milestone(conn, user_id, milestone_id)
        conn.close()

    def load_quests(self, conn):
        c = conn.cursor()
        quests_path = Path(__file__).parent.parent / 'quests'

        # List of all quest files to load
        quest_files = [
            'copilot_quests.json',
            'onboarding_quests.json',
            'iac_quests.json',
            'cicd_quests.json',
            'deployment_quests.json'
        ]

        all_milestones = []

        for quest_file in quest_files:
            file_path = quests_path / quest_file

            # Skip if file doesn't exist
            if not file_path.exists():
                print(f"Quest file {quest_file} not found, skipping...")
                continue

            try:
                with open(file_path, 'r') as f:
                    quest_data = json.load(f)

                # Handle different JSON structures with better error handling
                milestones_to_add = []

                if 'quest_lines' in quest_data:
                    # Original format with quest_lines -> milestones
                    for quest_line in quest_data.get('quest_lines', []):
                        for milestone in quest_line.get('milestones', []):
                            milestone['quest_category'] = quest_data.get('quest_category', 'General')
                            milestones_to_add.append(milestone)

                elif 'quests' in quest_data:
                    # New format with quests array
                    for milestone in quest_data.get('quests', []):
                        milestone['quest_category'] = quest_data.get('quest_category', 'General')
                        milestones_to_add.append(milestone)

                elif 'milestones' in quest_data:
                    # Direct milestones format
                    for milestone in quest_data.get('milestones', []):
                        milestone['quest_category'] = quest_data.get('quest_category', 'General')
                        milestones_to_add.append(milestone)

                else:
                    # Try to handle as array of milestones directly
                    if isinstance(quest_data, list):
                        for milestone in quest_data:
                            if isinstance(milestone, dict):
                                milestone['quest_category'] = 'General'
                                milestones_to_add.append(milestone)

                print(f"Loaded {len(milestones_to_add)} items from {quest_file}")
                all_milestones.extend(milestones_to_add)

            except Exception as e:
                print(f"Error loading quests from {quest_file}: {e}")
                continue

        # Insert all milestones into database with proper error handling
        for milestone in all_milestones:
            try:
                # Safely get values with defaults
                milestone_id = milestone.get('id', f"unknown_{hash(str(milestone))}")
                name = milestone.get('name', 'Unnamed Milestone')
                description = milestone.get('description', '')
                points = milestone.get('points', 0)
                quest_category = milestone.get('quest_category', 'General')
                difficulty = milestone.get('difficulty', 'beginner')

                # Convert lists to strings for database storage
                prerequisites = json.dumps(milestone.get('prerequisites', [])) if isinstance(
                    milestone.get('prerequisites'), list) else milestone.get('prerequisites', '[]')
                tags = json.dumps(milestone.get('tags', [])) if isinstance(milestone.get('tags'),
                                                                           list) else milestone.get('tags', '[]')
                badge = milestone.get('badge', '')

                # Insert or ignore if milestone already exists
                c.execute('''
                INSERT OR IGNORE INTO milestones 
                (id, name, description, points, quest_category, difficulty, prerequisites, tags, badge)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    milestone_id,
                    name,
                    description,
                    points,
                    quest_category,
                    difficulty,
                    prerequisites,
                    tags,
                    badge
                ))

                # Also ensure badges are created
                if badge:
                    c.execute('''
                    INSERT OR IGNORE INTO badges (id, name, description, icon)
                    VALUES (?, ?, ?, ?)
                    ''', (
                        badge,
                        name,
                        description,
                        f"badge_{badge}.png"
                    ))

            except Exception as e:
                print(f"Error inserting milestone {milestone.get('id', 'unknown')}: {e}")
                continue

        conn.commit()
        print(f"Successfully loaded {len(all_milestones)} milestones from all quest files")

    def debug_quest_files(self):
        """Debug method to check quest file structures"""
        print("=== DEBUG: Quest File Structures ===")

        quests_path = Path(__file__).parent.parent / 'quests'
        quest_files = ['copilot_quests.json', 'onboarding_quests.json', 'iac_quests.json', 'cicd_quests.json',
                       'deployment_quests.json']

        for quest_file in quest_files:
            file_path = quests_path / quest_file

            if not file_path.exists():
                print(f"{quest_file}: MISSING")
                continue

            try:
                with open(file_path, 'r') as f:
                    content = json.load(f)

                print(f"\n{quest_file}:")
                print(f"  Type: {type(content)}")

                if isinstance(content, dict):
                    print(f"  Keys: {list(content.keys())}")

                    if 'quests' in content:
                        print(f"  Quests count: {len(content['quests'])}")
                        if content['quests']:
                            print(f"  First quest keys: {list(content['quests'][0].keys())}")

                    elif 'milestones' in content:
                        print(f"  Milestones count: {len(content['milestones'])}")
                        if content['milestones']:
                            print(f"  First milestone keys: {list(content['milestones'][0].keys())}")

                    elif 'quest_lines' in content:
                        print(f"  Quest lines count: {len(content['quest_lines'])}")
                        if content['quest_lines']:
                            print(f"  First quest line keys: {list(content['quest_lines'][0].keys())}")
                            if 'milestones' in content['quest_lines'][0]:
                                print(
                                    f"  First milestone keys: {list(content['quest_lines'][0]['milestones'][0].keys())}")

                elif isinstance(content, list):
                    print(f"  List length: {len(content)}")
                    if content:
                        print(f"  First item keys: {list(content[0].keys())}")

            except Exception as e:
                print(f"{quest_file}: ERROR - {e}")

        print("===================================")


# Create the database manager instance
db_manager = DatabaseManager('gamification.db')

# Backward compatibility - create 'db' alias for existing code
db = db_manager