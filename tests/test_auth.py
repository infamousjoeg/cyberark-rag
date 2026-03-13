"""Tests for cyberark_rag/auth.py credential management."""

import json
import os

import pytest

from cyberark_rag.auth import AuthConfig, _mask_token, CREDENTIALS_FILE


class TestMaskToken:
    """Tests for token masking."""

    def test_short_token(self):
        assert _mask_token("sk-ab") == "sk-a..."

    def test_long_token(self):
        result = _mask_token("sk-ant-oat01-abcdefghijklmnop")
        assert result.startswith("sk-ant-oat01")
        assert result.endswith("mnop")
        assert "..." in result

    def test_empty_token(self):
        result = _mask_token("")
        assert result == "..."


class TestAuthConfigResolve:
    """Tests for credential resolution order."""

    def test_oauth_env_var_takes_precedence(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-token-123")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "api-key-456")

        auth_type, token = AuthConfig.resolve()
        assert auth_type == "oauth"
        assert token == "oauth-token-123"

    def test_api_key_env_var_second(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "api-key-456")

        auth_type, token = AuthConfig.resolve()
        assert auth_type == "api_key"
        assert token == "api-key-456"

    def test_credentials_file_fallback(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        # Write a credentials file
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({
            "auth_type": "oauth",
            "token": "file-token-789",
        }))

        monkeypatch.setattr("cyberark_rag.auth.CREDENTIALS_FILE", creds_file)

        auth_type, token = AuthConfig.resolve()
        assert auth_type == "oauth"
        assert token == "file-token-789"

    def test_no_credentials_raises(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        # Point to nonexistent file
        monkeypatch.setattr(
            "cyberark_rag.auth.CREDENTIALS_FILE",
            tmp_path / "nonexistent.json",
        )

        with pytest.raises(ValueError, match="No credentials found"):
            AuthConfig.resolve()

    def test_empty_token_in_file_raises(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({
            "auth_type": "api_key",
            "token": "",
        }))
        monkeypatch.setattr("cyberark_rag.auth.CREDENTIALS_FILE", creds_file)

        with pytest.raises(ValueError, match="No credentials found"):
            AuthConfig.resolve()


class TestAuthConfigSave:
    """Tests for credential file I/O."""

    def test_save_creates_file(self, monkeypatch, tmp_path):
        creds_dir = tmp_path / ".config" / "cyberark-rag"
        creds_file = creds_dir / "credentials.json"

        monkeypatch.setattr("cyberark_rag.auth.CREDENTIALS_DIR", creds_dir)
        monkeypatch.setattr("cyberark_rag.auth.CREDENTIALS_FILE", creds_file)

        AuthConfig.save("api_key", "test-token-123")

        assert creds_file.exists()
        data = json.loads(creds_file.read_text())
        assert data["auth_type"] == "api_key"
        assert data["token"] == "test-token-123"
        assert "created_at" in data

    def test_save_sets_permissions(self, monkeypatch, tmp_path):
        creds_dir = tmp_path / ".config" / "cyberark-rag"
        creds_file = creds_dir / "credentials.json"

        monkeypatch.setattr("cyberark_rag.auth.CREDENTIALS_DIR", creds_dir)
        monkeypatch.setattr("cyberark_rag.auth.CREDENTIALS_FILE", creds_file)

        AuthConfig.save("oauth", "test-token")

        mode = oct(creds_file.stat().st_mode)[-3:]
        assert mode == "600"

    def test_save_load_roundtrip(self, monkeypatch, tmp_path):
        creds_dir = tmp_path / ".config" / "cyberark-rag"
        creds_file = creds_dir / "credentials.json"

        monkeypatch.setattr("cyberark_rag.auth.CREDENTIALS_DIR", creds_dir)
        monkeypatch.setattr("cyberark_rag.auth.CREDENTIALS_FILE", creds_file)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        AuthConfig.save("oauth", "roundtrip-token")

        auth_type, token = AuthConfig.resolve()
        assert auth_type == "oauth"
        assert token == "roundtrip-token"


class TestAuthConfigRemove:
    """Tests for credential removal."""

    def test_remove_existing_file(self, monkeypatch, tmp_path):
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        monkeypatch.setattr("cyberark_rag.auth.CREDENTIALS_FILE", creds_file)

        assert AuthConfig.remove() is True
        assert not creds_file.exists()

    def test_remove_nonexistent_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "cyberark_rag.auth.CREDENTIALS_FILE",
            tmp_path / "nonexistent.json",
        )

        assert AuthConfig.remove() is False


class TestAuthConfigStatus:
    """Tests for auth status reporting."""

    def test_status_from_oauth_env(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-test")

        status = AuthConfig.status()
        assert status is not None
        assert status["auth_type"] == "oauth"
        assert "CLAUDE_CODE_OAUTH_TOKEN" in status["source"]

    def test_status_from_api_key_env(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-test")

        status = AuthConfig.status()
        assert status is not None
        assert status["auth_type"] == "api_key"

    def test_status_not_configured(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(
            "cyberark_rag.auth.CREDENTIALS_FILE",
            tmp_path / "nonexistent.json",
        )

        status = AuthConfig.status()
        assert status is None
