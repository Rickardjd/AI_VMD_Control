"""
Credential Manager
Handles secure storage and retrieval of camera credentials using system keyring
"""
import keyring
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

SERVICE_NAME = "CameraAIVMDManager"
USERNAME_KEY = "camera_username"
PASSWORD_KEY = "camera_password"


class CredentialManager:
    """Manages secure credential storage using system keyring"""
    
    def __init__(self, service_name: str = SERVICE_NAME):
        """
        Initialize Credential Manager
        
        Args:
            service_name: Service name for keyring storage
        """
        self.service_name = service_name
    
    def store_credentials(self, username: str, password: str):
        """
        Store credentials in system keyring
        
        Args:
            username: Camera username
            password: Camera password
        """
        try:
            keyring.set_password(self.service_name, USERNAME_KEY, username)
            keyring.set_password(self.service_name, PASSWORD_KEY, password)
            logger.info("Credentials stored successfully in keyring")
        except Exception as e:
            logger.error(f"Error storing credentials: {str(e)}")
            raise
    
    def get_credentials(self) -> Optional[Tuple[str, str]]:
        """
        Retrieve credentials from system keyring
        
        Returns:
            Tuple of (username, password) or None if not found
        """
        try:
            username = keyring.get_password(self.service_name, USERNAME_KEY)
            password = keyring.get_password(self.service_name, PASSWORD_KEY)
            
            if username and password:
                logger.info("Credentials retrieved successfully from keyring")
                return (username, password)
            else:
                logger.warning("Credentials not found in keyring")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving credentials: {str(e)}")
            return None
    
    def delete_credentials(self):
        """Delete credentials from system keyring"""
        try:
            keyring.delete_password(self.service_name, USERNAME_KEY)
            keyring.delete_password(self.service_name, PASSWORD_KEY)
            logger.info("Credentials deleted from keyring")
        except keyring.errors.PasswordDeleteError:
            logger.warning("No credentials found to delete")
        except Exception as e:
            logger.error(f"Error deleting credentials: {str(e)}")
            raise
    
    def has_credentials(self) -> bool:
        """
        Check if credentials are stored
        
        Returns:
            True if credentials exist, False otherwise
        """
        credentials = self.get_credentials()
        return credentials is not None
    
    def update_username(self, username: str):
        """
        Update only the username
        
        Args:
            username: New username
        """
        try:
            keyring.set_password(self.service_name, USERNAME_KEY, username)
            logger.info("Username updated successfully")
        except Exception as e:
            logger.error(f"Error updating username: {str(e)}")
            raise
    
    def update_password(self, password: str):
        """
        Update only the password
        
        Args:
            password: New password
        """
        try:
            keyring.set_password(self.service_name, PASSWORD_KEY, password)
            logger.info("Password updated successfully")
        except Exception as e:
            logger.error(f"Error updating password: {str(e)}")
            raise
