"""年度统计与 digest 导出。"""

import json

from .config import APP_DIR, data_dir


def load_snapshots(year: int) -> list[dict]:
    d = APP_DIR / "data" / "snapshots" / str(year)
    snaps = []
    if d.exists():
        for f in sorted(d.glob("*.json")):
            snaps.append(json.loads(f.read_text(encoding="utf-8")))
    return snaps


def _dir_key(fpath: str) -> str:
    parts = fpath.replace("\\", "/").split("/")
    return "/".join(parts[:3])


def build_overview(year: int, snaps: list[dict]) -> dict:
    months_all = [f"{year}-{m:02d}" for m in range(1, 13)]
    per_month = {m: 0 for m in months_all}
    domains: dict[str, dict] = {}
    days: set[str] = set()
    total_commits = total_ins = total_dels = 0
    dircount: dict[str, int] = {}

    for s in snaps:
        r_commits = r_ins = r_dels = 0
        r_days: set[str] = set()
        r_months = {m: 0 for m in months_all}
        for m, md in s["months"].items():
            for c in md["commits"]:
                per_month[m] = per_month.get(m, 0) + 1
                r_months[m] += 1
                r_commits += 1
                r_ins += c.get("ins", 0)
                r_dels += c.get("dels", 0)
                r_days.add(c["d"])
                days.add(c["d"])
                for f in c.get("files", []):
                    k = _dir_key(f[2])
                    dircount[k] = dircount.get(k, 0) + 1
        total_commits += r_commits
        total_ins += r_ins
        total_dels += r_dels
        dom = domains.setdefault(s["domain"], {"commits": 0, "repos": {}})
        dom["commits"] += r_commits
        dom["repos"][s["name"]] = {
            "key": s["key"],
            "commits": r_commits,
            "ins": r_ins,
            "dels": r_dels,
            "active_days": len(r_days),
            "months": {m: n for m, n in r_months.items() if n},
        }

    return {
        "year": year,
        "repos": len(snaps),
        "total_commits": total_commits,
        "total_ins": total_ins,
        "total_dels": total_dels,
        "active_days": len(days),
        "per_month": per_month,
        "domains": domains,
        "top_dirs": sorted(dircount.items(), key=lambda x: -x[1])[:30],
    }


def build_digest(snap: dict, cap_subjects: int = 40) -> dict:
    """把快照压缩成提炼层输入：每月去重后的提交说明 + 热点目录。"""
    months = {}
    total = 0
    for m in sorted(snap["months"].keys()):
        commits = snap["months"][m]["commits"]
        total += len(commits)
        seen: set[str] = set()
        subjects: list[str] = []
        dircount: dict[str, int] = {}
        ins = dels = 0
        for c in commits:
            ins += c.get("ins", 0)
            dels += c.get("dels", 0)
            subject = c["s"].strip()
            if subject and subject not in seen and len(subjects) < cap_subjects:
                seen.add(subject)
                subjects.append(subject[:100])
            for f in c.get("files", []):
                k = _dir_key(f[2])
                dircount[k] = dircount.get(k, 0) + 1
        months[m] = {
            "n": len(commits),
            "ins": ins,
            "dels": dels,
            "subjects": subjects,
            "top_dirs": [k for k, _ in sorted(dircount.items(), key=lambda x: -x[1])[:8]],
        }
    return {
        "key": snap["key"],
        "name": snap["name"],
        "domain": snap["domain"],
        "year": snap["year"],
        "total": total,
        "months": months,
        "tags": snap.get("tags", []),
    }


def find_duplicate_sets(snaps: list[dict], threshold: float = 0.3) -> list[dict]:
    """检测跨仓库提交重复（worktree/克隆副本会让同一批提交被统计多次）。"""
    sets: dict[str, set] = {}
    for s in snaps:
        hashes = {c["h"] for md in s["months"].values() for c in md["commits"]}
        if hashes:
            sets[s["key"]] = hashes
    out = []
    keys = sorted(sets)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            inter = len(sets[a] & sets[b])
            if inter and inter / min(len(sets[a]), len(sets[b])) > threshold:
                out.append({
                    "a": a, "b": b, "overlap": inter,
                    "a_total": len(sets[a]), "b_total": len(sets[b]),
                })
    return out


def overview_path(year: int):
    return data_dir("stats", year) / "overview.json"


def save_overview(year: int, snaps: list[dict]) -> dict:
    ov = build_overview(year, snaps)
    overview_path(year).write_text(
        json.dumps(ov, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ov


def load_overview(year: int) -> dict | None:
    p = overview_path(year)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None
