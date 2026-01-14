"""
Session Manager
Handles user session management with secure tokens
"""
import secrets
import time
import logging
from typing import Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Session timeout in seconds (default: 24 hours)
SESSION_TIMEOUT = 24 * 60 * 60


@dataclass
class Session:
    """User session"""
    token: str
    username: str
    role: str
    created_at: float
    last_activity: float
    
    def is_expired(self, timeout: int = SESSION_TIMEOUT) -> bool:
        """Check if session has expired"""
        return (time.time() - self.last_activity) > timeout
    
    def update_activity(self):
        """Update last activity time"""
        self.last_activity = time.time()


class SessionManager:
    """Manages user sessions"""
    
    def __init__(self, timeout: int = SESSION_TIMEOUT):
        self.sessions: Dict[str, Session] = {}
        self.timeout = timeout
    
    def create_session(self, username: str, role: str) -> str:
        """
        Create new session for user
        
        Args:
            username: Username
            role: User role
            
        Returns:
            Session token
        """
        # Generate secure random token
        token = secrets.token_urlsafe(32)
        
        # Create session
        session = Session(
            token=token,
            username=username,
            role=role,
            created_at=time.time(),
            last_activity=time.time()
        )
        
        self.sessions[token] = session
        
        logger.info(f"Created session for user: {username}")
        return token
    
    def get_session(self, token: str) -> Optional[Session]:
        """
        Get session by token
        
        Args:
            token: Session token
            
        Returns:
            Session object if valid, None otherwise
        """
        if not token or token not in self.sessions:
            return None
        
        session = self.sessions[token]
        
        # Check if expired
        if session.is_expired(self.timeout):
            logger.info(f"Session expired for user: {session.username}")
            self.destroy_session(token)
            return None
        
        # Update activity
        session.update_activity()
        
        return session
    
    def destroy_session(self, token: str) -> bool:
        """
        Destroy session
        
        Args:
            token: Session token
            
        Returns:
            True if session destroyed, False if not found
        """
        if token in self.sessions:
            username = self.sessions[token].username
            del self.sessions[token]
            logger.info(f"Destroyed session for user: {username}")
            return True
        return False
    
    def destroy_user_sessions(self, username: str):
        """Destroy all sessions for a user"""
        tokens_to_remove = [
            token for token, session in self.sessions.items()
            if session.username == username
        ]
        
        for token in tokens_to_remove:
            del self.sessions[token]
        
        if tokens_to_remove:
            logger.info(f"Destroyed {len(tokens_to_remove)} session(s) for user: {username}")
    
    def cleanup_expired_sessions(self):
        """Remove all expired sessions"""
        expired_tokens = [
            token for token, session in self.sessions.items()
            if session.is_expired(self.timeout)
        ]
        
        for token in expired_tokens:
            username = self.sessions[token].username
            del self.sessions[token]
        
        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired session(s)")
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        return len(self.sessions)
    
    def list_active_sessions(self) -> list:
        """List all active sessions (for admin)"""
        return [
            {
                'username': session.username,
                'role': session.role,
                'created_at': session.created_at,
                'last_activity': session.last_activity
            }
            for session in self.sessions.values()
        ]
