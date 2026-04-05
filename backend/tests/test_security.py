from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_round_trip():
    raw_password = "demo_pass_123"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("wrong_pass_123", hashed) is False


def test_access_token_round_trip():
    token = create_access_token("42", expires_minutes=5)
    payload = decode_access_token(token)

    assert payload["sub"] == "42"
