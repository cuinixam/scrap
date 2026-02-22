"""Download and extraction progress reporting for Poks."""

import threading
from collections.abc import Callable

from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

ProgressCallback = Callable[[str, int, int | None], None]
# Signature: (app_name, current, total_or_none)


class RichProgressHandler:
    """Rich-based progress display with separate download and extraction bars."""

    def __init__(self) -> None:
        self._download_progress: Progress | None = None
        self._extract_progress: Progress | None = None
        self._download_tasks: dict[str, TaskID] = {}
        self._extract_tasks: dict[str, TaskID] = {}
        self._lock = threading.Lock()

    def _ensure_download_progress(self) -> Progress:
        if self._download_progress is None:
            self._download_progress = Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            )
            self._download_progress.start()
        return self._download_progress

    def _ensure_extract_progress(self) -> Progress:
        if self._extract_progress is None:
            self._extract_progress = Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
            )
            self._extract_progress.start()
        return self._extract_progress

    def _update_task(
        self,
        progress: Progress,
        tasks: dict[str, TaskID],
        app_name: str,
        current: int,
        total: int | None,
    ) -> None:
        with self._lock:
            if app_name not in tasks:
                tasks[app_name] = progress.add_task(app_name, total=total or 0)
            task_id = tasks[app_name]
        if total and progress.tasks[task_id].total != total:
            progress.update(task_id, total=total)
        progress.update(task_id, completed=current)

    def _finish_task(self, progress: Progress | None, tasks: dict[str, TaskID], app_name: str) -> None:
        with self._lock:
            tasks.pop(app_name, None)
            if not tasks and progress is not None:
                progress.stop()

    def on_download(self, app_name: str, downloaded: int, total: int | None) -> None:
        """Report download progress for an app."""
        with self._lock:
            progress = self._ensure_download_progress()
        self._update_task(progress, self._download_tasks, app_name, downloaded, total)
        if total and downloaded >= total:
            self._finish_task(self._download_progress, self._download_tasks, app_name)
            with self._lock:
                if not self._download_tasks:
                    self._download_progress = None

    def on_extract(self, app_name: str, extracted: int, total: int | None) -> None:
        """Report extraction progress for an app."""
        with self._lock:
            progress = self._ensure_extract_progress()
        self._update_task(progress, self._extract_tasks, app_name, extracted, total)
        if total and extracted >= total:
            self._finish_task(self._extract_progress, self._extract_tasks, app_name)
            with self._lock:
                if not self._extract_tasks:
                    self._extract_progress = None


default_progress = RichProgressHandler()
