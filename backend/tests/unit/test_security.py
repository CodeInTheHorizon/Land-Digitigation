"""Tests for JWT and password utilities."""

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "test_password_123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)


class TestJWT:
    def test_access_token_round_trip(self):
        token = create_access_token("user-id-123")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-id-123"
        assert payload["type"] == "access"

    def test_refresh_token_round_trip(self):
        token = create_refresh_token("user-id-456")
        payload = decode_token(token, token_type="refresh")
        assert payload is not None
        assert payload["sub"] == "user-id-456"
        assert payload["type"] == "refresh"

    def test_refresh_token_rejected_as_access(self):
        """A refresh token must not be accepted as an access token."""
        token = create_refresh_token("user-id-789")
        assert decode_token(token, token_type="access") is None

    def test_access_token_rejected_as_refresh(self):
        """An access token must not be accepted as a refresh token."""
        token = create_access_token("user-id-789")
        assert decode_token(token, token_type="refresh") is None

    def test_invalid_token(self):
        assert decode_token("not.a.valid.token") is None
