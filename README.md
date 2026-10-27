# Git Year in Review · git 年度研发报告

[![skills.sh](https://skills.sh/b/ynnyh/git-year-in-review)](https://skills.sh/ynnyh/git-year-in-review)

[English](#english) ｜ 一个 **Agent Skill**：让 AI 编码助手（ZCode / Claude Code / Trae 等支持 Agent Skills 的工具）读取你本地的 git 仓库，生成一份**个人年度研发报告**——年终总结、年度复盘、述职材料的底稿。

**核心特性**

- 🔒 **纯本地执行**：只读 git 历史，代码不出机器，公司项目也能放心分析（提炼在你的 agent 会话内完成，无需 API key）
- 👤 **按作者过滤**：多人仓库只统计你自己的提交
- 📈 **增量快照**：平时每月刷新一次（几秒），年底一键出全年报告
- 🏗️ **确定性引擎 + LLM 提炼**：采集/统计/报告组装是脚本（零 pip 依赖，仅 python3 + git），逐项目叙事由 agent 生成并落盘为可修订的 JSON
- 📄 **报告是中间产物**：Markdown 结构（总览 / 分项目大事记 / 年度亮点 / 附录）与 PPT 章节一一对应，可直接二次加工

## 安装

**方式一：skills CLI（推荐，适用于 Claude Code / Codex / Cursor / OpenCode 等 75+ agent）**

```bash
npx skills add ynnyh/git-year-in-review
```

**方式二：手动复制到 agent skills 目录**

```bash
# ZCode / Claude Code（用户级）
git clone https://github.com/ynnyh/git-year-in-review.git ~/.zcode/skills/git-year-in-review
# 或 Claude Code:
git clone https://github.com/ynnyh/git-year-in-review.git ~/.claude/skills/git-year-in-review
# Trae 及其他支持 Agent Skills 的工具按其 skills 目录放置（或用 Upload Skill 上传 zip）
```

不需要 pip install，不需要 API key。

## 使用

装好后直接对 agent 说：

> 帮我把 D:\work 下的项目做一份 2026 年度研发报告，我的邮箱是 me@example.com

Skill 会引导确认项目根目录 / 作者邮箱 / 年份，然后跑完整流水线并交付报告。全年流程也可以手工驱动：

```bash
python3 scripts/gyr.py author --add me@example.com
python3 scripts/gyr.py scan --root D:\work
python3 scripts/gyr.py snapshot --year 2026          # 增量：--refresh 只重采最近 3 个月
python3 scripts/gyr.py check  --year 2026            # worktree/克隆副本查重
python3 scripts/gyr.py stats  --year 2026
python3 scripts/gyr.py digest --year 2026
python3 scripts/gyr.py report --year 2026 --out 报告.md
```

可选：配置任意 OpenAI 兼容模型后可全自动提炼（不配则由 agent 人工提炼）：

```bash
python3 scripts/gyr.py provider --add glm --base-url https://open.bigmodel.cn/api/paas/v4 --api-key XXX --model glm-4.7
python3 scripts/gyr.py provider --use glm
python3 scripts/gyr.py analyze --year 2026 --overview
```

示例报告见 [assets/example-report.md](assets/example-report.md)，数据格式与命令全表见 [references/workflow.md](references/workflow.md)。

## 它是怎么算的

- 采集口径：`git log --all --no-merges --author=<你的邮箱> --since=<年>-01-01 --numstat`
- 自动跳过 git worktree，并内置跨仓库提交查重（同一仓库的发布副本会虚增数字）
- 每个项目输出：提交数、活跃天数、增删行数、年度版本（tag）、逐月主题、全年亮点
- 数据全部落在 `~/.year-review/`，删掉即卸载

## 发布

本目录即 Agent Skills 开放标准的发布包（`SKILL.md` + `scripts/` + `references/` + `assets/`），可提交到支持该标准的 skill 市场/索引（Trae、awesome-agent-skills、skillsllm 等）。

## License

MIT

---

<a name="english"></a>

# Git Year in Review

An **Agent Skill** that turns the git history of your local repositories into a personal **year-in-review coding report** — stats, per-project monthly themes, and annual highlights, delivered as structured Markdown you can turn into slides.

- **Fully local**: only reads git history; nothing leaves your machine. Company repos are fine.
- **Author-filtered**: counts only your commits in shared repos.
- **Incremental snapshots**: refresh monthly in seconds, generate the full-year report in December.
- **Deterministic engine + LLM narrative**: stdlib-only Python (python3 + git) for extraction/stats; per-project narratives written by your agent as revisable JSON files.

```bash
git clone https://github.com/ynnyh/git-year-in-review.git ~/.claude/skills/git-year-in-review
# or: npx skills add ynnyh/git-year-in-review
# then just ask your agent:
# "Generate my 2026 year-in-review report from ~/work, my email is me@example.com"
```
