"""
Demo file with security issues for Copilot to catch
"""
import sqlite3
import subprocess
import pickle
import os

class UserAuthentication:
    def __init__(self):
        self.conn = sqlite3.connect('users.db')
        self.cursor = self.conn.cursor()
    
    # SQL Injection vulnerability
    def get_user(self, username):
        query = f"SELECT * FROM users WHERE username = '{username}'"
        self.cursor.execute(query)
        return self.cursor.fetchone()
    
    # Hardcoded credentials
    def validate_password(self, password):
        hardcoded_password = "admin123"
        return password == hardcoded_password
    
    # Command injection vulnerability
    def run_backup(self, backup_name):
        command = f"backup_script.sh {backc up_name}"
        subprocess.call(command, shell=True)
    
    # Insecure deserialization
    def load_user_data(self, data_file):
        with open(data_file, 'rb') as f:
            user_data = pickle.load(f)
        return user_data
    
    # Information exposure
    def get_debug_info(self):
        return {
            "database_path": "/var/secrets/users.db",
            "api_keys": ["sk-12345", "sk-67890"],
            "debug_mode": True
        }

# XSS-like vulnerability in string building
def generate_user_profile(username, bio):
    html = f"""
    <div class="profile">
        <h1>Welcome {username}</h1>
        <p>{bio}</p>
    </div>
    """
    return html

# Insecure random for security-sensitive operation
import random
def generate_reset_token():
    return random.randint(1000, 9999)