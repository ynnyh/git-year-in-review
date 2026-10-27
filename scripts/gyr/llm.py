"""LLM 提炼层：OpenAI 兼容接口，cc-switch 风格的多 provider 配置。

config.json 里的 providers 形如：
{
  "active": "glm",
  "profiles": {
    "glm":   {"base_url": "https://open.bigmodel.cn/api/paas/v4", "api_key": "...', "model": "glm-4.7"},
    "dsl":   {"base_url": "https://api.deepseek.com",             "api_key": "...", "model": "deepseek-chat"}
  }
}
任何 OpenAI 兼容服务（GLM/DeepSeek/Kimi/Qwen/OpenAI/Ollama/vLLM…）都能接。
"""

import json
import re
import urllib.request

REPO_SYSTEM = "你是资深研发负责人，为团队成员撰写年度复盘。只输出一个 JSON 对象，不要输出任何其他文字。"

REPO_PROMPT = """以下是某项目 {year} 年的 git 提交记录摘要（仅本人提交，按月整理：n 为当月提交数，subjects 为提交说明，top_dirs 为当月改动最多的目录）。

项目：{name}（业务域：{domain}）
数据：
{digest}

请输出 JSON，字段必须齐全：
{{
  "summary": "一句话概括项目定位与本人全年工作重点，不超过80字",
  "months": {{"{year}-01": "本月工作主题，不超过40字"}}  （只写有提交的月份）,
  "highlights": ["全年亮点3-8条，每条不超过60字，突出业务价值、功能规模、技术要点，口吻适合写入年终述职"]
}}
要求：基于提交事实提炼，不要编造数字和功能名；提交说明质量低时，结合 top_dirs 和 tags 推断主题，措辞可以概括，但不能虚构具体功能。"""

OVERVIEW_SYSTEM = "你是资深研发负责人，为团队成员撰写年度总结。只输出一个 JSON 对象，不要输出任何其他文字。"

OVERVIEW_PROMPT = """以下是 {year} 年度跨项目统计数据和各项目摘要（JSON）。

{data}

请输出 JSON：
{{
  "year_summary": "全年工作总述，120字以内，述职口吻",
  "highlights": ["年度亮点5-8条，每条不超过60字，跨项目提炼，突出主线：如某业务域从0到1、持续迭代发版、重要重构、多端覆盖等"]
}}"""


def active_profile(cfg: dict):
    p = cfg.get("providers", {})
    name = p.get("active", "")
    prof = p.get("profiles", {}).get(name)
    if not prof or not prof.get("api_key") or not prof.get("base_url"):
        return None
    return name, prof


def chat(profile, system: str, user: str, timeout: int = 180) -> str:
    _, prof = profile
    url = prof["base_url"].rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": prof["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + prof["api_key"],
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.M)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("模型输出中没有 JSON：" + text[:200])
    return json.loads(text[start : end + 1])
