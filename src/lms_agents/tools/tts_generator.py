"""
TTS Generator — dual-provider: AWS Polly (default) + ElevenLabs (premium/cloning).

Provider routing:
  - Polly Neural voices: cheap default ($16/1M chars), available to all tiers
  - ElevenLabs presets: premium tier only (~$30/1M chars)
  - ElevenLabs cloned voice: premium tier only (teacher's custom voice)

Caching system (provider-aware) reduces costs via SHA-256 content hashing.
"""
import hashlib
import logging
import os
import tempfile
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Voice catalogs
# ---------------------------------------------------------------------------

POLLY_VOICES = {
    "Joanna": {"id": "Joanna", "provider": "polly", "name": "Joanna", "desc": "Friendly female, default", "engine": "neural", "tier": "standard"},
    "Matthew": {"id": "Matthew", "provider": "polly", "name": "Matthew", "desc": "Male, professional", "engine": "neural", "tier": "standard"},
    "Ivy": {"id": "Ivy", "provider": "polly", "name": "Ivy", "desc": "Child voice, K-2", "engine": "neural", "tier": "standard"},
    "Kendra": {"id": "Kendra", "provider": "polly", "name": "Kendra", "desc": "Warm female alternative", "engine": "neural", "tier": "standard"},
    "Stephen": {"id": "Stephen", "provider": "polly", "name": "Stephen", "desc": "Male alternative", "engine": "neural", "tier": "standard"},
}

ELEVENLABS_VOICES = {
    "el_rachel": {"id": "21m00Tcm4TlvDq8ikWAM", "provider": "elevenlabs", "name": "Rachel", "desc": "Warm female, elementary", "tier": "premium"},
    "el_adam": {"id": "pNInz6obpgDQGcFmaJgB", "provider": "elevenlabs", "name": "Adam", "desc": "Male, professional", "tier": "premium"},
    "el_bella": {"id": "EXAVITQu4vr4xnSDxMaL", "provider": "elevenlabs", "name": "Bella", "desc": "Gentle female, K-2", "tier": "premium"},
    "el_antoni": {"id": "ErXwobaYiN019PkySvjV", "provider": "elevenlabs", "name": "Antoni", "desc": "Friendly male", "tier": "premium"},
}

ELEVENLABS_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.3,
    "use_speaker_boost": True,
}

# Cost per character
COST_PER_CHAR = {
    "polly": 0.000016,       # $16 per 1M chars (Neural)
    "elevenlabs": 0.00003,   # $30 per 1M chars
}

DEFAULT_VOICE = "Joanna"  # Polly default


# ---------------------------------------------------------------------------
# Provider routing
# ---------------------------------------------------------------------------

def get_provider_for_voice(voice_id: str, custom_voice_id: str | None = None, tier: str = "basic") -> str:
    """
    Determine which TTS provider to use based on voice selection and teacher tier.

    Returns "polly" or "elevenlabs".
    """
    # If voice matches teacher's cloned voice → ElevenLabs
    if custom_voice_id and voice_id == custom_voice_id:
        return "elevenlabs"
    # If voice is an ElevenLabs preset (starts with "el_" or is a known EL voice ID)
    if voice_id.startswith("el_") or voice_id in {v["id"] for v in ELEVENLABS_VOICES.values()}:
        return "elevenlabs" if tier in ("premium", "max") else "polly"
    # Default → Polly
    return "polly"


def resolve_voice_id(voice_id: str) -> str:
    """Resolve a voice key to the actual API voice ID."""
    # Check ElevenLabs catalog (el_rachel → actual EL voice ID)
    if voice_id in ELEVENLABS_VOICES:
        return ELEVENLABS_VOICES[voice_id]["id"]
    # Check Polly catalog
    if voice_id in POLLY_VOICES:
        return POLLY_VOICES[voice_id]["id"]
    # Already a raw voice ID
    return voice_id


# ---------------------------------------------------------------------------
# Caching (provider-aware)
# ---------------------------------------------------------------------------

def _get_cache_key(text: str, voice_id: str, provider: str) -> str:
    """SHA-256 hash including provider for separate caching."""
    content = f"{provider}:{text}:{voice_id}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def _check_cache(cache_key: str) -> str | None:
    try:
        s3 = boto3.client(
            "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        key = f"tts-cache/{cache_key}.mp3"
        s3.head_object(Bucket="lulia-generated", Key=key)
        return key
    except ClientError:
        return None


def _store_cache(cache_key: str, audio_bytes: bytes) -> str:
    s3 = boto3.client(
        "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )
    key = f"tts-cache/{cache_key}.mp3"
    s3.put_object(Bucket="lulia-generated", Key=key, Body=audio_bytes, ContentType="audio/mpeg")
    return key


def _download_cached(cache_key: str) -> str:
    """Download cached audio to a temp file."""
    s3 = boto3.client(
        "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    s3.download_fileobj("lulia-generated", f"tts-cache/{cache_key}.mp3", tmp)
    tmp.close()
    return tmp.name


def _track_usage(teacher_id: str, characters: int, provider: str, cache_hit: bool):
    cost = 0 if cache_hit else characters * COST_PER_CHAR.get(provider, 0.00003)
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO tts_usage (usage_id, teacher_id, characters_used, cost_estimate, cache_hit)
               VALUES (%s, %s, %s, %s, %s)""",
            (str(uuid4()), teacher_id, characters, cost, cache_hit),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        log.warning(f"TTS usage tracking failed: {e}")


# ---------------------------------------------------------------------------
# Polly synthesis
# ---------------------------------------------------------------------------

def _polly_synthesize(text: str, voice_id: str) -> bytes | None:
    """Synthesize speech using AWS Polly Neural engine."""
    try:
        polly = boto3.client(
            "polly",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )

        # Use SSML for better educational delivery
        ssml_text = f'<speak><prosody rate="95%">{text}</prosody></speak>'

        response = polly.synthesize_speech(
            Engine="neural",
            OutputFormat="mp3",
            VoiceId=voice_id,
            TextType="ssml",
            Text=ssml_text,
        )

        audio_stream = response.get("AudioStream")
        if audio_stream:
            return audio_stream.read()

    except Exception as e:
        log.error(f"[TTS/Polly] Synthesis failed: {e}")
        # Fallback: try standard engine
        try:
            response = polly.synthesize_speech(
                Engine="standard",
                OutputFormat="mp3",
                VoiceId=voice_id,
                Text=text,
            )
            audio_stream = response.get("AudioStream")
            if audio_stream:
                return audio_stream.read()
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# ElevenLabs synthesis
# ---------------------------------------------------------------------------

def _elevenlabs_synthesize(text: str, voice_id: str) -> bytes | None:
    """Synthesize speech using ElevenLabs API."""
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        log.warning("ELEVENLABS_API_KEY not set")
        return None

    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=api_key)
        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            voice_settings={
                "stability": ELEVENLABS_SETTINGS["stability"],
                "similarity_boost": ELEVENLABS_SETTINGS["similarity_boost"],
                "style": ELEVENLABS_SETTINGS["style"],
                "use_speaker_boost": ELEVENLABS_SETTINGS["use_speaker_boost"],
            },
        )
        return b"".join(audio_generator)

    except Exception as e:
        log.error(f"[TTS/ElevenLabs] Synthesis failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def synthesize_speech(
    text: str,
    voice_id: str | None = None,
    teacher_id: str = "",
    provider: str = "polly",
) -> str | None:
    """
    Synthesize speech from text using the specified provider.

    Args:
        text: narration text
        voice_id: voice identifier (Polly name or ElevenLabs ID)
        teacher_id: for usage tracking
        provider: "polly" or "elevenlabs"

    Returns: path to temp MP3 file, or None on failure.
    """
    if not text or not text.strip():
        return None

    voice = resolve_voice_id(voice_id or DEFAULT_VOICE)
    char_count = len(text)

    # Check cache (provider-aware)
    cache_key = _get_cache_key(text, voice, provider)
    cached = _check_cache(cache_key)
    if cached:
        log.info(f"[TTS/{provider}] Cache hit for {cache_key[:8]}...")
        _track_usage(teacher_id, char_count, provider, cache_hit=True)
        return _download_cached(cache_key)

    # Synthesize
    if provider == "elevenlabs":
        audio_bytes = _elevenlabs_synthesize(text, voice)
    else:
        audio_bytes = _polly_synthesize(text, voice)

    if not audio_bytes:
        # Cross-provider fallback: if Polly fails try ElevenLabs and vice versa
        fallback = "elevenlabs" if provider == "polly" else "polly"
        log.warning(f"[TTS] {provider} failed, trying {fallback}")
        if fallback == "elevenlabs":
            audio_bytes = _elevenlabs_synthesize(text, voice)
        else:
            audio_bytes = _polly_synthesize(text, DEFAULT_VOICE)

    if not audio_bytes:
        _track_usage(teacher_id, char_count, provider, cache_hit=False)
        return None

    # Cache and save
    _store_cache(cache_key, audio_bytes)
    _track_usage(teacher_id, char_count, provider, cache_hit=False)

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.write(audio_bytes)
    tmp.close()

    log.info(f"[TTS/{provider}] Generated {char_count} chars, voice={voice}")
    return tmp.name


# ---------------------------------------------------------------------------
# Voice catalog
# ---------------------------------------------------------------------------

def list_voices(teacher_id: str | None = None, custom_voice_id: str | None = None) -> list[dict]:
    """
    List all available voices grouped by tier.

    Returns voices from both Polly (standard) and ElevenLabs (premium).
    If teacher has a cloned voice, includes it as "Your Voice".
    """
    voices = []

    # Polly voices — standard tier, available to all
    for key, v in POLLY_VOICES.items():
        voices.append({
            "voice_id": key,
            "name": v["name"],
            "description": v["desc"],
            "provider": "polly",
            "tier": "standard",
        })

    # ElevenLabs preset voices — premium tier
    for key, v in ELEVENLABS_VOICES.items():
        voices.append({
            "voice_id": key,
            "name": v["name"],
            "description": v["desc"],
            "provider": "elevenlabs",
            "tier": "premium",
        })

    # Custom cloned voice
    if custom_voice_id:
        voices.insert(0, {
            "voice_id": custom_voice_id,
            "name": "Your Voice",
            "description": "Your cloned teaching voice",
            "provider": "elevenlabs",
            "tier": "premium",
        })

    return voices
