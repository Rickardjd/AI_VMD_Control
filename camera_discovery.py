#!/usr/bin/env python3
"""
Camera Discovery Module
Uses i-PRO Easy IP Setup protocol to discover cameras on the network
Integrates with Camera AI-VMD Manager
"""

import socket
import struct
import logging
import json
import time
from typing import List, Optional, Dict
from dataclasses import dataclass
from enum import IntEnum

from camera_manager import Camera

logger = logging.getLogger(__name__)


class MessageType(IntEnum):
    """i-PRO Easy IP Setup protocol message types"""
    SEARCH_REQUEST = 0x0011
    SEARCH_RESPONSE = 0x0012
    CONFIG_REQUEST = 0x0021
    CONFIG_RESPONSE = 0x0022


@dataclass
class DiscoveredCamera:
    """Information about a discovered i-PRO camera"""
    mac_address: str
    model_name: str
    ip_address: str
    subnet_mask: str
    gateway: str
    http_port: int
    firmware_version: str
    camera_name: str
    serial_number: str
    network_mode: str
    
    def to_camera(self, installid: Optional[int] = None, enhanced_security: bool = True) -> Camera:
        """
        Convert DiscoveredCamera to Camera object for use with CameraManager
        
        Args:
            installid: Optional install ID (must be configured separately)
            enhanced_security: Enable i-PRO enhanced security
            
        Returns:
            Camera object
        """
        return Camera(
            mac_address=self.mac_address,
            model_name=self.model_name,
            ip_address=self.ip_address,
            subnet_mask=self.subnet_mask,
            gateway=self.gateway,
            http_port=self.http_port,
            firmware_version=self.firmware_version,
            camera_name=self.camera_name or self.model_name,
            installid=installid,
            enhanced_security=enhanced_security
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'mac_address': self.mac_address,
            'model_name': self.model_name,
            'ip_address': self.ip_address,
            'subnet_mask': self.subnet_mask,
            'gateway': self.gateway,
            'http_port': self.http_port,
            'firmware_version': self.firmware_version,
            'camera_name': self.camera_name,
            'serial_number': self.serial_number,
            'network_mode': self.network_mode
        }


class CameraDiscovery:
    """Discover i-PRO cameras using Easy IP Setup protocol"""
    
    # Protocol ports (correct based on packet capture)
    SEND_PORT = 10670  # Port to send discovery requests to
    RECEIVE_PORT = 10669  # Port to receive discovery responses on
    
    def __init__(self, timeout: float = 3.0, interface: str = '0.0.0.0', verbose: bool = False):
        """
        Initialize camera discovery
        
        Args:
            timeout: Discovery timeout in seconds
            interface: Network interface IP to bind to
            verbose: Enable verbose logging
        """
        self.timeout = timeout
        self.interface = interface
        self.verbose = verbose
        self.sock = None
        
        if verbose:
            logger.setLevel(logging.DEBUG)
    
    def _create_search_packet(self) -> bytes:
        """
        Create i-PRO Easy IP search request packet
        Based on actual packet capture from i-PRO Easy IP Setup Tool
        
        Returns:
            Binary packet data
        """
        packet = bytearray()
        
        # Get local MAC and IP for the packet
        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            local_ip_bytes = bytes(map(int, local_ip.split('.')))
        except:
            local_ip_bytes = bytes([192, 168, 1, 100])  # Fallback
        
        # Try to get MAC address
        import uuid
        try:
            mac = uuid.getnode()
            mac_bytes = mac.to_bytes(6, 'big')
        except:
            mac_bytes = bytes([0xa0, 0x29, 0x19, 0x3e, 0xab, 0x91])  # Fallback
        
        # Build packet based on capture
        # Header: 00 01 00 2a
        packet.extend([0x00, 0x01, 0x00, 0x2a])
        
        # Command: 00 0d 00 00 00 00 00 00
        packet.extend([0x00, 0x0d, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        
        # Source MAC address (6 bytes)
        packet.extend(mac_bytes)
        
        # Source IP address (4 bytes)
        packet.extend(local_ip_bytes)
        
        # Padding/flags: 00 00 20 11 1e 11 23 1f 1e 19 13
        packet.extend([0x00, 0x00, 0x20, 0x11, 0x1e, 0x11, 0x23, 0x1f, 0x1e, 0x19, 0x13])
        
        # More data: 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 00
        packet.extend([0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 
                      0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        
        # Category flags: ff f0
        packet.extend([0xff, 0xf0])
        
        # Supported models/types
        model_types = [
            0x00, 0x26, 0x00, 0x20, 0x00, 0x21, 0x00, 0x22, 0x00, 0x23, 
            0x00, 0x25, 0x00, 0x28, 0x00, 0x40, 0x00, 0x41, 0x00, 0x42, 
            0x00, 0x44, 0x00, 0xa5, 0x00, 0xa6, 0x00, 0xa7, 0x00, 0xa8, 
            0x00, 0xad, 0x00, 0xb3, 0x00, 0xb4, 0x00, 0xb7, 0x00, 0xb8, 
            0xff, 0xff
        ]
        packet.extend(model_types)
        
        logger.debug(f"Built search packet: {len(packet)} bytes")
        if self.verbose:
            logger.debug(f"Packet hex: {packet.hex()}")
        
        return bytes(packet)
    
    def _parse_search_response(self, data: bytes, addr: tuple) -> Optional[DiscoveredCamera]:
        """
        Parse i-PRO Easy IP search response packet using TLV format
        
        Args:
            data: Binary response data
            addr: Source address tuple (ip, port)
            
        Returns:
            DiscoveredCamera object or None if parsing fails
        """
        logger.debug(f"Received {len(data)} bytes from {addr}")
        
        if len(data) < 20:
            logger.warning(f"Packet too short: {len(data)} bytes")
            return None
        
        try:
            # Check header - should start with 00 01
            if data[0] != 0x00 or data[1] != 0x01:
                logger.warning(f"Invalid header: expected 00 01, got {data[0]:02x} {data[1]:02x}")
                return None
            
            # Response type in bytes 2-3
            response_type = struct.unpack(">H", data[2:4])[0]
            logger.debug(f"Response type: 0x{response_type:04x}")
            
            # Extract MAC address at offset 6
            mac_bytes = data[6:12]
            mac_address = ":".join(f"{b:02x}" for b in mac_bytes)
            logger.debug(f"Camera MAC: {mac_address}")
            
            # Parse TLV fields
            tlv_data = {}
            offset = 0x30  # TLV data starts around here
            
            while offset + 4 < len(data):
                # Check for end marker (ff ff)
                if data[offset:offset+2] == b'\xff\xff':
                    break
                
                # Read tag (2 bytes) and length (2 bytes)
                tag = struct.unpack(">H", data[offset:offset+2])[0]
                length = struct.unpack(">H", data[offset+2:offset+4])[0]
                
                if offset + 4 + length > len(data):
                    break
                
                # Read value
                value = data[offset+4:offset+4+length]
                tlv_data[tag] = value
                
                logger.debug(f"TLV: tag=0x{tag:02x}, len={length}, value={value.hex()}")
                
                offset += 4 + length
            
            # Extract fields from TLV data
            
            # Network mode
            network_mode = "Unknown"
            network_mode_value = None
            
            if 0x01 in tlv_data and len(tlv_data[0x01]) >= 1:
                network_mode_value = tlv_data[0x01][0]
            elif 0x00 in tlv_data and len(tlv_data[0x00]) >= 1:
                network_mode_value = tlv_data[0x00][0]
            elif len(data) > 0x32:
                network_mode_value = data[0x32]
            
            if network_mode_value is not None:
                network_modes = {
                    0: "DHCP",
                    3: "Static",
                    4: "Auto (AutoIP)",
                    5: "Auto Advanced"
                }
                network_mode = network_modes.get(network_mode_value, f"Unknown({network_mode_value})")
            
            # IP address (tag 0x20)
            ip_address = "0.0.0.0"
            if 0x20 in tlv_data and len(tlv_data[0x20]) >= 4:
                ip_bytes = tlv_data[0x20][:4]
                ip_address = ".".join(str(b) for b in ip_bytes)
            
            # Subnet mask (tag 0x21)
            subnet_mask = "0.0.0.0"
            if 0x21 in tlv_data and len(tlv_data[0x21]) >= 4:
                subnet_bytes = tlv_data[0x21][:4]
                subnet_mask = ".".join(str(b) for b in subnet_bytes)
            
            # Gateway (tag 0x22)
            gateway = "0.0.0.0"
            if 0x22 in tlv_data and len(tlv_data[0x22]) >= 4:
                gateway_bytes = tlv_data[0x22][:4]
                gateway = ".".join(str(b) for b in gateway_bytes)
            
            # HTTP port (tag 0x25)
            http_port = 80
            if 0x25 in tlv_data and len(tlv_data[0x25]) >= 2:
                http_port = struct.unpack(">H", tlv_data[0x25][:2])[0]
            
            # Serial number (tag 0xd1)
            serial_number = ""
            if 0xd1 in tlv_data:
                try:
                    serial_number = tlv_data[0xd1].decode('ascii', errors='ignore').rstrip('\x00').strip()
                except:
                    pass
            
            # Camera name (tag 0xa7)
            camera_name = ""
            if 0xa7 in tlv_data:
                try:
                    camera_name = tlv_data[0xa7].decode('ascii', errors='ignore').rstrip('\x00').strip()
                except:
                    pass
            
            # Model name (tag 0xa8)
            model_name = ""
            if 0xa8 in tlv_data:
                try:
                    model_name = tlv_data[0xa8].decode('ascii', errors='ignore').rstrip('\x00').strip()
                except:
                    pass
            
            # Firmware version (tag 0xa9)
            firmware_version = ""
            if 0xa9 in tlv_data:
                try:
                    firmware_version = tlv_data[0xa9].decode('ascii', errors='ignore').rstrip('\x00').strip()
                except:
                    pass
            
            # Use model name as camera name if camera name is empty
            if not camera_name and model_name:
                camera_name = model_name
            
            camera = DiscoveredCamera(
                mac_address=mac_address,
                model_name=model_name,
                ip_address=ip_address,
                subnet_mask=subnet_mask,
                gateway=gateway,
                http_port=http_port,
                firmware_version=firmware_version,
                camera_name=camera_name,
                serial_number=serial_number,
                network_mode=network_mode
            )
            
            logger.info(f"✓ Discovered camera: {camera.camera_name} ({camera.ip_address})")
            return camera
            
        except Exception as e:
            logger.error(f"Error parsing response: {e}", exc_info=self.verbose)
            return None
    
    def discover_cameras(self) -> List[DiscoveredCamera]:
        """
        Discover all i-PRO cameras on the network
        
        Returns:
            List of DiscoveredCamera objects
        """
        cameras = []
        seen_macs = set()  # Avoid duplicates
        
        try:
            # Create UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to receive port
            try:
                self.sock.bind((self.interface, self.RECEIVE_PORT))
                logger.info(f"Bound to {self.interface}:{self.RECEIVE_PORT}")
            except OSError as e:
                logger.error(f"Failed to bind to port {self.RECEIVE_PORT}: {e}")
                logger.info("Trying alternative binding...")
                self.sock.bind((self.interface, 0))
            
            # Set timeout
            self.sock.settimeout(self.timeout)
            
            # Send discovery broadcast
            search_packet = self._create_search_packet()
            broadcast_addr = ('255.255.255.255', self.SEND_PORT)
            
            logger.info(f"Sending discovery broadcast to {broadcast_addr}")
            bytes_sent = self.sock.sendto(search_packet, broadcast_addr)
            logger.info(f"Sent {bytes_sent} bytes")
            
            # Collect responses
            logger.info(f"Listening for responses (timeout: {self.timeout}s)...")
            start_time = time.time()
            response_count = 0
            
            while time.time() - start_time < self.timeout:
                remaining = self.timeout - (time.time() - start_time)
                logger.debug(f"Time remaining: {remaining:.2f}s")
                
                try:
                    # Receive response
                    data, addr = self.sock.recvfrom(4096)
                    response_count += 1
                    logger.info(f"Response #{response_count} from {addr}")
                    
                    # Parse response
                    camera = self._parse_search_response(data, addr)
                    
                    if camera and camera.mac_address not in seen_macs:
                        logger.info(f"✓ Valid camera found: {camera.model_name} ({camera.mac_address})")
                        cameras.append(camera)
                        seen_macs.add(camera.mac_address)
                    elif camera:
                        logger.debug(f"Duplicate camera response from {camera.mac_address}")
                
                except socket.timeout:
                    logger.debug("Socket timeout - no more responses")
                    break
                except Exception as e:
                    logger.error(f"Error receiving response: {e}", exc_info=self.verbose)
                    continue
            
            elapsed = time.time() - start_time
            logger.info("=" * 60)
            logger.info(f"Discovery complete in {elapsed:.2f}s")
            logger.info(f"Total responses received: {response_count}")
            logger.info(f"Valid cameras found: {len(cameras)}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Discovery error: {e}", exc_info=self.verbose)
        
        finally:
            if self.sock:
                self.sock.close()
        
        return cameras
    
    def discover_and_save(self, output_file: str = 'cameras.json', 
                         include_installid: bool = False,
                         default_installid: int = 272) -> List[Camera]:
        """
        Discover cameras and save to JSON file compatible with CameraManager
        
        Args:
            output_file: Path to output JSON file
            include_installid: Whether to include installid field
            default_installid: Default installid value (increments for each camera)
            
        Returns:
            List of Camera objects
        """
        discovered = self.discover_cameras()
        
        if not discovered:
            logger.warning("No cameras discovered")
            return []
        
        # Convert to Camera objects
        cameras = []
        installid = default_installid
        
        for disc_cam in discovered:
            cam = disc_cam.to_camera(
                installid=installid if include_installid else None,
                enhanced_security=True
            )
            cameras.append(cam)
            installid += 256  # Increment by 256 for next camera
        
        # Create JSON structure
        camera_data = {
            'count': len(cameras),
            'cameras': []
        }
        
        for cam in cameras:
            cam_dict = {
                'mac_address': cam.mac_address,
                'model_name': cam.model_name,
                'ip_address': cam.ip_address,
                'subnet_mask': cam.subnet_mask,
                'gateway': cam.gateway,
                'http_port': cam.http_port,
                'firmware_version': cam.firmware_version,
                'camera_name': cam.camera_name,
                'enhanced_security': cam.enhanced_security
            }
            
            if cam.installid is not None:
                cam_dict['installid'] = cam.installid
            
            camera_data['cameras'].append(cam_dict)
        
        # Save to file
        try:
            with open(output_file, 'w') as f:
                json.dump(camera_data, f, indent=2)
            
            logger.info(f"Saved {len(cameras)} cameras to {output_file}")
            print(f"\n✓ Discovered and saved {len(cameras)} cameras to {output_file}")
            print("\n📝 Next Steps:")
            print("   1. Reload the web application or restart it")
            print("   2. Go to the Cameras tab")
            print("   3. Click the ⚙️ button next to each camera to configure AI apps")
            print("   4. Select the AI applications you want to enable")
            print("   5. Save and test with the 🎮 control button")
            print("\nNote: AI apps will default to [272, 528, 784, 1040] until configured.\n")
            
        except Exception as e:
            logger.error(f"Error saving to file: {e}")
        
        return cameras


def print_discovered_cameras(cameras: List[DiscoveredCamera]):
    """
    Print discovered cameras in a formatted table
    
    Args:
        cameras: List of DiscoveredCamera objects
    """
    if not cameras:
        print("No cameras discovered.")
        return
    
    print(f"\nDiscovered {len(cameras)} camera(s):\n")
    print("-" * 100)
    print(f"{'Camera Name':<20} {'Model':<15} {'IP Address':<15} {'MAC Address':<17} {'Port':<6}")
    print("-" * 100)
    
    for camera in cameras:
        print(f"{camera.camera_name:<20} {camera.model_name:<15} {camera.ip_address:<15} "
              f"{camera.mac_address:<17} {camera.http_port:<6}")
    
    print("-" * 100)
