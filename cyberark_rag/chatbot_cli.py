"""
Interactive CLI for CyberArk RAG chatbot.

Provides an async REPL with prompt_toolkit for non-blocking input,
command history, and streaming output.
"""

import asyncio
import sys

from cyberark_rag.config import Settings
from cyberark_rag.logging_config import setup_logging

logger = setup_logging(__name__)

HELP_TEXT = """\
Commands:
  /clear   - Reset conversation history
  /stats   - Show index statistics
  /status  - Show authentication status
  /help    - Show this help
  /quit    - Exit"""


async def chat_repl(model: str) -> None:
    """Async REPL with prompt_toolkit for non-blocking input.

    Args:
        model: Claude model ID to use.
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory

    from cyberark_rag.auth import AuthConfig, show_status
    from cyberark_rag.chatbot import CyberArkChatbot

    # Resolve auth before creating chatbot (fail fast with helpful message)
    try:
        AuthConfig.resolve()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Set up input history
    history_dir = Settings.PROJECT_ROOT / ".config"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / "chat_history"

    session = PromptSession(history=FileHistory(str(history_file)))
    bot = CyberArkChatbot(model=model)

    print(f"CyberArk RAG Chatbot ({model})")
    print("Type /help for commands, Ctrl+C to exit")
    print("-" * 50)

    try:
        while True:
            try:
                user_input = await session.prompt_async("\nYou: ")
                user_input = user_input.strip()
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                cmd = user_input.split()[0].lower()

                if cmd == "/quit":
                    break

                elif cmd == "/clear":
                    bot.reset()
                    print("Conversation cleared.")
                    continue

                elif cmd == "/stats":
                    try:
                        result = await bot._execute_tool("get_index_stats", {})
                        print(result)
                    except Exception as e:
                        print(f"Error: {e}", file=sys.stderr)
                    continue

                elif cmd == "/status":
                    await show_status()
                    continue

                elif cmd == "/help":
                    print(HELP_TEXT)
                    continue

                else:
                    print(f"Unknown command: {cmd}. Type /help for commands.")
                    continue

            # Stream response
            print("\nAssistant: ", end="", flush=True)
            try:
                async for chunk in bot.chat_stream(user_input):
                    print(chunk, end="", flush=True)
                print()
            except Exception as e:
                print(f"\nError: {e}", file=sys.stderr)

    finally:
        await bot.close()
        print("\nGoodbye!")


def main() -> None:
    """CLI entry point for chatbot."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CyberArk RAG Chatbot - Chat with Claude about CyberArk docs"
    )
    parser.add_argument(
        "--model",
        default=Settings.CHATBOT_MODEL,
        help=f"Claude model ID (default: {Settings.CHATBOT_MODEL})",
    )
    args = parser.parse_args()

    asyncio.run(chat_repl(model=args.model))


if __name__ == "__main__":
    main()
