"""Daemon lifecycle management."""

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from .classifier import FileClassifier
from .config import load_config
from .hierarchy import create_hierarchy
from .logger import setup_logging
from .mover import FileMover
from .watcher import FileWatcher

logger = logging.getLogger("file_manager")

PID_FILE = Path.home() / ".file-manager" / "file_manager.pid"


class FileManagerDaemon:
    """Manages the file manager daemon lifecycle."""

    def __init__(self, config_path: str | Path | None = None):
        self.config_path = config_path
        self.config: dict[str, Any] = {}
        self.watcher: FileWatcher | None = None
        self.running = False

    def start(self, foreground: bool = False) -> None:
        """Start the file manager daemon."""
        self.config = load_config(self.config_path)
        setup_logging(self.config, foreground=foreground)

        # Preflight checks
        self._check_openrouter()
        self._check_pid_file()

        # Create folder hierarchy
        create_hierarchy(self.config["drop_zone"], self.config)
        logger.info("Folder hierarchy ready at: %s", self.config["drop_zone"])

        if not foreground:
            self._daemonize()

        self._write_pid_file()
        self._register_signals()

        # Initialize components
        classifier = FileClassifier(self.config)
        mover = FileMover(self.config)
        self.watcher = FileWatcher(self.config, classifier, mover)

        self.running = True
        self.watcher.start()

        if foreground:
            print(f"File Manager running (PID {os.getpid()}). Press Ctrl+C to stop.")

        logger.info("File Manager daemon started (PID %d)", os.getpid())

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def stop(self) -> None:
        """Stop a running daemon by sending SIGTERM to its PID."""
        pid = self._read_pid_file()
        if pid is None:
            print("No running daemon found.")
            return

        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent stop signal to daemon (PID {pid}).")
        except ProcessLookupError:
            print(f"Daemon (PID {pid}) is not running. Cleaning up PID file.")
            self._remove_pid_file()
        except PermissionError:
            print(f"Permission denied to stop daemon (PID {pid}).")

    def status(self) -> None:
        """Check if the daemon is running."""
        pid = self._read_pid_file()
        if pid is None:
            print("File Manager is not running.")
            return

        try:
            os.kill(pid, 0)  # Signal 0: check if process exists
            print(f"File Manager is running (PID {pid}).")
        except ProcessLookupError:
            print(f"File Manager is not running (stale PID file for {pid}).")
            self._remove_pid_file()
        except PermissionError:
            print(f"File Manager appears to be running (PID {pid}), but cannot verify.")

    def organize_existing(self) -> None:
        """One-time scan and organize existing files in the drop zone."""
        self.config = load_config(self.config_path)
        setup_logging(self.config, foreground=True)

        create_hierarchy(self.config["drop_zone"], self.config)

        classifier = FileClassifier(self.config)
        mover = FileMover(self.config)
        watcher = FileWatcher(self.config, classifier, mover)

        print(f"Scanning: {self.config['drop_zone']}")
        watcher.organize_existing()

        # Wait for queue to drain
        watcher.handler._queue.join()
        print("Done organizing existing files.")

    def _check_openrouter(self) -> None:
        """Verify OpenRouter API key is configured and reachable."""
        ai_config = self.config["openrouter"]
        api_key = ai_config.get("api_key", "")
        if not api_key:
            print("Error: OpenRouter API key not configured.")
            print("Set it in config.yaml under openrouter.api_key")
            sys.exit(1)

        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            # Quick validation: list models to confirm the key works
            client.models.list()
            logger.info("OpenRouter OK, using model '%s'.", ai_config["model"])
        except Exception as e:
            print(f"Error: Cannot connect to OpenRouter.")
            print(f"Details: {e}")
            print("Check your API key in config.yaml")
            sys.exit(1)

    def _check_pid_file(self) -> None:
        """Ensure no other daemon instance is running."""
        pid = self._read_pid_file()
        if pid is not None:
            try:
                os.kill(pid, 0)
                print(f"File Manager is already running (PID {pid}).")
                sys.exit(1)
            except ProcessLookupError:
                self._remove_pid_file()

    def _daemonize(self) -> None:
        """Double-fork to daemonize the process (Unix only)."""
        # First fork
        pid = os.fork()
        if pid > 0:
            sys.exit(0)

        os.setsid()

        # Second fork
        pid = os.fork()
        if pid > 0:
            sys.exit(0)

        # Redirect standard file descriptors to /dev/null
        sys.stdout.flush()
        sys.stderr.flush()
        devnull = open(os.devnull, "r+b")
        os.dup2(devnull.fileno(), sys.stdin.fileno())
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())

    def _register_signals(self) -> None:
        """Register signal handlers."""
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGHUP, self._handle_sighup)

    def _handle_sigterm(self, signum, frame) -> None:
        """Handle SIGTERM: graceful shutdown."""
        logger.info("Received SIGTERM, shutting down...")
        self.running = False

    def _handle_sighup(self, signum, frame) -> None:
        """Handle SIGHUP: reload configuration."""
        logger.info("Received SIGHUP, reloading config...")
        try:
            self.config = load_config(self.config_path)
            if self.watcher:
                self.watcher.handler.classifier = FileClassifier(self.config)
                self.watcher.handler.mover = FileMover(self.config)
            logger.info("Config reloaded successfully.")
        except Exception as e:
            logger.error("Failed to reload config: %s", e)

    def _shutdown(self) -> None:
        """Clean shutdown: stop watcher, remove PID file."""
        if self.watcher:
            self.watcher.stop()
        self._remove_pid_file()
        logger.info("File Manager daemon stopped.")

    def _write_pid_file(self) -> None:
        """Write current PID to file."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

    def _read_pid_file(self) -> int | None:
        """Read PID from file, return None if not found."""
        if not PID_FILE.exists():
            return None
        try:
            return int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            return None

    def _remove_pid_file(self) -> None:
        """Remove the PID file."""
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
