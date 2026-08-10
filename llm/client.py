"""LLM 客户端：对话 + 结构化输出。

结构化输出实现要点（企业级关键点）：
1. 不直接信任大模型返回的自由文本，而是把目标 Pydantic 模型的 JSON Schema
   作为约束注入 system prompt，要求模型输出纯 JSON。
2. 对返回结果做容错解析：剥离 ```json 代码块、提取首个 JSON 对象。
3. 用 Pydantic 校验；校验失败则把错误信息回喂模型重试（最多 N 次），
   形成自纠错闭环，最大化结构化输出的稳定性。

安全/健壮性说明：
- API Key 仅来自配置，不在日志中打印。
- 对输入文本做长度截断，避免超大文档导致 token 超限或费用失控。
- 网络/解析异常向上抛出，由调用方决定降级策略。
"""
from __future__ import annotations

import json
import re
from typing import List, Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from config import settings

T = TypeVar("T", bound=BaseModel)

# 单次输入文本硬上限（按字符数粗略截断，约对应数千 token）
_MAX_INPUT_CHARS = 12000

def _truncate(text: str, limit: int = _MAX_INPUT_CHARS) -> str:
    """超长文本截断，保留头部内容。"""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...(内容过长，已截断)"


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(raw: str) -> dict:
    """从模型输出中稳健地提取首个 JSON 对象。

    处理三种常见情况：
    1. 纯 JSON 文本
    2. 包裹在 ```json ... ``` 代码块中
    3. JSON 前后混有说明文字
    """
    if not raw:
        raise json.JSONDecodeError("空输出", raw, 0)

    # 优先匹配代码块
    fence_match = _JSON_FENCE_RE.search(raw)
    candidate = fence_match.group(1) if fence_match else raw

    # 直接尝试
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 退而求其次：定位首个 { 到末尾首个匹配的 }（贪心到最外层）
    start = candidate.find("{")
    if start == -1:
        raise json.JSONDecodeError("未找到 JSON 对象起始 '{'", candidate, 0)
    # 用栈匹配大括号，避免字段内含 } 导致提前截断
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(candidate)):
        ch = candidate[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(candidate[start:i + 1])
    raise json.JSONDecodeError("JSON 大括号未闭合", candidate, start)


class LLMClient:
    """OpenAI 兼容接口的封装客户端。"""

    def __init__(self):
        if not settings.has_llm_key:
            raise RuntimeError(
                "未检测到 LLM_API_KEY，请在 .env 中配置（参考 .env.example）。"
            )
        self._client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        self._model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._max_retries = settings.structured_max_retries

    def chat(self, system: str, user: str, temperature: Optional[float] = None) -> str:
        """普通对话，返回纯文本。"""
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": _truncate(user)},
            ],
            temperature=self._temperature if temperature is None else temperature,
        )
        return (resp.choices[0].message.content or "").strip()

    def chat_structured(
        self,
        system: str,
        user: str,
        model: Type[T],
        temperature: Optional[float] = None,
    ) -> T:
        """结构化对话：强制输出符合 Pydantic 模型 model 的对象。

        流程：注入 JSON Schema -> 解析 -> Pydantic 校验 -> 失败回喂重试。
        """
        schema_json = json.dumps(model.model_json_schema(), ensure_ascii=False)
        system_with_schema = (
            system.strip()
            + "\n\n【输出约束】你必须只输出一个 JSON 对象，严格符合下面的 JSON Schema，"
            "不要包含任何解释性文字、不要使用 markdown 代码块包裹：\n"
            + schema_json
        )

        current_user = user
        last_err: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                raw = self.chat(system_with_schema, current_user, temperature)
                data = _extract_json(raw)
                return model.model_validate(data)
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                last_err = e
                # 回喂错误，引导模型在下一轮自纠错
                current_user = (
                    user
                    + f"\n\n【重试提示】你第 {attempt} 次输出的内容无法通过校验：{e}。"
                    "请只输出符合 Schema 的纯 JSON，不要有任何多余文字。"
                )
        raise ValueError(f"结构化输出解析失败（重试 {self._max_retries} 次）：{last_err}")

    def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """批量获取向量。失败时返回 None，由上层降级到 BM25。"""
        if not settings.has_embedding_key or not settings.enable_embedding_rag:
            return None
        try:
            base_url = settings.embedding_base_url or settings.llm_base_url
            embed_client = OpenAI(api_key=settings.embedding_api_key, base_url=base_url)
            # 多数兼容服务支持批量；为稳妥按批请求
            resp = embed_client.embeddings.create(
                model=settings.embedding_model,
                input=texts,
            )
            return [d.embedding for d in resp.data]
        except Exception:
            # 降级：返回 None 让 RAG 切换 BM25
            return None
