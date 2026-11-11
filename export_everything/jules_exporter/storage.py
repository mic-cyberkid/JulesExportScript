"""Storage and file serialization logic for Google Jules export.

Creates structured directories per session and activity, dumps raw JSON data,
extracts Git patches (.patch), Bash outputs (.log), Media files (decoded binary images/video),
and renders comprehensive Markdown summaries for easy human review.
"""

from __future__ import annotations
import base64
import json
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import Activity, Artifact, Session, Source

logger = logging.getLogger(__name__)


def sanitize_filename(name: str, max_length: int = 60) -> str:
    """Sanitizes strings to be safe directory and file names cross-platform."""
    if not name:
        return "unnamed"
    # Replace non-alphanumeric chars (excluding hyphens and underscores) with hyphens
    cleaned = re.sub(r"[^\w\s-]", "", name).strip()
    cleaned = re.sub(r"[-\s]+", "-", cleaned)
    if not cleaned:
        cleaned = "unnamed"
    return cleaned[:max_length].rstrip("-")


class ExportStorage:
    """Manages writing exported Jules sessions and activities to local disk."""

    def __init__(self, output_dir: str | Path, extract_artifacts: bool = True):
        self.output_dir = Path(output_dir).resolve()
        self.extract_artifacts = extract_artifacts
        self.sessions_dir = self.output_dir / "sessions"
        self.sources_dir = self.output_dir / "sources"

    def init_workspace(self) -> None:
        """Initializes output workspace directories."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)

    def get_session_dir(self, session: Session) -> Path:
        """Returns the specific directory path for a session."""
        slug = sanitize_filename(session.title or session.prompt or "session")
        dir_name = f"{session.id}_{slug}" if slug else session.id
        return self.sessions_dir / dir_name

    def write_json(self, file_path: Path, data: Any) -> None:
        """Atomically/safely writes JSON with pretty formatting."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_session_metadata(self, session: Session) -> Path:
        """Saves session.json and session_summary.md in the session folder."""
        session_folder = self.get_session_dir(session)
        session_folder.mkdir(parents=True, exist_ok=True)

        json_path = session_folder / "session.json"
        self.write_json(json_path, session.raw_data)

        md_path = session_folder / "README.md"
        summary_md = self._render_session_summary(session)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(summary_md)

        return session_folder

    def _render_session_summary(self, session: Session) -> str:
        """Generates Markdown overview of the session."""
        lines = [
            f"# Session: {session.title or session.id}",
            "",
            f"- **Session ID:** `{session.id}`",
            f"- **State:** `{session.state}`",
            f"- **Source:** `{session.source or 'None'}`",
            f"- **Starting Branch:** `{session.starting_branch or 'default'}`",
            f"- **Created At:** `{session.create_time}`",
            f"- **Updated At:** `{session.update_time}`",
            f"- **Jules Web URL:** {session.url if session.url else 'N/A'}",
            "",
            "## Initial Prompt",
            "",
            "```text",
            session.prompt,
            "```",
            "",
        ]

        if session.pull_requests:
            lines.append("## Pull Requests Generated")
            lines.append("")
            for pr in session.pull_requests:
                lines.append(f"### [{pr.title}]({pr.url})")
                if pr.description:
                    lines.append(pr.description)
                lines.append("")

        return "\n".join(lines)

    def save_activity(
        self,
        session_folder: Path,
        index: int,
        activity: Activity,
    ) -> Path:
        """Saves an individual activity JSON and any extracted artifacts."""
        activities_dir = session_folder / "activities"
        activities_dir.mkdir(parents=True, exist_ok=True)

        kind_slug = sanitize_filename(activity.activity_type)
        activity_dir_name = f"{index:04d}_{activity.id[:8]}_{kind_slug}"
        act_folder = activities_dir / activity_dir_name
        act_folder.mkdir(parents=True, exist_ok=True)

        # Write activity raw JSON
        self.write_json(act_folder / "activity.json", activity.raw_data)

        # Write activity human-readable markdown
        with open(act_folder / "activity.md", "w", encoding="utf-8") as f:
            f.write(self._render_activity_markdown(index, activity))

        # Extract artifacts if enabled
        if self.extract_artifacts and activity.artifacts:
            artifacts_folder = act_folder / "artifacts"
            artifacts_folder.mkdir(parents=True, exist_ok=True)
            self._extract_artifacts(artifacts_folder, activity)

        return act_folder

    def _render_activity_markdown(self, index: int, activity: Activity) -> str:
        lines = [
            f"# Activity {index}: {activity.activity_type}",
            "",
            f"- **Activity ID:** `{activity.id}`",
            f"- **Originator:** `{activity.originator}`",
            f"- **Created At:** `{activity.create_time}`",
        ]
        if activity.description:
            lines.append(f"- **Description:** {activity.description}")
        lines.append("")

        if activity.agent_message:
            lines.extend([
                "## Agent Message",
                "",
                activity.agent_message,
                "",
            ])
        elif activity.user_message:
            lines.extend([
                "## User Message",
                "",
                activity.user_message,
                "",
            ])
        elif activity.plan:
            lines.extend([
                "## Generated Plan",
                "",
                f"**Plan ID:** `{activity.plan.id}`",
                "",
                "### Steps:",
            ])
            for step in activity.plan.steps:
                lines.append(f"{step.index + 1}. **{step.title}**")
                if step.description:
                    lines.append(f"   {step.description}")
            lines.append("")
        elif activity.plan_id_approved:
            lines.extend([
                "## Plan Approved",
                "",
                f"Approved Plan ID: `{activity.plan_id_approved}`",
                "",
            ])
        elif activity.progress_title or activity.progress_description:
            lines.extend([
                f"## Progress: {activity.progress_title or ''}",
                "",
                activity.progress_description or "",
                "",
            ])
        elif activity.is_session_completed:
            lines.extend([
                "## Session Completed",
                "",
                "Session was marked as completed.",
                "",
            ])
        elif activity.session_failed_reason:
            lines.extend([
                "## Session Failed",
                "",
                f"**Reason:** {activity.session_failed_reason}",
                "",
            ])

        return "\n".join(lines)

    def _extract_artifacts(self, artifacts_dir: Path, activity: Activity) -> None:
        """Extracts patches, logs, and media files from artifacts."""
        for i, art in enumerate(activity.artifacts):
            prefix = f"{i:02d}"

            # Extract Git Patch
            if art.change_set and art.change_set.git_patch:
                gp = art.change_set.git_patch
                patch_file = artifacts_dir / f"{prefix}_changes.patch"
                with open(patch_file, "w", encoding="utf-8") as f:
                    f.write(gp.unidiff_patch)

                if gp.suggested_commit_message:
                    msg_file = artifacts_dir / f"{prefix}_commit_message.txt"
                    with open(msg_file, "w", encoding="utf-8") as f:
                        f.write(gp.suggested_commit_message)

            # Extract Bash Output
            if art.bash_output:
                bo = art.bash_output
                log_file = artifacts_dir / f"{prefix}_bash.log"
                with open(log_file, "w", encoding="utf-8") as f:
                    if bo.command:
                        f.write(f"$ {bo.command}\n\n")
                    f.write(bo.output or "")
                    if bo.exit_code is not None:
                        f.write(f"\n\n[Exit Code: {bo.exit_code}]\n")

            # Extract Media (Base64 decoded)
            if art.media and art.media.data:
                mime = art.media.mime_type or "application/octet-stream"
                ext = mimetypes.guess_extension(mime) or ".bin"
                media_file = artifacts_dir / f"{prefix}_media{ext}"
                try:
                    raw_bytes = base64.b64decode(art.media.data)
                    with open(media_file, "wb") as f:
                        f.write(raw_bytes)
                except Exception as e:
                    logger.warning("Failed decoding base64 media artifact %s: %s", media_file, e)

    def render_activities_timeline(
        self,
        session_folder: Path,
        session: Session,
        activities: List[Activity],
    ) -> Path:
        """Renders unified chronological activity_timeline.md for the entire session."""
        timeline_path = session_folder / "timeline.md"
        lines = [
            f"# Activity Timeline: {session.title or session.id}",
            "",
            f"Total Activities: {len(activities)}",
            "",
        ]

        for i, act in enumerate(activities):
            created = act.create_time
            orig = act.originator
            act_type = act.activity_type
            title = ""
            if act.progress_title:
                title = f": {act.progress_title}"
            elif act.agent_message:
                snippet = act.agent_message.split("\n")[0][:80]
                title = f": {snippet}"
            elif act.user_message:
                snippet = act.user_message.split("\n")[0][:80]
                title = f": {snippet}"

            lines.append(f"### #{i + 1} [{created}] [{orig.upper()}] `{act_type}`{title}")
            lines.append(f"- **ID:** `{act.id}`")

            if act.artifacts:
                art_types = [a.kind for a in act.artifacts]
                lines.append(f"- **Artifacts:** {', '.join(art_types)}")

            lines.append("")

        with open(timeline_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return timeline_path

    def save_sources(self, sources: List[Source]) -> Path:
        """Saves all connected sources metadata to sources/sources.json."""
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        sources_file = self.sources_dir / "sources.json"
        raw_list = [s.raw_data for s in sources]
        self.write_json(sources_file, raw_list)

        # Markdown index
        summary_md = self.sources_dir / "README.md"
        lines = ["# Connected Sources", "", f"Total Sources: {len(sources)}", ""]
        for s in sources:
            repo_info = ""
            if s.github_repo:
                repo_info = f" ({s.github_repo.owner}/{s.github_repo.repo})"
            lines.append(f"- **{s.id}**{repo_info}")
        with open(summary_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return sources_file
