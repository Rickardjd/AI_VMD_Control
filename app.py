"""
Flask Web Application for Camera AI-VMD Manager
Provides REST API and web interface for managing camera groups
"""
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect
from flask_cors import CORS
import os
import logging
from typing import List, Dict
import json

import re
import uuid

from camera_manager import CameraManager, Camera, VMDMode, load_cameras_from_json
from group_manager import GroupManager, CameraGroup
from credential_manager import CredentialManager
from camera_discovery import CameraDiscovery, print_discovered_cameras
from ai_apps import get_ai_apps_dict, get_ai_app_name, AI_APPS
from auth_manager import AuthenticationManager
from session_manager import SessionManager
from activity_logger import ActivityLogger


def parse_ip_input(ip_input: str) -> List[str]:
    """
    Parse IP address input that can be a single IP or a range.

    Supported formats:
    - Single IP: "192.168.1.10"
    - IP range with last octet: "192.168.1.10-20" (expands to 192.168.1.10 through 192.168.1.20)
    - Full IP range: "192.168.1.10-192.168.1.20"
    - Multiple entries separated by commas or newlines

    Args:
        ip_input: String containing IP address(es) or range(s)

    Returns:
        List of individual IP addresses
    """
    ip_list = []

    # Split by comma or newline
    entries = re.split(r'[,\n]+', ip_input.strip())

    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # Check if it's a range
        if '-' in entry:
            # Check if it's a full IP range (e.g., 192.168.1.10-192.168.1.20)
            if entry.count('.') > 3:
                parts = entry.split('-')
                if len(parts) == 2:
                    start_ip = parts[0].strip()
                    end_ip = parts[1].strip()

                    # Validate both IPs
                    if not is_valid_ip(start_ip) or not is_valid_ip(end_ip):
                        continue

                    # Get the last octets
                    start_octets = start_ip.split('.')
                    end_octets = end_ip.split('.')

                    # Ensure same subnet
                    if start_octets[:3] != end_octets[:3]:
                        # Different subnets - just add both IPs
                        ip_list.append(start_ip)
                        ip_list.append(end_ip)
                    else:
                        # Same subnet - expand range
                        start_last = int(start_octets[3])
                        end_last = int(end_octets[3])

                        for i in range(min(start_last, end_last), max(start_last, end_last) + 1):
                            ip_list.append(f"{start_octets[0]}.{start_octets[1]}.{start_octets[2]}.{i}")
            else:
                # Short format range (e.g., 192.168.1.10-20)
                parts = entry.split('-')
                if len(parts) == 2:
                    base_ip = parts[0].strip()
                    end_octet = parts[1].strip()

                    if is_valid_ip(base_ip) and end_octet.isdigit():
                        base_octets = base_ip.split('.')
                        start_last = int(base_octets[3])
                        end_last = int(end_octet)

                        if 0 <= end_last <= 255:
                            for i in range(min(start_last, end_last), max(start_last, end_last) + 1):
                                ip_list.append(f"{base_octets[0]}.{base_octets[1]}.{base_octets[2]}.{i}")
        else:
            # Single IP
            if is_valid_ip(entry):
                ip_list.append(entry)

    return ip_list


def is_valid_ip(ip: str) -> bool:
    """
    Validate an IPv4 address.

    Args:
        ip: IP address string

    Returns:
        True if valid, False otherwise
    """
    pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(pattern, ip)

    if not match:
        return False

    # Check each octet is in valid range
    for group in match.groups():
        if not 0 <= int(group) <= 255:
            return False

    return True


def generate_mac_address() -> str:
    """
    Generate a pseudo-random MAC address for manually added cameras.
    Uses a local administered address prefix (02:xx:xx:xx:xx:xx).

    Returns:
        MAC address string in format xx:xx:xx:xx:xx:xx
    """
    # Generate random bytes
    random_bytes = uuid.uuid4().bytes[:5]

    # Use 02 as first octet (locally administered, unicast)
    mac = '02:' + ':'.join(f'{b:02x}' for b in random_bytes)

    return mac


def fetch_camera_info_by_ip(ip_address: str, http_port: int = 80, username: str = None, password: str = None) -> dict:
    """
    Fetch camera information directly from the device by IP address.
    Tries Digest Auth first, then falls back to Basic Auth.

    Args:
        ip_address: Camera IP address
        http_port: HTTP port (default 80)
        username: Camera username
        password: Camera password

    Returns:
        Dict with camera_name, model_name, mac_address (or None for each if not found)
    """
    import requests
    from requests.auth import HTTPDigestAuth, HTTPBasicAuth

    result = {
        'camera_name': None,
        'model_name': None,
        'mac_address': None,
        'success': False,
        'errors': []
    }

    if not username or not password:
        result['errors'].append('No credentials provided')
        return result

    protocol = "https" if http_port == 443 else "http"
    base_url = f"{protocol}://{ip_address}:{http_port}"

    # Auth methods to try
    auth_methods = [
        ('Digest', HTTPDigestAuth(username, password)),
        ('Basic', HTTPBasicAuth(username, password))
    ]

    # Fetch camera title from /cgi-bin/getdata
    for auth_name, auth_method in auth_methods:
        try:
            response = requests.get(
                f"{base_url}/cgi-bin/getdata",
                auth=auth_method,
                timeout=10,
                verify=False
            )
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    line = line.strip()
                    # Handle both formats: CAMTITLE=value and CAMTITLE,"value"
                    if line.startswith('CAMTITLE'):
                        if 'CAMTITLE=' in line:
                            result['camera_name'] = line.split('CAMTITLE=', 1)[1].strip().strip('"')
                        elif 'CAMTITLE,' in line:
                            # CSV format: CAMTITLE,"value"
                            parts = line.split(',', 1)
                            if len(parts) > 1:
                                result['camera_name'] = parts[1].strip().strip('"')
                        break
                break  # Success, don't try other auth methods
            elif response.status_code not in [401, 403]:
                result['errors'].append(f"getdata returned HTTP {response.status_code}")
                break
        except requests.exceptions.Timeout:
            result['errors'].append(f"Timeout connecting to {ip_address}")
            break
        except Exception as e:
            result['errors'].append(f"Failed to fetch camera title: {str(e)}")
            break

    # Fetch MAC and model from /cgi-bin/getinfo?FILE=1
    for auth_name, auth_method in auth_methods:
        try:
            response = requests.get(
                f"{base_url}/cgi-bin/getinfo?FILE=1",
                auth=auth_method,
                timeout=10,
                verify=False
            )
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    line = line.strip()
                    if line.startswith('MAC='):
                        mac_raw = line.split('MAC=', 1)[1].strip()
                        # Normalize MAC address to use colons
                        # Handle formats: d42dc52a8d13, d4-2d-c5-2a-8d-13, d4:2d:c5:2a:8d:13
                        mac_clean = mac_raw.replace('-', '').replace(':', '').lower()
                        if len(mac_clean) == 12:
                            result['mac_address'] = ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2))
                        else:
                            result['mac_address'] = mac_raw.lower().replace('-', ':')
                    elif line.startswith('NAME='):
                        result['model_name'] = line.split('NAME=', 1)[1].strip()
                break  # Success, don't try other auth methods
            elif response.status_code not in [401, 403]:
                result['errors'].append(f"getinfo returned HTTP {response.status_code}")
                break
        except requests.exceptions.Timeout:
            if f"Timeout connecting to {ip_address}" not in result['errors']:
                result['errors'].append(f"Timeout connecting to {ip_address}")
            break
        except Exception as e:
            result['errors'].append(f"Failed to fetch MAC/model: {str(e)}")
            break

    # Mark as success if we got at least some data
    if result['camera_name'] or result['model_name'] or result['mac_address']:
        result['success'] = True

    return result

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Configuration
CAMERAS_FILE = os.environ.get('CAMERAS_FILE', 'cameras.json')
GROUPS_FILE = os.environ.get('GROUPS_FILE', 'groups_config.json')

# Initialize managers
credential_manager = CredentialManager()
group_manager = GroupManager(GROUPS_FILE)
auth_manager = AuthenticationManager()
session_manager = SessionManager()
activity_logger = ActivityLogger()

# Global cameras list
cameras_list: List[Camera] = []


def load_cameras():
    """Load cameras from JSON file"""
    global cameras_list
    try:
        cameras_list = load_cameras_from_json(CAMERAS_FILE)
        logger.info(f"Loaded {len(cameras_list)} cameras")
    except Exception as e:
        logger.error(f"Error loading cameras: {str(e)}")
        cameras_list = []


def get_camera_manager():
    """Get CameraManager instance with credentials"""
    credentials = credential_manager.get_credentials()
    if not credentials:
        raise ValueError("Credentials not configured. Please set credentials first.")
    
    username, password = credentials
    return CameraManager(username, password)


# API Routes

# Authentication decorator
from functools import wraps

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get token from cookie or header
        token = request.cookies.get('session_token')
        if not token:
            token = request.headers.get('Authorization')
            if token and token.startswith('Bearer '):
                token = token[7:]  # Remove 'Bearer ' prefix
        
        if not token:
            return jsonify({
                'success': False,
                'message': 'Authentication required',
                'error': 'NO_TOKEN'
            }), 401
        
        # Validate session
        session = session_manager.get_session(token)
        if not session:
            return jsonify({
                'success': False,
                'message': 'Invalid or expired session',
                'error': 'INVALID_SESSION'
            }), 401
        
        # Add session to request context
        request.session = session
        return f(*args, **kwargs)
    
    return decorated_function


def require_admin(f):
    """Decorator to require admin role"""
    @wraps(f)
    @require_auth
    def decorated_function(*args, **kwargs):
        if request.session.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


# Public routes (no authentication required)

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """User login"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({
            'success': False,
            'message': 'Username and password required'
        }), 400
    
    # Verify credentials
    if auth_manager.verify_password(username, password):
        # Get user info
        user = auth_manager.get_user(username)
        
        # Create session
        token = session_manager.create_session(username, user.role)
        
        # Create response
        response = jsonify({
            'success': True,
            'message': 'Login successful',
            'user': {
                'username': username,
                'role': user.role
            }
        })
        
        # Set session cookie (httpOnly for security)
        response.set_cookie(
            'session_token',
            token,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite='Lax',
            max_age=24*60*60  # 24 hours
        )
        
        return response
    else:
        return jsonify({
            'success': False,
            'message': 'Invalid username or password'
        }), 401


@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def api_logout():
    """User logout"""
    token = request.cookies.get('session_token')
    if token:
        session_manager.destroy_session(token)
    
    response = jsonify({
        'success': True,
        'message': 'Logged out successfully'
    })
    
    # Clear session cookie
    response.set_cookie('session_token', '', expires=0)
    
    return response


@app.route('/api/auth/check', methods=['GET'])
def api_check_auth():
    """Check if user is authenticated"""
    token = request.cookies.get('session_token')
    if not token:
        return jsonify({
            'authenticated': False
        })
    
    session = session_manager.get_session(token)
    if session:
        return jsonify({
            'authenticated': True,
            'user': {
                'username': session.username,
                'role': session.role
            }
        })
    else:
        return jsonify({
            'authenticated': False
        })


# User management routes (admin only)

@app.route('/api/users', methods=['GET'])
@require_admin
@require_auth
def api_list_users():
    """List all users (admin only)"""
    users = auth_manager.list_users()
    return jsonify({
        'success': True,
        'users': users,
        'count': len(users)
    })


@app.route('/api/users', methods=['POST'])
@require_admin
@require_auth
def api_create_user():
    """Create new user (admin only)"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')
    
    if not username or not password:
        return jsonify({
            'success': False,
            'message': 'Username and password required'
        }), 400
    
    if auth_manager.create_user(username, password, role):
        return jsonify({
            'success': True,
            'message': f'User {username} created successfully'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to create user (may already exist)'
        }), 400


@app.route('/api/users/<username>', methods=['DELETE'])
@require_admin
@require_auth
def api_delete_user(username):
    """Delete user (admin only)"""
    if auth_manager.delete_user(username):
        # Destroy all sessions for this user
        session_manager.destroy_user_sessions(username)
        
        return jsonify({
            'success': True,
            'message': f'User {username} deleted successfully'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to delete user'
        }), 400


@app.route('/api/users/<username>/reset-password', methods=['POST'])
@require_admin
@require_auth
def api_admin_reset_password(username):
    """Reset user password (admin only)"""
    data = request.json
    new_password = data.get('new_password')
    
    if not new_password:
        return jsonify({
            'success': False,
            'message': 'New password required'
        }), 400
    
    if auth_manager.reset_password(username, new_password):
        # Destroy all sessions for this user (force re-login)
        session_manager.destroy_user_sessions(username)
        
        return jsonify({
            'success': True,
            'message': f'Password reset for user {username}'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to reset password'
        }), 400


@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def api_change_password():
    """Change own password"""
    data = request.json
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not old_password or not new_password:
        return jsonify({
            'success': False,
            'message': 'Old and new passwords required'
        }), 400
    
    username = request.session.username
    
    if auth_manager.change_password(username, old_password, new_password):
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to change password (incorrect old password?)'
        }), 400


# Protected routes - Add @require_auth to existing routes

@app.route('/')
def index():
    """Serve main web interface"""
    # Check if user is authenticated
    token = request.cookies.get('session_token')
    if token:
        session = session_manager.get_session(token)
        if session:
            # Authenticated - serve main app
            return render_template('index.html')
    
    # Not authenticated - redirect to login
    return redirect('/login')


@app.route('/login')
def login_page():
    """Serve login page"""
    # If already authenticated, redirect to main app
    token = request.cookies.get('session_token')
    if token:
        session = session_manager.get_session(token)
        if session:
            return redirect('/')
    
    return render_template('login.html')


@app.route('/api/status')
@require_auth
def api_status():
    """Get system status"""
    has_credentials = credential_manager.has_credentials()
    cameras_loaded = len(cameras_list) > 0
    
    return jsonify({
        'success': True,
        'status': {
            'credentials_configured': has_credentials,
            'cameras_loaded': cameras_loaded,
            'camera_count': len(cameras_list),
            'group_count': len(group_manager.get_all_groups())
        }
    })


@app.route('/api/credentials', methods=['GET', 'POST', 'DELETE'])
@require_auth
def api_credentials():
    """Manage credentials"""
    if request.method == 'GET':
        has_creds = credential_manager.has_credentials()
        username = None
        
        if has_creds:
            creds = credential_manager.get_credentials()
            username = creds[0] if creds else None
        
        return jsonify({
            'success': True,
            'configured': has_creds,
            'username': username
        })
    
    elif request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Username and password required'
            }), 400
        
        try:
            credential_manager.store_credentials(username, password)
            return jsonify({
                'success': True,
                'message': 'Credentials stored successfully'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error storing credentials: {str(e)}'
            }), 500
    
    elif request.method == 'DELETE':
        try:
            credential_manager.delete_credentials()
            return jsonify({
                'success': True,
                'message': 'Credentials deleted successfully'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error deleting credentials: {str(e)}'
            }), 500


@app.route('/api/cameras', methods=['GET'])
@require_auth
def api_cameras():
    """Get all cameras"""
    cameras_data = [
        {
            'mac_address': cam.mac_address,
            'model_name': cam.model_name,
            'ip_address': cam.ip_address,
            'camera_name': cam.camera_name,
            'http_port': cam.http_port,
            'firmware_version': cam.firmware_version,
            'installids': cam.installids  # Return the array, not single installid
        } for cam in cameras_list
    ]
    
    return jsonify({
        'success': True,
        'cameras': cameras_data,
        'count': len(cameras_data)
    })


@app.route('/api/cameras/reload', methods=['POST'])
@require_auth
def api_cameras_reload():
    """Reload cameras from file"""
    try:
        load_cameras()
        return jsonify({
            'success': True,
            'message': f'Reloaded {len(cameras_list)} cameras',
            'count': len(cameras_list)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error reloading cameras: {str(e)}'
        }), 500


@app.route('/api/cameras/<mac_address>/test', methods=['POST'])
@require_auth
def api_camera_test(mac_address):
    """Test connection to a specific camera"""
    try:
        camera_manager = get_camera_manager()
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    
    # Find camera
    camera = next((c for c in cameras_list if c.mac_address == mac_address), None)
    if not camera:
        return jsonify({
            'success': False,
            'message': 'Camera not found'
        }), 404
    
    # Test connection
    result = camera_manager.test_connection(camera)
    
    return jsonify({
        'success': result.success,
        'camera_name': result.camera_name,
        'ip_address': result.ip_address,
        'message': result.message,
        'response_code': result.response_code
    })


@app.route('/api/cameras/discover', methods=['POST'])
@require_auth
def api_cameras_discover():
    """Discover cameras on the network using i-PRO Easy IP protocol"""
    try:
        data = request.json or {}
        timeout = data.get('timeout', 3.0)
        save_to_file = data.get('save', False)
        
        logger.info(f"Starting camera discovery (timeout={timeout}s)")
        
        # Run discovery
        discovery = CameraDiscovery(timeout=timeout, verbose=False)
        discovered = discovery.discover_cameras()
        
        if not discovered:
            return jsonify({
                'success': True,
                'message': 'No cameras discovered on the network',
                'cameras': [],
                'count': 0
            })
        
        # Convert to dict format
        cameras_data = [cam.to_dict() for cam in discovered]
        
        # Optionally save to file
        if save_to_file:
            try:
                discovery.discover_and_save(
                    output_file=CAMERAS_FILE,
                    include_installid=False  # User must configure installid manually
                )
                # Reload cameras in memory
                load_cameras()
            except Exception as e:
                logger.error(f"Error saving discovered cameras: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Discovery succeeded but failed to save: {str(e)}',
                    'cameras': cameras_data,
                    'count': len(cameras_data)
                }), 500
        
        return jsonify({
            'success': True,
            'message': f'Discovered {len(discovered)} cameras',
            'cameras': cameras_data,
            'count': len(cameras_data),
            'saved': save_to_file
        })
        
    except Exception as e:
        logger.error(f"Discovery error: {e}")
        return jsonify({
            'success': False,
            'message': f'Discovery failed: {str(e)}'
        }), 500


@app.route('/api/ai-apps', methods=['GET'])
@require_auth
def api_ai_apps():
    """Get all available AI applications with human-readable names"""
    return jsonify({
        'success': True,
        'ai_apps': get_ai_apps_dict()
    })


@app.route('/api/cameras/add-manual', methods=['POST'])
@require_admin
def api_cameras_add_manual():
    """
    Add cameras manually by IP address or IP range.
    Automatically queries devices for MAC, model, and camera name.

    Supports:
    - Single IP: "192.168.1.10"
    - IP range with last octet: "192.168.1.10-20"
    - Full IP range: "192.168.1.10-192.168.1.20"
    - Multiple entries separated by commas or newlines
    """
    global cameras_list

    try:
        data = request.json or {}
        ip_input = data.get('ip_addresses', '')
        http_port = data.get('http_port', 80)
        camera_name_prefix = data.get('camera_name_prefix', 'Manual Camera')
        enhanced_security = data.get('enhanced_security', True)

        if not ip_input:
            return jsonify({
                'success': False,
                'message': 'IP address(es) required'
            }), 400

        # Parse IP addresses
        ip_addresses = parse_ip_input(ip_input)

        if not ip_addresses:
            return jsonify({
                'success': False,
                'message': 'No valid IP addresses found in input'
            }), 400

        # Get credentials for querying cameras
        creds = credential_manager.get_credentials()
        username, password = creds if creds else (None, None)

        # Get existing MAC addresses to avoid duplicates
        existing_macs = {cam.mac_address for cam in cameras_list}
        existing_ips = {cam.ip_address for cam in cameras_list}

        # Track results
        added_cameras = []
        skipped_ips = []

        for ip in ip_addresses:
            # Skip if IP already exists
            if ip in existing_ips:
                skipped_ips.append({'ip': ip, 'reason': 'IP already exists'})
                continue

            # Try to fetch camera info from device
            device_info = fetch_camera_info_by_ip(ip, int(http_port), username, password)

            # Use fetched MAC or generate one
            if device_info.get('mac_address') and device_info['mac_address'] not in existing_macs:
                mac = device_info['mac_address']
            else:
                mac = generate_mac_address()
                while mac in existing_macs:
                    mac = generate_mac_address()
            existing_macs.add(mac)

            # Use fetched camera name or generate one
            if device_info.get('camera_name'):
                camera_name = device_info['camera_name']
            else:
                camera_index = len(cameras_list) + len(added_cameras) + 1
                camera_name = f"{camera_name_prefix} {camera_index}" if camera_name_prefix else f"Camera {ip}"

            # Use fetched model or default
            model_name = device_info.get('model_name') or 'Manual'

            # Create camera object (only include fields that Camera dataclass accepts)
            camera_data = {
                'mac_address': mac,
                'model_name': model_name,
                'ip_address': ip,
                'subnet_mask': '255.255.255.0',
                'gateway': '.'.join(ip.split('.')[:3]) + '.1',
                'http_port': int(http_port),
                'firmware_version': 'Unknown',
                'camera_name': camera_name,
                'installids': [],
                'enhanced_security': enhanced_security,
                'actual_app_count': 0
            }

            added_cameras.append(camera_data)

        if not added_cameras:
            return jsonify({
                'success': False,
                'message': 'No new cameras to add. All IPs already exist.',
                'skipped': skipped_ips
            }), 400

        # Load existing cameras.json
        try:
            with open(CAMERAS_FILE, 'r') as f:
                camera_file_data = json.load(f)
        except FileNotFoundError:
            camera_file_data = {'count': 0, 'cameras': []}

        # Add new cameras to file
        for cam_data in added_cameras:
            camera_file_data['cameras'].append(cam_data)

        camera_file_data['count'] = len(camera_file_data['cameras'])

        # Save to file
        with open(CAMERAS_FILE, 'w') as f:
            json.dump(camera_file_data, f, indent=2)

        # Reload cameras in memory
        load_cameras()

        logger.info(f"Added {len(added_cameras)} cameras manually")

        return jsonify({
            'success': True,
            'message': f'Added {len(added_cameras)} camera(s) successfully',
            'added': added_cameras,
            'skipped': skipped_ips,
            'total_cameras': len(cameras_list)
        })

    except Exception as e:
        logger.error(f"Error adding manual cameras: {e}")
        return jsonify({
            'success': False,
            'message': f'Error adding cameras: {str(e)}'
        }), 500


@app.route('/api/cameras/<mac_address>/fetch-info', methods=['GET'])
@require_admin
def api_camera_fetch_info(mac_address):
    """Fetch camera information directly from the device"""
    global cameras_list

    try:
        # Find camera
        camera = next((c for c in cameras_list if c.mac_address == mac_address), None)
        if not camera:
            return jsonify({
                'success': False,
                'message': 'Camera not found'
            }), 404

        # Get credentials
        creds = credential_manager.get_credentials()
        if not creds:
            return jsonify({
                'success': False,
                'message': 'No camera credentials configured'
            }), 400

        username, password = creds
        protocol = "https" if camera.http_port == 443 else "http"
        base_url = f"{protocol}://{camera.ip_address}:{camera.http_port}"

        fetched_data = {}
        errors = []

        # Import auth classes
        from requests.auth import HTTPDigestAuth, HTTPBasicAuth
        import requests

        # Fetch camera title from /cgi-bin/getdata
        try:
            response = requests.get(
                f"{base_url}/cgi-bin/getdata",
                auth=HTTPDigestAuth(username, password),
                timeout=10,
                verify=False
            )
            if response.status_code == 200:
                # Parse response - handle both CAMTITLE=value and CAMTITLE,"value" formats
                for line in response.text.split('\n'):
                    line = line.strip()
                    if line.startswith('CAMTITLE'):
                        if 'CAMTITLE=' in line:
                            fetched_data['camera_name'] = line.split('CAMTITLE=', 1)[1].strip().strip('"')
                        elif 'CAMTITLE,' in line:
                            parts = line.split(',', 1)
                            if len(parts) > 1:
                                fetched_data['camera_name'] = parts[1].strip().strip('"')
                        break
            else:
                errors.append(f"getdata returned HTTP {response.status_code}")
        except Exception as e:
            errors.append(f"Failed to fetch camera title: {str(e)}")

        # Fetch MAC and model from /cgi-bin/getinfo?FILE=1
        try:
            response = requests.get(
                f"{base_url}/cgi-bin/getinfo?FILE=1",
                auth=HTTPDigestAuth(username, password),
                timeout=10,
                verify=False
            )
            if response.status_code == 200:
                # Parse response - look for MAC= and NAME=
                for line in response.text.split('\n'):
                    line = line.strip()
                    if line.startswith('MAC='):
                        mac_raw = line.split('MAC=', 1)[1].strip()
                        # Normalize MAC address to use colons
                        # Handle formats: d42dc52a8d13, d4-2d-c5-2a-8d-13, d4:2d:c5:2a:8d:13
                        mac_clean = mac_raw.replace('-', '').replace(':', '').lower()
                        if len(mac_clean) == 12:
                            fetched_data['mac_address'] = ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2))
                        else:
                            fetched_data['mac_address'] = mac_raw.lower().replace('-', ':')
                    elif line.startswith('NAME='):
                        fetched_data['model_name'] = line.split('NAME=', 1)[1].strip()
            else:
                errors.append(f"getinfo returned HTTP {response.status_code}")
        except Exception as e:
            errors.append(f"Failed to fetch MAC/model: {str(e)}")

        if not fetched_data:
            return jsonify({
                'success': False,
                'message': 'Could not fetch any data from camera',
                'errors': errors
            }), 500

        logger.info(f"Fetched info from camera {camera.ip_address}: {fetched_data}")

        return jsonify({
            'success': True,
            'message': 'Camera info fetched successfully',
            'data': fetched_data,
            'errors': errors if errors else None
        })

    except Exception as e:
        logger.error(f"Error fetching camera info: {e}")
        return jsonify({
            'success': False,
            'message': f'Error fetching camera info: {str(e)}'
        }), 500


@app.route('/api/cameras/<mac_address>/update', methods=['PUT'])
@require_admin
def api_camera_update(mac_address):
    """Update camera properties (MAC address, model, camera name)"""
    global cameras_list

    try:
        data = request.json or {}

        # Find camera
        camera = next((c for c in cameras_list if c.mac_address == mac_address), None)
        if not camera:
            return jsonify({
                'success': False,
                'message': 'Camera not found'
            }), 404

        # Get new values (use existing if not provided)
        new_mac = data.get('mac_address', camera.mac_address).strip().lower()
        new_model = data.get('model_name', camera.model_name).strip()
        new_name = data.get('camera_name', camera.camera_name).strip()

        # Validate MAC address format if changed
        if new_mac != camera.mac_address:
            mac_pattern = r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$'
            if not re.match(mac_pattern, new_mac):
                return jsonify({
                    'success': False,
                    'message': 'Invalid MAC address format. Use format: xx:xx:xx:xx:xx:xx'
                }), 400

            # Check for duplicate MAC
            existing = next((c for c in cameras_list if c.mac_address == new_mac), None)
            if existing:
                return jsonify({
                    'success': False,
                    'message': f'MAC address already exists for camera "{existing.camera_name}"'
                }), 400

        # Validate camera name
        if not new_name:
            return jsonify({
                'success': False,
                'message': 'Camera name cannot be empty'
            }), 400

        # Load existing cameras.json
        with open(CAMERAS_FILE, 'r') as f:
            camera_file_data = json.load(f)

        # Update camera in file
        for cam in camera_file_data['cameras']:
            if cam.get('mac_address') == mac_address:
                cam['mac_address'] = new_mac
                cam['model_name'] = new_model
                cam['camera_name'] = new_name
                break

        # Save to file
        with open(CAMERAS_FILE, 'w') as f:
            json.dump(camera_file_data, f, indent=2)

        # Update in memory
        camera.mac_address = new_mac
        camera.model_name = new_model
        camera.camera_name = new_name

        logger.info(f"Updated camera: {new_name} ({new_mac})")

        return jsonify({
            'success': True,
            'message': f'Camera "{new_name}" updated successfully',
            'camera': {
                'mac_address': new_mac,
                'model_name': new_model,
                'camera_name': new_name
            }
        })

    except Exception as e:
        logger.error(f"Error updating camera: {e}")
        return jsonify({
            'success': False,
            'message': f'Error updating camera: {str(e)}'
        }), 500


@app.route('/api/cameras/<mac_address>', methods=['DELETE'])
@require_admin
def api_camera_delete(mac_address):
    """Delete a camera by MAC address"""
    global cameras_list

    try:
        # Find camera
        camera = next((c for c in cameras_list if c.mac_address == mac_address), None)
        if not camera:
            return jsonify({
                'success': False,
                'message': 'Camera not found'
            }), 404

        camera_name = camera.camera_name

        # Load existing cameras.json
        with open(CAMERAS_FILE, 'r') as f:
            camera_file_data = json.load(f)

        # Remove camera from list
        camera_file_data['cameras'] = [
            c for c in camera_file_data['cameras']
            if c.get('mac_address') != mac_address
        ]
        camera_file_data['count'] = len(camera_file_data['cameras'])

        # Save to file
        with open(CAMERAS_FILE, 'w') as f:
            json.dump(camera_file_data, f, indent=2)

        # Reload cameras in memory
        load_cameras()

        logger.info(f"Deleted camera: {camera_name} ({mac_address})")

        return jsonify({
            'success': True,
            'message': f'Camera "{camera_name}" deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting camera: {e}")
        return jsonify({
            'success': False,
            'message': f'Error deleting camera: {str(e)}'
        }), 500


@app.route('/api/cameras/<mac_address>', methods=['GET'])
@require_auth
def api_camera_detail(mac_address):
    """Get detailed information about a specific camera"""
    camera = next((c for c in cameras_list if c.mac_address == mac_address), None)
    if not camera:
        return jsonify({
            'success': False,
            'message': 'Camera not found'
        }), 404
    
    # Get AI app names
    ai_apps_info = []
    if camera.installids:
        for app_id in camera.installids:
            ai_apps_info.append({
                'id': app_id,
                'name': get_ai_app_name(app_id)
            })
    
    return jsonify({
        'success': True,
        'camera': {
            'mac_address': camera.mac_address,
            'model_name': camera.model_name,
            'ip_address': camera.ip_address,
            'camera_name': camera.camera_name,
            'http_port': camera.http_port,
            'firmware_version': camera.firmware_version,
            'installids': camera.installids,
            'ai_apps': ai_apps_info,
            'enhanced_security': camera.enhanced_security
        }
    })


@app.route('/api/cameras/<mac_address>/installids', methods=['PUT'])
@require_admin
def api_camera_update_installids(mac_address):
    """Update AI app install IDs for a specific camera"""
    camera = next((c for c in cameras_list if c.mac_address == mac_address), None)
    if not camera:
        return jsonify({
            'success': False,
            'message': 'Camera not found'
        }), 404
    
    data = request.json
    installids = data.get('installids', [])
    
    if not isinstance(installids, list):
        return jsonify({
            'success': False,
            'message': 'installids must be an array'
        }), 400
    
    # Update camera in memory
    camera.installids = installids
    
    # Query camera for actual installed app count and save it
    try:
        camera_manager = get_camera_manager()
        installed_apps_result = camera_manager.get_installed_apps(camera)
        if installed_apps_result.get('success'):
            camera.actual_app_count = installed_apps_result.get('app_count', 0)
            logger.info(f"Updated actual app count for {camera.camera_name}: {camera.actual_app_count}")
        else:
            # If query fails, use configured count
            camera.actual_app_count = len(installids)
    except Exception as e:
        logger.warning(f"Could not query actual apps for {camera.camera_name}: {e}")
        camera.actual_app_count = len(installids)
    
    # Save to cameras.json
    try:
        import json
        camera_data = {
            'count': len(cameras_list),
            'cameras': []
        }
        
        for cam in cameras_list:
            cam_dict = {
                'mac_address': cam.mac_address,
                'model_name': cam.model_name,
                'ip_address': cam.ip_address,
                'subnet_mask': cam.subnet_mask,
                'gateway': cam.gateway,
                'http_port': cam.http_port,
                'firmware_version': cam.firmware_version,
                'camera_name': cam.camera_name,
                'installids': cam.installids,
                'enhanced_security': cam.enhanced_security,
                'actual_app_count': cam.actual_app_count
            }
            camera_data['cameras'].append(cam_dict)
        
        with open(CAMERAS_FILE, 'w') as f:
            json.dump(camera_data, f, indent=2)
        
        logger.info(f"Updated AI apps for camera {camera.camera_name}")
        
        return jsonify({
            'success': True,
            'message': 'AI apps updated successfully',
            'installids': installids
        })
        
    except Exception as e:
        logger.error(f"Error saving camera configuration: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to save configuration: {str(e)}'
        }), 500


@app.route('/api/cameras/<mac_address>/arm', methods=['POST'])
@require_auth
def api_camera_arm(mac_address):
    """Arm (enable) AI-VMD for a single camera"""
    try:
        camera_manager = get_camera_manager()
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    
    camera = next((c for c in cameras_list if c.mac_address == mac_address), None)
    if not camera:
        return jsonify({
            'success': False,
            'message': 'Camera not found'
        }), 404
    
    # Get schedule parameters from request (optional)
    data = request.json or {}
    start_hour = data.get('start_hour', 0)
    start_min = data.get('start_min', 0)
    end_hour = data.get('end_hour', 0)
    end_min = data.get('end_min', 0)
    
    # Execute command
    results = camera_manager.set_ai_vmd(
        camera,
        VMDMode.ENABLE,
        start_hour,
        start_min,
        end_hour,
        end_min
    )
    
    # Format results
    results_data = [
        {
            'camera_name': r.camera_name,
            'ip_address': r.ip_address,
            'success': r.success,
            'message': r.message,
            'error_type': r.error_type
        } for r in results
    ]
    
    success_count = sum(1 for r in results if r.success)
    
    return jsonify({
        'success': True,
        'message': f'Armed {success_count}/{len(results)} AI apps',
        'results': results_data,
        'summary': {
            'total': len(results),
            'successful': success_count,
            'failed': len(results) - success_count
        }
    })


@app.route('/api/cameras/<mac_address>/disarm', methods=['POST'])
@require_auth
def api_camera_disarm(mac_address):
    """Disarm (disable) AI-VMD for a single camera"""
    try:
        camera_manager = get_camera_manager()
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    
    camera = next((c for c in cameras_list if c.mac_address == mac_address), None)
    if not camera:
        return jsonify({
            'success': False,
            'message': 'Camera not found'
        }), 404
    
    # Execute command
    results = camera_manager.set_ai_vmd(
        camera,
        VMDMode.DISABLE,
        0, 0, 0, 0
    )
    
    # Format results
    results_data = [
        {
            'camera_name': r.camera_name,
            'ip_address': r.ip_address,
            'success': r.success,
            'message': r.message,
            'error_type': r.error_type
        } for r in results
    ]
    
    success_count = sum(1 for r in results if r.success)
    
    return jsonify({
        'success': True,
        'message': f'Disarmed {success_count}/{len(results)} AI apps',
        'results': results_data,
        'summary': {
            'total': len(results),
            'successful': success_count,
            'failed': len(results) - success_count
        }
    })


@app.route('/api/cameras/<mac_address>/installed-apps', methods=['GET'])
@require_admin
def api_get_installed_apps(mac_address):
    """Get installed AI applications on camera"""
    camera = next((c for c in cameras_list if c.mac_address == mac_address), None)
    if not camera:
        return jsonify({
            'success': False,
            'message': 'Camera not found'
        }), 404
    
    try:
        camera_manager = get_camera_manager()
        result = camera_manager.get_installed_apps(camera)
        
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error getting installed apps: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/groups', methods=['GET'])
@require_auth
def api_groups():
    """Get all groups"""
    groups = group_manager.get_all_groups()
    groups_data = [group.to_dict() for group in groups]
    
    return jsonify({
        'success': True,
        'groups': groups_data,
        'count': len(groups_data)
    })


@app.route('/api/groups', methods=['POST'])
@require_admin
def api_groups_create():
    """Create a new group"""
    data = request.json
    
    name = data.get('name')
    description = data.get('description', '')
    camera_macs = data.get('camera_macs', [])
    
    if not name:
        return jsonify({
            'success': False,
            'message': 'Group name is required'
        }), 400
    
    # Auto-generate group ID from name if not provided
    group_id = data.get('id')
    if not group_id:
        # Create ID from name: lowercase, replace spaces with underscores
        import re
        group_id = re.sub(r'[^a-z0-9_]', '', name.lower().replace(' ', '_'))
        # Add timestamp to ensure uniqueness
        import time
        group_id = f"{group_id}_{int(time.time())}"
    
    try:
        group = group_manager.add_group(group_id, name, description, camera_macs)
        return jsonify({
            'success': True,
            'message': 'Group created successfully',
            'group': group.to_dict()
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating group: {str(e)}'
        }), 500


@app.route('/api/groups/<group_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def api_group(group_id):
    """Get, update, or delete a specific group"""
    if request.method == 'GET':
        group = group_manager.get_group(group_id)
        if not group:
            return jsonify({
                'success': False,
                'message': 'Group not found'
            }), 404
        
        # Get cameras in this group
        group_cameras = group_manager.get_cameras_in_group(group_id, cameras_list)
        cameras_data = [
            {
                'mac_address': cam.mac_address,
                'camera_name': cam.camera_name,
                'ip_address': cam.ip_address,
                'model_name': cam.model_name
            } for cam in group_cameras
        ]
        
        return jsonify({
            'success': True,
            'group': group.to_dict(),
            'cameras': cameras_data
        })
    
    elif request.method == 'PUT':
        # Admin only for editing
        if request.session.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        data = request.json
        
        try:
            group = group_manager.update_group(
                group_id,
                name=data.get('name'),
                description=data.get('description'),
                camera_macs=data.get('camera_macs'),
                enabled=data.get('enabled')
            )
            
            return jsonify({
                'success': True,
                'message': 'Group updated successfully',
                'group': group.to_dict()
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error updating group: {str(e)}'
            }), 500
    
    elif request.method == 'DELETE':
        # Admin only for deleting
        if request.session.role != 'admin':
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        try:
            group_manager.delete_group(group_id)
            return jsonify({
                'success': True,
                'message': 'Group deleted successfully'
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error deleting group: {str(e)}'
            }), 500


@app.route('/api/groups/<group_id>/arm', methods=['POST'])
@require_auth
def api_group_arm(group_id):
    """Arm (enable) AI-VMD for all cameras in a group"""
    try:
        camera_manager = get_camera_manager()
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    
    # Get group
    group = group_manager.get_group(group_id)
    if not group:
        return jsonify({
            'success': False,
            'message': 'Group not found'
        }), 404
    
    # Get cameras in group
    group_cameras = group_manager.get_cameras_in_group(group_id, cameras_list)
    
    if not group_cameras:
        return jsonify({
            'success': False,
            'message': 'No cameras in group'
        }), 400
    
    # Get schedule parameters from request (optional)
    data = request.json or {}
    start_hour = data.get('start_hour', 0)
    start_min = data.get('start_min', 0)
    end_hour = data.get('end_hour', 0)
    end_min = data.get('end_min', 0)
    
    # Execute command
    results = camera_manager.set_ai_vmd_bulk(
        group_cameras,
        VMDMode.ENABLE,
        start_hour,
        start_min,
        end_hour,
        end_min
    )
    
    # Format results
    results_data = [
        {
            'camera_name': r.camera_name,
            'ip_address': r.ip_address,
            'success': r.success,
            'message': r.message,
            'error_type': r.error_type
        } for r in results
    ]
    
    success_count = sum(1 for r in results if r.success)
    
    # Update group status
    if success_count > 0:
        group_manager.update_group_status(group_id, "armed")
    
    # Log activity
    activity_logger.log_action(
        user=request.session.username,
        action="arm",
        target_type="group",
        target_id=group_id,
        target_name=group.name,
        success=success_count > 0,
        cameras_affected=success_count,
        message=f'Armed {success_count}/{len(results)} cameras'
    )
    
    return jsonify({
        'success': True,
        'message': f'Armed {success_count}/{len(results)} cameras',
        'results': results_data,
        'summary': {
            'total': len(results),
            'successful': success_count,
            'failed': len(results) - success_count
        }
    })


@app.route('/api/groups/<group_id>/disarm', methods=['POST'])
@require_auth
def api_group_disarm(group_id):
    """Disarm (disable) AI-VMD for all cameras in a group"""
    try:
        camera_manager = get_camera_manager()
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    
    # Get group
    group = group_manager.get_group(group_id)
    if not group:
        return jsonify({
            'success': False,
            'message': 'Group not found'
        }), 404
    
    # Get cameras in group
    group_cameras = group_manager.get_cameras_in_group(group_id, cameras_list)
    
    if not group_cameras:
        return jsonify({
            'success': False,
            'message': 'No cameras in group'
        }), 400
    
    # Execute command
    results = camera_manager.set_ai_vmd_bulk(
        group_cameras,
        VMDMode.DISABLE,
        0, 0, 0, 0
    )
    
    # Format results
    results_data = [
        {
            'camera_name': r.camera_name,
            'ip_address': r.ip_address,
            'success': r.success,
            'message': r.message,
            'error_type': r.error_type
        } for r in results
    ]
    
    success_count = sum(1 for r in results if r.success)
    
    # Update group status
    if success_count > 0:
        group_manager.update_group_status(group_id, "disarmed")
    
    # Log activity
    activity_logger.log_action(
        user=request.session.username,
        action="disarm",
        target_type="group",
        target_id=group_id,
        target_name=group.name,
        success=success_count > 0,
        cameras_affected=success_count,
        message=f'Disarmed {success_count}/{len(results)} cameras'
    )
    
    return jsonify({
        'success': True,
        'message': f'Disarmed {success_count}/{len(results)} cameras',
        'results': results_data,
        'summary': {
            'total': len(results),
            'successful': success_count,
            'failed': len(results) - success_count
        }
    })


@app.route('/api/groups/<group_id>/cameras/<camera_mac>', methods=['POST', 'DELETE'])
@require_auth
def api_group_camera(group_id, camera_mac):
    """Add or remove a camera from a group"""
    if request.method == 'POST':
        try:
            group_manager.add_camera_to_group(group_id, camera_mac)
            return jsonify({
                'success': True,
                'message': 'Camera added to group'
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error adding camera: {str(e)}'
            }), 500
    
    elif request.method == 'DELETE':
        try:
            group_manager.remove_camera_from_group(group_id, camera_mac)
            return jsonify({
                'success': True,
                'message': 'Camera removed from group'
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error removing camera: {str(e)}'
            }), 500


# Error handlers



# Activity Log Endpoints

@app.route('/api/activity-log', methods=['GET'])
@require_auth
def api_get_activity_log():
    """Get activity log entries"""
    limit = request.args.get('limit', 100, type=int)
    entries = activity_logger.get_recent_entries(limit)
    
    return jsonify({
        'success': True,
        'entries': [entry.to_dict() for entry in entries],
        'count': len(entries)
    })


@app.route('/api/activity-log/statistics', methods=['GET'])
@require_auth
def api_get_activity_statistics():
    """Get activity log statistics"""
    stats = activity_logger.get_statistics()
    
    return jsonify({
        'success': True,
        'statistics': stats
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'success': False,
        'message': 'Internal server error'
    }), 500


def main():
    """Main entry point"""
    # Load cameras on startup
    load_cameras()
    
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Camera AI-VMD Manager on port {port}")
    logger.info(f"Cameras file: {CAMERAS_FILE}")
    logger.info(f"Groups file: {GROUPS_FILE}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    main()
