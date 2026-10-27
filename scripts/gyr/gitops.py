"""Git 数据采集：仓库发现、提交记录提取、tag 收集。"""

import subprocess
from pathlib import Path


def _git(path: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args[:3])} 失败 ({path}): {r.stderr.strip()[:200]}"
        )
    return r.stdout


def discover(root: str, depth: int = 2) -> list[dict]:
    """在 root 下发现 git 仓库（最多下钻 depth 层），返回 [{name, path, domain}]。"""
    rootp = Path(root).resolve()
    results = []

    def walk(d: Path, level: int):
        try:
            entries = sorted(d.iterdir())
        except OSError:
            return
        # worktree 的 .git 是文件（指向主仓 gitdir），会导致提交重复统计，跳过
        if (d / ".git").is_dir() and d != rootp:
            domain = d.parent.name if d.parent != rootp else "其他"
            results.append({"name": d.name, "path": str(d), "domain": domain})
            return
        if level >= depth:
            return
        for e in entries:
            if e.is_dir() and not e.name.startswith("."):
                walk(e, level + 1)

    walk(rootp, 0)
    return results


def author_commit_count(path: str, year: int, authors: list[str]) -> int:
    args = [
        "rev-list", "--count", "--all", "--no-merges",
        f"--since={year}-01-01", f"--until={year + 1}-01-01",
    ]
    for a in authors:
        args.append(f"--author={a}")
    out = _git(Path(path), *args).strip()
    return int(out or 0)


def extract_year(path: str, year: int, authors: list[str]) -> dict:
    """提取全年本人（--no-merges）提交，返回 {month: [commit]}。

    commit = {h, d(日期), s(说明), ins, dels, files:[[adds, dels, path], ...]}
    """
    args = [
        "log", "--all", "--no-merges", "--date=iso-strict",
        f"--since={year}-01-01", f"--until={year + 1}-01-01",
        "--pretty=format:%x00%H%x00%ad%x00%s", "--numstat",
    ]
    for a in authors:
        args.append(f"--author={a}")
    months: dict[str, list] = {}
    cur = None
    for line in _git(Path(path), *args).splitlines():
        if line.startswith("\x00"):
            parts = line.split("\x00")
            # parts: ['', hash, date, subject]
            if len(parts) < 4:
                continue
            _, h, d, s = parts[0], parts[1], parts[2], parts[3]
            cur = {"h": h, "d": d[:10], "s": s, "ins": 0, "dels": 0, "files": []}
            months.setdefault(d[:7], []).append(cur)
        elif cur is not None and "\t" in line:
            pieces = line.split("\t", 2)
            if len(pieces) < 3:
                continue
            adds, dels, fpath = pieces
            cur["files"].append([adds, dels, fpath])
            if adds.isdigit():
                cur["ins"] += int(adds)
            if dels.isdigit():
                cur["dels"] += int(dels)
    return months


def extract_months(path: str, year: int, authors: list[str], months: list[str]) -> dict:
    """按需提取指定月份（内部仍一次 git log 全年，再按月过滤）。"""
    all_months = extract_year(path, year, authors)
    return {m: all_months.get(m, []) for m in months}


def list_tags(path: str, year: int) -> list[dict]:
    text = _git(
        Path(path), "for-each-ref", "refs/tags", "--sort=creatordate",
        "--format=%(refname:short)%09%(creatordate:iso-strict)",
    )
    tags = []
    for line in text.splitlines():
        if "\t" not in line:
            continue
        name, date = line.split("\t", 1)
        if date[:4] == str(year):
            tags.append({"name": name, "date": date[:10]})
    return tags


def month_range(year: int) -> list[str]:
    return [f"{year}-{m:02d}" for m in range(1, 13)]
