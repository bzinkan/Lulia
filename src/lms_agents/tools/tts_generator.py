"""
ElevenLabs TTS Generator — synthesizes speech from text.

Supports preset voices and teacher-cloned custom voices.
Caching system reduces API costs via SHA-256 content hashing.
"""
import hashlib
import io
import logging
import os
import tempfile
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from src.lms_agents.tools.db import get_connection

log = logging.getLogger(__name__)

# Preset voices
PRESET_VOICES = {
    "rachel": {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel", "desc": "Warm female, elementary"},
    "adam": {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "desc": "Male, professional"},
    "bella": {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella", "desc": "Gentle female, K-2"},
    "antoni": {"id": "ErXwobaYiN019PkySvjV", "name": "Antoni", "desc": "Friendly male"},
}

VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.3,
    "use_speaker_boost": True,
}


def _get_cache_key(text: str, voice_id: str) -> str:
    """SHA-256 hash for caching."""
    content = f"{text}:{voice_id}:{VOICE_SETTINGS}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def _check_cache(cache_key: str) -> str | None:
    """Check MinIO for cached audio. Returns URL if found."""
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
    """Store audio in MinIO cache."""
    s3 = boto3.client(
        "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )
    key = f"tts-cache/{cache_key}.mp3"
    s3.put_object(Bucket="lulia-generated", Key=key, Body=audio_bytes, ContentType="audio/mpeg")
    return key


def _track_usage(teacher_id: str, characters: int, cache_hit: bool):
    """Track TTS usage for cost monitoring."""
    cost = 0 if cache_hit else characters * 0.00003  # ~$0.03 per 1000 chars
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


def synthesize_speech(
    text: str,
    voice_id: str | None = None,
    teacher_id: str = "",
    model_id: str = "eleven_multilingual_v2",
) -> str | None:
    """
    Synthesize speech from text using ElevenLabs API.
    Returns path to local temp file with the audio, or None on failure.
    Checks cache first to avoid redundant API calls.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        log.warning("ELEVENLABS_API_KEY not set — TTS skipped")
        return None

    voice = voice_id or os.environ.get("ELEVENLABS_DEFAULT_VOICE", PRESET_VOICES["rachel"]["id"])
    char_count = len(text)

    # Check cache
    cache_key = _get_cache_key(text, voice)
    cached = _check_cache(cache_key)
    if cached:
        log.info(f"[TTS] Cache hit for {cache_key[:8]}...")
        _track_usage(teacher_id, char_count, cache_hit=True)
        # Download from cache to temp file
        s3 = boto3.client(
            "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        s3.download_fileobj("lulia-generated", cached, tmp)
        tmp.close()
        return tmp.name

    # Generate via ElevenLabs
    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=api_key)
        audio_generator = client.text_to_speech.convert(
            voice_id=voice,
            text=text,
            model_id=model_id,
            voice_settings={
                "stability": VOICE_SETTINGS["stability"],
                "similarity_boost": VOICE_SETTINGS["similarity_boost"],
                "style": VOICE_SETTINGS["style"],
                "use_speaker_boost": VOICE_SETTINGS["use_speaker_boost"],
            },
        )

        # Collect audio bytes from generator
        audio_bytes = b"".join(audio_generator)

        # Cache it
        _store_cache(cache_key, audio_bytes)
        _track_usage(teacher_id, char_count, cache_hit=False)

        # Write to temp file
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        log.info(f"[TTS] Generated {char_count} chars, voice={voice[:8]}...")
        return tmp.name

    except Exception as e:
        log.error(f"[TTS] ElevenLabs synthesis failed: {e}")
        _track_usage(teacher_id, char_count, cache_hit=False)
        return None


def list_voices() -> list[dict]:
    """List available preset voices."""
    voices = [{"voice_id": v["id"], "name": v["name"], "description": v["desc"]} for v in PRESET_VOICES.values()]
    return voices
