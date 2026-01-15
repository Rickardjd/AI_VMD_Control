# Camera AI-VMD Manager

A Flask-based web application for managing i-PRO IP camera AI-VMD (Video Motion Detection) systems. This application enables users to discover cameras on a network, organize them into groups, and control AI video motion detection features across multiple cameras simultaneously.

## Features

- **Automatic Camera Discovery** - Discover i-PRO cameras on your network using the Easy IP Setup protocol (UDP broadcast)
- **Manual Camera Addition** - Add cameras manually by IP address when automatic discovery isn't available
  - Single IP: `192.168.1.10`
  - IP Range (short): `192.168.1.10-20`
  - IP Range (full): `192.168.1.10-192.168.1.20`
  - Multiple IPs: comma or newline separated
- **Camera Details Editing** - Update camera name, model, and MAC address from the UI
- **Group Management** - Organize cameras into logical groups for batch operations
- **AI-VMD Control** - Arm/disarm AI video motion detection on individual cameras or entire groups
- **Multi-App Support** - Control multiple AI applications per camera (AI-VMD, AI-People Detection, AI-Vehicle, etc.)
- **User Authentication** - Role-based access control (admin/user roles)
- **Activity Logging** - Track all arm/disarm operations with timestamps and user info
- **Secure Credentials** - Camera credentials stored securely using system keyring

## Screenshots

The web interface provides:
- Dashboard with system overview
- Groups management for batch operations
- Camera configuration with AI app selection
- Activity log for operation history
- User management (admin only)

## Requirements

- Python 3.8+
- i-PRO network cameras with AI-VMD capability
- Network access to cameras (HTTP/HTTPS)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Rickardjd/AI_VMD_Control.git
cd AI_VMD_Control
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser to `http://localhost:5000`

## Initial Setup

1. **Login** - Default admin credentials are auto-generated on first run. Check the console output or `users.json`.

2. **Configure Camera Credentials** - Go to the Credentials tab and enter the username/password for your cameras.

3. **Add Cameras** - Either:
   - Click "Discover" to automatically find cameras on your network
   - Click "Add Manual" to enter camera IP addresses directly

4. **Configure AI Apps** - Click the gear icon on each camera to select which AI applications to control.

5. **Create Groups** - Organize cameras into groups for easier batch operations.

## Usage

### Discovering Cameras
Click the "Discover" button in the Cameras tab to scan for i-PRO cameras on your network using UDP broadcast on ports 10669-10670.

### Adding Cameras Manually
Click "Add Manual" and enter IP addresses in any of these formats:
- `192.168.1.10` - Single camera
- `192.168.1.10-20` - Range of cameras (.10 through .20)
- `192.168.1.10-192.168.1.20` - Full IP range
- Multiple entries separated by commas or newlines

When adding cameras, the system automatically queries each device to fetch the camera name, model, and MAC address. If credentials are configured and the device is reachable, these values are populated automatically. Otherwise, fallback values are used.

### Editing Camera Details
Click the pencil icon (✏️) on any camera to edit:
- **Camera Name** - Friendly display name
- **Model** - Camera model identifier
- **MAC Address** - Hardware address (format: `xx:xx:xx:xx:xx:xx`)

Use the **"Fetch from Camera"** button to automatically retrieve current values directly from the camera. You can still manually edit values after fetching.

Note: To change a camera's IP address, delete and re-add the camera.

### Arming/Disarming
- **Individual Camera**: Click the controller icon on any camera
- **Group**: Use the Arm/Disarm buttons on a group card

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cameras` | GET | List all cameras |
| `/api/cameras/discover` | POST | Discover cameras on network |
| `/api/cameras/add-manual` | POST | Add cameras by IP address |
| `/api/cameras/<mac>` | DELETE | Delete a camera |
| `/api/cameras/<mac>/update` | PUT | Update camera details (name, model, MAC) |
| `/api/cameras/<mac>/fetch-info` | GET | Fetch camera details from device |
| `/api/cameras/<mac>/arm` | POST | Arm AI-VMD on camera |
| `/api/cameras/<mac>/disarm` | POST | Disarm AI-VMD on camera |
| `/api/groups` | GET/POST | List/create groups |
| `/api/groups/<id>/arm` | POST | Arm all cameras in group |
| `/api/groups/<id>/disarm` | POST | Disarm all cameras in group |

## Supported AI Applications

| Application | Install ID |
|-------------|-----------|
| AI-VMD (Camera 1-4) | 272, 528, 784, 1040 |
| AI-People Detection (Camera 1-4) | 279, 535, 791, 1047 |
| AI-Vehicle Detection (Camera 1-4) | 280, 536, 792, 1048 |
| AI-People Counting | 285 |
| AI-Face Detection | 278 |

## Configuration Files

- `cameras.json` - Camera configuration (auto-generated)
- `groups_config.json` - Group definitions
- `users.json` - User accounts (auto-generated)

## Command Line Interface

A CLI is also available for scripting:

```bash
# Discover cameras
python cli.py discover --save

# List cameras
python cli.py list-cameras

# Arm/disarm a group
python cli.py arm <group_id>
python cli.py disarm <group_id>

# Test camera connection
python cli.py test-camera <ip_address>
```

## Security Notes

- Camera credentials are stored in the system keyring (Windows Credential Manager)
- User passwords are hashed with PBKDF2 (100,000 iterations, SHA256)
- Session tokens expire after 24 hours
- Enhanced Security (Randomnum parameter) is supported for i-PRO cameras

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
