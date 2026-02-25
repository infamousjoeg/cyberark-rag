"""
Terminal Integration for CyberArk RAG

This module provides natural language command generation using:
- MCP server for CyberArk documentation context
- Ollama for command generation
"""

import shutil
import sys
import json
import subprocess
from typing import Optional, Dict, Any, List
from pathlib import Path

import requests
import yaml

from cyberark_rag.config import Settings


class Config:
    """Configuration handler for terminal integration."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.yaml (defaults to project root)
        """
        if config_path is None:
            config_path = Settings.CONFIG_YAML_PATH

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Return default configuration
            return {
                'ollama': {
                    'endpoint': 'http://localhost:11434',
                    'model': 'llama3.1'
                },
                'mcp': {
                    'python_path': shutil.which("python3") or "python3",
                    'max_context_chunks': 3
                },
                'execution': {
                    'auto_execute': False,
                    'show_context': False
                }
            }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value


def communicate_with_mcp(
    query: str,
    tool: str = 'search_cyberark_docs',
    top_k: int = 3,
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Communicate with MCP server to get CyberArk documentation context.

    Args:
        query: Search query
        tool: MCP tool name
        top_k: Number of results to return
        config: Configuration object

    Returns:
        Dictionary with search results
    """
    if config is None:
        config = Config()

    python_path = config.get('mcp.python_path', 'python3')

    # Prepare MCP server command
    cmd = [
        python_path,
        '-m',
        'cyberark_rag.mcp_server'
    ]

    try:
        # Start MCP server as subprocess
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Send initialization request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "cyberark-rag-terminal",
                    "version": "1.0.0"
                }
            }
        }

        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()

        # Read initialization response
        init_response = process.stdout.readline()

        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }

        process.stdin.write(json.dumps(initialized_notification) + '\n')
        process.stdin.flush()

        # Prepare tool call request
        tool_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": {
                    "query": query,
                    "top_k": top_k
                }
            }
        }

        process.stdin.write(json.dumps(tool_request) + '\n')
        process.stdin.flush()

        # Read tool response
        tool_response_line = process.stdout.readline()

        # Close the process
        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)

        # Parse response
        if tool_response_line:
            tool_response = json.loads(tool_response_line)

            if 'result' in tool_response:
                result = tool_response['result']

                # Extract text content from MCP response
                if 'content' in result and len(result['content']) > 0:
                    text_content = result['content'][0].get('text', '')
                    return {
                        'success': True,
                        'context': text_content,
                        'query': query
                    }

            # If we have an error
            if 'error' in tool_response:
                return {
                    'success': False,
                    'error': tool_response['error'].get('message', 'Unknown error'),
                    'query': query
                }

        return {
            'success': False,
            'error': 'No response from MCP server',
            'query': query
        }

    except subprocess.TimeoutExpired:
        process.kill()
        return {
            'success': False,
            'error': 'MCP server timeout',
            'query': query
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'MCP communication error: {str(e)}',
            'query': query
        }


def generate_command(
    natural_language: str,
    context: str,
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Generate shell command using Ollama with CyberArk documentation context.

    Args:
        natural_language: Natural language description of desired command
        context: CyberArk documentation context from MCP
        config: Configuration object

    Returns:
        Dictionary with generated command
    """
    if config is None:
        config = Config()

    ollama_endpoint = config.get('ollama.endpoint', 'http://localhost:11434')
    ollama_model = config.get('ollama.model', 'llama3.1')

    # Construct enhanced prompt
    prompt = f"""You are a CyberArk command-line expert. Based on the following CyberArk documentation context, generate a shell command.

CyberArk Documentation Context:
{context}

User Request: {natural_language}

Generate ONLY the shell command that accomplishes the user's request based on the documentation context. Do not include explanations, markdown formatting, or code blocks. Output only the raw command.

Command:"""

    # Prepare Ollama API request
    ollama_request = {
        'model': ollama_model,
        'prompt': prompt,
        'stream': False,
        'options': {
            'temperature': 0.3,  # Lower temperature for more deterministic output
            'top_p': 0.9,
            'num_predict': 200
        }
    }

    try:
        # Call Ollama API
        response = requests.post(
            f'{ollama_endpoint}/api/generate',
            json=ollama_request,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            command = result.get('response', '').strip()

            # Clean up the command (remove markdown code blocks if present)
            if command.startswith('```'):
                lines = command.split('\n')
                command = '\n'.join([l for l in lines if not l.startswith('```')])
                command = command.strip()

            # Remove any "Command:" prefix if present
            if command.lower().startswith('command:'):
                command = command[8:].strip()

            return {
                'success': True,
                'command': command,
                'natural_language': natural_language,
                'context_used': bool(context)
            }
        else:
            return {
                'success': False,
                'error': f'Ollama API error: HTTP {response.status_code}',
                'natural_language': natural_language
            }

    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': 'Cannot connect to Ollama. Is it running? (Start with: ollama serve)',
            'natural_language': natural_language
        }
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': 'Ollama request timeout',
            'natural_language': natural_language
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Ollama error: {str(e)}',
            'natural_language': natural_language
        }


def execute_with_confirmation(
    natural_language: str,
    config: Optional[Config] = None,
    auto_execute: Optional[bool] = None
) -> None:
    """
    Main workflow: Get context, generate command, confirm, execute.

    Args:
        natural_language: Natural language command description
        config: Configuration object
        auto_execute: Override auto_execute config setting
    """
    if config is None:
        config = Config()

    if auto_execute is None:
        auto_execute = config.get('execution.auto_execute', False)

    show_context = config.get('execution.show_context', False)
    max_context_chunks = config.get('mcp.max_context_chunks', 3)

    print(f"🔍 Searching CyberArk documentation for: {natural_language}")

    # Step 1: Get CyberArk documentation context
    mcp_result = communicate_with_mcp(
        query=natural_language,
        top_k=max_context_chunks,
        config=config
    )

    if not mcp_result['success']:
        print(f"❌ Error getting documentation context: {mcp_result.get('error', 'Unknown error')}")
        return

    context = mcp_result.get('context', '')

    if not context:
        print("⚠️  No relevant documentation found. Generating command without specific context...")
        context = "No specific CyberArk documentation found. Generate a general command."
    else:
        print(f"✓ Found relevant documentation ({max_context_chunks} chunks)")

    if show_context:
        print(f"\n📚 Context:\n{context[:500]}...\n")

    # Step 2: Generate command using Ollama
    print(f"🤖 Generating command with Ollama...")

    command_result = generate_command(
        natural_language=natural_language,
        context=context,
        config=config
    )

    if not command_result['success']:
        print(f"❌ Error generating command: {command_result.get('error', 'Unknown error')}")
        return

    command = command_result.get('command', '')

    if not command:
        print("❌ No command generated")
        return

    # Step 3: Display command
    print(f"\n💻 Generated Command:")
    print(f"   {command}\n")

    # Step 4: Confirm execution
    if auto_execute:
        print("⚡ Auto-executing (auto_execute=true)...")
        execute = True
    else:
        try:
            response = input("Execute? (y/n): ").strip().lower()
            execute = response in ['y', 'yes']
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Cancelled")
            return

    # Step 5: Execute if confirmed
    if execute:
        print(f"\n▶️  Executing...\n")
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=False,
                text=True
            )

            if result.returncode != 0:
                print(f"\n⚠️  Command exited with code {result.returncode}")
            else:
                print(f"\n✓ Command completed successfully")

        except KeyboardInterrupt:
            print("\n❌ Execution interrupted")
        except Exception as e:
            print(f"\n❌ Execution error: {str(e)}")
    else:
        print("❌ Execution cancelled")


def main():
    """
    Main entry point for terminal command.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Natural language shell commands powered by CyberArk RAG + Ollama"
    )
    parser.add_argument(
        'query',
        nargs='+',
        help='Natural language command description'
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Auto-execute without confirmation'
    )
    parser.add_argument(
        '--show-context',
        action='store_true',
        help='Show CyberArk documentation context'
    )
    parser.add_argument(
        '--config',
        help='Path to config.yaml file'
    )

    args = parser.parse_args()

    # Load configuration
    config = Config(args.config) if args.config else Config()

    # Override config with CLI flags
    if args.show_context:
        config.config['execution']['show_context'] = True

    # Join query parts
    natural_language = ' '.join(args.query)

    # Execute the workflow
    execute_with_confirmation(
        natural_language=natural_language,
        config=config,
        auto_execute=args.auto
    )


if __name__ == "__main__":
    main()
