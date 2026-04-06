"""
Lumina Wiki - LLM Client
统一封装多种 LLM Provider 的 API 调用。
支持：GitHub Copilot、OpenAI、Azure OpenAI、Ollama（本地）。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

try:
    import httpx
except ImportError:
    print("❌ 缺少依赖: pip install httpx")
    sys.exit(1)

from .config import LuminaConfig, load_config


class LLMClient:
    """统一 LLM 客户端接口。"""

    def __init__(self, config: Optional[LuminaConfig] = None):
        self.config = config or load_config()
        llm_cfg = self.config.llm
        self.provider = llm_cfg.provider
        self.model = llm_cfg.model
        self.temperature = llm_cfg.temperature
        self.max_tokens = llm_cfg.max_tokens

        # 根据 provider 初始化客户端
        self._setup_client()

    def _setup_client(self) -> None:
        """根据配置初始化对应的 HTTP 客户端和认证信息。"""
        if self.provider == "openai":
            api_key = os.environ.get(
                self.config.llm.openai_api_key_env or "OPENAI_API_KEY", ""
            )
            base_url = (
                self.config.llm.openai_base_url or "https://api.openai.com/v1"
            )
            self.api_key = api_key
            self.base_url = base_url.rstrip("/")
            self._endpoint = f"{self.base_url}/chat/completions"

        elif self.provider == "azure":
            api_key = os.environ.get(
                self.config.llm.azure_api_key_env or "AZURE_OPENAI_API_KEY", ""
            )
            endpoint = os.environ.get(
                self.config.llm.azure_endpoint_env or "AZURE_OPENAI_ENDPOINT", ""
            ).rstrip("/")
            deployment = self.config.llm.azure_deployment or "gpt-4o"
            self.api_key = api_key
            self.base_url = endpoint
            self._endpoint = (
                f"{endpoint}/openai/deployments/{deployment}/chat/completions?"
                f"api-version=2024-02-15-preview"
            )

        elif self.provider == "ollama":
            base_url = self.config.llm.ollama_base_url or "http://localhost:11434"
            model = self.config.llm.ollama_model or "qwen2.5:14b"
            self.base_url = base_url.rstrip("/")
            self.model = model
            self._endpoint = f"{base_url}/api/chat"
            self.api_key = ""

        elif self.provider == "github-copilot":
            # GitHub Copilot 通过 OpenAI 兼容接口调用
            # 需要 GITHUB_TOKEN 作为 bearer token
            token = os.environ.get("GITHUB_TOKEN", "")
            self.api_key = token
            self.base_url = "https://api.githubcopilot.com"
            self._endpoint = f"{self.base_url}/chat/completions"

        else:
            raise ValueError(f"不支持的 LLM provider: {self.provider}")

    async def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """
        发送聊天请求并返回文本回复。

        Args:
            messages: 聊天消息列表 [{"role": "...", "content": "..."}]
            system_prompt: 可选的系统提示词
            temperature: 生成温度
            max_tokens: 最大生成 token 数
            json_mode: 是否强制 JSON 输出

        Returns:
            模型生成的文本内容
        """
        if system_prompt and messages and messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": system_prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = await self._build_headers()
        result = await self._post(payload, headers)
        return result

    async def extract_json(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
    ) -> dict:
        """发送请求并以 JSON 格式返回结构化数据。"""
        text = await self.chat(messages, system_prompt=system_prompt, json_mode=True)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取 ```json ... ``` 块
            import re

            match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"LLM 返回的不是有效 JSON: {text[:200]}")

    async def summarize(self, text: str, context: str = "") -> str:
        """生成文本摘要。"""
        prompt = f"""请对以下内容生成一个简洁的摘要（中文，{self.config.compiler.summary_max_tokens} 字以内）。
保留核心观点、关键数据和重要结论。

原文：
{text}

{"上下文：" + context if context else ""}
"""
        return await self.chat([{"role": "user", "content": prompt}])

    async def extract_entities(self, text: str) -> list[dict]:
        """从文本中提取实体/概念。"""
        prompt = f"""从以下学术/技术文本中提取核心概念和实体。

返回 JSON 格式：
{{"entities": [{{"name": "概念名", "type": "类型(algorithm/model/paper/method/concept/other)", "confidence": 0.95}}]}}

只提取重要的、有独立页面价值的概念。过滤掉过于通用的词。

文本：
{text[:4000]}
"""
        result = await self.extract_json([{"role": "user", "content": prompt}])
        entities = result.get("entities", [])
        # 过滤低置信度
        threshold = self.config.compiler.entity_confidence
        return [e for e in entities if e.get("confidence", 0) >= threshold]

    async def describe_image(self, image_url_or_path: str) -> str:
        """使用多模态模型描述图片内容。"""
        from pathlib import Path

        p = Path(image_url_or_path)
        if p.exists():
            # 本地图片 - 需要读取为 base64
            import base64

            suffix = p.suffix.lstrip(".")
            media_type = f"image/{suffix}" if suffix in ("png", "jpg", "jpeg", "gif", "webp") else "image/png"
            b64 = base64.b64encode(p.read_bytes()).decode()
            content = {
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{b64}"},
            }
        else:
            content = {
                "type": "image_url",
                "image_url": {"url": image_url_or_path},
            }

        messages = [
            {
                "role": "user",
                "content": [
                    content,
                    {
                        "type": "text",
                        "text": "请详细描述这张图片的内容。包括图中文字、图表、关键信息等。输出中文。",
                    },
                ],
            }
        ]

        return await self.chat(messages)

    async def _build_headers(self) -> dict:
        """构建 HTTP 请求头。"""
        if self.provider == "github-copilot":
            return {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Copilot-Integration-Id": "lumina-wiki-v1",
            }
        elif self.provider == "ollama":
            return {"Content-Type": "application/json"}
        else:
            return {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

    async def _post(self, payload: dict, headers: dict) -> str:
        """执行 POST 请求。"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(self._endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                # Ollama 格式不同
                if self.provider == "ollama":
                    return data["message"]["content"]

                return data["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            print(f"❌ LLM API 错误 ({e.response.status_code}): {error_body}")
            raise RuntimeError(f"LLM API 调用失败: {e.response.status_code}") from e
        except httpx.TimeoutException:
            raise RuntimeError("LLM API 请求超时") from None
        except Exception as e:
            print(f"❌ LLM 调用异常: {e}")
            raise


# ─── 同步包装器（供简单场景使用）─────────────────────────────────────
import asyncio


def sync_chat(client: LLMClient, *args, **kwargs) -> str:
    return asyncio.run(client.chat(*args, **kwargs))


def sync_summarize(client: LLMClient, text: str, context: str = "") -> str:
    return asyncio.run(client.summarize(text, context))


def sync_extract_entities(client: LLMClient, text: str) -> list[dict]:
    return asyncio.run(client.extract_entities(text))
