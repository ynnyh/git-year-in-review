#!/usr/bin/env python3
"""git-year-in-review 引擎命令行入口，支持从任意目录用绝对路径调用：

    python3 <skill目录>/scripts/gyr.py <command> ...
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gyr.cli import main

if __name__ == "__main__":
    sys.exit(main())
