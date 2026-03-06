"""Filesystem monitoring with watchdog."""

import logging
import queue
import threading
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .classifier import FileClassifier
from .hierarchy import get_managed_dirs
from .mover import FileMover
from .utils import is_file_stable

logger = logging.getLogger("file_manager")


class DropZoneHandler(FileSystemEventHandler):
    """Handles file creation events in the drop zone root."""

    def __init__(self, config: dict[str, Any], classifier: FileClassifier, mover: FileMover):
        super().__init__()
        self.config = config
        self.classifier = classifier
        self.mover = mover
        self.drop_zone = Path(config["drop_zone"])
        self.managed_dirs = get_managed_dirs(self.drop_zone, config)
        self.stabilization_delay = config.get("stabilization_delay", 2.0)
        self._pending_timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

        # Processing queue with single worker thread
        self._queue: queue.Queue[Path] = queue.Queue()
        self._worker = threading.Thread(target=self._process_queue, daemon=True)
        self._worker.start()

    def on_created(self, event):
        """Called when a file is created in the drop zone."""
        if event.is_directory:
            return

        filepath = Path(event.src_path)

        # Ignore files inside managed subdirectories
        if self._is_in_managed_dir(filepath):
            return

        # Ignore hidden files
        if filepath.name.startswith("."):
            return

        # Schedule processing after stabilization delay
        self._schedule_processing(filepath)

    def on_moved(self, event):
        """Called when a file is moved into the drop zone."""
        if event.is_directory:
            return

        filepath = Path(event.dest_path)

        if self._is_in_managed_dir(filepath):
            return

        if filepath.name.startswith("."):
            return

        self._schedule_processing(filepath)

    def _is_in_managed_dir(self, filepath: Path) -> bool:
        """Check if a file is inside one of the managed subdirectories."""
        for managed in self.managed_dirs:
            try:
                filepath.relative_to(managed)
                return True
            except ValueError:
                continue
        return False

    def _schedule_processing(self, filepath: Path) -> None:
        """Schedule file processing after a stabilization delay."""
        key = str(filepath)

        with self._lock:
            # Cancel any existing timer for this file
            if key in self._pending_timers:
                self._pending_timers[key].cancel()

            timer = threading.Timer(
                self.stabilization_delay,
                self._enqueue_file,
                args=(filepath,),
            )
            self._pending_timers[key] = timer
            timer.start()

    def _enqueue_file(self, filepath: Path) -> None:
        """Add a file to the processing queue after stabilization."""
        with self._lock:
            self._pending_timers.pop(str(filepath), None)

        if filepath.exists():
            self._queue.put(filepath)

    def _process_queue(self) -> None:
        """Worker thread: process files sequentially from the queue."""
        while True:
            filepath = self._queue.get()
            try:
                self._process_file(filepath)
            except Exception as e:
                logger.error("Error processing %s: %s", filepath, e)
            finally:
                self._queue.task_done()

    def _process_file(self, filepath: Path) -> None:
        """Classify and move a single file."""
        if not filepath.exists():
            logger.debug("File vanished before processing: %s", filepath)
            return

        # Verify file is stable (not still being copied)
        if not is_file_stable(filepath, delay=0.5):
            logger.warning("File not stable, re-queuing: %s", filepath)
            self._queue.put(filepath)
            return

        logger.info("Processing: %s", filepath.name)

        classification = self.classifier.classify(filepath)
        self.mover.move_file(filepath, classification)


class FileWatcher:
    """Manages the watchdog Observer for the drop zone."""

    def __init__(self, config: dict[str, Any], classifier: FileClassifier, mover: FileMover):
        self.config = config
        self.drop_zone = Path(config["drop_zone"])
        self.handler = DropZoneHandler(config, classifier, mover)
        self.observer = Observer()

    def start(self) -> None:
        """Start watching the drop zone."""
        self.observer.schedule(self.handler, str(self.drop_zone), recursive=False)
        self.observer.start()
        logger.info("Watching: %s", self.drop_zone)

    def stop(self) -> None:
        """Stop watching."""
        self.observer.stop()
        self.observer.join(timeout=5)
        logger.info("Watcher stopped.")

    def organize_existing(self) -> None:
        """One-time scan of existing files in the drop zone root."""
        managed = get_managed_dirs(self.drop_zone, self.config)
        for item in self.drop_zone.iterdir():
            if item.is_file() and not item.name.startswith("."):
                # Skip files inside managed dirs (shouldn't happen at root, but be safe)
                in_managed = False
                for m in managed:
                    try:
                        item.relative_to(m)
                        in_managed = True
                        break
                    except ValueError:
                        continue
                if not in_managed:
                    self.handler._queue.put(item)
