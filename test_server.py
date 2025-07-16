#!/usr/bin/env python3
"""
Test script to verify the server is running
"""
import requests
import time

def test_server():
    base_url = "http://localhost:5000"
    
    # Test endpoints
    endpoints = [
        "/",
        "/health",
        "/admin"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            print(f"✓ {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"✗ {endpoint}: Error - {e}")

if __name__ == "__main__":
    test_server()