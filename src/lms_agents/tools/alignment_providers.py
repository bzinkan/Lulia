"""
Provider abstraction for chunk-to-standards alignment.

Each provider function takes a single prompt (str) and returns a parsed dict
with keys: alignments, reading_level, grade_bands. The prompt template is
built by the caller (see build_alignment_prompt below) so every provider sees
the same input.

Why this exists
---------------
scripts/align_standards_offline.py needs to run alignment via any of:
  - OpenAI Batch API (default, cheapest, prepare-only writes JSONL)
  - OpenAI synchronous (same API, 2x cost, immediate)
  - Anthropic synchronous (existing path)
  - Groq (Llama 3.3 70B, very fast)
  - Ollama (local, free)

Rather than branching inside the script, callers pick a provider via the
ALIGN_PROVIDER env var and dispatch through get_provider(name).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Callable

log = logging.getLogger(__name__)

# The prompt template is copied from standards_alignment.align_chunk() so the
# offline script never has to import the online path (keeps concerns separated).
PROMPT_TEMPLATE = """You are an expert curriculum standards alignment specialist.

Given this educational content chunk and a list of candidate standards, determine which standards this content teaches or supports.

Content chunk:
{content}

Candidate standards:
{candidates}

Also determine:
1. The reading level of this content (Flesch-Kincaid grade level, numeric)
2. The appropriate grade bands (array from: "K-2", "3-5", "6-8", "9-12", "college")

Return ONLY a JSON object:
{{
  "alignments": [
    {{"code": "4.NF.1", "strength": "strong"}},
    {{"code": "4.NF.2", "strength": "partial"}}
  ],
  "reading_level": 4.2,
  "grade_bands": ["3-5"]
}}

Rules:
- "strong" = this content directly teaches or assesses this standard
- "partial" = this content supports or builds toward this standard
- Only include standards with strong or partial alignment (omit "none")
- Be conservative — only mark "strong" if the content clearly and directly addresses the standard
- reading_level should be a numeric Flesch-Kincaid grade estimate
- grade_bands should reflect the vocabulary and cognitive complexity, not just the topic"""


def build_alignment_prompt(chunk_content: str, candidates: list[dict]) -> str:
    """Construct the judgment prompt from a chunk and its top-20 candidate standards."""
    candidate_lines = []
    for c in candidates:
        code = c.get("code", "?")
        desc = c.get("description", "")
        grade = c.get("grade_level", "?")
        subj = c.get("subject", "?")
        candidate_lines.append(f"- {code}: {desc} (Grade {grade}, {subj})")
    candidates_text = "\n".join(candidate_lines)
    return PROMPT_TEMPLATE.format(
        content=chunk_content[:1500],
        candidates=candidates_text,
    )


def parse_response(text: str) -> dict | None:
    """Extract a JSON object from a model response.

    Tolerates markdown fences and trailing prose (Haiku often appends
    an **Explanation:** paragraph after the JSON). We find the first
    complete JSON object using brace-matching rather than relying on
    the response being pure JSON.
    """
    if not text:
        return None
    text = text.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)

    # Try the full text first (works for GPT-4o-mini with json_object mode)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: find the first { ... } block via brace-matching.
    # Handles Haiku's habit of appending explanations after the JSON.
    start = text.find("{")
    if start == -1:
        log.warning(f"No JSON object found in response; raw={text[:200]}")
        return None

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as e:
                    log.warning(f"Failed to parse extracted JSON: {e}; raw={candidate[:200]}")
                    return None

    log.warning(f"Unmatched braces in response; raw={text[:200]}")
    return None


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _openai_sync(prompt: str) -> dict | None:
    """Synchronous OpenAI GPT-4o-mini call. Env: OPENAI_API_KEY, optional OPENAI_ALIGN_MODEL."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.warning("OPENAI_API_KEY not set")
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = os.environ.get("OPENAI_ALIGN_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content
        return parse_response(text)
    except Exception as e:
        log.warning(f"OpenAI sync alignment call failed: {e}")
        return None


def _anthropic_sync(prompt: str) -> dict | None:
    """Synchronous Anthropic Haiku call (matches existing standards_alignment.py behavior)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set")
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        model = os.environ.get("ANTHROPIC_ALIGN_MODEL", "claude-haiku-4-5-20251001")
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
        return parse_response(text)
    except Exception as e:
        log.warning(f"Anthropic sync alignment call failed: {e}")
        return None


def _groq_sync(prompt: str) -> dict | None:
    """Groq OpenAI-compatible endpoint with Llama 3.3 70B."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        log.warning("GROQ_API_KEY not set")
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        )
        model = os.environ.get("GROQ_ALIGN_MODEL", "llama-3.3-70b-versatile")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content
        return parse_response(text)
    except Exception as e:
        log.warning(f"Groq alignment call failed: {e}")
        return None


def _ollama_sync(prompt: str) -> dict | None:
    """Local Ollama via its OpenAI-compatible /v1 endpoint."""
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key="ollama",  # Ollama ignores the key but the SDK requires one
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )
        model = os.environ.get("OLLAMA_ALIGN_MODEL", "llama3.1:8b")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content
        return parse_response(text)
    except Exception as e:
        log.warning(f"Ollama alignment call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

# openai-batch is a special case — it does NOT expose a synchronous call. The
# offline script writes a JSONL file and uploads it via the Batch API directly
# (see align_standards_offline.py). Calling get_provider("openai-batch") and
# then invoking its return value will raise, which is intentional — it's a
# prepare-only mode.

def _openai_batch_stub(prompt: str) -> dict | None:
    raise RuntimeError(
        "openai-batch is prepare-only. Use align_standards_offline.py "
        "'prepare' subcommand to write JSONL, then 'submit' to upload."
    )


_PROVIDERS: dict[str, Callable[[str], dict | None]] = {
    "openai-batch": _openai_batch_stub,
    "openai-sync": _openai_sync,
    "anthropic-sync": _anthropic_sync,
    "groq": _groq_sync,
    "ollama": _ollama_sync,
}


def get_provider(name: str | None = None) -> Callable[[str], dict | None]:
    """Resolve a provider by name (or env ALIGN_PROVIDER, default openai-batch)."""
    if name is None:
        name = os.environ.get("ALIGN_PROVIDER", "openai-batch")
    if name not in _PROVIDERS:
        raise ValueError(
            f"Unknown ALIGN_PROVIDER={name!r}. Options: {sorted(_PROVIDERS.keys())}"
        )
    return _PROVIDERS[name]


def list_providers() -> list[str]:
    return sorted(_PROVIDERS.keys())
