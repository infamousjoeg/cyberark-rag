"""
Authentication and credential management for CyberArk RAG chatbot.

Supports two authentication methods:
- OAuth Token (Claude Pro/Max subscription via CLAUDE_CODE_OAUTH_TOKEN)
- API Key (console.anthropic.com via ANTHROPIC_API_KEY)

Credentials are stored in ~/.config/cyberark-rag/credentials.json with 0600 permissions.
Environment variables take precedence over the credentials file.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CREDENTIALS_DIR = Path.home() / ".config" / "cyberark-rag"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"


class AuthConfig:
    """Load and manage authentication credentials."""

    @staticmethod
    def resolve() -> tuple[str, str]:
        """Resolve credentials from env vars or credentials file.

        Lookup order:
        1. CLAUDE_CODE_OAUTH_TOKEN env var -> ("oauth", token)
        2. ANTHROPIC_API_KEY env var -> ("api_key", token)
        3. ~/.config/cyberark-rag/credentials.json

        Returns:
            Tuple of (auth_type, token).

        Raises:
            ValueError: If no credentials found.
        """
        # 1. Environment variables
        oauth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        if oauth_token:
            return ("oauth", oauth_token)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return ("api_key", api_key)

        # 2. Credentials file
        if CREDENTIALS_FILE.exists():
            try:
                data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
                auth_type = data.get("auth_type", "api_key")
                token = data.get("token", "")
                if token:
                    return (auth_type, token)
            except (json.JSONDecodeError, KeyError):
                pass

        raise ValueError(
            "No credentials found. Run 'python -m cyberark_rag auth login' to set up authentication, "
            "or set ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN environment variable."
        )

    @staticmethod
    def save(auth_type: str, token: str, model: str = "claude-sonnet-4-6") -> None:
        """Save credentials to file with secure permissions.

        Args:
            auth_type: "oauth" or "api_key"
            token: The authentication token
            model: Claude model ID (stored for reference)
        """
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "auth_type": auth_type,
            "token": token,
            "model": model,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        CREDENTIALS_FILE.write_text(
            json.dumps(data, indent=2) + "\n",
            encoding="utf-8",
        )

        # Set file permissions to owner-only read/write (0600)
        CREDENTIALS_FILE.chmod(0o600)

    @staticmethod
    def remove() -> bool:
        """Delete credentials file.

        Returns:
            True if file was removed, False if it did not exist.
        """
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()
            return True
        return False

    @staticmethod
    def status() -> Optional[dict]:
        """Return current auth status or None if not configured.

        Returns:
            Dict with auth_type, token_prefix, model, created_at, source.
        """
        # Check env vars first
        oauth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        if oauth_token:
            return {
                "auth_type": "oauth",
                "token_prefix": _mask_token(oauth_token),
                "source": "CLAUDE_CODE_OAUTH_TOKEN env var",
            }

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            return {
                "auth_type": "api_key",
                "token_prefix": _mask_token(api_key),
                "source": "ANTHROPIC_API_KEY env var",
            }

        # Check credentials file
        if CREDENTIALS_FILE.exists():
            try:
                data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
                return {
                    "auth_type": data.get("auth_type", "unknown"),
                    "token_prefix": _mask_token(data.get("token", "")),
                    "model": data.get("model"),
                    "created_at": data.get("created_at"),
                    "source": str(CREDENTIALS_FILE),
                }
            except (json.JSONDecodeError, KeyError):
                pass

        return None


def _mask_token(token: str) -> str:
    """Mask a token for display, showing prefix and last 4 chars."""
    if len(token) <= 12:
        return token[:4] + "..."
    return token[:12] + "..." + token[-4:]


async def validate_token(auth_type: str, token: str) -> bool:
    """Validate a token by making a lightweight API call.

    Args:
        auth_type: "oauth" or "api_key"
        token: The authentication token

    Returns:
        True if the token is valid.
    """
    import anthropic

    try:
        if auth_type == "oauth":
            client = anthropic.AsyncAnthropic(auth_token=token)
        else:
            client = anthropic.AsyncAnthropic(api_key=token)

        # Make a minimal API call to validate
        await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True
    except anthropic.AuthenticationError:
        return False
    except Exception:
        # Network errors, rate limits, etc. -- token format may still be valid
        return True
    finally:
        await client.close()


async def login_interactive() -> None:
    """Interactive login wizard."""
    import asyncio

    print("CyberArk RAG - Authentication Setup")
    print("=" * 40)
    print()
    print("Choose authentication method:")
    print("  1) OAuth Token (Claude Pro/Max subscription)")
    print("  2) API Key (console.anthropic.com)")
    print()

    choice = input("Selection [1/2]: ").strip()

    if choice == "1":
        auth_type = "oauth"
        print()
        print("To get your OAuth token:")
        print("  1. Install Claude CLI: npm install -g @anthropic-ai/claude-code")
        print("  2. Run: claude setup-token")
        print("  3. Copy the token below")
        print()
        token = input("Paste OAuth token: ").strip()
    elif choice == "2":
        auth_type = "api_key"
        print()
        print("Get an API key from: https://console.anthropic.com/settings/keys")
        print()
        token = input("Paste API key: ").strip()
    else:
        print("Invalid selection.", file=sys.stderr)
        sys.exit(1)

    if not token:
        print("No token provided.", file=sys.stderr)
        sys.exit(1)

    print()
    print("Validating...", end=" ", flush=True)

    valid = await validate_token(auth_type, token)

    if not valid:
        print("FAILED")
        print("Authentication failed. Check your token and try again.", file=sys.stderr)
        sys.exit(1)

    print("OK")

    AuthConfig.save(auth_type, token)
    print(f"Credentials saved to {CREDENTIALS_FILE}")


async def show_status() -> None:
    """Print current authentication status."""
    status = AuthConfig.status()

    if status is None:
        print("Not authenticated.")
        print("Run 'python -m cyberark_rag auth login' to set up.")
        return

    print("Authentication Status")
    print("-" * 40)
    print(f"  Method:  {status['auth_type']}")
    print(f"  Token:   {status['token_prefix']}")
    print(f"  Source:  {status['source']}")
    if status.get("model"):
        print(f"  Model:   {status['model']}")
    if status.get("created_at"):
        print(f"  Created: {status['created_at']}")


def logout() -> None:
    """Remove stored credentials."""
    if AuthConfig.remove():
        print("Credentials removed.")
    else:
        print("No credentials file found.")


def main() -> None:
    """CLI entry point for auth subcommands."""
    import asyncio

    if len(sys.argv) < 1:
        print("Usage: python -m cyberark_rag auth [login|status|logout]")
        sys.exit(1)

    subcommand = sys.argv[0] if sys.argv else "status"

    if subcommand == "login":
        asyncio.run(login_interactive())
    elif subcommand == "status":
        asyncio.run(show_status())
    elif subcommand == "logout":
        logout()
    else:
        print(f"Unknown auth command: {subcommand}")
        print("Valid commands: login, status, logout")
        sys.exit(1)
