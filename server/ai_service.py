# server/ai_service.py
"""
Gemini-powered AI analysis service for the Decision Tracker.

Responsibilities:
  - Build rich, structured prompts from decision + outcome + behavior context
  - Call the Gemini API (gemini-2.5-flash)
  - Parse and return structured JSON insight from the model
  - Graceful degradation: if the API key is missing or the call fails,
    fall back to the rule-based analysis so the app never breaks
"""
import os
import json
import re
import logging
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Try importing dotenv and genai ───────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logger.warning("google-generativeai not installed — AI analysis disabled")


# ── Model configuration ───────────────────────────────────────────────────────
_PREFERRED_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
]
_CLIENT: Optional["genai.GenerativeModel"] = None
_CACHED_KEY: Optional[str] = None
_ACTIVE_MODEL_NAME: str = _PREFERRED_MODELS[0]

# ── Pydantic schema for Structured Outputs ────────────────────────────────────
class UserHabitAnalysisSchema(BaseModel):
    overall_reasoning_score: int
    habitual_patterns: List[str]
    common_blind_spots: List[str]
    strengths: List[str]
    macro_recommendations: List[str]
    summary: str


def _reload_env():
    """Ensure the latest .env file is loaded even after runtime updates."""
    if _DOTENV_AVAILABLE:
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=True)


def _get_client() -> Optional["genai.GenerativeModel"]:
    """Initialize or refresh the Gemini model client."""
    global _CLIENT, _CACHED_KEY, _ACTIVE_MODEL_NAME

    if not _GENAI_AVAILABLE:
        return None

    _reload_env()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key or api_key == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY not set — using rule-based fallback")
        _CLIENT = None
        _CACHED_KEY = None
        return None

    # If key changed or client not created yet, reconfigure
    if _CLIENT is None or _CACHED_KEY != api_key:
        genai.configure(api_key=api_key)
        _CACHED_KEY = api_key
        
        # Select best available model
        for model_name in _PREFERRED_MODELS:
            try:
                _CLIENT = genai.GenerativeModel(model_name)
                _ACTIVE_MODEL_NAME = model_name
                logger.info("Gemini client initialized with model: %s", model_name)
                break
            except Exception as e:
                logger.warning("Could not initialize model %s: %s", model_name, e)

    return _CLIENT


# ── Prompt builder ─────────────────────────────────────────────────────────────
def _build_user_habit_prompt(
    decision_history: list[dict],
    behavior_snapshot: list[dict],
) -> str:
    """Build a rich, structured prompt for macro-level user habit analysis."""

    behavior_block = ""
    if behavior_snapshot:
        lines = "\n".join(
            f"  - {b['behavior']} (seen {b['frequency']}x, confidence {int(b['confidence']*100)}%)"
            for b in behavior_snapshot[:5]
        )
        behavior_block = f"\n### System Detected Behavior Profile\n{lines}"

    history_block = ""
    for i, d in enumerate(decision_history, 1):
        history_block += f"\n#### Logged Decision {i}\n"
        history_block += f"- **Domain:** {d.get('domain', 'unknown')}\n"
        history_block += f"- **Decision:** {d.get('decision_text', '')}\n"
        history_block += f"- **Reasoning:** {d.get('reasoning', '')}\n"
        history_block += f"- **Expected:** {d.get('expected_outcome', '')}\n"
        actual = d.get('actual_outcome', '')
        history_block += f"- **Actual Outcome:** {actual if actual else '(Pending)'}\n"

    prompt = f"""You are an expert behavioral psychologist and decision-making coach. Your job is to analyze a user's decision history and identify macro-level habits, strengths, and blind spots.

Analyze this user's decision-making history objectively and constructively. Be specific and evidence-based. Never use vague platitudes.
{behavior_block}

### User's Decision History
{history_block}

## YOUR TASK

Analyze the history and provide specific, evidence-based insights. Reference patterns seen in their decisions.
"""
    return prompt


# ── JSON extractor ─────────────────────────────────────────────────────────────
def _extract_json(text: str) -> dict:
    """Pull the JSON object out of the model response robustly."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1)

    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]

    return json.loads(text)


# ── Public API ─────────────────────────────────────────────────────────────────
async def analyse_user_habits_with_gemini(
    decision_history: list[dict],
    behavior_snapshot: list[dict],
) -> dict:
    """
    Call Gemini and return a structured macro-level habit analysis dict.
    """
    client = _get_client()
    if client is None:
        return {"error": "Gemini API not configured", "fallback": True}

    prompt = _build_user_habit_prompt(
        decision_history=decision_history,
        behavior_snapshot=behavior_snapshot,
    )

    try:
        response = client.generate_content(
            prompt,
            generation_config={
                "temperature": 0.4,
                "response_mime_type": "application/json",
                "response_schema": UserHabitAnalysisSchema,
            },
        )
        text = response.text.strip()
        result = _extract_json(text)
        result["_model"] = _ACTIVE_MODEL_NAME
        return result

    except json.JSONDecodeError as e:
        logger.error("Gemini returned non-JSON: %s", e)
        return {"error": f"Model returned invalid JSON: {e}", "fallback": True}
    except Exception as e:
        logger.error("Gemini call failed: %s", e)
        return {"error": str(e), "fallback": True}
