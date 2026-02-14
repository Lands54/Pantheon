"""
CLI Utilities
Common helper functions for CLI commands.
"""
import requests


def get_base_url():
    """Get the base URL for the API server."""
    return "http://localhost:8000"


def handle_response(response, success_msg="Success", error_msg="Error"):
    """Handle API response and print appropriate message."""
    try:
        if response.status_code == 200:
            print(f"✅ {success_msg}")
            return response.json()
        else:
            print(f"❌ {error_msg}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ {error_msg}: {e}")
        return None
