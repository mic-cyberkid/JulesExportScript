"""Exporter orchestrator for Google Jules API.

Coordinates fetching sessions, automatic pagination of activities, rate-limit
handling, concurrent downloads, resume capabilities, and status reporting.
"""

from __future__ import annotations
import concurrent.futures
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .client import JulesClient
from .models import Activity, Session, Source
from .storage import ExportStorage

logger = logging.getLogger(__name__)


class JulesExporter:
    """Orchestrates exporting all sessions, activities, and sources from Jules."""

    def __init__(
        self,
        client: JulesClient,
        storage: ExportStorage,
        concurrency: int = 4,
        overwrite: bool = False,
    ):
        self.client = client
        self.storage = storage
        self.concurrency = max(1, concurrency)
        self.overwrite = overwrite

    def export_session(
        self,
        session: Session,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Path, int]:
        """Exports a single session and all its activities with automatic pagination."""
        def log(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)
            else:
                logger.info(msg)

        session_folder = self.storage.get_session_dir(session)
        is_completed = session.state == "COMPLETED"

        # Check if already exported (session.json + timeline.md exist) and skip if completed and not overwrite
        if (
            not self.overwrite
            and is_completed
            and (session_folder / "session.json").exists()
            and (session_folder / "timeline.md").exists()
        ):
            log(f"[SKIP] Session {session.id} ({session.title[:30] if session.title else ''}) already fully exported.")
            # Count activities already exported
            act_dir = session_folder / "activities"
            count = len(list(act_dir.glob("*"))) if act_dir.exists() else 0
            return session_folder, count

        log(f"[START] Exporting Session {session.id}: '{session.title or session.prompt[:40]}'")
        session_folder = self.storage.save_session_metadata(session)

        activities: List[Activity] = []
        for index, activity in enumerate(self.client.list_activities(session.id)):
            activities.append(activity)
            self.storage.save_activity(session_folder, index + 1, activity)

        self.storage.render_activities_timeline(session_folder, session, activities)
        log(f"[DONE] Session {session.id}: exported {len(activities)} activities to {session_folder.name}")
        return session_folder, len(activities)

    def export_sources(self) -> List[Source]:
        """Fetches and saves all connected sources."""
        sources = list(self.client.list_sources())
        self.storage.save_sources(sources)
        return sources

    def export_all(
        self,
        limit: Optional[int] = None,
        include_sources: bool = True,
        target_session_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Exports all sessions (or targeted session) with automatic pagination and multiprocessing."""
        self.storage.init_workspace()

        def log(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)
            else:
                logger.info(msg)

        start_time = time.time()
        exported_sources_count = 0
        if include_sources:
            log("Fetching and exporting connected sources...")
            try:
                sources = self.export_sources()
                exported_sources_count = len(sources)
                log(f"Exported {exported_sources_count} sources to {self.storage.sources_dir}")
            except Exception as e:
                logger.warning("Failed exporting sources: %s", e)

        # If a single session target was provided
        if target_session_id:
            log(f"Fetching targeted session {target_session_id}...")
            session = self.client.get_session(target_session_id)
            folder, act_count = self.export_session(session, progress_callback=log)
            elapsed = time.time() - start_time
            return {
                "sessions_count": 1,
                "activities_count": act_count,
                "sources_count": exported_sources_count,
                "elapsed_seconds": round(elapsed, 2),
            }

        # Otherwise list all sessions with pagination
        log("Discovering sessions via automatic pagination...")
        sessions_to_export: List[Session] = []
        for session in self.client.list_sessions():
            sessions_to_export.append(session)
            if limit and len(sessions_to_export) >= limit:
                break

        total_sessions = len(sessions_to_export)
        log(f"Found {total_sessions} session(s) to export.")

        total_activities = 0
        success_sessions = 0
        failed_sessions = 0

        if self.concurrency > 1 and total_sessions > 1:
            log(f"Starting concurrent export with {self.concurrency} workers...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                future_to_session = {
                    executor.submit(self.export_session, s, log): s
                    for s in sessions_to_export
                }
                for future in concurrent.futures.as_completed(future_to_session):
                    s = future_to_session[future]
                    try:
                        folder, acts = future.result()
                        total_activities += acts
                        success_sessions += 1
                    except Exception as exc:
                        failed_sessions += 1
                        logger.error("Error exporting session %s: %s", s.id, exc, exc_info=True)
        else:
            for s in sessions_to_export:
                try:
                    folder, acts = self.export_session(s, progress_callback=log)
                    total_activities += acts
                    success_sessions += 1
                except Exception as exc:
                    failed_sessions += 1
                    logger.error("Error exporting session %s: %s", s.id, exc, exc_info=True)

        elapsed = time.time() - start_time
        summary = {
            "sessions_count": success_sessions,
            "failed_sessions": failed_sessions,
            "activities_count": total_activities,
            "sources_count": exported_sources_count,
            "elapsed_seconds": round(elapsed, 2),
            "output_directory": str(self.storage.output_dir),
        }
        log(
            f"Finished export in {summary['elapsed_seconds']}s: "
            f"{success_sessions} sessions, {total_activities} activities."
        )
        return summary
