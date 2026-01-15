"""
Camera AI-VMD Manager
Handles sending CGI commands to security cameras with comprehensive error handling
Supports i-PRO Enhanced Security (Randomnum parameter) and Digest Authentication
"""
import requests
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

# Try to import AI apps for human-readable names
try:
    from ai_apps import get_ai_app_name
    HAS_AI_APPS = True
except ImportError:
    HAS_AI_APPS = False
    def get_ai_app_name(app_id):
        return f"AI app {app_id}"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VMDMode(Enum):
    """AI-VMD mode enumeration"""
    DISABLE = 0
    ENABLE = 1


@dataclass
class Camera:
    """Camera data structure"""
    mac_address: str
    model_name: str
    ip_address: str
    subnet_mask: str
    gateway: str
    http_port: int
    firmware_version: str
    camera_name: str
    installid: Optional[int] = None  # Deprecated - use installids list instead
    installids: Optional[List[int]] = None  # List of AI app install IDs
    enhanced_security: bool = True  # Enable i-PRO Enhanced Security by default
    actual_app_count: Optional[int] = None  # Number of apps actually installed on camera
    
    def __post_init__(self):
        """Validate camera data"""
        if not self.ip_address:
            raise ValueError("IP address is required")
        if not isinstance(self.http_port, int) or self.http_port <= 0:
            raise ValueError("Invalid HTTP port")
        
        # If installids not provided, use default common AI app IDs
        if self.installids is None:
            if self.installid is not None:
                # Backward compatibility: if single installid provided, use it
                self.installids = [self.installid]
            else:
                # Default: all common AI app install IDs
                self.installids = [272, 528, 784, 1040]
        
        # Ensure installids is a list
        if not isinstance(self.installids, list):
            self.installids = [self.installids]


@dataclass
class CommandResult:
    """Result of a CGI command execution"""
    camera_name: str
    ip_address: str
    success: bool
    message: str
    response_code: Optional[int] = None
    response_text: Optional[str] = None
    error_type: Optional[str] = None


class CameraCommandError(Exception):
    """Custom exception for camera command errors"""
    pass


class CameraManager:
    """Manages camera CGI commands with error handling, retry logic, and i-PRO Enhanced Security"""
    
    def __init__(self, username: str, password: str, timeout: int = 10, max_retries: int = 3):
        """
        Initialize Camera Manager
        
        Args:
            username: Camera authentication username
            password: Camera authentication password
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.username = username
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        # Cache for randomnum values per camera (ip_address -> randomnum)
        self._randomnum_cache: Dict[str, str] = {}
        
    def _get_randomnum(self, camera: Camera) -> Optional[str]:
        """
        Get randomnum from camera for Enhanced Security
        As per i-PRO specification: http://camera_ip/cgi-bin/get_randomnum
        
        Args:
            camera: Camera object
            
        Returns:
            Randomnum string or None if not supported/failed
        """
        protocol = "https" if camera.http_port == 443 else "http"
        url = f"{protocol}://{camera.ip_address}:{camera.http_port}/cgi-bin/get_randomnum"
        
        try:
            logger.debug(f"Requesting randomnum from {camera.camera_name}")
            
            # Use Digest Auth (primary method for i-PRO cameras)
            response = self.session.get(
                url,
                auth=HTTPDigestAuth(self.username, self.password),
                timeout=5,
                verify=False
            )
            
            if response.status_code == 200:
                # Parse response to extract randomnum
                # Expected format: randomnum=8C53C75B9462F1D8
                content = response.text.strip()
                match = re.search(r'randomnum=([A-F0-9]+)', content, re.IGNORECASE)
                
                if match:
                    randomnum = match.group(1)
                    logger.debug(f"Got randomnum for {camera.camera_name}: {randomnum[:8]}...")
                    return randomnum
                else:
                    logger.warning(f"Could not parse randomnum from response: {content[:100]}")
                    return None
            else:
                logger.debug(f"Randomnum request returned {response.status_code} - camera may not support enhanced security")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout getting randomnum from {camera.camera_name}")
            return None
        except Exception as e:
            logger.debug(f"Error getting randomnum from {camera.camera_name}: {str(e)}")
            return None
    
    def _build_url(self, camera: Camera, cgi_path: str, params: Dict[str, any]) -> str:
        """
        Build the complete CGI command URL with Enhanced Security support
        
        Args:
            camera: Camera object
            cgi_path: CGI script path
            params: Query parameters
            
        Returns:
            Complete URL string with Randomnum if enhanced security is enabled
        """
        protocol = "https" if camera.http_port == 443 else "http"
        base_url = f"{protocol}://{camera.ip_address}:{camera.http_port}"
        
        # Add Randomnum parameter if enhanced security is enabled
        if camera.enhanced_security:
            # Check cache first
            randomnum = self._randomnum_cache.get(camera.ip_address)
            
            # If not cached or older than 60 seconds, get new randomnum
            if not randomnum:
                randomnum = self._get_randomnum(camera)
                if randomnum:
                    self._randomnum_cache[camera.ip_address] = randomnum
            
            # Add Randomnum to params if available
            if randomnum:
                params['Randomnum'] = randomnum
                logger.debug(f"Added Randomnum parameter for enhanced security")
            else:
                logger.info(f"Enhanced security enabled but randomnum unavailable for {camera.camera_name}")
        
        # Build query string
        query_parts = [f"{key}={value}" for key, value in params.items()]
        query_string = "&".join(query_parts)
        
        return f"{base_url}{cgi_path}?{query_string}"
    
    def _send_command(self, camera: Camera, url: str, retry_count: int = 0) -> CommandResult:
        """
        Send CGI command to camera with retry logic
        Uses Digest Authentication (primary for i-PRO cameras) with Basic Auth fallback
        Removes Accept headers for enhanced security compatibility
        
        Args:
            camera: Camera object
            url: Complete command URL
            retry_count: Current retry attempt
            
        Returns:
            CommandResult object
        """
        try:
            # Prepare headers - exclude Accept header as per i-PRO enhanced security method 1
            headers = {
                'User-Agent': 'CameraAIVMDManager/1.0'
            }
            # Explicitly avoid Accept header to prevent "400 Bad Request" with enhanced security
            
            # Use Digest Auth as PRIMARY method (standard for i-PRO cameras)
            # Only fallback to Basic Auth if Digest fails
            auth_methods = [
                ('Digest', HTTPDigestAuth(self.username, self.password)),
                ('Basic', HTTPBasicAuth(self.username, self.password))
            ]
            
            last_exception = None
            
            for auth_name, auth_method in auth_methods:
                try:
                    logger.debug(f"Attempting {auth_name} authentication for {camera.camera_name}")
                    
                    response = self.session.get(
                        url,
                        auth=auth_method,
                        headers=headers,  # No Accept header
                        timeout=self.timeout,
                        verify=False  # Disable SSL verification for self-signed certs
                    )
                    
                    # Success cases
                    if response.status_code == 200:
                        logger.info(f"✓ Command successful to {camera.camera_name} ({camera.ip_address}) via {auth_name} Auth")
                        return CommandResult(
                            camera_name=camera.camera_name,
                            ip_address=camera.ip_address,
                            success=True,
                            message=f"Command executed successfully via {auth_name} Auth",
                            response_code=200,
                            response_text=response.text[:200]  # Limit response text
                        )
                    
                    # Enhanced Security 400 Bad Request - try to get new randomnum
                    if response.status_code == 400 and camera.enhanced_security:
                        logger.warning(f"Got 400 Bad Request from {camera.camera_name} - may need fresh randomnum")
                        # Clear cached randomnum and retry will get fresh one
                        if camera.ip_address in self._randomnum_cache:
                            del self._randomnum_cache[camera.ip_address]
                        
                        if retry_count < self.max_retries:
                            logger.info(f"Retrying with fresh randomnum for {camera.camera_name}")
                            time.sleep(1)
                            # Rebuild URL with fresh randomnum
                            return self._send_command(camera, url, retry_count + 1)
                    
                    # If we get a response other than auth error, break the auth loop
                    if response.status_code not in [401, 403]:
                        last_exception = Exception(f"HTTP {response.status_code}: {response.reason}")
                        break
                        
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    continue
            
            # If we get here, all auth methods failed or got non-success response
            if last_exception:
                raise last_exception
                
        except requests.exceptions.Timeout:
            error_msg = f"Timeout connecting to camera {camera.camera_name} ({camera.ip_address})"
            logger.warning(error_msg)
            
            # Retry logic
            if retry_count < self.max_retries:
                logger.info(f"Retrying {camera.camera_name} (attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(1 * (retry_count + 1))  # Exponential backoff
                return self._send_command(camera, url, retry_count + 1)
            
            return CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=False,
                message=error_msg,
                error_type="Timeout"
            )
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error to {camera.camera_name} ({camera.ip_address}): {str(e)}"
            logger.error(error_msg)
            
            return CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=False,
                message=f"Cannot connect to camera. Check IP address and network connectivity.",
                error_type="ConnectionError"
            )
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error for {camera.camera_name}: {str(e)}"
            logger.error(error_msg)
            
            return CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=False,
                message=f"Authentication failed or access denied. Check credentials.",
                error_type="HTTPError",
                response_code=e.response.status_code if hasattr(e, 'response') else None
            )
            
        except Exception as e:
            error_msg = f"Unexpected error for {camera.camera_name}: {str(e)}"
            logger.error(error_msg)
            
            return CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=False,
                message=f"Unexpected error: {str(e)}",
                error_type="UnexpectedError"
            )
    
    def get_installed_apps(self, camera: Camera) -> Dict:
        """
        Get list of installed AI applications on camera
        
        Args:
            camera: Camera object
            
        Returns:
            Dict with application list and metadata
        """
        params = {
            'methodName': 'getApplicationList'
        }
        
        url = self._build_url(camera, '/cgi-bin/adam.cgi', params)
        
        logger.info(f"Getting installed apps for {camera.camera_name}")
        
        try:
            # Prepare headers - exclude Accept header for enhanced security compatibility
            headers = {
                'User-Agent': 'CameraAIVMDManager/1.0'
            }
            
            # Use Digest Auth as PRIMARY method
            auth_methods = [
                ('Digest', HTTPDigestAuth(self.username, self.password)),
                ('Basic', HTTPBasicAuth(self.username, self.password))
            ]
            
            response = None
            last_error = None
            
            for auth_name, auth_method in auth_methods:
                try:
                    logger.debug(f"Attempting {auth_name} authentication for {camera.camera_name}")
                    
                    response = self.session.get(
                        url,
                        auth=auth_method,
                        headers=headers,
                        timeout=self.timeout,
                        verify=False
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"✓ Got app list from {camera.camera_name} via {auth_name} Auth")
                        break
                    elif response.status_code not in [401, 403]:
                        # Got a response but not success - break and handle below
                        break
                        
                except requests.exceptions.RequestException as e:
                    last_error = e
                    continue
            
            if response is None:
                error_msg = f"Failed to connect: {last_error}" if last_error else "No response from camera"
                logger.error(f"Error getting apps for {camera.camera_name}: {error_msg}")
                return {
                    'success': False,
                    'camera': camera.camera_name,
                    'message': error_msg
                }
            
            if response.status_code != 200:
                logger.error(f"HTTP {response.status_code} from {camera.camera_name}")
                return {
                    'success': False,
                    'camera': camera.camera_name,
                    'message': f'HTTP {response.status_code}: {response.reason}'
                }
            
            # Parse ResponseData parameter
            response_text = response.text
            logger.debug(f"Raw response from {camera.camera_name}: {response_text[:500]}")
            
            # Try parsing response - may have "ResponseData=" prefix or be raw JSON
            json_str = None
            data = None
            
            if 'ResponseData=' in response_text:
                # Standard format with ResponseData= prefix
                json_str = response_text.split('ResponseData=', 1)[1].strip()
                logger.debug(f"Found ResponseData= prefix, JSON: {json_str[:200]}")
            elif response_text.strip().startswith('{'):
                # Raw JSON response
                json_str = response_text.strip()
                logger.debug(f"Raw JSON response (no prefix): {json_str[:200]}")
            else:
                logger.error(f"Invalid response format from {camera.camera_name}: {response_text[:200]}")
                return {
                    'success': False,
                    'camera': camera.camera_name,
                    'message': f'Invalid response format - no ResponseData found. Response: {response_text[:100]}'
                }
            
            # Parse JSON
            try:
                data = json.loads(json_str)
                
                logger.info(f"Found {data.get('appCount', 0)} installed apps on {camera.camera_name}")
                return {
                    'success': True,
                    'camera': camera.camera_name,
                    'app_count': int(data.get('appCount', 0)),
                    'max_app_count': int(data.get('maxAppCount', 0)),
                    'limitation_mode': data.get('limitationMode', 'Unknown'),
                    'apps': self._parse_app_list(data.get('appList', []))
                }
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error for {camera.camera_name}: {e}")
                logger.error(f"Failed to parse: {json_str[:200]}")
                return {
                    'success': False,
                    'camera': camera.camera_name,
                    'message': f'JSON parse error: {str(e)}'
                }
        except Exception as e:
            logger.error(f"Error getting apps for {camera.camera_name}: {e}")
            return {
                'success': False,
                'camera': camera.camera_name,
                'message': str(e)
            }
    
    def _parse_app_list(self, app_list: List[Dict]) -> List[Dict]:
        """Parse application list into simplified format"""
        parsed_apps = []
        
        for app in app_list:
            func_id = app.get('funcId', '')
            app_info = app.get('appInfo', {})
            
            # Get English name (langId=0)
            app_name = 'Unknown'
            for name_entry in app_info.get('appNameList', []):
                if name_entry.get('langId') == '0':
                    app_name = name_entry.get('name', 'Unknown')
                    break
            
            parsed_apps.append({
                'func_id': func_id,
                'install_id': app_info.get('installId', ''),
                'name': app_name,
                'version': app_info.get('version', ''),
                'use_ai': app_info.get('useAI') == '1',
                'cpu_rate': app_info.get('cpuRate', '0'),
                'ram_size': app_info.get('ramSize', '0'),
                'rom_size': app_info.get('romSize', '0'),
                'remain_trial_time': app_info.get('remainTrialTime', '-1'),
                'channel': app_info.get('channel', '1')
            })
        
        return parsed_apps
    
    def set_ai_vmd(self, camera: Camera, mode: VMDMode, 
                   start_hour: int = 0, start_min: int = 0,
                   end_hour: int = 0, end_min: int = 0) -> List[CommandResult]:
        """
        Set AI-VMD schedule for all AI apps in a camera
        Only operates on apps that are actually installed on the camera.
        
        Args:
            camera: Camera object
            mode: VMDMode.ENABLE or VMDMode.DISABLE
            start_hour: Schedule start hour (0-23)
            start_min: Schedule start minute (0-59)
            end_hour: Schedule end hour (0-23)
            end_min: Schedule end minute (0-59)
            
        Returns:
            List of CommandResult objects (one per AI app/installid)
        """
        if not camera.installids or len(camera.installids) == 0:
            return [CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=False,
                message="No AI app install IDs configured",
                error_type="ConfigurationError"
            )]
        
        # Get actually installed apps to filter out non-existent ones
        installed_apps_result = self.get_installed_apps(camera)
        installed_func_ids = set()
        
        if installed_apps_result.get('success') and installed_apps_result.get('apps'):
            installed_func_ids = {int(app['func_id']) for app in installed_apps_result['apps']}
            logger.info(f"Camera {camera.camera_name} has {len(installed_func_ids)} apps actually installed: {installed_func_ids}")
        else:
            logger.warning(f"Could not query installed apps on {camera.camera_name}, will try all configured installids")
            # If we can't query installed apps, fall back to using all configured installids
            # This maintains backward compatibility if the camera doesn't support the query
            installed_func_ids = set(camera.installids)
        
        # Filter installids to only those actually installed
        valid_installids = [installid for installid in camera.installids if installid in installed_func_ids]
        
        if not valid_installids:
            return [CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=False,
                message=f"None of the configured AI apps ({camera.installids}) are actually installed on this camera",
                error_type="ConfigurationError"
            )]
        
        # Log if there's a mismatch
        if len(valid_installids) < len(camera.installids):
            missing = set(camera.installids) - set(valid_installids)
            logger.warning(f"Camera {camera.camera_name}: Configured installids {missing} are not installed, skipping them")
        
        # Validate time parameters
        if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
            return [CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=False,
                message="Invalid hour value (must be 0-23)",
                error_type="ValidationError"
            )]
            
        if not (0 <= start_min <= 59 and 0 <= end_min <= 59):
            return [CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=False,
                message="Invalid minute value (must be 0-59)",
                error_type="ValidationError"
            )]
        
        results = []
        
        # Send command for each VALID AI app install ID (only actually installed ones)
        for installid in valid_installids:
            # Build CGI parameters
            params = {
                'installid': installid,
                'start_hour1_t1': start_hour,
                'start_min1_t1': start_min,
                'end_hour1_t1': end_hour,
                'end_min1_t1': end_min,
                'ext_mode1_t1': mode.value
            }
            
            url = self._build_url(camera, '/cgi-bin/set_ext2_schedule', params)
            
            ai_app_name = get_ai_app_name(installid)
            logger.info(f"Setting AI-VMD to {mode.name} for {camera.camera_name} ({ai_app_name})")
            result = self._send_command(camera, url)
            
            # Add AI app name to result message
            if result.success:
                result.message = f"{ai_app_name}: {result.message}"
            else:
                result.message = f"{ai_app_name}: {result.message}"
            
            results.append(result)
        
        return results
    
    def set_ai_vmd_bulk(self, cameras: List[Camera], mode: VMDMode,
                        start_hour: int = 0, start_min: int = 0,
                        end_hour: int = 0, end_min: int = 0,
                        max_workers: int = 10) -> List[CommandResult]:
        """
        Set AI-VMD for multiple cameras in parallel
        Each camera will have all its AI apps (installids) configured
        
        Args:
            cameras: List of Camera objects
            mode: VMDMode.ENABLE or VMDMode.DISABLE
            start_hour: Schedule start hour
            start_min: Schedule start minute
            end_hour: Schedule end hour
            end_min: Schedule end minute
            max_workers: Maximum parallel threads
            
        Returns:
            List of CommandResult objects (multiple per camera if multiple AI apps)
        """
        results = []
        
        logger.info(f"Processing {len(cameras)} cameras in parallel (max_workers={max_workers})")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_camera = {
                executor.submit(
                    self.set_ai_vmd, 
                    camera, 
                    mode, 
                    start_hour, 
                    start_min, 
                    end_hour, 
                    end_min
                ): camera for camera in cameras
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_camera):
                camera = future_to_camera[future]
                try:
                    camera_results = future.result()  # Now returns a list
                    results.extend(camera_results)  # Add all results from this camera
                except Exception as e:
                    logger.error(f"Exception processing {camera.camera_name}: {str(e)}")
                    results.append(CommandResult(
                        camera_name=camera.camera_name,
                        ip_address=camera.ip_address,
                        success=False,
                        message=f"Exception during execution: {str(e)}",
                        error_type="ExecutionError"
                    ))
        
        # Log summary
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Bulk operation complete: {success_count}/{len(results)} AI app commands successful")
        
        return results
    
    def test_connection(self, camera: Camera) -> CommandResult:
        """
        Test connection to a camera
        
        Args:
            camera: Camera object
            
        Returns:
            CommandResult object
        """
        protocol = "https" if camera.http_port == 443 else "http"
        url = f"{protocol}://{camera.ip_address}:{camera.http_port}/"
        
        try:
            response = self.session.get(
                url,
                auth=HTTPDigestAuth(self.username, self.password),
                timeout=5,
                verify=False
            )
            
            return CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=True,
                message="Connection successful",
                response_code=response.status_code
            )
            
        except Exception as e:
            return CommandResult(
                camera_name=camera.camera_name,
                ip_address=camera.ip_address,
                success=False,
                message=f"Connection failed: {str(e)}",
                error_type="ConnectionError"
            )


def load_cameras_from_json(json_path: str) -> List[Camera]:
    """
    Load cameras from JSON file

    Args:
        json_path: Path to JSON file

    Returns:
        List of Camera objects
    """
    # Get valid Camera field names
    import dataclasses
    valid_fields = {f.name for f in dataclasses.fields(Camera)}

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        cameras = []
        for cam_data in data.get('cameras', []):
            # Filter out unknown fields to prevent TypeError
            filtered_data = {k: v for k, v in cam_data.items() if k in valid_fields}
            camera = Camera(**filtered_data)
            cameras.append(camera)

        logger.info(f"Loaded {len(cameras)} cameras from {json_path}")
        return cameras

    except FileNotFoundError:
        logger.error(f"File not found: {json_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {json_path}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error loading cameras: {str(e)}")
        raise


# Disable SSL warnings for self-signed certificates
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
