"""
Camera Group Manager
Handles organization of cameras into groups/buildings for batch operations
"""
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CameraGroup:
    """Camera group/building definition"""
    id: str
    name: str
    description: str
    camera_macs: List[str]  # List of camera MAC addresses
    enabled: bool = True
    status: str = "unknown"  # "armed", "disarmed", "unknown"
    last_action: Optional[str] = None  # ISO timestamp of last arm/disarm
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


class GroupManager:
    """Manages camera groups and their configurations"""
    
    def __init__(self, config_path: str = 'groups_config.json'):
        """
        Initialize Group Manager
        
        Args:
            config_path: Path to groups configuration file
        """
        self.config_path = config_path
        self.groups: Dict[str, CameraGroup] = {}
        self.load_groups()
    
    def load_groups(self):
        """Load groups from configuration file"""
        if not os.path.exists(self.config_path):
            logger.info(f"No existing groups config found at {self.config_path}")
            self._create_default_groups()
            return
        
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            
            self.groups = {}
            for group_data in data.get('groups', []):
                group = CameraGroup(**group_data)
                self.groups[group.id] = group
            
            logger.info(f"Loaded {len(self.groups)} groups from {self.config_path}")
            
        except Exception as e:
            logger.error(f"Error loading groups: {str(e)}")
            self._create_default_groups()
    
    def save_groups(self):
        """Save groups to configuration file"""
        try:
            data = {
                'groups': [group.to_dict() for group in self.groups.values()]
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(self.groups)} groups to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Error saving groups: {str(e)}")
            raise
    
    def _create_default_groups(self):
        """Create default example groups"""
        self.groups = {
            'building_a': CameraGroup(
                id='building_a',
                name='Building A',
                description='Main office building',
                camera_macs=[]
            ),
            'building_b': CameraGroup(
                id='building_b',
                name='Building B',
                description='Warehouse',
                camera_macs=[]
            ),
            'parking': CameraGroup(
                id='parking',
                name='Parking Areas',
                description='All parking lot cameras',
                camera_macs=[]
            )
        }
        self.save_groups()
        logger.info("Created default groups")
    
    def add_group(self, group_id: str, name: str, description: str, 
                  camera_macs: List[str] = None) -> CameraGroup:
        """
        Add a new group
        
        Args:
            group_id: Unique group identifier
            name: Group display name
            description: Group description
            camera_macs: List of camera MAC addresses
            
        Returns:
            Created CameraGroup object
        """
        if group_id in self.groups:
            raise ValueError(f"Group {group_id} already exists")
        
        group = CameraGroup(
            id=group_id,
            name=name,
            description=description,
            camera_macs=camera_macs or []
        )
        
        self.groups[group_id] = group
        self.save_groups()
        
        logger.info(f"Added group: {name} ({group_id})")
        return group
    
    def update_group(self, group_id: str, name: Optional[str] = None,
                     description: Optional[str] = None,
                     camera_macs: Optional[List[str]] = None,
                     enabled: Optional[bool] = None) -> CameraGroup:
        """
        Update an existing group
        
        Args:
            group_id: Group identifier
            name: New name (optional)
            description: New description (optional)
            camera_macs: New camera list (optional)
            enabled: New enabled status (optional)
            
        Returns:
            Updated CameraGroup object
        """
        if group_id not in self.groups:
            raise ValueError(f"Group {group_id} not found")
        
        group = self.groups[group_id]
        
        if name is not None:
            group.name = name
        if description is not None:
            group.description = description
        if camera_macs is not None:
            group.camera_macs = camera_macs
        if enabled is not None:
            group.enabled = enabled
        
        self.save_groups()
        
        logger.info(f"Updated group: {group.name} ({group_id})")
        return group
    
    def delete_group(self, group_id: str):
        """
        Delete a group
        
        Args:
            group_id: Group identifier
        """
        if group_id not in self.groups:
            raise ValueError(f"Group {group_id} not found")
        
        group_name = self.groups[group_id].name
        del self.groups[group_id]
        self.save_groups()
        
        logger.info(f"Deleted group: {group_name} ({group_id})")
    
    def get_group(self, group_id: str) -> Optional[CameraGroup]:
        """
        Get a group by ID
        
        Args:
            group_id: Group identifier
            
        Returns:
            CameraGroup object or None
        """
        return self.groups.get(group_id)
    
    def get_all_groups(self) -> List[CameraGroup]:
        """
        Get all groups
        
        Returns:
            List of CameraGroup objects
        """
        return list(self.groups.values())
    
    def add_camera_to_group(self, group_id: str, camera_mac: str):
        """
        Add a camera to a group
        
        Args:
            group_id: Group identifier
            camera_mac: Camera MAC address
        """
        if group_id not in self.groups:
            raise ValueError(f"Group {group_id} not found")
        
        group = self.groups[group_id]
        
        if camera_mac not in group.camera_macs:
            group.camera_macs.append(camera_mac)
            self.save_groups()
            logger.info(f"Added camera {camera_mac} to group {group.name}")
        else:
            logger.warning(f"Camera {camera_mac} already in group {group.name}")
    
    def remove_camera_from_group(self, group_id: str, camera_mac: str):
        """
        Remove a camera from a group
        
        Args:
            group_id: Group identifier
            camera_mac: Camera MAC address
        """
        if group_id not in self.groups:
            raise ValueError(f"Group {group_id} not found")
        
        group = self.groups[group_id]
        
        if camera_mac in group.camera_macs:
            group.camera_macs.remove(camera_mac)
            self.save_groups()
            logger.info(f"Removed camera {camera_mac} from group {group.name}")
        else:
            logger.warning(f"Camera {camera_mac} not in group {group.name}")
    
    def get_cameras_in_group(self, group_id: str, all_cameras: List) -> List:
        """
        Get all cameras in a group
        
        Args:
            group_id: Group identifier
            all_cameras: List of all Camera objects
            
        Returns:
            List of Camera objects in the group
        """
        if group_id not in self.groups:
            raise ValueError(f"Group {group_id} not found")
        
        group = self.groups[group_id]
        
        # Create MAC to camera mapping
        mac_to_camera = {cam.mac_address: cam for cam in all_cameras}
        
        # Get cameras in this group
        group_cameras = []
        for mac in group.camera_macs:
            if mac in mac_to_camera:
                group_cameras.append(mac_to_camera[mac])
            else:
                logger.warning(f"Camera with MAC {mac} not found in camera list")
        
        return group_cameras
    
    def update_group_status(self, group_id: str, status: str):
        """
        Update the armed/disarmed status of a group
        
        Args:
            group_id: Group identifier
            status: "armed" or "disarmed"
        """
        if group_id not in self.groups:
            raise ValueError(f"Group {group_id} not found")
        
        from datetime import datetime
        
        group = self.groups[group_id]
        group.status = status
        group.last_action = datetime.utcnow().isoformat() + 'Z'
        
        # Save to file
        self.save_groups()
        
        logger.info(f"Updated group {group.name} status to {status}")
