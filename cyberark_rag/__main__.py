"""
CLI entry point for cyberark_rag package.
"""

import sys


def main():
    """
    Main CLI entry point that routes to indexer, search, MCP server, or terminal based on subcommand.
    """
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m cyberark_rag index        - Build the vector index")
        print("  python -m cyberark_rag search       - Search the documentation")
        print("  python -m cyberark_rag mcp_server   - Start the MCP server")
        print("  python -m cyberark_rag terminal     - Natural language terminal assistant")
        print("\nFor help on specific commands:")
        print("  python -m cyberark_rag index --help")
        print("  python -m cyberark_rag search --help")
        print("  python -m cyberark_rag terminal --help")
        sys.exit(1)

    command = sys.argv[1]

    # Remove the subcommand from argv
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if command == "index":
        from cyberark_rag.indexer import main as indexer_main
        indexer_main()
    elif command == "search":
        from cyberark_rag.search import main as search_main
        search_main()
    elif command == "mcp_server":
        from cyberark_rag.mcp_server import main as mcp_server_main
        mcp_server_main()
    elif command == "terminal":
        from cyberark_rag.terminal import main as terminal_main
        terminal_main()
    else:
        print(f"Unknown command: {command}")
        print("Valid commands: index, search, mcp_server, terminal")
        sys.exit(1)


if __name__ == "__main__":
    main()
