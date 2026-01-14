#!/usr/bin/env python3
"""
Command Line Interface for Camera AI-VMD Manager
Quick operations without using the web interface
"""
import argparse
import sys
import json
from camera_manager import CameraManager, Camera, VMDMode, load_cameras_from_json
from group_manager import GroupManager
from credential_manager import CredentialManager
from camera_discovery import CameraDiscovery, print_discovered_cameras


def main():
    parser = argparse.ArgumentParser(
        description='Camera AI-VMD Manager CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover cameras on the network
  python cli.py discover

  # Discover and save to cameras.json
  python cli.py discover --save

  # Discover with longer timeout
  python cli.py discover --timeout 5.0

  # Arm all cameras in a group
  python cli.py arm building_a

  # Disarm all cameras in a group
  python cli.py disarm parking

  # List all groups
  python cli.py list-groups

  # List all cameras
  python cli.py list-cameras

  # Test connection to a camera
  python cli.py test-camera 192.168.1.47

  # Set credentials
  python cli.py set-credentials admin mypassword
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover cameras on the network')
    discover_parser.add_argument('--timeout', type=float, default=3.0,
                                help='Discovery timeout in seconds (default: 3.0)')
    discover_parser.add_argument('--save', action='store_true',
                                help='Save discovered cameras to cameras.json')
    discover_parser.add_argument('--output', default='cameras.json',
                                help='Output file path (default: cameras.json)')
    discover_parser.add_argument('--json', action='store_true',
                                help='Output in JSON format')
    discover_parser.add_argument('-v', '--verbose', action='store_true',
                                help='Enable verbose output')
    
    # Arm command
    arm_parser = subparsers.add_parser('arm', help='Arm (enable) AI-VMD for a group')
    arm_parser.add_argument('group_id', help='Group ID to arm')
    arm_parser.add_argument('--cameras-file', default='cameras.json', help='Path to cameras JSON file')
    
    # Disarm command
    disarm_parser = subparsers.add_parser('disarm', help='Disarm (disable) AI-VMD for a group')
    disarm_parser.add_argument('group_id', help='Group ID to disarm')
    disarm_parser.add_argument('--cameras-file', default='cameras.json', help='Path to cameras JSON file')
    
    # List groups
    list_groups_parser = subparsers.add_parser('list-groups', help='List all groups')
    
    # List cameras
    list_cameras_parser = subparsers.add_parser('list-cameras', help='List all cameras')
    list_cameras_parser.add_argument('--cameras-file', default='cameras.json', help='Path to cameras JSON file')
    
    # Test camera
    test_parser = subparsers.add_parser('test-camera', help='Test connection to a camera')
    test_parser.add_argument('ip_address', help='Camera IP address')
    test_parser.add_argument('--cameras-file', default='cameras.json', help='Path to cameras JSON file')
    
    # Set credentials
    creds_parser = subparsers.add_parser('set-credentials', help='Set camera credentials')
    creds_parser.add_argument('username', help='Camera username')
    creds_parser.add_argument('password', help='Camera password')
    
    # Check credentials
    check_creds_parser = subparsers.add_parser('check-credentials', help='Check if credentials are set')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize managers
    cred_manager = CredentialManager()
    group_manager = GroupManager()
    
    try:
        if args.command == 'discover':
            print("Discovering cameras on the network...")
            print(f"Timeout: {args.timeout}s\n")
            
            # Run discovery
            discovery = CameraDiscovery(timeout=args.timeout, verbose=args.verbose)
            discovered = discovery.discover_cameras()
            
            if not discovered:
                print("No cameras discovered.")
                return 1
            
            # Output format
            if args.json:
                # JSON output
                output = {
                    'count': len(discovered),
                    'cameras': [cam.to_dict() for cam in discovered]
                }
                print(json.dumps(output, indent=2))
            else:
                # Table output
                print_discovered_cameras(discovered)
            
            # Save if requested
            if args.save:
                print(f"\nSaving to {args.output}...")
                discovery.discover_and_save(output_file=args.output, include_installid=False)
                print("\nNOTE: You must manually add 'installid' values for each camera.")
                print("Check your camera CGI documentation for correct installid values.")
            
            return 0
        
        elif args.command == 'set-credentials':
            cred_manager.store_credentials(args.username, args.password)
            print("✓ Credentials saved successfully")
            return 0
        
        elif args.command == 'check-credentials':
            if cred_manager.has_credentials():
                creds = cred_manager.get_credentials()
                print(f"✓ Credentials configured for user: {creds[0]}")
                return 0
            else:
                print("✗ No credentials configured")
                print("Use: python cli.py set-credentials <username> <password>")
                return 1
        
        elif args.command == 'list-groups':
            groups = group_manager.get_all_groups()
            if not groups:
                print("No groups configured")
                return 0
            
            print(f"\n{'ID':<20} {'Name':<30} {'Cameras':<10} {'Status'}")
            print("-" * 70)
            for group in groups:
                status = "Enabled" if group.enabled else "Disabled"
                print(f"{group.id:<20} {group.name:<30} {len(group.camera_macs):<10} {status}")
            return 0
        
        elif args.command == 'list-cameras':
            cameras = load_cameras_from_json(args.cameras_file)
            if not cameras:
                print("No cameras loaded")
                return 0
            
            print(f"\n{'Name':<20} {'IP Address':<15} {'Model':<15} {'Install ID':<10}")
            print("-" * 70)
            for cam in cameras:
                install_id = str(cam.installid) if cam.installid else "N/A"
                print(f"{cam.camera_name:<20} {cam.ip_address:<15} {cam.model_name:<15} {install_id:<10}")
            return 0
        
        elif args.command == 'test-camera':
            credentials = cred_manager.get_credentials()
            if not credentials:
                print("✗ No credentials configured. Use 'set-credentials' first.")
                return 1
            
            cameras = load_cameras_from_json(args.cameras_file)
            camera = next((c for c in cameras if c.ip_address == args.ip_address), None)
            
            if not camera:
                print(f"✗ Camera with IP {args.ip_address} not found")
                return 1
            
            print(f"Testing connection to {camera.camera_name} ({camera.ip_address})...")
            
            username, password = credentials
            manager = CameraManager(username, password)
            result = manager.test_connection(camera)
            
            if result.success:
                print(f"✓ Connection successful")
                print(f"  Response code: {result.response_code}")
            else:
                print(f"✗ Connection failed: {result.message}")
                return 1
            
            return 0
        
        elif args.command in ['arm', 'disarm']:
            credentials = cred_manager.get_credentials()
            if not credentials:
                print("✗ No credentials configured. Use 'set-credentials' first.")
                return 1
            
            group = group_manager.get_group(args.group_id)
            if not group:
                print(f"✗ Group '{args.group_id}' not found")
                return 1
            
            cameras = load_cameras_from_json(args.cameras_file)
            group_cameras = group_manager.get_cameras_in_group(args.group_id, cameras)
            
            if not group_cameras:
                print(f"✗ No cameras in group '{args.group_id}'")
                return 1
            
            mode = VMDMode.ENABLE if args.command == 'arm' else VMDMode.DISABLE
            action = "Arming" if args.command == 'arm' else "Disarming"
            
            print(f"{action} {len(group_cameras)} cameras in '{group.name}'...")
            
            username, password = credentials
            manager = CameraManager(username, password)
            
            results = manager.set_ai_vmd_bulk(group_cameras, mode, 0, 0, 0, 0)
            
            # Print results
            success_count = sum(1 for r in results if r.success)
            print(f"\n{'Camera':<25} {'IP Address':<15} {'Status':<10} {'Message'}")
            print("-" * 80)
            
            for result in results:
                status = "✓ Success" if result.success else "✗ Failed"
                message = result.message[:30] if result.message else ""
                print(f"{result.camera_name:<25} {result.ip_address:<15} {status:<10} {message}")
            
            print(f"\nSummary: {success_count}/{len(results)} successful")
            
            return 0 if success_count == len(results) else 1
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
