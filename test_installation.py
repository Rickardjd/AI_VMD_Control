#!/usr/bin/env python3
"""
Test script to validate Camera AI-VMD Manager installation
"""
import sys
import os

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    try:
        import flask
        print("  ✓ Flask")
        import flask_cors
        print("  ✓ Flask-CORS")
        import requests
        print("  ✓ Requests")
        import keyring
        print("  ✓ Keyring")
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False

def test_modules():
    """Test if application modules can be imported"""
    print("\nTesting application modules...")
    try:
        import camera_manager
        print("  ✓ camera_manager")
        import group_manager
        print("  ✓ group_manager")
        import credential_manager
        print("  ✓ credential_manager")
        import app
        print("  ✓ app")
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False

def test_camera_json():
    """Test if cameras.json exists and is valid"""
    print("\nTesting cameras.json...")
    if not os.path.exists('cameras.json'):
        print("  ⚠ cameras.json not found (optional)")
        return True
    
    try:
        import json
        with open('cameras.json', 'r') as f:
            data = json.load(f)
        
        if 'cameras' not in data:
            print("  ✗ Invalid format: 'cameras' key missing")
            return False
        
        print(f"  ✓ Found {len(data['cameras'])} cameras")
        
        # Check first camera has required fields (installids is optional, will use defaults)
        if data['cameras']:
            cam = data['cameras'][0]
            required = ['mac_address', 'ip_address', 'camera_name']
            missing = [f for f in required if f not in cam]
            if missing:
                print(f"  ⚠ Warning: First camera missing required fields: {missing}")
            else:
                print("  ✓ Camera format valid")
                
                # Check for AI app configuration (optional)
                if 'installids' in cam:
                    print(f"  ✓ AI apps configured: {len(cam['installids'])} apps")
                elif 'installid' in cam:
                    print("  ℹ Old format detected: 'installid' (will auto-convert to 'installids')")
                else:
                    print("  ℹ No AI apps configured (will use defaults: [272, 528, 784, 1040])")
        
        return True
    except json.JSONDecodeError as e:
        print(f"  ✗ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_keyring():
    """Test if keyring is accessible"""
    print("\nTesting keyring access...")
    try:
        import keyring
        # Try to get a non-existent key (should not error)
        keyring.get_password("test_service", "test_user")
        print("  ✓ Keyring accessible")
        return True
    except Exception as e:
        print(f"  ⚠ Keyring warning: {e}")
        print("  Note: Credentials storage may not work properly")
        return True  # Non-fatal

def test_file_structure():
    """Test if all required files exist"""
    print("\nTesting file structure...")
    required_files = [
        'app.py',
        'camera_manager.py',
        'group_manager.py',
        'credential_manager.py',
        'requirements.txt',
        'templates/index.html',
        'static/css/style.css',
        'static/js/app.js'
    ]
    
    all_present = True
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} missing")
            all_present = False
    
    return all_present

def main():
    print("Camera AI-VMD Manager - Installation Test")
    print("=" * 50)
    print()
    
    tests = [
        ("Required packages", test_imports),
        ("Application modules", test_modules),
        ("File structure", test_file_structure),
        ("Camera configuration", test_camera_json),
        ("Keyring access", test_keyring)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Unexpected error in {name}: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print("-" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:<30} {status}")
    
    print("-" * 50)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 50)
    
    if passed == total:
        print("\n✓ All tests passed! You're ready to run the application.")
        print("\nTo start the server:")
        print("  python app.py")
        print("\nOr use the quick start script:")
        print("  ./start.sh")
        return 0
    else:
        print("\n✗ Some tests failed. Please review the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
