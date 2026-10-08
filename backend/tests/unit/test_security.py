import jwt
import pytest

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_password, hash_token, new_refresh_token, verify_password


def test_password_hashing_round_trip():
    hashed = hash_password("correct horse 1")
    assert hashed != "correct horse 1" and hashed.startswith("$argon2")
    assert verify_password("correct horse 1", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_contains_subject_and_expires():
    token, expires_in = create_access_token(42, "learner")
    payload = decode_access_token(token)
    assert payload["sub"] == "42" and payload["role"] == "learner"
    assert expires_in == settings.access_token_minutes * 60


def test_tampered_token_is_rejected():
    token, _ = create_access_token(1, "learner")
    forged = jwt.encode({"sub": "1", "role": "admin"}, "an-attacker-controlled-secret-0123456789", algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token[:-2] + "xx")


def test_refresh_tokens_are_random_and_stored_hashed():
    a, b = new_refresh_token(), new_refresh_token()
    assert a != b and len(a) >= 40
    assert hash_token(a) != a and len(hash_token(a)) == 64
