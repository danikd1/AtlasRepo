
import pytest
from fastapi import HTTPException

from src.auth.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

def test_hash_password_not_equal_to_plain():
    
    hashed = hash_password("secret123")
    assert hashed != "secret123"

def test_hash_password_different_hashes_for_same_password():
    
    hash1 = hash_password("secret123")
    hash2 = hash_password("secret123")
    assert hash1 != hash2

def test_verify_password_correct():
    
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True

def test_verify_password_wrong():
    
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False

def test_verify_password_empty():
    
    hashed = hash_password("mypassword")
    assert verify_password("", hashed) is False

def test_create_access_token_returns_string():
    
    token = create_access_token(user_id=42)
    assert isinstance(token, str)
    assert len(token) > 0

def test_create_and_decode_token_same_user_id():
    
    user_id = 99
    token = create_access_token(user_id=user_id)
    decoded_id = decode_access_token(token)
    assert decoded_id == user_id

def test_decode_access_token_correct_user_id():
    
    token = create_access_token(user_id=7)
    assert decode_access_token(token) == 7

def test_decode_access_token_invalid_token_raises():
    
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("this.is.not.a.valid.token")
assert exc_info.value.status_code == 401

def test_decode_access_token_no_sub_raises():
    
    from jose import jwt
    from config.config import JWT_SECRET, JWT_ALGORITHM
    from datetime import datetime, timedelta, timezone

    payload = {"exp": datetime.now(timezone.utc) + timedelta(days=1)}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
assert exc_info.value.status_code == 401
