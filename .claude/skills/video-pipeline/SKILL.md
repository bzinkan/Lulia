---
name: video-pipeline
description: "Use this skill whenever building the video generation pipeline. Triggers include: implementing TTS, generating Gemini Imagen illustrations per scene, configuring ffmpeg video assembly, writing Video Script Agent output format, or handling video render jobs. Also trigger when discussing Veo API future-proofing."
---

# Video Generation Pipeline

## Pipeline (Imagen-Powered)

```
Video Script Agent (Claude Opus, RAG KB)
    ↓ video_script JSON (scenes[])
Gemini Imagen (AI illustration per scene)
    ↓ PNG images per scene (16:9)
TTS Engine (Google Cloud TTS or ElevenLabs)
    ↓ MP3 audio per scene
ffmpeg Assembly
    ↓ combined MP4 with scene transitions
Delivery (S3 + YouTube unlisted + Classroom)
```

## Video Script Format

```json
{
  "metadata": {"title": "Intro to Decimals", "scene_count": 7, "standards": ["OH.4.NF.5"]},
  "scenes": [
    {
      "scene_number": 1,
      "narration_text": "Hey there! Today we're going to learn how to turn fractions into decimals.",
      "visual_description": "A pizza divided into 4 equal slices, with one slice highlighted. Fraction 1/4 shown transforming into 0.25.",
      "on_screen_text": "Fractions → Decimals",
      "duration_seconds": 25
    }
  ]
}
```

## Gemini Imagen (Replaces Puppeteer HTML Slides)

```python
import google.generativeai as genai

def generate_scene_image(scene):
    model = genai.ImageGenerationModel("imagen-3.0-generate-002")
    prompt = f"{scene['visual_description']}, educational illustration, clean background, 16:9"
    response = model.generate_images(prompt=prompt, number_of_images=1, aspect_ratio="16:9")
    image_path = f"/tmp/video/{scene['scene_number']:03d}.png"
    response.images[0].save(image_path)
    return image_path
```

Each scene gets a unique, professional AI-generated illustration instead of a static HTML template. A fractions scene gets a custom pizza diagram. A chemistry scene gets molecule illustrations.

## TTS Options

- **Google Cloud TTS** (free tier: 4M chars/month): speaking_rate=0.95 for students
- **ElevenLabs** (~$5/month): higher quality, more natural voices
- **pyttsx3** (offline fallback): lower quality but always works

## ffmpeg Assembly

```python
def assemble_video(scenes_dir, output_path):
    # Build complex ffmpeg filter combining images + audio per scene
    # -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k
    # -movflags +faststart for web streaming
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", filter_str,
                    "-map", "[outv]", "-map", "[outa]", output_path])
```

## Veo Future-Proofing

When Google releases the Veo API:
- Script Agent's scene descriptions already work as Veo prompts
- Swap one module: `generate_scene_image()` → `generate_scene_video()`
- Output goes from illustrated slides to fully animated footage
- No other changes: same script format, same TTS, same ffmpeg, same delivery

## Delivery

1. Always save to S3 (lms-generated/ bucket)
2. If Classroom enabled: upload to YouTube (unlisted) → link in Classroom
3. Teacher can preview on dashboard before publishing

## Key Rules

1. Single narrator only — no two-host dialogue
2. Speaking rate 0.95 for students
3. Imagen generates 16:9 illustrations — one per scene
4. Videos target 3-5 minutes
5. YouTube always unlisted — only via Classroom link
6. ffmpeg installed in Worker container, not API container
7. Temp files cleaned after assembly
8. Video costs 6 credits (script + Imagen + TTS + render)
