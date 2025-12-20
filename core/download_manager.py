"""
Download Manager

Single-threaded download queue with:
- priority scheduling
- dedupe (by URL)
- cancel token support (best-effort mid-download)
- throttled progress events
"""

from __future__ import annotations

import heapq
import itertools
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional

from yt_dlp.utils import DownloadCancelled

logger = logging.getLogger("DownloadManager")


def new_request_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class DownloadTask:
    url: str
    title: str = ""
    artist: str = ""
    playlist: str = ""
    request_id: str = ""
    priority: int = 100
    created_at: float = field(default_factory=time.time)


@dataclass
class RequestStats:
    request_id: str
    priority: int
    label: str = ""
    total: int = 0
    done: int = 0
    failed: int = 0
    canceled: int = 0


class DownloadManager:
    def __init__(
        self,
        downloader: Any,
        *,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        progress_throttle_sec: float = 0.25,
    ):
        self._downloader = downloader
        self._event_cb = event_callback or (lambda e: None)
        self._progress_throttle_sec = max(0.05, float(progress_throttle_sec))

        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._seq = itertools.count()
        self._queue: list[tuple[int, int, DownloadTask]] = []
        self._queued_urls: set[str] = set()
        self._current_task: Optional[DownloadTask] = None
        self._current_cancel = threading.Event()

        self._requests: Dict[str, RequestStats] = {}

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self, *, cancel_in_progress: bool = True) -> None:
        with self._lock:
            self._stop.set()
            if cancel_in_progress:
                self._current_cancel.set()
            self._cv.notify_all()

        t = self._thread
        if t:
            t.join(timeout=2.0)

    def enqueue(
        self,
        tracks: Iterable[Dict[str, Any]],
        *,
        request_id: str,
        priority: int,
        default_playlist: str = "",
        replace: bool = False,
        cancel_in_progress: bool = False,
        label: str = "",
    ) -> int:
        """
        Enqueue track dicts. Returns number of newly queued tasks.

        Track dict keys used: url, title, artist, _playlist
        """
        prepared: list[DownloadTask] = []
        for t in tracks:
            url = (t or {}).get("url")
            if not url:
                continue
            title = (t or {}).get("title") or ""
            artist = (t or {}).get("artist") or ""
            playlist = (t or {}).get("_playlist") or default_playlist or ""
            prepared.append(
                DownloadTask(
                    url=url,
                    title=title,
                    artist=artist,
                    playlist=playlist,
                    request_id=request_id,
                    priority=int(priority),
                )
            )

        if not prepared:
            return 0

        with self._cv:
            if replace:
                # Mark cleared queued tasks as canceled for stats
                for _, _, existing in self._queue:
                    st = self._requests.get(existing.request_id)
                    if st:
                        st.canceled += 1
                self._queue.clear()
                self._queued_urls.clear()
                if cancel_in_progress:
                    self._current_cancel.set()

            stats = self._requests.get(request_id)
            if not stats:
                stats = RequestStats(
                    request_id=request_id,
                    priority=int(priority),
                    label=label,
                    total=0,
                )
                self._requests[request_id] = stats

            added = 0
            for task in prepared:
                if task.url in self._queued_urls:
                    continue
                if self._current_task and self._current_task.url == task.url:
                    continue
                if self._downloader.is_cached(
                    task.url, title=task.title or None, artist=task.artist or None
                ):
                    continue

                heapq.heappush(self._queue, (task.priority, next(self._seq), task))
                self._queued_urls.add(task.url)
                added += 1

            if added:
                stats.total += added
                self._emit(
                    {
                        "type": "queue",
                        "request_id": request_id,
                        "added": added,
                        "queue_size": len(self._queue),
                    }
                )
                self._cv.notify_all()

            return added

    def cancel_all(self, *, cancel_in_progress: bool = True) -> None:
        with self._cv:
            for _, _, existing in self._queue:
                st = self._requests.get(existing.request_id)
                if st:
                    st.canceled += 1
            self._queue.clear()
            self._queued_urls.clear()
            if cancel_in_progress:
                self._current_cancel.set()
            self._emit({"type": "cancel_all"})
            self._cv.notify_all()

    def cancel_request(
        self, request_id: str, *, cancel_in_progress: bool = True
    ) -> int:
        with self._cv:
            kept: list[tuple[int, int, DownloadTask]] = []
            removed = 0
            for item in self._queue:
                task = item[2]
                if task.request_id == request_id:
                    removed += 1
                    self._queued_urls.discard(task.url)
                else:
                    kept.append(item)
            self._queue = kept
            heapq.heapify(self._queue)

            if (
                cancel_in_progress
                and self._current_task
                and self._current_task.request_id == request_id
            ):
                self._current_cancel.set()

            stats = self._requests.get(request_id)
            if stats and removed:
                stats.canceled += removed

            self._emit(
                {"type": "cancel_request", "request_id": request_id, "removed": removed}
            )
            self._cv.notify_all()
            return removed

    def cancel_playlist(self, playlist: str, *, cancel_in_progress: bool = True) -> int:
        """Remove queued tasks for a given playlist name."""
        if not playlist:
            return 0
        with self._cv:
            kept: list[tuple[int, int, DownloadTask]] = []
            removed = 0
            for item in self._queue:
                task = item[2]
                if task.playlist == playlist:
                    removed += 1
                    self._queued_urls.discard(task.url)
                    st = self._requests.get(task.request_id)
                    if st:
                        st.canceled += 1
                else:
                    kept.append(item)
            self._queue = kept
            heapq.heapify(self._queue)

            if (
                cancel_in_progress
                and self._current_task
                and self._current_task.playlist == playlist
            ):
                self._current_cancel.set()

            self._emit(
                {"type": "cancel_playlist", "playlist": playlist, "removed": removed}
            )
            self._cv.notify_all()
            return removed

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            current = self._current_task
            return {
                "running": bool(self._thread and self._thread.is_alive()),
                "queue_size": len(self._queue),
                "current": current,
            }

    def is_downloading(self, url: str) -> bool:
        """Check if a URL is currently in queue or downloading."""
        if not url:
            return False
        with self._lock:
            if self._current_task and self._current_task.url == url:
                return True
            return url in self._queued_urls

    # ---- internals ----
    def _emit(self, event: Dict[str, Any]) -> None:
        try:
            self._event_cb(event)
        except Exception:
            logger.exception("event_callback failed")

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._cv:
                while not self._queue and not self._stop.is_set():
                    self._cv.wait(timeout=0.5)
                if self._stop.is_set():
                    return

                _, _, task = heapq.heappop(self._queue)
                self._queued_urls.discard(task.url)
                self._current_task = task
                self._current_cancel = threading.Event()

            stats = self._requests.get(task.request_id)
            position = 1
            total = 0
            if stats:
                # Current is counted as next item to process
                position = stats.done + stats.failed + stats.canceled + 1
                total = stats.total

            self._emit(
                {
                    "type": "start",
                    "task": task,
                    "request_id": task.request_id,
                    "position": position,
                    "total": total,
                    "queue_size": self._queue_size_safe(),
                    "label": (stats.label if stats else ""),
                }
            )

            last_emit = 0.0

            def progress_cb(percent: float, downloaded: int, total_bytes: int):
                nonlocal last_emit
                if self._stop.is_set() or self._current_cancel.is_set():
                    raise DownloadCancelled()

                now = time.monotonic()
                if percent >= 100 or (now - last_emit) >= self._progress_throttle_sec:
                    last_emit = now
                    self._emit(
                        {
                            "type": "progress",
                            "task": task,
                            "request_id": task.request_id,
                            "percent": float(percent),
                            "downloaded": int(downloaded),
                            "total_bytes": int(total_bytes),
                            "position": position,
                            "total": total,
                            "queue_size": self._queue_size_safe(),
                        }
                    )

            try:
                self._downloader.download(
                    task.url,
                    progress_callback=progress_cb,
                    title=task.title or None,
                    artist=task.artist or None,
                )
                if stats:
                    stats.done += 1
                self._emit(
                    {
                        "type": "complete",
                        "task": task,
                        "request_id": task.request_id,
                        "position": position,
                        "total": total,
                        "queue_size": self._queue_size_safe(),
                    }
                )
            except DownloadCancelled:
                if stats:
                    stats.canceled += 1
                self._emit(
                    {
                        "type": "canceled",
                        "task": task,
                        "request_id": task.request_id,
                        "position": position,
                        "total": total,
                        "queue_size": self._queue_size_safe(),
                    }
                )
            except Exception as e:
                if stats:
                    stats.failed += 1
                self._emit(
                    {
                        "type": "error",
                        "task": task,
                        "request_id": task.request_id,
                        "error": str(e),
                        "position": position,
                        "total": total,
                        "queue_size": self._queue_size_safe(),
                    }
                )
            finally:
                with self._lock:
                    self._current_task = None

            # If queue is empty, emit idle signal (useful for UI)
            if self._queue_size_safe() == 0:
                self._emit({"type": "idle"})

    def _queue_size_safe(self) -> int:
        with self._lock:
            return len(self._queue)
