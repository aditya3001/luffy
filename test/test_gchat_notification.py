#!/usr/bin/env python3
"""
Test script for Google Chat notifications.
Usage: python scripts/test_gchat_notification.py
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.gchat_notifier import GChatNotifier
from src.config import settings


def test_simple_notification():
    """Test a simple text notification"""
    print("\n=== Testing Simple Notification ===")
    
    notifier = GChatNotifier()
    
    if not notifier.enabled:
        print("❌ Google Chat notifications are not enabled")
        print("   Set ENABLE_GCHAT_NOTIFICATIONS=true and GCHAT_WEBHOOK_URL in .env")
        return False
    
    print(f"Webhook URL configured: {notifier.webhook_url[:50]}...")
    
    success = notifier.notify_simple(
        title="Test Notification",
        message="This is a test message from Luffy Log Observability Platform",
        severity="INFO"
    )
    
    if success:
        print("✅ Simple notification sent successfully")
    else:
        print("❌ Failed to send simple notification")
    
    return success


def test_exception_notification():
    """Test an exception cluster notification"""
    print("\n=== Testing Exception Cluster Notification ===")
    
    notifier = GChatNotifier()
    
    if not notifier.enabled:
        print("❌ Google Chat notifications are not enabled")
        return False
    
    # Mock cluster data
    cluster_data = {
        'cluster_id': 'cluster_test123',
        'exception_type': 'NullPointerException',
        'exception_message': 'Cannot invoke method on null object reference',
        'cluster_size': 15,
        'service_id': 'UserService',
        'frequency_24h': 25
    }
    
    # Mock exception with stack trace
    exceptions = [
        {
            'exception_type': 'NullPointerException',
            'exception_message': 'Cannot invoke method on null object reference',
            'stack_frames': [
                {
                    'symbol': 'com.example.UserService.getUser',
                    'file': 'UserService.java',
                    'line': 45,
                    'frame_type': 'java'
                },
                {
                    'symbol': 'com.example.api.UserController.getUserById',
                    'file': 'UserController.java',
                    'line': 123,
                    'frame_type': 'java'
                }
            ]
        }
    ]
    
    success = notifier.notify_exception_cluster(
        cluster_id=cluster_data['cluster_id'],
        cluster_data=cluster_data,
        exceptions=exceptions
    )
    
    if success:
        print("✅ Exception notification sent successfully")
    else:
        print("❌ Failed to send exception notification")
    
    return success


def test_connection():
    """Test Google Chat webhook connection"""
    print("\n=== Testing Webhook Connection ===")
    
    notifier = GChatNotifier()
    
    if not notifier.webhook_url:
        print("❌ No webhook URL configured")
        print("   Set GCHAT_WEBHOOK_URL in your .env file")
        return False
    
    print(f"Testing webhook: {notifier.webhook_url[:50]}...")
    
    success = notifier.test_connection()
    
    if success:
        print("✅ Connection test successful")
    else:
        print("❌ Connection test failed")
    
    return success


def main():
    print("="*70)
    print("GOOGLE CHAT NOTIFICATION TEST")
    print("="*70)
    
    # Check configuration
    print(f"\nConfiguration:")
    print(f"  Enable GChat Notifications: {settings.enable_gchat_notifications}")
    print(f"  Webhook URL configured: {bool(settings.gchat_webhook_url)}")
    print(f"  Notification Threshold: {settings.gchat_notification_threshold}")
    
    if not settings.gchat_webhook_url:
        print("\n⚠️  To enable Google Chat notifications:")
        print("   1. Create a Google Chat webhook URL")
        print("   2. Add to .env file: GCHAT_WEBHOOK_URL=<your-webhook-url>")
        print("   3. Add to .env file: ENABLE_GCHAT_NOTIFICATIONS=true")
        print("\n   See: https://developers.google.com/chat/how-tos/webhooks")
        return
    
    # Run tests
    results = []
    
    results.append(("Connection Test", test_connection()))
    results.append(("Simple Notification", test_simple_notification()))
    results.append(("Exception Notification", test_exception_notification()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70)


if __name__ == '__main__':
    main()
