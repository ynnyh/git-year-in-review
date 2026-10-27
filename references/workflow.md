# 引擎命令全表与数据格式（参考文档）

## 命令总表

| 命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `author --add <邮箱>` / `--list` | 管理作者邮箱（提交过滤，可多个） | `--add` 可重复 |
| `scan --root <目录>` | 扫描登记 git 仓库（自动跳过 worktree；默认选中年内本人有提交的） | `--depth`（默认下钻 2 层） |
| `list` | 列出仓库与年内本人提交数（`*` 为已选） | `--year` |
| `select --min N` / `--all` / `--none` / `--domain X` | 勾选参与分析的仓库 | `--year` |
| `snapshot` | 采集 git 快照（增量） | `--refresh`（重采最近 3 个月）、`--force`（全量） |
| `check` | 跨仓提交查重（worktree/克隆副本检测） | `--year` |
| `stats` | 生成年度统计 overview.json | `--year` |
| `digest` | 导出提炼层输入摘要 | `--year` |
| `provider --add 名称 --base-url URL --api-key KEY --model 型号` / `--use 名称` / `--list` | 管理 LLM 配置（cc-switch 风格，任意 OpenAI 兼容服务） | |
| `analyze` | 调 LLM 提炼叙事（可选 `--overview` 附带年度总述，`--only KEY` 单仓） | `--year` |
| `report` | 生成 Markdown 年度报告 | `--year`、`--out` |

入口：`python3 <skill目录>/scripts/gyr.py <命令>`（Windows 常为 `python`）。

## 数据位置

默认根：`~/.year-review/`（环境变量 `GYR_HOME` 可覆盖）。

```
~/.year-review/
  config.json                  # roots/authors/repos/providers
  data/
    snapshots/<年>/<key>.json  # 采集快照（key = 业务域__项目名）
    digests/<年>/<key>.json    # 提炼输入（每月去重 subjects + top_dirs + tags）
    narrative/<年>/<key>.json  # 提炼输出（LLM 或 agent 人工）
    narrative/<年>/_overview.json  # 年度总述
    stats/<年>/overview.json   # 年度统计
    reports/                   # 默认报告输出目录
```

## 快照 JSON 结构（摘要）

```json
{
  "key": "ecommerce__order-center", "name": "order-center", "domain": "ecommerce",
  "year": 2026, "authors": ["..."],
  "months": {"2026-03": {"commits": [{"h": "哈希", "d": "2026-03-04", "s": "说明", "ins": 12, "dels": 3, "files": [["12", "3", "src/a.vue"]]}]}},
  "tags": [{"name": "v2.1.0", "date": "2026-03-15"}]
}
```

采集口径：`git log --all --no-merges --author=<邮箱> --since --until --numstat`。

## 常见问题

- **总提交数虚高**：十有八九是 worktree/克隆副本被当成了独立仓库。`check` 命令会按 commit 哈希交集（>30%）报出重复对；处理掉副本后 `snapshot --force` 重采。
- **commit message 质量差**（"1"、"update"、重复模板）：提炼时以 `top_dirs`、`tags`、每月提交数走势为主推断主题，不硬编功能名。
- **Windows 控制台中文乱码**：脚本已强制 UTF-8 输出；终端显示乱码不影响写盘的文件。
- **Windows 上没有 `python3`**：用 `python`。要求 Python ≥ 3.10（用了 `X | Y` 类型语法）。
- **报告里某项目叙事有误**：直接改 `narrative/<年>/<key>.json` 再重跑 `report`，不要手改报告。
- **换机器/换数据目录**：设 `GYR_HOME`；config 里的仓库路径按新机器调整后重跑 snapshot。
