# Google Jules API Sessions & Activities Exporter

Author: **Jules** (Autonomous Software Engineering Agent)
Collaborator: **mickey_cyberkid**

A modular, production-grade Python tool for deeply exporting, inspecting, and archiving sessions and activities from the [Google Jules REST API](https://developers.google.com/jules/api).

---

## Features

- **Automatic Pagination Traversal**: Fully walks through paginated endpoints (`v1alpha/sessions`, `v1alpha/sessions/{id}/activities`, `v1alpha/sources`) following `nextPageToken` until everything is fetched.
- **Artifact Extraction**:
  - Extracts Git diffs into `.patch` files and suggested commit messages into `.txt`.
  - Extracts Bash command logs (`.log`) containing commands, outputs, and exit codes.
  - Decodes binary media artifacts (PNG, JPEG, WebM) from Base64 into binary files.
- **Human-Readable Summaries**:
  - Generates `README.md` session overviews.
  - Generates `timeline.md` chronological activity event logs.
  - Generates individual `activity.md` for each activity (messages, plans, progress updates).
- **Resilience & Rate Limiting**:
  - Exponential backoff with jitter on HTTP 429 (rate limits) and 5xx errors.
  - Respects `Retry-After` headers.
  - Configurable rate-limit delays and request timeouts.
- **Concurrent & Incremental Export**:
  - Multithreaded session downloading with customizable concurrency.
  - Resumption support: skips already-completed and fully exported sessions unless `--overwrite` is specified.

---

## Installation & Requirements

Python 3.8+ (Zero external dependencies — uses Python standard library `urllib`, `json`, `dataclasses`, `concurrent.futures`, `argparse`).

```bash
git clone https://github.com/mic-cyberkid/JulesExportScript.git
cd JulesExportScript
```

---

## Usage

### 1. Command Line Interface

```bash
# Export everything with API key provided via argument
python3 export_jules.py --api-key "YOUR_JULES_API_KEY" --output-dir ./jules_export

# Or set environment variable
export JULES_API_KEY="YOUR_JULES_API_KEY"
python3 export_jules.py --output-dir ./jules_export

# Export a single specific session
python3 export_jules.py --session-id "9207611789457307748"

# Test run: export the latest 5 sessions with 3 concurrent workers
python3 export_jules.py --limit 5 --concurrency 3
```

### CLI Options

| Flag | Description | Default |
|---|---|---|
| `-k`, `--api-key` | Google Jules API key (or `JULES_API_KEY` env var) | `None` |
| `-o`, `--output-dir` | Local directory to store exports | `./jules_export` |
| `-s`, `--session-id` | Export only a specific session ID | `None` (all) |
| `-l`, `--limit` | Limit number of sessions to export | `None` (all) |
| `-c`, `--concurrency` | Number of concurrent worker threads | `3` |
| `--no-sources` | Skip exporting connected repository sources | `False` |
| `--no-extract-artifacts` | Skip extracting `.patch`, `.log`, media files | `False` |
| `--overwrite` | Overwrite completed sessions on re-run | `False` |
| `-v`, `--verbose` | Enable debug logging | `False` |

---

### 2. Python Modular Library

You can integrate `jules_exporter` directly into your own automation pipelines:

```python
from jules_exporter import JulesClient, ExportStorage, JulesExporter

client = JulesClient(api_key="YOUR_API_KEY")
storage = ExportStorage(output_dir="./custom_export")
exporter = JulesExporter(client=client, storage=storage, concurrency=4)

# Export all sessions and activities
summary = exporter.export_all()
print(f"Exported {summary['sessions_count']} sessions with {summary['activities_count']} activities.")
```

---

## Export Directory Structure

```text
jules_export/
├── sources/
│   ├── README.md
│   └── sources.json
└── sessions/
    └── 9207611789457307748_Branch_name/
        ├── session.json
        ├── README.md
        ├── timeline.md
        └── activities/
            ├── 0001_a49ac5bb_progressUpdated/
            │   ├── activity.json
            │   └── activity.md
            ├── 0005_b913f76f_planGenerated/
            │   ├── activity.json
            │   └── activity.md
            └── 0012_022837db_sessionCompleted/
                ├── activity.json
                ├── activity.md
                └── artifacts/
                    ├── 00_changes.patch
                    └── 00_commit_message.txt
```
