#!/usr/bin/env python3
"""Test the shopping item delete endpoint."""

import requests

# Base URL for the app
BASE_URL = "http://localhost:8008"

# Test endpoints
endpoints = [
    ("GET (should fail)", "GET", f"{BASE_URL}/shopping/api/item/13/delete/"),
    ("POST (should work)", "POST", f"{BASE_URL}/shopping/api/item/13/delete/"),
]

print("Testing delete endpoint methods:\n")
print("-" * 50)

for label, method, url in endpoints:
    try:
        if method == "GET":
            response = requests.get(url, allow_redirects=False)
        else:
            response = requests.post(url, allow_redirects=False)
        
        print(f"{label}:")
        print(f"  URL: {url}")
        print(f"  Method: {method}")
        print(f"  Status: {response.status_code} {response.reason}")
        
        # Check if it's a Method Not Allowed error
        if response.status_code == 405:
            print(f"  ✗ Method Not Allowed")
        elif response.status_code == 302:
            print(f"  → Redirecting to login (authentication required)")
        else:
            print(f"  Response: {response.text[:100] if response.text else 'No content'}")
        print()
    except Exception as e:
        print(f"{label}: ERROR - {e}\n")

print("-" * 50)
print("\nSummary:")
print("- GET request should return 405 (Method Not Allowed) or redirect to login")
print("- POST request should redirect to login (since we're not authenticated)")
print("- Both prove the endpoint now correctly handles HTTP methods")