"""git-year-review 命令行入口。

用法（在项目目录下）：
  python -m gyr author --add me@example.com
  python -m gyr scan --root D:\\work
  python -m gyr list
  python -m gyr select --min 5
  python -m gyr snapshot --year 2026            # 增量：已有快照跳过
  python -m gyr snapshot --year 2026 --refresh  # 只重采最近 3 个月
  python -m gyr snapshot --year 2026 --force    # 全部重采
  python -m gyr stats --year 2026
  python -m gyr digest --year 2026
  python -m gyr provider --add glm --base-url https://open.bigmodel.cn/api/paas/v4 \
      --api-key XXX --model glm-4.7
  python -m gyr provider --use glm
  python -m gyr analyze --year 2026 [--overview]
  python -m gyr report --year 2026 --out 报告.md
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from . import gitops, llm
from .config import CONFIG_PATH, data_dir, load_config, read_dir_json, save_config
from .stats import (
    build_digest,
    find_duplicate_sets,
    load_snapshots,
    load_overview,
    overview_path,
    save_overview,
)


def _setup_stdio():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------- author ----------

def cmd_author(args):
    cfg = load_config()
    if args.list or not args.add:
        print("作者邮箱：" + ("、".join(cfg["authors"]) or "（未配置）"))
        return 0
    for a in args.add:
        if a not in cfg["authors"]:
            cfg["authors"].append(a)
            print("已添加 " + a)
    save_config(cfg)
    print("当前作者：" + "、".join(cfg["authors"]))
    return 0


# ---------- scan ----------

def cmd_scan(args):
    cfg = load_config()
    year = args.year
    if not cfg["authors"]:
        print("请先配置作者邮箱：python -m gyr author --add you@example.com")
        return 1
    if args.root:
        roots = [args.root]
        if args.root not in cfg["roots"]:
            cfg["roots"].append(args.root)
    else:
        roots = cfg["roots"]
    if not roots:
        print("没有根目录：python -m gyr scan --root D:\\coding")
        return 1

    known_paths = {r["path"] for r in cfg["repos"]}
    known_keys = {r["key"] for r in cfg["repos"]}
    added = 0
    for root in roots:
        for item in gitops.discover(root, depth=args.depth):
            if item["path"] in known_paths:
                continue
            key = f"{item['domain']}__{item['name']}"
            if key in known_keys:
                digest = hashlib.md5(item["path"].encode("utf-8")).hexdigest()[:6]
                key = f"{key}_{digest}"
            known_paths.add(item["path"])
            known_keys.add(key)
            n = gitops.author_commit_count(item["path"], year, cfg["authors"])
            cfg["repos"].append({
                "key": key, "name": item["name"], "domain": item["domain"],
                "path": item["path"], "selected": n > 0, f"commits_{year}": n,
            })
            added += 1
            print(f"  + {key} ({n})")
    save_config(cfg)
    total = len(cfg["repos"])
    sel = sum(1 for r in cfg["repos"] if r["selected"])
    print(f"新登记 {added} 个，共 {total} 个仓库，已选 {sel} 个（默认选中年内本人有提交的）。")
    return 0


# ---------- list / select ----------

def cmd_list(args):
    cfg = load_config()
    field = f"commits_{args.year}"
    rows = sorted(cfg["repos"], key=lambda r: -r.get(field, 0))
    for r in rows:
        mark = "*" if r.get("selected") else " "
        print(f"{mark} {r.get(field, '?'):>5}  {r['key']}")
    print(f"\n* 为已选，共 {sum(1 for r in cfg['repos'] if r.get('selected'))}/{len(rows)}")
    return 0


def cmd_select(args):
    cfg = load_config()
    year = args.year
    for r in cfg["repos"]:
        if args.all:
            r["selected"] = True
        elif args.none:
            r["selected"] = False
        elif args.domain and r["domain"] == args.domain:
            r["selected"] = True
        elif args.min is not None:
            c = gitops.author_commit_count(r["path"], year, cfg["authors"])
            r[f"commits_{year}"] = c
            r["selected"] = c >= args.min
    save_config(cfg)
    sel = sum(1 for r in cfg["repos"] if r.get("selected"))
    print(f"已选 {sel}/{len(cfg['repos'])} 个仓库。")
    return 0


# ---------- snapshot ----------

def cmd_snapshot(args):
    cfg = load_config()
    if not cfg["authors"]:
        print("请先配置作者邮箱。")
        return 1
    year = args.year
    sdir = data_dir("snapshots", year)
    sel = [r for r in cfg["repos"] if r.get("selected")]
    if not sel:
        print("没有已选仓库。")
        return 1
    now_ym = datetime.now().strftime("%Y-%m")
    recent = [m for m in gitops.month_range(year) if m <= now_ym][-3:]

    for i, r in enumerate(sel, 1):
        f = sdir / (r["key"] + ".json")
        snap = None
        if f.exists() and not args.force:
            snap = json.loads(f.read_text(encoding="utf-8"))
            if not args.refresh:
                print(f"[{i}/{len(sel)}] 跳过 {r['key']}（已有快照，--refresh/--force 可重采）")
                continue
        if snap is None:
            snap = {
                "key": r["key"], "name": r["name"], "domain": r["domain"],
                "path": r["path"], "year": year, "authors": list(cfg["authors"]),
                "months": {}, "tags": [],
            }
            months = gitops.month_range(year)
        else:
            months = sorted(set(snap["months"].keys()) | set(recent))

        try:
            got = gitops.extract_months(r["path"], year, cfg["authors"], months)
            tags = gitops.list_tags(r["path"], year)
        except RuntimeError as e:
            print(f"[{i}/{len(sel)}] 失败 {r['key']}: {e}")
            continue
        for m in months:
            if got.get(m):
                snap["months"][m] = {"commits": got[m]}
            else:
                snap["months"].pop(m, None)
        snap["tags"] = tags
        snap["generated_at"] = datetime.now().isoformat(timespec="seconds")
        f.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
        total = sum(len(md["commits"]) for md in snap["months"].values())
        print(f"[{i}/{len(sel)}] {r['key']}: {total} commits / {len(snap['months'])} 个月")
    print("快照完成。")
    return 0


def cmd_check(args):
    snaps = load_snapshots(args.year)
    if not snaps:
        print("没有快照数据，先跑 snapshot。")
        return 1
    dups = find_duplicate_sets(snaps)
    if not dups:
        print(f"查重通过：{len(snaps)} 份快照无跨仓重复提交。")
        return 0
    print(f"发现 {len(dups)} 组疑似重复（通常是同一仓库的 worktree / 克隆副本，提交被重复统计）：")
    for d in dups:
        print(f"  {d['a']}({d['a_total']}) <-> {d['b']}({d['b_total']}) 交集 {d['overlap']}")
    print("处理：把副本从登记中移除（编辑 config.json 或 select --none 后重扫），再 snapshot --force、stats、digest。")
    return 0


# ---------- stats / digest ----------

def cmd_stats(args):
    snaps = load_snapshots(args.year)
    if not snaps:
        print("没有快照数据，先跑 snapshot。")
        return 1
    ov = save_overview(args.year, snaps)
    print(f"总提交 {ov['total_commits']:,}｜活跃 {ov['active_days']} 天｜"
          f"{len(ov['domains'])} 个业务域 / {ov['repos']} 个项目")
    print("统计写入 " + str(overview_path(args.year)))
    return 0


def cmd_digest(args):
    snaps = load_snapshots(args.year)
    if not snaps:
        print("没有快照数据，先跑 snapshot。")
        return 1
    ddir = data_dir("digests", args.year)
    for s in snaps:
        d = build_digest(s)
        (ddir / (s["key"] + ".json")).write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8"
        )
    print(f"已导出 {len(snaps)} 份 digest 到 {ddir}")
    return 0


# ---------- provider / analyze ----------

def cmd_provider(args):
    cfg = load_config()
    prov = cfg.setdefault("providers", {"active": "", "profiles": {}})
    if args.list or not (args.add or args.use):
        for name, p in prov.get("profiles", {}).items():
            mark = "*" if name == prov.get("active") else " "
            key = (p.get("api_key", "")[:6] + "...") if p.get("api_key") else "(无key)"
            print(f"{mark} {name}: {p.get('base_url')} | {p.get('model')} | {key}")
        if not prov.get("profiles"):
            print("（还没有 provider，--add 添加）")
        return 0
    if args.use:
        if args.use not in prov.get("profiles", {}):
            print(f"不存在 {args.use}")
            return 1
        prov["active"] = args.use
        save_config(cfg)
        print(f"当前 provider：{args.use}")
        return 0
    prof = {"base_url": args.base_url, "api_key": args.api_key, "model": args.model}
    prov.setdefault("profiles", {})[args.add] = prof
    if not prov.get("active"):
        prov["active"] = args.add
    save_config(cfg)
    print(f"已保存 provider {args.add}（active={prov['active']}）")
    return 0


def cmd_analyze(args):
    cfg = load_config()
    profile = llm.active_profile(cfg)
    if profile is None:
        print("未配置可用的模型 provider（provider --add ... 后 provider --use 启用）。")
        print("也可以把 data/digests 交给 AI 助手人工提炼，写入 data/narrative 后直接 report。")
        return 1
    year = args.year
    ddir = data_dir("digests", year)
    ndir = data_dir("narrative", year)

    keys = [args.only] if args.only else sorted(p.stem for p in ddir.glob("*.json"))
    if not keys:
        print("没有 digest，先跑 digest。")
        return 1
    for i, key in enumerate(keys, 1):
        digest = json.loads((ddir / (key + ".json")).read_text(encoding="utf-8"))
        try:
            text = llm.chat(profile, llm.REPO_SYSTEM, llm.REPO_PROMPT.format(
                year=digest["year"], name=digest["name"], domain=digest["domain"],
                digest=json.dumps(digest, ensure_ascii=False),
            ))
            out = llm.parse_json(text)
        except Exception as e:
            print(f"[{i}/{len(keys)}] 失败 {key}: {e}")
            continue
        out.update({"key": key, "name": digest["name"], "domain": digest["domain"]})
        (ndir / (key + ".json")).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{i}/{len(keys)}] {key}: OK")

    if args.overview:
        ov = load_overview(year) or save_overview(year, load_snapshots(year))
        repo_summaries = []
        for p in sorted(ndir.glob("*.json")):
            if p.stem == "_overview":
                continue
            n = json.loads(p.read_text(encoding="utf-8"))
            repo_summaries.append({
                "name": n.get("name"), "domain": n.get("domain"),
                "summary": n.get("summary"), "highlights": n.get("highlights"),
            })
        compact = {
            "总览": {k: ov[k] for k in
                     ("total_commits", "active_days", "total_ins", "total_dels", "repos", "per_month")},
            "业务域": {d: v["commits"] for d, v in ov["domains"].items()},
            "项目摘要": repo_summaries,
        }
        text = llm.chat(profile, llm.OVERVIEW_SYSTEM, llm.OVERVIEW_PROMPT.format(
            year=year, data=json.dumps(compact, ensure_ascii=False)))
        out = llm.parse_json(text)
        (ndir / "_overview.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("_overview: OK")
    return 0


# ---------- report ----------

def cmd_report(args):
    from . import report as rpt
    outp = rpt.generate(args.year, args.out)
    print("报告已生成：" + str(outp))
    return 0


# ---------- parser ----------

def build_parser():
    p = argparse.ArgumentParser(prog="gyr", description="git 年度研发报告工具")
    p.add_argument("--version", action="version", version="gyr 0.1.0")
    sub = p.add_subparsers(dest="cmd", required=True)

    def year_arg(sp, default=None):
        sp.add_argument("--year", type=int,
                        default=default or datetime.now().year)

    sp = sub.add_parser("author", help="管理作者邮箱（提交过滤）")
    sp.add_argument("--add", action="append", help="添加作者邮箱，可重复")
    sp.add_argument("--list", action="store_true")
    sp.set_defaults(func=cmd_author)

    sp = sub.add_parser("scan", help="扫描根目录，登记 git 仓库")
    sp.add_argument("--root", help="项目根目录，如 D:\\coding")
    sp.add_argument("--depth", type=int, default=2)
    year_arg(sp)
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("list", help="列出仓库与年内提交数")
    year_arg(sp)
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("select", help="勾选参与分析的仓库")
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--none", action="store_true")
    g.add_argument("--min", type=int, metavar="N", help="年内本人提交数 >= N")
    g.add_argument("--domain", help="按业务域选中")
    year_arg(sp)
    sp.set_defaults(func=cmd_select)

    sp = sub.add_parser("snapshot", help="采集 git 快照（增量）")
    year_arg(sp)
    sp.add_argument("--refresh", action="store_true", help="重采已有月份中最近 3 个月")
    sp.add_argument("--force", action="store_true", help="全部重采")
    sp.set_defaults(func=cmd_snapshot)

    sp = sub.add_parser("check", help="跨仓提交查重（worktree/克隆副本检测）")
    year_arg(sp)
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("stats", help="生成年度统计")
    year_arg(sp)
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("digest", help="导出提炼层输入摘要")
    year_arg(sp)
    sp.set_defaults(func=cmd_digest)

    sp = sub.add_parser("provider", help="管理模型配置（cc-switch 风格）")
    sp.add_argument("--add", metavar="NAME")
    sp.add_argument("--base-url")
    sp.add_argument("--api-key")
    sp.add_argument("--model")
    sp.add_argument("--use", metavar="NAME")
    sp.add_argument("--list", action="store_true")
    sp.set_defaults(func=cmd_provider)

    sp = sub.add_parser("analyze", help="调 LLM 提炼各项目叙事")
    year_arg(sp)
    sp.add_argument("--only", metavar="KEY")
    sp.add_argument("--overview", action="store_true", help="附带生成年度总述")
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("report", help="生成 markdown 年度报告")
    year_arg(sp)
    sp.add_argument("--out", help="输出路径（默认 ~/.year-review/data/reports/）")
    sp.set_defaults(func=cmd_report)

    return p


def main(argv=None):
    _setup_stdio()
    args = build_parser().parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
