import time
from unittest.mock import MagicMock, patch

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient

from cms_aipilot.auth import ALGORITHM
from cms_aipilot.main import app

client = TestClient(app)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "correct-horse-battery-staple"
ADMIN_PASSWORD_HASH = bcrypt.hashpw(ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode(
    "utf-8"
)
JWT_SECRET = "test-secret-value-that-is-at-least-32-bytes-long"


@pytest.fixture(autouse=True)
def _clear_ssm_cache():
    """SSM getters are lru_cache-wrapped; clear between tests for isolation."""
    from cms_aipilot import auth as auth_module

    auth_module.get_jwt_secret.cache_clear()
    auth_module.get_admin_username.cache_clear()
    auth_module.get_admin_password_hash.cache_clear()
    yield
    auth_module.get_jwt_secret.cache_clear()
    auth_module.get_admin_username.cache_clear()
    auth_module.get_admin_password_hash.cache_clear()


@pytest.fixture
def mock_ssm(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_SSM_PARAM", "/cms-aipilot/auth/jwt-secret")
    monkeypatch.setenv("ADMIN_USERNAME_SSM_PARAM", "/cms-aipilot/auth/admin-username")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH_SSM_PARAM", "/cms-aipilot/auth/admin-password-hash"
    )

    values = {
        "/cms-aipilot/auth/jwt-secret": JWT_SECRET,
        "/cms-aipilot/auth/admin-username": ADMIN_USERNAME,
        "/cms-aipilot/auth/admin-password-hash": ADMIN_PASSWORD_HASH,
    }

    def fake_get_parameter(Name, WithDecryption=True):
        return {"Parameter": {"Value": values[Name]}}

    fake_ssm_client = MagicMock()
    fake_ssm_client.get_parameter.side_effect = fake_get_parameter

    with patch("cms_aipilot.auth.boto3.client", return_value=fake_ssm_client):
        yield fake_ssm_client


@pytest.fixture
def mock_auth_table():
    fake_table = MagicMock()
    fake_table.get_item.return_value = {}
    with patch("cms_aipilot.main.get_auth_table", return_value=fake_table):
        yield fake_table


def auth_item(failed_attempts=0, locked_until=0):
    return {
        "Item": {
            "id": "admin_login_state",
            "failed_attempts": failed_attempts,
            "locked_until": locked_until,
        }
    }


class TestLoginSuccess:
    """Scenario: 帳密正確,登入成功並核發 JWT"""

    def test_returns_200(self, mock_ssm, mock_auth_table):
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200

    def test_response_contains_access_token_and_bearer_type(self, mock_ssm, mock_auth_table):
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_jwt_signed_hs256_with_sub_iat_exp(self, mock_ssm, mock_auth_table):
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        token = response.json()["access_token"]
        header = jwt.get_unverified_header(token)
        assert header["alg"] == ALGORITHM

        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        assert payload["sub"] == ADMIN_USERNAME
        assert "iat" in payload
        assert "exp" in payload

    def test_jwt_expires_in_8_hours(self, mock_ssm, mock_auth_table):
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        token = response.json()["access_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        assert payload["exp"] - payload["iat"] == 8 * 60 * 60

    def test_resets_failed_attempts_to_zero(self, mock_ssm, mock_auth_table):
        mock_auth_table.get_item.return_value = auth_item(failed_attempts=3, locked_until=0)
        client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        mock_auth_table.put_item.assert_called_once()
        item = mock_auth_table.put_item.call_args.kwargs["Item"]
        assert item["failed_attempts"] == 0
        assert item["locked_until"] == 0


class TestLoginWrongPassword:
    """Scenario: 密碼錯誤,登入被拒絕"""

    def test_returns_401(self, mock_ssm, mock_auth_table):
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": "wrong-password"}
        )
        assert response.status_code == 401

    def test_no_token_in_response(self, mock_ssm, mock_auth_table):
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": "wrong-password"}
        )
        assert "access_token" not in response.json()

    def test_increments_failed_attempts(self, mock_ssm, mock_auth_table):
        mock_auth_table.get_item.return_value = auth_item(failed_attempts=0, locked_until=0)
        client.post("/login", json={"username": ADMIN_USERNAME, "password": "wrong-password"})
        mock_auth_table.put_item.assert_called_once()
        item = mock_auth_table.put_item.call_args.kwargs["Item"]
        assert item["failed_attempts"] == 1


class TestLoginLockoutTriggered:
    """Scenario: 連續失敗達到門檻,帳號進入鎖定狀態"""

    def test_fifth_failure_returns_401_and_locks(self, mock_ssm, mock_auth_table):
        mock_auth_table.get_item.return_value = auth_item(failed_attempts=4, locked_until=0)
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": "wrong-password"}
        )
        assert response.status_code == 401

        item = mock_auth_table.put_item.call_args.kwargs["Item"]
        assert item["failed_attempts"] == 5
        now = int(time.time())
        assert item["locked_until"] > now
        assert item["locked_until"] <= now + 15 * 60 + 5


class TestLoginWhileLocked:
    """Scenario: 帳號鎖定期間,即使帳密正確也拒絕登入"""

    def test_returns_429(self, mock_ssm, mock_auth_table):
        locked_until = int(time.time()) + 600
        mock_auth_table.get_item.return_value = auth_item(
            failed_attempts=5, locked_until=locked_until
        )
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 429

    def test_response_includes_retry_after_info(self, mock_ssm, mock_auth_table):
        locked_until = int(time.time()) + 600
        mock_auth_table.get_item.return_value = auth_item(
            failed_attempts=5, locked_until=locked_until
        )
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        body = response.json()
        assert "retry_after_seconds" in body
        assert body["retry_after_seconds"] > 0
        assert "Retry-After" in response.headers

    def test_no_token_issued(self, mock_ssm, mock_auth_table):
        locked_until = int(time.time()) + 600
        mock_auth_table.get_item.return_value = auth_item(
            failed_attempts=5, locked_until=locked_until
        )
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        assert "access_token" not in response.json()

    def test_does_not_increment_failed_attempts(self, mock_ssm, mock_auth_table):
        locked_until = int(time.time()) + 600
        mock_auth_table.get_item.return_value = auth_item(
            failed_attempts=5, locked_until=locked_until
        )
        client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        mock_auth_table.put_item.assert_not_called()


class TestLoginAfterLockoutExpires:
    """Scenario: 鎖定時間到期後,允許重新嘗試登入"""

    def test_returns_200_with_new_jwt(self, mock_ssm, mock_auth_table):
        expired_lock = int(time.time()) - 60
        mock_auth_table.get_item.return_value = auth_item(
            failed_attempts=5, locked_until=expired_lock
        )
        response = client.post(
            "/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_resets_failed_attempts(self, mock_ssm, mock_auth_table):
        expired_lock = int(time.time()) - 60
        mock_auth_table.get_item.return_value = auth_item(
            failed_attempts=5, locked_until=expired_lock
        )
        client.post("/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        item = mock_auth_table.put_item.call_args.kwargs["Item"]
        assert item["failed_attempts"] == 0
        assert item["locked_until"] == 0


class TestDecodeAccessTokenValid:
    """Scenario: 提供有效 JWT 可通過 token 驗證函式"""

    def test_returns_payload_with_sub(self, mock_ssm):
        from cms_aipilot.auth import create_access_token, decode_access_token

        token = create_access_token(subject=ADMIN_USERNAME)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == ADMIN_USERNAME


class TestDecodeAccessTokenInvalid:
    """Scenario: 提供過期或簽章錯誤的 JWT,驗證失敗"""

    def test_expired_token_returns_none(self, mock_ssm):
        from cms_aipilot.auth import decode_access_token

        now = int(time.time())
        expired_payload = {"sub": ADMIN_USERNAME, "iat": now - 100, "exp": now - 50}
        expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm=ALGORITHM)

        result = decode_access_token(expired_token)
        assert result is None

    def test_bad_signature_returns_none(self, mock_ssm):
        from cms_aipilot.auth import decode_access_token

        now = int(time.time())
        payload = {"sub": ADMIN_USERNAME, "iat": now, "exp": now + 3600}
        wrong_secret_token = jwt.encode(
            payload, "wrong-secret-value-that-is-at-least-32-bytes", algorithm=ALGORITHM
        )

        result = decode_access_token(wrong_secret_token)
        assert result is None

    def test_malformed_token_returns_none(self, mock_ssm):
        from cms_aipilot.auth import decode_access_token

        result = decode_access_token("not-a-jwt-token")
        assert result is None

    def test_does_not_raise(self, mock_ssm):
        from cms_aipilot.auth import decode_access_token

        try:
            decode_access_token("")
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"decode_access_token raised an exception: {exc}")
