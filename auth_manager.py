"""
User Authentication Manager
Handles user authentication with secure password storage using keyring
Supports user creation, login verification, and password resets
"""
import hashlib
import secrets
import json
import os
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import keyring

logger = logging.getLogger(__name__)

# Service name for keyring storage
AUTH_SERVICE = "camera_manager_auth"
USERS_FILE = "users.json"


@dataclass
class User:
    """User account information"""
    username: str
    password_hash: str
    salt: str
    role: str = "user"  # "user" or "admin"
    created_at: str = None
    last_login: str = None
    
    def to_dict(self):
        return {
            'username': self.username,
            'password_hash': self.password_hash,
            'salt': self.salt,
            'role': self.role,
            'created_at': self.created_at,
            'last_login': self.last_login
        }


class AuthenticationManager:
    """Manages user authentication and password storage"""
    
    def __init__(self, users_file: str = USERS_FILE):
        self.users_file = users_file
        self.users: Dict[str, User] = {}
        self._load_users()
        
        # Create default admin if no users exist
        if not self.users:
            logger.info("No users found. Creating default admin account.")
            self._create_default_admin()
    
    def _load_users(self):
        """Load users from JSON file"""
        if not os.path.exists(self.users_file):
            logger.info(f"Users file not found: {self.users_file}")
            return
        
        try:
            with open(self.users_file, 'r') as f:
                data = json.load(f)
            
            for user_data in data.get('users', []):
                user = User(**user_data)
                self.users[user.username] = user
            
            logger.info(f"Loaded {len(self.users)} users from {self.users_file}")
        
        except Exception as e:
            logger.error(f"Error loading users: {e}")
    
    def _save_users(self):
        """Save users to JSON file"""
        try:
            data = {
                'users': [user.to_dict() for user in self.users.values()]
            }
            
            with open(self.users_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(self.users)} users to {self.users_file}")
        
        except Exception as e:
            logger.error(f"Error saving users: {e}")
            raise
    
    def _create_default_admin(self):
        """Create default admin account with random password"""
        username = "admin"
        password = secrets.token_urlsafe(16)  # Generate random password
        
        try:
            self.create_user(username, password, role="admin")
            
            # Save password to keyring for server access
            keyring.set_password(AUTH_SERVICE, "default_admin_password", password)
            
            logger.warning("=" * 60)
            logger.warning("DEFAULT ADMIN ACCOUNT CREATED")
            logger.warning(f"Username: {username}")
            logger.warning(f"Password: {password}")
            logger.warning("IMPORTANT: Change this password immediately!")
            logger.warning("=" * 60)
            
            # Also print to console
            print("\n" + "=" * 60)
            print("DEFAULT ADMIN ACCOUNT CREATED")
            print(f"Username: {username}")
            print(f"Password: {password}")
            print("IMPORTANT: Change this password immediately!")
            print("=" * 60 + "\n")
            
        except Exception as e:
            logger.error(f"Error creating default admin: {e}")
    
    def _hash_password(self, password: str, salt: str = None) -> Tuple[str, str]:
        """
        Hash password with salt using PBKDF2
        
        Args:
            password: Plain text password
            salt: Salt (hex string), generates new if None
            
        Returns:
            Tuple of (password_hash, salt)
        """
        if salt is None:
            # Generate new salt
            salt_bytes = secrets.token_bytes(32)
            salt = salt_bytes.hex()
        else:
            salt_bytes = bytes.fromhex(salt)
        
        # Hash password with salt using PBKDF2
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt_bytes,
            100000  # 100,000 iterations
        ).hex()
        
        return password_hash, salt
    
    def create_user(self, username: str, password: str, role: str = "user") -> bool:
        """
        Create a new user account
        
        Args:
            username: Username (must be unique)
            password: Plain text password
            role: User role ("user" or "admin")
            
        Returns:
            True if successful, False otherwise
        """
        if not username or not password:
            logger.error("Username and password required")
            return False
        
        if username in self.users:
            logger.error(f"User already exists: {username}")
            return False
        
        if role not in ["user", "admin"]:
            logger.error(f"Invalid role: {role}")
            return False
        
        # Hash password
        password_hash, salt = self._hash_password(password)
        
        # Create user
        user = User(
            username=username,
            password_hash=password_hash,
            salt=salt,
            role=role,
            created_at=datetime.now().isoformat(),
            last_login=None
        )
        
        self.users[username] = user
        self._save_users()
        
        logger.info(f"Created user: {username} (role: {role})")
        return True
    
    def verify_password(self, username: str, password: str) -> bool:
        """
        Verify user password
        
        Args:
            username: Username
            password: Plain text password to verify
            
        Returns:
            True if password correct, False otherwise
        """
        if username not in self.users:
            logger.warning(f"Login attempt for non-existent user: {username}")
            return False
        
        user = self.users[username]
        
        # Hash provided password with user's salt
        password_hash, _ = self._hash_password(password, user.salt)
        
        # Compare hashes
        if password_hash == user.password_hash:
            # Update last login
            user.last_login = datetime.now().isoformat()
            self._save_users()
            
            logger.info(f"Successful login: {username}")
            return True
        else:
            logger.warning(f"Failed login attempt: {username}")
            return False
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """
        Change user password (requires old password)
        
        Args:
            username: Username
            old_password: Current password
            new_password: New password
            
        Returns:
            True if successful, False otherwise
        """
        if not self.verify_password(username, old_password):
            logger.error(f"Password change failed: incorrect old password for {username}")
            return False
        
        return self.reset_password(username, new_password)
    
    def reset_password(self, username: str, new_password: str) -> bool:
        """
        Reset user password (admin function, no old password required)
        
        Args:
            username: Username
            new_password: New password
            
        Returns:
            True if successful, False otherwise
        """
        if username not in self.users:
            logger.error(f"Cannot reset password: user not found: {username}")
            return False
        
        user = self.users[username]
        
        # Generate new salt and hash
        password_hash, salt = self._hash_password(new_password)
        
        # Update user
        user.password_hash = password_hash
        user.salt = salt
        
        self._save_users()
        
        logger.info(f"Password reset for user: {username}")
        return True
    
    def delete_user(self, username: str) -> bool:
        """
        Delete user account
        
        Args:
            username: Username to delete
            
        Returns:
            True if successful, False otherwise
        """
        if username not in self.users:
            logger.error(f"Cannot delete user: not found: {username}")
            return False
        
        # Prevent deleting last admin
        if self.users[username].role == "admin":
            admin_count = sum(1 for u in self.users.values() if u.role == "admin")
            if admin_count <= 1:
                logger.error("Cannot delete last admin user")
                return False
        
        del self.users[username]
        self._save_users()
        
        logger.info(f"Deleted user: {username}")
        return True
    
    def get_user(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.users.get(username)
    
    def list_users(self) -> List[Dict]:
        """
        List all users (without sensitive data)
        
        Returns:
            List of user info dictionaries
        """
        return [
            {
                'username': user.username,
                'role': user.role,
                'created_at': user.created_at,
                'last_login': user.last_login
            }
            for user in self.users.values()
        ]
    
    def is_admin(self, username: str) -> bool:
        """Check if user is admin"""
        user = self.users.get(username)
        return user.role == "admin" if user else False
    
    def user_exists(self, username: str) -> bool:
        """Check if user exists"""
        return username in self.users
