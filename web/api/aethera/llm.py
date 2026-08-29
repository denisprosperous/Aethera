"""AETHERA LLM Integration (v25.0).

Primary: NVIDIA NIM free endpoints (https://integrate.api.nvidia.com/v1)
Default model chain (OpenAI-compatible, no user API key required):
  1. deepseek-ai/deepseek-v4-flash-0731      (deep reasoning)
  2. nvidia/nemotron-3.5-lightning-30b-a3b   (fast, reliable)
  3. moonshotai/kimi-k3                      (long-context)

Seamless by default: the platform ships with a built-in NVIDIA API key so
end users never need to enter one. Users may still override the key:

  * environment variable ``NVIDIA_API_KEY`` (deployment-level override)
  * ``POST /api/llm/key`` (rotates the key on the running instance)
  * per-request override: ``api_key`` field of ``/api/llm/query`` body or
    the ``x-nvidia-key`` header (the dashboard palette stores the user's
    own key in localStorage and sends it per request).

A backup NVIDIA key is used automatically when the active key is rejected
(401/403/429). Fallback chain after NVIDIA: DeepSeek → ChatGPT → Gemini →
Mistral → Local LLM (Ollama). All other keys are read from environment
variables; no user input required.
"""

import os
import json
import asyncio
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# NVIDIA NIM configuration (default provider — free endpoint)
# ---------------------------------------------------------------------------

NVIDIA_BASE_URL = os.environ.get(
    "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
)

# Built-in keys: the platform works out of the box, zero configuration.
DEFAULT_NVIDIA_API_KEY = os.environ.get(
    "AETHERA_NVIDIA_DEFAULT_KEY",
    "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",
)
BACKUP_NVIDIA_API_KEY = os.environ.get(
    "AETHERA_NVIDIA_BACKUP_KEY",
    "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",
)

# Default model chain order. NVIDIA_MODEL pins a single model.
NVIDIA_MODEL_CHAIN = [
    "deepseek-ai/deepseek-v4-flash-0731",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "moonshotai/kimi-k3",
]

# Per-request timeout (seconds). Deep reasoning models can be slow; the
# chain falls through to the next model on timeout. The first model in
# the chain (deepseek-v4-flash) gets a shorter budget so that a stalled
# endpoint does not block the fast fallback models.
NVIDIA_TIMEOUT_S = int(os.environ.get("NVIDIA_TIMEOUT_S", "60"))
MODEL_TIMEOUT_OVERRIDE = {
    "deepseek-ai/deepseek-v4-flash-0731": int(
        os.environ.get("DEEPSEEK_TIMEOUT_S", "45"))
}


def _timeout_for(model: str) -> int:
    return MODEL_TIMEOUT_OVERRIDE.get(model, NVIDIA_TIMEOUT_S)

# Runtime key override (set via /api/llm/key or environment).
_key_lock = threading.Lock()
_runtime_key: Optional[str] = None
_KStatePath = os.environ.get("AETHERA_LLM_KEY_PATH", "/tmp/aethera_llm_key.json")


def _load_persisted_key() -> Optional[str]:
    try:
        with open(_KStatePath, "r") as fh:
            data = json.load(fh)
            return data.get("nvidia_api_key") or None
    except Exception:
        return None


def _persist_key(key: Optional[str]) -> None:
    try:
        with open(_KStatePath, "w") as fh:
            json.dump({"nvidia_api_key": key}, fh)
    except Exception:
        pass


# Load any key persisted by a previous call in this instance.
_runtime_key = _load_persisted_key()


def get_nvidia_key() -> str:
    """Resolve the active NVIDIA API key (runtime > env > built-in default)."""
    with _key_lock:
        if _runtime_key:
            return _runtime_key
    env = os.environ.get("NVIDIA_API_KEY")
    return env or DEFAULT_NVIDIA_API_KEY


def get_backup_key() -> Optional[str]:
    env = os.environ.get("NVIDIA_API_KEY_BACKUP")
    if env:
        return env
    if BACKUP_NVIDIA_API_KEY and BACKUP_NVIDIA_API_KEY != get_nvidia_key():
        return BACKUP_NVIDIA_API_KEY
    return None


def set_nvidia_key(key: Optional[str]) -> None:
    """Set (or reset, when None) the runtime NVIDIA API key."""
    global _runtime_key
    with _key_lock:
        _runtime_key = key
    _persist_key(key)


def mask_key(key: str) -> str:
    if not key:
        return "(none)"
    if len(key) <= 12:
        return key[:4] + "****"
    return f"{key[:9]}****{key[-4:]}"


def get_nvidia_models() -> List[str]:
    pinned = os.environ.get("NVIDIA_MODEL")
    if pinned:
        return [pinned]
    return list(NVIDIA_MODEL_CHAIN)


# ---------------------------------------------------------------------------
# Fallback providers (unchanged from v10.11, used only when NVIDIA fails)
# ---------------------------------------------------------------------------

LLM_PROVIDERS = [
    {
        "name": "NVIDIA NIM (free)",
        "env_key": "NVIDIA_API_KEY",
        "priority": 1,
        "sdk": "nvidia",
        "no_key_required": True,  # built-in key ships with the platform
    },
    {
        "name": "GLM-5.2 (Z.ai)",
        "env_key": "ZAI_API_KEY",
        "priority": 2,
        "sdk": "zai",
    },
    {
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "priority": 3,
        "sdk": "openai_compat",
    },
    {
        "name": "ChatGPT",
        "env_key": "OPENAI_API_KEY",
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "priority": 4,
        "sdk": "openai_compat",
    },
    {
        "name": "Gemini",
        "env_key": "GEMINI_API_KEY",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
        "model": "gemini-pro",
        "priority": 5,
        "sdk": "gemini",
    },
    {
        "name": "Mistral",
        "env_key": "MISTRAL_API_KEY",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-large-latest",
        "priority": 6,
        "sdk": "openai_compat",
    },
    {
        "name": "Local LLM (Ollama)",
        "env_key": "LOCAL_LLM_URL",
        "url": os.environ.get("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions"),
        "model": "llama3",
        "priority": 7,
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
    reasoning: Optional[str] = None


def get_available_providers() -> list:
    """Return list of providers with configuration status."""
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


# ---------------------------------------------------------------------------
# Query implementations
# ---------------------------------------------------------------------------

def query_nvidia(prompt: str, system_prompt: str = None,
                 api_key: str = None, models: List[str] = None) -> LLMResponse:
    """Query NVIDIA NIM endpoints, walking the model chain.

    Tries the active key first; if the key itself is rejected (401/403/429)
    the backup key is substituted for the remaining models.
    """
    import requests

    chain = models or get_nvidia_models()
    active_key = api_key or get_nvidia_key()
    backup = None if api_key else get_backup_key()

    last_error = "no models attempted"
    for model in chain:
        for key in dict.fromkeys([active_key, backup]):  # de-dup, keep order
            if not key:
                continue
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.6,
                "top_p": 0.95,
                "max_tokens": 4096,
                "stream": False,
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {key}",
            }
            try:
                resp = requests.post(
                    f"{NVIDIA_BASE_URL}/chat/completions",
                    json=payload, headers=headers, timeout=_timeout_for(model),
                )
                if resp.status_code in (401, 403, 429):
                    last_error = f"HTTP {resp.status_code} (key rejected)"
                    continue  # try backup key / next model
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}"
                    break  # key OK, model issue → next model
                data = resp.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                text = msg.get("content") or ""
                reasoning = (
                    msg.get("reasoning_content") or msg.get("reasoning") or None
                )
                if not text and reasoning:
                    # reasoning-only response: surface the reasoning trace
                    text = reasoning
                return LLMResponse(text, "NVIDIA NIM (free)", model, True,
                                   reasoning=reasoning)
            except requests.exceptions.Timeout:
                last_error = f"timeout after {_timeout_for(model)}s"
                break  # next model
            except Exception as e:
                last_error = str(e)
                break  # next model

    return LLMResponse("", "NVIDIA NIM (free)", chain[0], False, last_error)


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
    payload = {"model": provider["model"], "messages": messages, "max_tokens": 4096}
    headers = {"Content-Type": "application/json"}
    if not provider.get("no_key_required"):
        headers["Authorization"] = f"Bearer {key}"

    try:
        resp = requests.post(provider["url"], json=payload, headers=headers, timeout=60)
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
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code != 200:
            return LLMResponse("", provider["name"], provider["model"], False, f"HTTP {resp.status_code}")
        text = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return LLMResponse(text, provider["name"], provider["model"], True)
    except Exception as e:
        return LLMResponse("", provider["name"], provider["model"], False, str(e))


def query_llm_sync(prompt: str, system_prompt: str = None,
                   api_key: str = None, model: str = None) -> LLMResponse:
    """Query the LLM with fallback chain (synchronous).

    Order: NVIDIA NIM (deepseek-v4-flash → nemotron-3.5-lightning →
    kimi-k3, with automatic backup key) → GLM-5.2 → DeepSeek → ChatGPT →
    Gemini → Mistral → Local. Returns the first successful response.
    """
    models = [model] if model else None

    # 1) NVIDIA (default — works with the built-in key)
    result = query_nvidia(prompt, system_prompt, api_key=api_key, models=models)
    if result.success:
        return result

    # 2) Configured fallbacks
    for provider in sorted(LLM_PROVIDERS, key=lambda p: p["priority"]):
        if provider["sdk"] == "nvidia":
            continue  # already tried
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

    return LLMResponse(
        text="No LLM provider reachable. NVIDIA NIM is default and ships "
             "with a built-in key — if you see this, the endpoint itself is "
             "unreachable from this host.",
        provider="none", model="none", success=False,
        error=result.error if result else "no providers configured",
    )


async def query_llm(prompt: str, system_prompt: str = None,
                    api_key: str = None, model: str = None) -> LLMResponse:
    """Async wrapper for query_llm_sync."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: query_llm_sync(prompt, system_prompt, api_key, model)
    )


def llm_status() -> dict:
    """Return the status of all LLM providers."""
    providers = []
    for p in LLM_PROVIDERS:
        key = os.environ.get(p["env_key"])
        is_configured = bool(key) or p.get("no_key_required")
        providers.append({
            "name": p["name"],
            "model": p.get("model", get_nvidia_models()[0]),
            "priority": p["priority"],
            "configured": is_configured,
        })
    return {
        "primary": "NVIDIA NIM (free) — no API key required",
        "default_models": get_nvidia_models(),
        "active_key_masked": mask_key(get_nvidia_key()),
        "custom_key_active": bool(_runtime_key or os.environ.get("NVIDIA_API_KEY")),
        "backup_key_available": bool(get_backup_key()),
        "fallback_chain": ["GLM-5.2 (Z.ai)", "DeepSeek", "ChatGPT", "Gemini", "Mistral", "Local LLM"],
        "providers": providers,
        "any_available": True,  # NVIDIA always available via built-in key
    }
