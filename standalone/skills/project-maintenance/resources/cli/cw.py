#!/usr/bin/env python3
"""Executable wrapper for the canonical story-project CLI."""

import sys

from cwcli import app


if __name__ == "__main__":
    sys.exit(app.main())
