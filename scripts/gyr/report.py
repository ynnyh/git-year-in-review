"""Markdown 年度报告生成。报告是中间产物，后续 PPT 以它为输入。"""

import json
from datetime import datetime
from pathlib import Path

from .config import APP_DIR, data_dir, load_config, read_dir_json
from .stats import load_overview, load_snapshots

MONTH_LABELS = [f"{m}月" for m in range(1, 13)]


def _month_label(m: str) -> str:
    try:
        return f"{int(m.split('-')[1])}月"
    except (ValueError, IndexError):
        return m


def _fmt(n: int) -> str:
    return f"{n:,}"


def _repo_numbers(snap: dict) -> dict:
    commits = ins = dels = 0
    days = set()
    months = {}
    for m, md in snap["months"].items():
        months[m] = len(md["commits"])
        for c in md["commits"]:
            commits += 1
            ins += c.get("ins", 0)
            dels += c.get("dels", 0)
            days.add(c["d"])
    return {"commits": commits, "ins": ins, "dels": dels,
            "active_days": len(days), "months": months}


def _repo_section(sb: list, name: str, snap: dict, narrative: dict | None,
                  digest: dict | None, year: int):
    nums = _repo_numbers(snap)
    sb.append(f"#### {name}\n")
    if narrative and narrative.get("summary"):
        sb.append(narrative["summary"] + "\n")
    tags = snap.get("tags", [])
    tag_txt = "、".join(t["name"] for t in tags) if tags else "无"
    sb.append(
        f"- 提交 **{_fmt(nums['commits'])}** 次｜活跃 **{nums['active_days']}** 天｜"
        f"新增 **{_fmt(nums['ins'])}** 行 / 删除 {_fmt(nums['dels'])} 行｜"
        f"年度版本：{tag_txt}"
    )
    months_with = sorted(nums["months"].keys())
    if months_with:
        span = f"{_month_label(months_with[0])} ~ {_month_label(months_with[-1])}"
        sb.append(f"- 活跃区间：{span}（{_fmt(len(months_with))} 个月有提交）")
    sb.append("")

    if narrative and narrative.get("months"):
        sb.append("| 月份 | 工作主题 |")
        sb.append("| --- | --- |")
        for m in months_with:
            theme = narrative["months"].get(m, "")
            if theme:
                sb.append(f"| {_month_label(m)} | {theme} |")
        sb.append("")
    elif digest:
        # 无叙事时的兜底：每月最多列 3 条提交说明
        for m in months_with:
            subs = digest["months"].get(m, {}).get("subjects", [])[:3]
            if subs:
                sb.append(f"- **{_month_label(m)}**：{'；'.join(subs)}")
        sb.append("")

    if narrative and narrative.get("highlights"):
        sb.append("**年度亮点**\n")
        for h in narrative["highlights"]:
            sb.append(f"- {h}")
        sb.append("")


def generate(year: int, out: str | None = None) -> Path:
    cfg = load_config()
    snaps = load_snapshots(year)
    if not snaps:
        raise SystemExit(f"没有 {year} 年快照数据，先跑 snapshot。")
    overview = load_overview(year)
    if overview is None:
        from .stats import build_overview
        overview = build_overview(year, snaps)
    digests = read_dir_json(data_dir("digests", year))
    narratives = read_dir_json(data_dir("narrative", year))
    overview_narrative = narratives.pop("_overview", None)

    sb: list[str] = []
    sb.append(f"# {year} 年度研发工作报告\n")
    authors = "、".join(cfg["authors"]) or "（未过滤）"
    roots = "；".join(cfg["roots"])
    sb.append(
        f"> 作者：{authors} ｜ 范围：{roots} ｜ "
        f"覆盖 {overview['repos']} 个项目 ｜ "
        f"生成时间：{datetime.now():%Y-%m-%d %H:%M}\n"
    )

    # 一、年度总览
    sb.append("## 一、年度总览\n")
    ov_n = overview_narrative or {}
    if ov_n.get("year_summary"):
        sb.append(ov_n["year_summary"] + "\n")
    sb.append(
        f"- 总提交 **{_fmt(overview['total_commits'])}** 次，活跃 **{overview['active_days']}** 天，"
        f"新增 **{_fmt(overview['total_ins'])}** 行、删除 {_fmt(overview['total_dels'])} 行"
    )
    sb.append(
        f"- 覆盖 **{len(overview['domains'])}** 个业务域、**{overview['repos']}** 个项目\n"
    )
    sb.append("**月度提交分布**\n")
    sb.append("| " + " | ".join(MONTH_LABELS) + " |")
    sb.append("| " + " | ".join(["---"] * 12) + " |")
    pm = overview["per_month"]
    sb.append("| " + " | ".join(_fmt(pm.get(f"{year}-{m:02d}", 0)) for m in range(1, 13)) + " |\n")

    dom_rows = sorted(overview["domains"].items(), key=lambda x: -x[1]["commits"])
    sb.append("**业务域分布**\n")
    sb.append("| 业务域 | 项目数 | 提交数 |")
    sb.append("| --- | --- | --- |")
    for dom, info in dom_rows:
        sb.append(f"| {dom} | {len(info['repos'])} | {_fmt(info['commits'])} |")
    sb.append("")

    # 二、分领域大事记
    sb.append("## 二、分项目大事记\n")
    dom_snaps: dict[str, list] = {}
    for s in snaps:
        dom_snaps.setdefault(s["domain"], []).append(s)
    for dom, info in dom_rows:
        dsnaps = sorted(
            dom_snaps.get(dom, []),
            key=lambda s: -sum(len(md["commits"]) for md in s["months"].values()),
        )
        if not dsnaps:
            continue
        sb.append(f"### {dom}（{len(dsnaps)} 个项目 · {_fmt(info['commits'])} 次提交）\n")
        for s in dsnaps:
            _repo_section(sb, s["name"], s, narratives.get(s["key"]),
                          digests.get(s["key"]), year)
        sb.append("")

    # 三、年度亮点
    if ov_n.get("highlights"):
        sb.append("## 三、年度亮点\n")
        for h in ov_n["highlights"]:
            sb.append(f"- {h}")
        sb.append("")

    # 附录
    sb.append("## 附录：项目清单\n")
    sb.append("| 项目 | 业务域 | 提交 | 活跃天 | 新增行 | 删除行 |")
    sb.append("| --- | --- | --- | --- | --- | --- |")
    rows = []
    for s in snaps:
        n = _repo_numbers(s)
        rows.append((n["commits"], s["name"], s["domain"], n))
    for commits, name, dom, n in sorted(rows, reverse=True):
        sb.append(
            f"| {name} | {dom} | {_fmt(n['commits'])} | {n['active_days']} "
            f"| {_fmt(n['ins'])} | {_fmt(n['dels'])} |"
        )
    sb.append("")

    text = "\n".join(sb)
    if out:
        outp = Path(out)
    else:
        outp = data_dir("reports") / f"{year}年度研发报告.md"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(text, encoding="utf-8")
    return outp
