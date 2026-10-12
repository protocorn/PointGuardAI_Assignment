"""Flush progress lines so a long run is visible while models are thinking."""

from __future__ import annotations

import sys
from datetime import datetime


def progress(text: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{stamp}] {text}\n"
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    sys.stdout.buffer.write(line.encode(encoding, errors="replace"))
    sys.stdout.buffer.flush()
