"""Command-line interface for Google Jules sessions and activities export."""

from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from .client import JulesClient
from .exporter import JulesExporter
from .storage import ExportStorage


def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="export_jules",
        description="High-quality Google Jules API Sessions & Activities Export Tool.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--api-key",
        "-k",
        type=str,
        default=os.environ.get("JULES_API_KEY", ""),
        help="Google Jules API key (or set via JULES_API_KEY env var).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="./jules_export",
        help="Destination directory to save exported sessions and activities.",
    )
    parser.add_argument(
        "--session-id",
        "-s",
        type=str,
        default=None,
        help="Specific session ID to export (if omitted, all sessions will be exported).",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Maximum number of sessions to export (useful for testing or partial runs).",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=3,
        help="Number of concurrent worker threads for fetching sessions.",
    )
    parser.add_argument(
        "--no-sources",
        action="store_true",
        help="Skip exporting connected source repository metadata.",
    )
    parser.add_argument(
        "--no-extract-artifacts",
        action="store_true",
        help="Skip extracting Git patches, bash logs, and media files to separate files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite previously exported completed sessions instead of skipping.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose / debug logging.",
    )
    return parser.parse_args(args)


def main(args: Optional[Sequence[str]] = None) -> int:
    parsed = parse_args(args)

    api_key = parsed.api_key.strip()
    if not api_key:
        sys.stderr.write(
            "Error: No API key provided! Please supply --api-key or set the JULES_API_KEY environment variable.\n"
        )
        return 1

    import logging
    log_level = logging.DEBUG if parsed.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    client = JulesClient(api_key=api_key)
    storage = ExportStorage(
        output_dir=parsed.output_dir,
        extract_artifacts=not parsed.no_extract_artifacts,
    )
    exporter = JulesExporter(
        client=client,
        storage=storage,
        concurrency=parsed.concurrency,
        overwrite=parsed.overwrite,
    )

    print("=" * 60)
    print("Google Jules Sessions & Activities Exporter")
    print(f"Destination: {storage.output_dir}")
    print("=" * 60)

    try:
        summary = exporter.export_all(
            limit=parsed.limit,
            include_sources=not parsed.no_sources,
            target_session_id=parsed.session_id,
            progress_callback=print,
        )
        print("\n" + "=" * 60)
        print("Export Completed Successfully!")
        print(f"Total Sessions Exported:   {summary['sessions_count']}")
        if summary.get("failed_sessions"):
            print(f"Failed Sessions:           {summary['failed_sessions']}")
        print(f"Total Activities Exported: {summary['activities_count']}")
        print(f"Sources Exported:          {summary['sources_count']}")
        print(f"Elapsed Time:              {summary['elapsed_seconds']}s")
        print(f"Files saved to:            {summary.get('output_directory', parsed.output_dir)}")
        print("=" * 60)
        return 0
    except KeyboardInterrupt:
        print("\nExport cancelled by user.")
        return 130
    except Exception as e:
        sys.stderr.write(f"\nExport failed: {e}\n")
        if parsed.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
