"""AETHERA LLM Integration (v10.11).

Primary: GLM-5.2 via Z.ai VibeSDK (zai-sdk Python package)
Fallback chain: DeepSeek → ChatGPT → Gemini → Mistral → Local LLM (Ollama)

All API keys are read from environment variables. No user input required.
The fallback is automatic — if GLM-5.2 fails (timeout, rate limit, etc.),
the next provider is tried immediately.
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass

# LLM provider configuration.
LLM_PROVIDERS = [
    {
        "name": "GLM-5.2 (Z.ai)",
        "env_key": "ZAI_API_KEY",
        "priority": 1,
        "sdk": "zai",
    },
    {
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "priority": 2,
        "sdk": "openai_compat",
    },
    {
        "name": "ChatGPT",
        "env_key": "OPENAI_API_KEY",
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "priority": 3,
        "sdk": "openai_compat",
    },
    {
        "name": "Gemini",
        "env_key": "GEMINI_API_KEY",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
        "model": "gemini-pro",
        "priority": 4,
        "sdk": "gemini",
    },
    {
        "name": "Mistral",
        "env_key": "MISTRAL_API_KEY",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-large-latest",
        "priority": 5,
        "sdk": "openai_compat",
    },
    {
        "name": "Local LLM (Ollama)",
        "env_key": "LOCAL_LLM_URL",
        "url": os.environ.get("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions"),
        "model": "llama3",
        "priority": 6,
        "sdk": "openai_compat",
        "no_key_required": True,
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
        is_configured = bool(key) or p.get("no_key_required")
        available.append({
            "name": p["name"],
            "priority": p["priority"],
            "configured": is_configured,
        })
    return available


def query_glm_zai(prompt: str, system_prompt: str = None) -> LLMResponse:
    """Query GLM-5.2 via the Z.ai VibeSDK (synchronous)."""
    try:
        from zai import ZaiClient
        key = os.environ.get("ZAI_API_KEY")
        if not key:
            return LLMResponse("", "GLM-5.2", "glm-5.2", False, "ZAI_API_KEY not set")

        client = ZaiClient(api_key=key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model="glm-5.2",
            messages=messages,
        )
        text = response.choices[0].message.content
        return LLMResponse(text, "GLM-5.2 (Z.ai)", "glm-5.2", True)
    except Exception as e:
        return LLMResponse("", "GLM-5.2", "glm-5.2", False, str(e))


def query_openai_compat(provider: dict, prompt: str, system_prompt: str, key: str) -> LLMResponse:
    """Query an OpenAI-compatible API (DeepSeek, ChatGPT, Mistral, Ollama)."""
    import requests
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": provider["model"], "messages": messages, "max_tokens": 1000}
    headers = {"Content-Type": "application/json"}
    if not provider.get("no_key_required"):
        headers["Authorization"] = f"Bearer {key}"

    try:
        resp = requests.post(provider["url"], json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            return LLMResponse("", provider["name"], provider["model"], False, f"HTTP {resp.status_code}")
        text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResponse(text, provider["name"], provider["model"], True)
    except Exception as e:
        return LLMResponse("", provider["name"], provider["model"], False, str(e))


def query_gemini(provider: dict, prompt: str, key: str) -> LLMResponse:
    """Query Google Gemini API."""
    import requests
    url = f"{provider['url']}?key={key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            return LLMResponse("", provider["name"], provider["model"], False, f"HTTP {resp.status_code}")
        text = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return LLMResponse(text, provider["name"], provider["model"], True)
    except Exception as e:
        return LLMResponse("", provider["name"], provider["model"], False, str(e))


def query_llm_sync(prompt: str, system_prompt: str = None) -> LLMResponse:
    """Query the LLM with fallback chain (synchronous).

    Tries GLM-5.2 (Z.ai) first, then DeepSeek, ChatGPT, Gemini, Mistral, Local.
    Returns the first successful response.
    """
    for provider in sorted(LLM_PROVIDERS, key=lambda p: p["priority"]):
        key = os.environ.get(provider["env_key"]) if not provider.get("no_key_required") else "local"
        if not key:
            continue

        if provider["sdk"] == "zai":
            result = query_glm_zai(prompt, system_prompt)
        elif provider["sdk"] == "gemini":
            result = query_gemini(provider, prompt, key)
        else:  # openai_compat
            result = query_openai_compat(provider, prompt, system_prompt, key)

        if result.success:
            return result
        # Otherwise, try next provider.

    return LLMResponse(
        text="No LLM provider available. Set ZAI_API_KEY for GLM-5.2.",
        provider="none", model="none", success=False,
        error="no providers configured",
    )


async def query_llm(prompt: str, system_prompt: str = None) -> LLMResponse:
    """Async wrapper for query_llm_sync."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query_llm_sync, prompt, system_prompt)


def llm_status() -> dict:
    """Return the status of all LLM providers."""
    providers = []
    for p in LLM_PROVIDERS:
        key = os.environ.get(p["env_key"])
        is_configured = bool(key) or p.get("no_key_required")
        providers.append({
            "name": p["name"],
            "model": p.get("model", "glm-5.2"),
            "priority": p["priority"],
            "configured": is_configured,
        })
    return {
        "primary": "GLM-5.2 (Z.ai VibeSDK)",
        "fallback_chain": ["DeepSeek", "ChatGPT", "Gemini", "Mistral", "Local LLM"],
        "providers": providers,
        "any_available": any(p["configured"] for p in providers),
    }
