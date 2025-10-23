"""
Demo file with code quality and maintainability issues
"""
import os
import sys
from typing import Optional, List

# Too many parameters
def process_user_data(user_id: int, username: str, email: str, 
                     first_name: str, last_name: str, age: int,
                     address: str, phone: str, preferences: dict,
                     metadata: dict, is_active: bool) -> bool:
    # Complex conditional logic
    if user_id and username and email and first_name and last_name:
        if age > 18 and age < 100:
            if address and phone:
                if preferences.get('newsletter', False):
                    if metadata.get('verified', False):
                        if is_active:
                            return True
    return False

# God class with multiple responsibilities
class UserManager:
    def __init__(self):
        self.users = []
        self.log_file = "user_log.txt"
        self.db_connection = None
    
    # Mixing data access with business logic
    def create_user(self, user_data: dict) -> bool:
        # Validation logic
        if not user_data.get('email'):
            return False
        
        # Database operation
        self._save_to_database(user_data)
        
        # Logging
        self._write_to_log(f"Created user: {user_data['email']}")
        
        # Notification
        self._send_welcome_email(user_data['email'])
        
        # Cache update
        self._update_cache(user_data)
        
        return True
    
    def _save_to_database(self, user_data):
        # Simulate DB save
        pass
    
    def _write_to_log(self, message):
        with open(self.log_file, 'a') as f:
            f.write(message + '\n')
    
    def _send_welcome_email(self, email):
        # Email sending logic
        pass
    
    def _update_cache(self, user_data):
        # Cache update logic
        pass
    
    # Also handles authentication? Violates SRP
    def authenticate_user(self, username, password):
        # Authentication logic
        pass

# Long method with multiple levels of nesting
def complex_data_processing(input_data: List[dict]) -> List[dict]:
    results = []
    
    for item in input_data:
        if item.get('type') == 'user':
            if item.get('status') == 'active':
                if 'profile' in item:
                    profile = item['profile']
                    if 'email' in profile:
                        email = profile['email']
                        if '@' in email:
                            domain = email.split('@')[1]
                            if domain in ['company.com', 'partner.com']:
                                if item.get('permissions'):
                                    permissions = item['permissions']
                                    if 'read' in permissions and 'write' in permissions:
                                        results.append(item)
    
    return results

# Inconsistent naming conventions
def GetUserData(userId):  # Mixed case
    user_name = ""  # snake_case
    userAge = 0     # camelCase
    return {"id": userId, "name": user_name, "age": userAge}

# Dead code and unused imports
def unused_function():
    return "This is never called"

# Magic numbers and hardcoded values
def calculate_discount(price: float) -> float:
    if price > 100:  # Magic number
        return price * 0.9  # Magic number
    elif price > 50:  # Magic number
        return price * 0.95  # Magic number
    else:
        return price