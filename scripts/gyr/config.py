"""配置与数据目录管理。

所有用户数据放在 ~/.year-review（可用 GYR_HOME 环境变量覆盖）：
- config.json：根目录、作者邮箱、仓库登记、模型 provider 配置
- data/snapshots/<year>/<key>.json：按年快照（增量采集）
- data/digests/<year>/<key>.json：提炼层输入摘要
- data/narrative/<year>/<key>.json：提炼层输出叙事（LLM 或人工）
- data/stats/<year>/overview.json：年度统计
"""

import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("GYR_HOME", str(Path.home() / ".year-review")))
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_CONFIG = {
    "roots": [],
    "authors": [],
    "repos": [],
    "providers": {"active": "", "profiles": {}},
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        cfg = {}
    for key, value in DEFAULT_CONFIG.items():
        cfg.setdefault(key, json.loads(json.dumps(value)))
    return cfg


def save_config(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def data_dir(*parts) -> Path:
    d = APP_DIR.joinpath("data", *(str(p) for p in parts))
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_dir_json(directory: Path) -> dict:
    """读取目录下所有 <stem>.json，返回 {stem: obj}。目录不存在返回空。"""
    out = {}
    if directory.exists():
        for f in sorted(directory.glob("*.json")):
            try:
                out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
    return out
