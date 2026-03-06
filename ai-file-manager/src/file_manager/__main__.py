"""CLI entry point for the AI File Manager."""

import argparse
import sys
from pathlib import Path

from .daemon import FileManagerDaemon


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="file-manager",
        description="AI-powered file organizer using Ollama",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.yaml (default: built-in defaults)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # start
    start_parser = subparsers.add_parser("start", help="Start the file manager daemon")
    start_parser.add_argument(
        "--foreground", "-f",
        action="store_true",
        help="Run in foreground (don't daemonize)",
    )

    # stop
    subparsers.add_parser("stop", help="Stop the running daemon")

    # status
    subparsers.add_parser("status", help="Check if the daemon is running")

    # organize-existing
    subparsers.add_parser(
        "organize-existing",
        help="One-time scan and organize files already in the drop zone",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Resolve config path
    config_path = args.config
    if config_path is None:
        # Look for config.yaml in the package directory
        pkg_config = Path(__file__).parent.parent.parent / "config.yaml"
        if pkg_config.exists():
            config_path = str(pkg_config)

    daemon = FileManagerDaemon(config_path=config_path)

    if args.command == "start":
        daemon.start(foreground=args.foreground)
    elif args.command == "stop":
        daemon.stop()
    elif args.command == "status":
        daemon.status()
    elif args.command == "organize-existing":
        daemon.organize_existing()


if __name__ == "__main__":
    main()
