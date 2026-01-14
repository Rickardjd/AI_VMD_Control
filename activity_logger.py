"""
Activity Log Manager
Tracks all arm/disarm operations for groups and cameras
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ActivityLogEntry:
    """Single activity log entry"""
    timestamp: str  # ISO 8601 format
    user: str  # Username who performed action
    action: str  # "arm" or "disarm"
    target_type: str  # "group" or "camera"
    target_id: str  # Group ID or camera MAC
    target_name: str  # Group name or camera name
    success: bool
    cameras_affected: int  # Number of cameras affected
    message: str  # Result message
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


class ActivityLogger:
    """Manages activity logging for arm/disarm operations"""
    
    def __init__(self, log_path: str = 'data/activity_log.json'):
        """
        Initialize Activity Logger
        
        Args:
            log_path: Path to activity log file
        """
        self.log_path = log_path
        self.entries: List[ActivityLogEntry] = []
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        self.load_log()
    
    def load_log(self):
        """Load activity log from file"""
        if not os.path.exists(self.log_path):
            logger.info(f"No existing activity log found at {self.log_path}")
            self.entries = []
            return
        
        try:
            with open(self.log_path, 'r') as f:
                data = json.load(f)
                self.entries = [
                    ActivityLogEntry(**entry) 
                    for entry in data.get('entries', [])
                ]
            logger.info(f"Loaded {len(self.entries)} activity log entries")
        except Exception as e:
            logger.error(f"Error loading activity log: {e}")
            self.entries = []
    
    def save_log(self):
        """Save activity log to file"""
        try:
            data = {
                'entries': [entry.to_dict() for entry in self.entries]
            }
            
            with open(self.log_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved activity log with {len(self.entries)} entries")
        except Exception as e:
            logger.error(f"Error saving activity log: {e}")
            raise
    
    def log_action(
        self,
        user: str,
        action: str,
        target_type: str,
        target_id: str,
        target_name: str,
        success: bool,
        cameras_affected: int,
        message: str
    ):
        """
        Log an arm/disarm action
        
        Args:
            user: Username who performed action
            action: "arm" or "disarm"
            target_type: "group" or "camera"
            target_id: Group ID or camera MAC
            target_name: Group name or camera name
            success: Whether operation succeeded
            cameras_affected: Number of cameras affected
            message: Result message
        """
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        entry = ActivityLogEntry(
            timestamp=timestamp,
            user=user,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            success=success,
            cameras_affected=cameras_affected,
            message=message
        )
        
        # Add to beginning of list (most recent first)
        self.entries.insert(0, entry)
        
        # Keep only last 1000 entries to prevent file from growing too large
        if len(self.entries) > 1000:
            self.entries = self.entries[:1000]
        
        # Save to file
        self.save_log()
        
        logger.info(f"Logged {action} action by {user} on {target_type} {target_name}")
    
    def get_recent_entries(self, limit: int = 100) -> List[ActivityLogEntry]:
        """
        Get recent activity log entries
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of recent entries (newest first)
        """
        return self.entries[:limit]
    
    def get_entries_for_target(
        self,
        target_type: str,
        target_id: str,
        limit: int = 50
    ) -> List[ActivityLogEntry]:
        """
        Get activity log entries for specific target
        
        Args:
            target_type: "group" or "camera"
            target_id: Group ID or camera MAC
            limit: Maximum number of entries to return
            
        Returns:
            List of entries for this target (newest first)
        """
        filtered = [
            entry for entry in self.entries
            if entry.target_type == target_type and entry.target_id == target_id
        ]
        return filtered[:limit]
    
    def get_entries_by_user(self, username: str, limit: int = 50) -> List[ActivityLogEntry]:
        """
        Get activity log entries by user
        
        Args:
            username: Username to filter by
            limit: Maximum number of entries to return
            
        Returns:
            List of entries by this user (newest first)
        """
        filtered = [
            entry for entry in self.entries
            if entry.user == username
        ]
        return filtered[:limit]
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about activity log
        
        Returns:
            Dictionary with statistics
        """
        total_actions = len(self.entries)
        total_arms = sum(1 for e in self.entries if e.action == "arm")
        total_disarms = sum(1 for e in self.entries if e.action == "disarm")
        total_success = sum(1 for e in self.entries if e.success)
        total_failures = total_actions - total_success
        
        # Get unique users
        users = set(e.user for e in self.entries)
        
        # Get most recent entry
        most_recent = self.entries[0] if self.entries else None
        
        return {
            'total_actions': total_actions,
            'total_arms': total_arms,
            'total_disarms': total_disarms,
            'total_success': total_success,
            'total_failures': total_failures,
            'unique_users': len(users),
            'most_recent': most_recent.to_dict() if most_recent else None
        }
