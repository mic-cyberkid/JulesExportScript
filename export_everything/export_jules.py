#!/usr/bin/env python3
"""Google Jules Sessions and Activities Exporter.

Standalone and modular runner script to fetch and export all Jules sessions,
activities, git patches, bash outputs, and media artifacts locally with automatic
pagination handling.
"""

import sys
from jules_exporter.cli import main

if __name__ == "__main__":
    sys.exit(main())
