---
name: git-year-in-review
description: 从 git 提交记录生成个人年度研发报告（年终总结 / 年度复盘 / 述职素材）。扫描本地项目目录、按作者邮箱过滤提交、增量快照，统计提交/活跃天/代码行分布，逐项目提炼每月工作主题与年度亮点，输出结构化 Markdown 报告（可再生成 PPT）。Generate a personal year-in-review coding report from git history across multiple local repositories — scans project folders, filters commits by author email, takes incremental snapshots, computes stats, and extracts per-project monthly themes and highlights into a Markdown annual report. 触发词：年终总结、年度报告、年度复盘、年度盘点、述职报告、git 年报、year in review、annual report、year in code、git wrapped。
license: MIT
---

# Git 年度研发报告（Git Year in Review）

把用户本地的一批 git 仓库分析成一份年度研发报告。流水线分三段：**采集（脚本）→ 提炼（由你完成）→ 报告（脚本组装）**。提炼层不需要任何 API key——你就是提炼模型。

引擎入口：`python3 <本skill目录>/scripts/gyr.py`（下文简写为 `GYR`；Windows 上命令可能是 `python` 而非 `python3`）。依赖仅 python3.10+ 与 git，无 pip 依赖。所有用户数据写在 `~/.year-review/`（可用环境变量 `GYR_HOME` 改），代码不出本机。

## 第 0 步：收集参数

开始前向用户确认三件事（一轮问齐）：

1. **项目根目录**（可多个），如 `D:\work`、`~/projects`；
2. **作者邮箱**（提交过滤，可多个）。用户不确定时，从他的仓库里查：
   `git -C <某仓库> log --format='%ae' --since=<当年>-01-01 | sort -u`，让用户认领；
3. **年份**（默认当前年）。

公司多人仓库**必须**按作者过滤，否则统计的是整个团队的产出。

## 第 1 步：登记与勾选

```bash
GYR author --add <邮箱1> --add <邮箱2>
GYR scan --root <项目根目录>          # 自动发现仓库；默认选中年内本人有提交的
GYR list --year <年>                  # 查看（* 为已选）
GYR select --min 5 --year <年>        # 可选：只保留提交数 >= 5 的项目
```

`scan` 已自动跳过 git worktree（其 `.git` 是文件）。同名仓库出现在多个根目录时 key 会加哈希后缀，属正常。

## 第 2 步：采集快照（增量）

```bash
GYR snapshot --year <年>              # 已有快照的仓库跳过
# --refresh 只重采最近 3 个月（平时每月跑一次用这个）
# --force  全部重采
```

首次全量大约每仓几秒。快照落盘在 `~/.year-review/data/snapshots/<年>/<业务域__项目名>.json`。

## 第 3 步：查重、统计、摘要

```bash
GYR check  --year <年>                # 跨仓提交查重
GYR stats  --year <年>
GYR digest --year <年>
```

`check` 报出交集 >30% 的仓库对，几乎总是同一仓库的 worktree/克隆副本——按提示把副本从登记中移除后重跑 2、3 步，**否则总数字会虚高**。digest 输出在 `~/.year-review/data/digests/<年>/`。

## 第 4 步：提炼叙事（你来做）

对每份 digest 生成同名叙事 JSON，写入 `~/.year-review/data/narrative/<年>/<key>.json`：

```json
{
  "key": "<digest 的 key 原样>", "name": "<原样>", "domain": "<原样>",
  "summary": "一句话：项目定位 + 本人全年工作重点，≤80字",
  "months": {"2026-03": "本月工作主题，≤40字"},
  "highlights": ["全年亮点 3-8 条（提交<10 次的项目 1-2 条），每条 ≤60字，业务价值导向、述职口吻"]
}
```

规则：

- **基于提交事实**（subjects、top_dirs、每月 n、tags），不编造数字、版本号、功能名；
- subjects 质量差（"1"、"update"、大量重复）时，结合 top_dirs 和 tags 概括主题，措辞可泛化但不得虚构；
- `months` 的 key 必须与 digest 里的月份完全一致，只写有提交的月份；
- 全部用用户报告语言（中文场景用中文）。

规模策略：**≤12 个仓库**直接逐个读写；**更多**则并行派子代理，每批约 15 个 digest，要求各批写完后汇报校验结果，你抽查几个。全部完成后读 `~/.year-review/data/stats/<年>/overview.json` 和各项目 summary，写 `_overview.json`：

```json
{
  "year_summary": "全年总述，≤120字，述职口吻",
  "highlights": ["跨项目年度主线 5-8 条，每条 ≤60字"]
}
```

> 备选：用户在 config.json 配了模型 provider（`GYR provider --add 名称 --base-url <OpenAI兼容地址> --api-key KEY --model 型号` 后 `GYR provider --use 名称`）时，可直接 `GYR analyze --year <年> --overview` 自动完成本步。

## 第 5 步：生成报告

```bash
GYR report --year <年> --out "<输出路径>.md"
```

建议输出到用户显眼处（如项目目录 `reports/<年>年度研发报告.md`）。报告结构：年度总览（数字 + 月度分布 + 业务域分布）→ 分项目大事记（逐仓：定位、年度数字、逐月主题表、亮点）→ 年度亮点 → 附录清单。

交付时：报告路径 + 3-5 个头条数字 + 提醒用户**人工核对各项目叙事**（推断自提交记录，可能有出入；改对应 narrative JSON 后重跑 report 即可）。报告是中间产物，用户需要时可基于它再生成 PPT/docx。

## 增量使用节奏（告诉用户）

平时每月一次 `snapshot --refresh`（几秒）；年底 `snapshot --refresh → check → stats → digest → 提炼 → report` 出全年报告。11、12 月等新月份会被自动补齐。

## 数据安全（可向用户承诺）

纯本地执行，只读 git 历史，不联网；唯一出网场景是用户主动配置 provider 走 `analyze`。公司项目可放心分析。

细节参考：[references/workflow.md](references/workflow.md)（命令全表、数据格式、常见问题）。
