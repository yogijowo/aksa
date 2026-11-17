"""Real-Time Workspace Folder Watcher Service powered by watchdog."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.rag.ingest import SUPPORTED_RAG_EXTENSIONS
from app.rag.store import HybridRAGStore, rag_store


class _AksaFolderEventHandler(FileSystemEventHandler):
    """Watchdog event handler triggering incremental SHA-256 RAG indexing on file changes."""

    def __init__(
        self,
        workspace_id: str,
        store: HybridRAGStore,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        super().__init__()
        self.workspace_id = workspace_id
        self.store = store
        self.loop = loop

    def _schedule_index(self, src_path: str) -> None:
        path = Path(src_path)
        if any(part.startswith(".") for part in path.parts):
            return
        if path.suffix.lower() not in SUPPORTED_RAG_EXTENSIONS:
            return
        if path.exists() and path.is_file():
            asyncio.run_coroutine_threadsafe(
                self.store.index_file(self.workspace_id, path),
                self.loop,
            )

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule_index(str(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule_index(str(event.src_path))


class WorkspaceRAGWatcher:
    """Manages real-time watchdog observers across authorized workspace folders."""

    def __init__(self, store: HybridRAGStore = rag_store) -> None:
        self.store = store
        self._observer: Any = None
        self._watched_folders: dict[str, str] = {}

    def start_watching(self, workspace_id: str, folder_path: str | Path) -> bool:
        """Start monitoring a workspace folder for real-time incremental RAG indexing."""
        resolved = Path(folder_path).expanduser().resolve()
        if not resolved.exists() or not resolved.is_dir():
            return False

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False

        if self._observer is None:
            self._observer = Observer()
            self._observer.daemon = True
            self._observer.start()

        if str(resolved) not in self._watched_folders:
            handler = _AksaFolderEventHandler(workspace_id, self.store, loop)
            self._observer.schedule(handler, str(resolved), recursive=True)
            self._watched_folders[str(resolved)] = workspace_id
        return True

    def stop_all(self) -> None:
        """Stop all active watchdog observers cleanly."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None
        self._watched_folders.clear()

    def list_watched(self) -> dict[str, str]:
        return dict(self._watched_folders)


rag_watcher = WorkspaceRAGWatcher()

