#!/usr/bin/env python3
"""
User Management CLI Tool
Allows server admins to manage user accounts from command line
"""
import argparse
import sys
import secrets
from auth_manager import AuthenticationManager


def create_user(args):
    """Create a new user"""
    auth_manager = AuthenticationManager()
    
    password = args.password
    if not password:
        # Generate random password
        password = secrets.token_urlsafe(16)
        print(f"Generated password: {password}")
    
    if auth_manager.create_user(args.username, password, args.role):
        print(f"✓ User '{args.username}' created successfully")
        print(f"  Role: {args.role}")
        if not args.password:
            print(f"  Password: {password}")
            print("  IMPORTANT: Save this password - it won't be shown again!")
        return 0
    else:
        print(f"✗ Failed to create user '{args.username}'")
        return 1


def reset_password(args):
    """Reset user password"""
    auth_manager = AuthenticationManager()
    
    password = args.password
    if not password:
        # Generate random password
        password = secrets.token_urlsafe(16)
        print(f"Generated password: {password}")
    
    if auth_manager.reset_password(args.username, password):
        print(f"✓ Password reset for user '{args.username}'")
        if not args.password:
            print(f"  New password: {password}")
            print("  IMPORTANT: Save this password - it won't be shown again!")
        return 0
    else:
        print(f"✗ Failed to reset password for '{args.username}'")
        return 1


def delete_user(args):
    """Delete a user"""
    auth_manager = AuthenticationManager()
    
    # Confirm deletion
    if not args.yes:
        confirm = input(f"Delete user '{args.username}'? (yes/no): ")
        if confirm.lower() not in ['yes', 'y']:
            print("Cancelled")
            return 0
    
    if auth_manager.delete_user(args.username):
        print(f"✓ User '{args.username}' deleted successfully")
        return 0
    else:
        print(f"✗ Failed to delete user '{args.username}'")
        return 1


def list_users(args):
    """List all users"""
    auth_manager = AuthenticationManager()
    
    users = auth_manager.list_users()
    
    if not users:
        print("No users found")
        return 0
    
    print(f"\nTotal users: {len(users)}\n")
    print(f"{'Username':<20} {'Role':<10} {'Created':<25} {'Last Login':<25}")
    print("-" * 80)
    
    for user in users:
        created = user['created_at'][:19] if user['created_at'] else 'N/A'
        last_login = user['last_login'][:19] if user['last_login'] else 'Never'
        
        print(f"{user['username']:<20} {user['role']:<10} {created:<25} {last_login:<25}")
    
    print()
    return 0


def show_default_password(args):
    """Show default admin password from keyring"""
    import keyring
    
    try:
        password = keyring.get_password("camera_manager_auth", "default_admin_password")
        if password:
            print(f"Default admin password: {password}")
            print("\nIMPORTANT: Change this password immediately!")
            print("Use: python user_cli.py reset-password admin --password <new_password>")
        else:
            print("No default admin password found in keyring")
    except Exception as e:
        print(f"Error retrieving password: {e}")
        return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='User Management CLI for Camera AI-VMD Manager'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Create user
    create_parser = subparsers.add_parser('create', help='Create a new user')
    create_parser.add_argument('username', help='Username')
    create_parser.add_argument('--password', help='Password (auto-generated if not provided)')
    create_parser.add_argument('--role', choices=['user', 'admin'], default='user', help='User role')
    
    # Reset password
    reset_parser = subparsers.add_parser('reset-password', help='Reset user password')
    reset_parser.add_argument('username', help='Username')
    reset_parser.add_argument('--password', help='New password (auto-generated if not provided)')
    
    # Delete user
    delete_parser = subparsers.add_parser('delete', help='Delete a user')
    delete_parser.add_argument('username', help='Username')
    delete_parser.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    
    # List users
    list_parser = subparsers.add_parser('list', help='List all users')
    
    # Show default password
    default_pw_parser = subparsers.add_parser('show-default', help='Show default admin password')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    if args.command == 'create':
        return create_user(args)
    elif args.command == 'reset-password':
        return reset_password(args)
    elif args.command == 'delete':
        return delete_user(args)
    elif args.command == 'list':
        return list_users(args)
    elif args.command == 'show-default':
        return show_default_password(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
