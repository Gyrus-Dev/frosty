import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Provider selection ────────────────────────────────────────────────────────
# Set MODEL_PROVIDER to "google" (default), "anthropic", "openai", or "ollama"
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "google").lower()
USE_SKILLS = os.environ.get("USE_SKILLS", "true").lower() != "false"
IS_GOOGLE_MODEL = False
IS_NATIVE_GOOGLE_MODEL = False

# ── Model resolution ──────────────────────────────────────────────────────────
if MODEL_PROVIDER == "anthropic":
    from google.adk.models.lite_llm import LiteLlm

    _primary = os.environ.get("MODEL_PRIMARY", "anthropic/claude-3-5-haiku-20241022")
    _thinking = os.environ.get("MODEL_THINKING", "anthropic/claude-3-5-sonnet-20241022")

    PRIMARY_MODEL = LiteLlm(model=_primary)
    THINKING_MODEL = LiteLlm(model=_thinking)

elif MODEL_PROVIDER == "openai":
    from google.adk.models.lite_llm import LiteLlm

    _primary = os.environ.get("MODEL_PRIMARY", "openai/gpt-4o-mini")
    _thinking = os.environ.get("MODEL_THINKING", "openai/gpt-4o")

    PRIMARY_MODEL = LiteLlm(model=_primary)
    THINKING_MODEL = LiteLlm(model=_thinking)

elif MODEL_PROVIDER == "ollama":
    from google.adk.models.lite_llm import LiteLlm

    _primary = os.environ.get("MODEL_PRIMARY", "ollama/gemma4:e2b")

    PRIMARY_MODEL = LiteLlm(model=_primary)
    THINKING_MODEL = None

else:  # google (default)
    _primary = os.environ.get("PRIMARY_MODEL", "gemini-2.5-flash")
    _thinking = os.environ.get("THINKING_MODEL", "gemini-2.5-pro-preview-03-25")

    # Allow LiteLLM-backed Gemini models (e.g., Gemma 4 via Gemini API).
    # If the model uses provider-style naming or starts with "gemma-",
    # route through LiteLLM instead of the native Gemini registry.
    if "/" in _primary or _primary.startswith("gemma-"):
        from google.adk.models.lite_llm import LiteLlm

        if "/" not in _primary:
            _primary = f"gemini/{_primary}"
        if _thinking and "/" not in _thinking:
            _thinking = f"gemini/{_thinking}"

        PRIMARY_MODEL = LiteLlm(model=_primary)
        THINKING_MODEL = LiteLlm(model=_thinking) if _thinking else None
        IS_NATIVE_GOOGLE_MODEL = False
    else:
        PRIMARY_MODEL = _primary
        THINKING_MODEL = _thinking
        IS_NATIVE_GOOGLE_MODEL = True

    IS_GOOGLE_MODEL = True

_primary_label = getattr(PRIMARY_MODEL, "model", PRIMARY_MODEL)
_thinking_label = getattr(THINKING_MODEL, "model", THINKING_MODEL)
logger.info("Model provider: %s | primary: %s | thinking: %s", MODEL_PROVIDER, _primary_label, _thinking_label)
print(f"[config] provider={MODEL_PROVIDER}  primary={_primary_label}  thinking={_thinking_label}")


# ── Planner factory ───────────────────────────────────────────────────────────
def get_planner(thinking_budget: int = 512) -> Optional[object]:
    """Returns a BuiltInPlanner for Google models, None for all other providers.

    BuiltInPlanner / ThinkingConfig are Gemini-specific features and are not
    supported by Anthropic or OpenAI models via LiteLLM.
    """
    if not IS_NATIVE_GOOGLE_MODEL:
        return None
    from google.adk.planners import BuiltInPlanner
    from google.genai import types

    return BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=thinking_budget,
        )
    )
