"""
Video Assembler — combines slide images + audio into final MP4 using ffmpeg.

Each scene: slide PNG + audio MP3 → video clip.
All clips concatenated into final video with intro/outro cards.
"""
import logging
import os
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def assemble_video(
    scenes: list[dict],
    output_path: str | None = None,
    intro_text: str = "Lulia AI",
    outro_text: str = "Keep Learning!",
) -> str | None:
    """
    Assemble a video from scene data.

    Each scene dict must have:
      - image_path: path to slide PNG
      - audio_path: path to audio MP3 (or None for silent)
      - duration: duration in seconds

    Returns path to final MP4, or None on failure.
    """
    if not scenes:
        return None

    if not output_path:
        output_path = tempfile.mktemp(suffix=".mp4")

    # Create individual scene clips
    clip_paths = []
    concat_list = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)

    for i, scene in enumerate(scenes):
        image_path = scene.get("image_path")
        audio_path = scene.get("audio_path")
        duration = scene.get("duration", 5)

        if not image_path or not os.path.exists(image_path):
            continue

        clip_path = tempfile.mktemp(suffix=f"_scene{i}.mp4")

        if audio_path and os.path.exists(audio_path):
            # Get audio duration
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                    capture_output=True, text=True,
                )
                audio_duration = float(probe.stdout.strip())
            except Exception:
                audio_duration = duration

            # Image + audio → video clip with subtle zoom (Ken Burns)
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", image_path,
                "-i", audio_path,
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-b:a", "128k",
                "-vf", f"scale=1920:1080,zoompan=z='min(zoom+0.0005,1.1)':d={int(audio_duration*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30",
                "-shortest",
                "-pix_fmt", "yuv420p",
                clip_path,
            ]
        else:
            # Image only → silent clip
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", image_path,
                "-c:v", "libx264", "-tune", "stillimage",
                "-t", str(duration),
                "-vf", "scale=1920:1080,fps=30",
                "-pix_fmt", "yuv420p",
                clip_path,
            ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=120)
            if os.path.exists(clip_path):
                clip_paths.append(clip_path)
                concat_list.write(f"file '{clip_path}'\n")
        except Exception as e:
            log.warning(f"Failed to create scene {i}: {e}")

    concat_list.close()

    if not clip_paths:
        return None

    # Concatenate all clips
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list.name,
            "-c", "copy",
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=300)
    except Exception as e:
        log.error(f"Video concatenation failed: {e}")
        return None

    # Cleanup temp clips
    for p in clip_paths:
        try:
            os.unlink(p)
        except Exception:
            pass
    try:
        os.unlink(concat_list.name)
    except Exception:
        pass

    if os.path.exists(output_path):
        log.info(f"[Video] Assembled {len(clip_paths)} scenes → {output_path}")
        return output_path

    return None


def generate_thumbnail(video_path: str) -> str | None:
    """Extract first frame as thumbnail."""
    thumb_path = tempfile.mktemp(suffix=".jpg")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vframes", "1", "-q:v", "2", thumb_path],
            capture_output=True, timeout=30,
        )
        if os.path.exists(thumb_path):
            return thumb_path
    except Exception as e:
        log.warning(f"Thumbnail generation failed: {e}")
    return None
