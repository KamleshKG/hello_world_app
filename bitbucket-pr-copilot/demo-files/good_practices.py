"""
Demo file with good practices for positive reinforcement
"""
from typing import List, Optional, Dict
from dataclasses import dataclass
from enum import Enum
import logging

class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

@dataclass
class UserProfile:
    username: str
    email: str
    first_name: str
    last_name: str
    age: int
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def is_adult(self) -> bool:
        return self.age >= 18

class UserService:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._users: Dict[int, UserProfile] = {}
    
    def create_user(self, user_data: dict) -> Optional[UserProfile]:
        """Create a new user with validation."""
        try:
            # Input validation
            if not self._is_valid_user_data(user_data):
                self.logger.warning("Invalid user data provided")
                return None
            
            user = UserProfile(
                username=user_data['username'],
                email=user_data['email'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                age=user_data['age']
            )
            
            # Business logic validation
            if not user.is_adult():
                self.logger.warning("User must be adult")
                return None
            
            # Store user
            user_id = self._generate_user_id()
            self._users[user_id] = user
            
            self.logger.info(f"Created user: {user.username}")
            return user
            
        except KeyError as e:
            self.logger.error(f"Missing required field: {e}")
            return None
    
    def _is_valid_user_data(self, user_data: dict) -> bool:
        """Validate user data structure and content."""
        required_fields = ['username', 'email', 'first_name', 'last_name', 'age']
        return all(field in user_data for field in required_fields)
    
    def _generate_user_id(self) -> int:
        """Generate a unique user ID."""
        return max(self._users.keys(), default=0) + 1
    
    def get_users_by_status(self, status: UserStatus) -> List[UserProfile]:
        """Get users by status with proper filtering."""
        return [user for user in self._users.values() 
                if self._get_user_status(user) == status]
    
    def _get_user_status(self, user: UserProfile) -> UserStatus:
        """Determine user status based on business rules."""
        # Simplified status logic
        return UserStatus.ACTIVE

# Context manager for resource handling
class DatabaseConnection:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None
    
    def __enter__(self):
        self.connection = self._create_connection()
        return self.connection
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
    
    def _create_connection(self):
        # Simulate connection creation
        return {"connected": True, "string": self.connection_string}

# Type hints and modern Python features
def process_users(users: List[UserProfile]) -> Dict[UserStatus, List[UserProfile]]:
    """Process users and group by status."""
    from collections import defaultdict
    
    grouped = defaultdict(list)
    for user in users:
        status = UserStatus.ACTIVE  # Simplified
        grouped[status].append(user)
    
    return dict(grouped)