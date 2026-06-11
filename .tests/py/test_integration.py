"""
Integration Tests for ABC Desktop API

Tests end-to-end workflows via HTTP requests.

# Last Update: 2026-03-18 04:10:00
# Author: Daniel Chung
# Version: 1.0.0
"""

import os
import urllib.request
import urllib.error
import json


API_BASE = os.getenv("API_BASE", "http://localhost:6500")


def make_request(method: str, path: str, data: dict = None, token: str = None) -> tuple:
    """Make HTTP request to API"""
    url = f"{API_BASE}{path}"
    
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    body = json.dumps(data).encode("utf-8") if data else None
    
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8")}


def test_health():
    """Test health endpoint"""
    status, body = make_request("GET", "/health")
    assert status == 200, f"Health check failed: {body}"
    assert body.get("status") == "healthy"
    print("✓ test_health passed")


def test_login_success():
    """Test successful login"""
    status, body = make_request("POST", "/api/v1/auth/login", {
        "username": "admin",
        "password": "admin123"
    })
    assert status == 200, f"Login failed: {body}"
    assert "data" in body
    assert "token" in body.get("data", {})
    print("✓ test_login_success passed")
    return body["data"]["token"]


def test_login_invalid_password():
    """Test login with wrong password"""
    status, body = make_request("POST", "/api/v1/auth/login", {
        "username": "admin",
        "password": "wrongpassword"
    })
    assert status == 401, f"Expected 401, got {status}"
    print("✓ test_login_invalid_password passed")


def test_login_nonexistent_user():
    """Test login with non-existent user"""
    status, body = make_request("POST", "/api/v1/auth/login", {
        "username": "nonexistent",
        "password": "password"
    })
    assert status == 401, f"Expected 401, got {status}"
    print("✓ test_login_nonexistent_user passed")


def test_list_users():
    """Test list users endpoint"""
    status, body = make_request("GET", "/api/v1/users")
    assert status == 200, f"List users failed: {body}"
    assert "data" in body
    print("✓ test_list_users passed")


def test_list_roles():
    """Test list roles endpoint"""
    status, body = make_request("GET", "/api/v1/roles")
    assert status == 200, f"List roles failed: {body}"
    assert "data" in body
    print("✓ test_list_roles passed")


def test_list_system_params():
    """Test list system params endpoint"""
    status, body = make_request("GET", "/api/v1/system-params")
    assert status == 200, f"List params failed: {body}"
    assert "data" in body
    params = body["data"]
    assert len(params) > 0, "No system params found"
    print("✓ test_list_system_params passed")


def test_get_user():
    """Test get specific user"""
    status, body = make_request("GET", "/api/v1/users/admin")
    assert status == 200, f"Get user failed: {body}"
    assert body.get("data", {}).get("username") == "admin"
    print("✓ test_get_user passed")


def test_get_role():
    """Test get specific role"""
    status, body = make_request("GET", "/api/v1/roles/admin")
    assert status == 200, f"Get role failed: {body}"
    assert body.get("data", {}).get("_key") == "admin"
    print("✓ test_get_role passed")


def test_auth_me_with_token():
    """Test /auth/me endpoint with valid token"""
    status, login_body = make_request("POST", "/api/v1/auth/login", {
        "username": "admin",
        "password": "admin123"
    })
    token = login_body.get("data", {}).get("token")
    
    status, body = make_request("GET", "/api/v1/auth/me", token=token)
    assert status == 200, f"Auth me failed: {body}"
    assert body.get("data", {}).get("username") == "admin"
    print("✓ test_auth_me_with_token passed")


def test_auth_me_without_token():
    """Test /auth/me endpoint without token"""
    status, body = make_request("GET", "/api/v1/auth/me")
    assert status == 401, f"Expected 401, got {status}"
    print("✓ test_auth_me_without_token passed")


def test_logout():
    """Test logout endpoint"""
    status, body = make_request("POST", "/api/v1/auth/logout")
    assert status == 200, f"Logout failed: {body}"
    print("✓ test_logout passed")


if __name__ == "__main__":
    print("Running Integration Tests...\n")
    
    test_health()
    test_login_success()
    test_login_invalid_password()
    test_login_nonexistent_user()
    test_list_users()
    test_list_roles()
    test_list_system_params()
    test_get_user()
    test_get_role()
    test_auth_me_with_token()
    test_auth_me_without_token()
    test_logout()
    
    print("\n✅ All Integration Tests Passed!")
