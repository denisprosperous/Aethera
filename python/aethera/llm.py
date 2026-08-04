"""AETHERA LLM Integration (v10.8).

Primary: GLM-5.2 (via z-ai-web-dev-sdk)
Fallback chain: DeepSeek → ChatGPT → Gemini → Mistral → Local LLM

The LLM is used for:
- Natural language queries about the manifold ("What's the area of Russia?")
- Explaining distortion metrics in plain language
- Generating rationale summaries for Ghost Resolver outputs
- Command bar suggestions in the frontend

All LLM calls are async with timeout fallback.
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass

# LLM provider configuration.
# In production, set these as environment variables.
LLM_PROVIDERS = [
    {
        "name": "GLM-5.2",
        "env_key": "GLM_API_KEY",
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-5.2",
        "priority": 1,
    },
    {
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "priority": 2,
    },
    {
        "name": "ChatGPT",
        "env_key": "OPENAI_API_KEY",
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "priority": 3,
    },
    {
        "name": "Gemini",
        "env_key": "GEMINI_API_KEY",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
        "model": "gemini-pro",
        "priority": 4,
    },
    {
        "name": "Mistral",
        "env_key": "MISTRAL_API_KEY",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-large-latest",
        "priority": 5,
    },
    {
        "name": "Local LLM",
        "env_key": "LOCAL_LLM_URL",
        "url": os.environ.get("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions"),
        "model": "llama3",
        "priority": 6,
    },
]


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    success: bool
    error: Optional[str] = None


def get_available_providers() -> list:
    """Return list of providers that have API keys configured."""
    available = []
    for p in LLM_PROVIDERS:
        key = os.environ.get(p["env_key"])
        if key:
            available.append({
                "name": p["name"],
                "model": p["model"],
                "priority": p["priority"],
                "configured": True,
            })
    return available


async def query_llm(prompt: str, system_prompt: str = None) -> LLMResponse:
    """Query the LLM with fallback chain.

    Tries GLM-5.2 first, then DeepSeek, ChatGPT, Gemini, Mistral, Local.
    Returns the first successful response.
    """
    import aiohttp

    for provider in sorted(LLM_PROVIDERS, key=lambda p: p["priority"]):
        key = os.environ.get(provider["env_key"])
        if not key:
            continue

        try:
            response = await _query_provider(provider, prompt, system_prompt, key)
            if response.success:
                return response
        except Exception as e:
            continue

    return LLMResponse(
        text="No LLM provider available. Set GLM_API_KEY, DEEPSEEK_API_KEY, etc.",
        provider="none",
        model="none",
        success=False,
        error="no providers configured",
    )


async def _query_provider(provider: dict, prompt: str, system_prompt: str, key: str) -> LLMResponse:
    """Query a single LLM provider."""
    import aiohttp

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }

    if provider["name"] == "Gemini":
        # Gemini has a different API format.
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        url = f"{provider['url']}?key={key}"
        headers = {"Content-Type": "application/json"}
    else:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": provider["model"],
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7,
        }
        url = provider["url"]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return LLMResponse(
                        text="", provider=provider["name"], model=provider["model"],
                        success=False, error=f"HTTP {resp.status}",
                    )
                data = await resp.json()
                if provider["name"] == "Gemini":
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                else:
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return LLMResponse(
                    text=text, provider=provider["name"], model=provider["model"], success=True,
                )
    except Exception as e:
        return LLMResponse(
            text="", provider=provider["name"], model=provider["model"],
            success=False, error=str(e),
        )


def llm_status() -> dict:
    """Return the status of all LLM providers."""
    providers = []
    for p in LLM_PROVIDERS:
        key = os.environ.get(p["env_key"])
        providers.append({
            "name": p["name"],
            "model": p["model"],
            "priority": p["priority"],
            "configured": bool(key),
        })
    return {
        "primary": "GLM-5.2",
        "fallback_chain": ["DeepSeek", "ChatGPT", "Gemini", "Mistral", "Local LLM"],
        "providers": providers,
        "any_available": any(p["configured"] for p in providers),
    }
