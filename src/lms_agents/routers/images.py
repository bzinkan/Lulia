"""Teacher image library — upload, generate, manage."""
import os
import tempfile
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

router = APIRouter(prefix="/images", tags=["Images"])


def get_db():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )
    try:
        yield conn
    finally:
        conn.close()


def _get_s3():
    return boto3.client(
        "s3", endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    teacher_id: str = Form("00000000-0000-0000-0000-000000000001"),
    conn=Depends(get_db),
):
    """Upload an image to the teacher's library."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        return JSONResponse({"error": "File too large (max 10MB)"}, status_code=400)

    image_id = str(uuid4())
    key = f"images/{teacher_id}/{image_id}/{file.filename}"
    thumb_key = f"images/{teacher_id}/{image_id}/thumb_{file.filename}"

    try:
        s3 = _get_s3()
        s3.put_object(Bucket="lulia-uploads", Key=key, Body=content, ContentType=file.content_type or "image/png")
        # Generate thumbnail using Pillow
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(content))
            w, h = img.size
            img.thumbnail((256, 256))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            s3.put_object(Bucket="lulia-uploads", Key=thumb_key, Body=buf.getvalue(), ContentType="image/png")
        except Exception:
            thumb_key = key
            w, h = 0, 0
    except Exception as e:
        return JSONResponse({"error": f"Upload failed: {e}"}, status_code=500)

    endpoint = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    storage_url = f"{endpoint}/lulia-uploads/{key}"
    thumbnail_url = f"{endpoint}/lulia-uploads/{thumb_key}"

    cur = conn.cursor()
    cur.execute(
        """INSERT INTO teacher_images (image_id, teacher_id, filename, storage_url, thumbnail_url, source, file_size, width, height)
           VALUES (%s, %s::uuid, %s, %s, %s, 'upload', %s, %s, %s)""",
        (image_id, teacher_id, file.filename, storage_url, thumbnail_url, len(content), w, h),
    )
    conn.commit(); cur.close()
    return {"image_id": image_id, "storage_url": storage_url, "thumbnail_url": thumbnail_url}


@router.get("")
async def list_images(
    teacher_id: str = Query("00000000-0000-0000-0000-000000000001"),
    search: str = Query(None),
    conn=Depends(get_db),
):
    """List teacher's saved images."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if search:
        cur.execute(
            "SELECT * FROM teacher_images WHERE teacher_id = %s::uuid AND filename ILIKE %s ORDER BY created_at DESC LIMIT 50",
            (teacher_id, f"%{search}%"),
        )
    else:
        cur.execute(
            "SELECT * FROM teacher_images WHERE teacher_id = %s::uuid ORDER BY created_at DESC LIMIT 50",
            (teacher_id,),
        )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"images": rows}


@router.delete("/{image_id}")
async def delete_image(image_id: str, conn=Depends(get_db)):
    """Delete an image from the library."""
    cur = conn.cursor()
    cur.execute("DELETE FROM teacher_images WHERE image_id = %s", (image_id,))
    conn.commit(); cur.close()
    return {"status": "deleted"}


class GenerateImageRequest(BaseModel):
    prompt: str
    style: str = "illustration"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"


@router.post("/generate")
async def generate_image_endpoint(req: GenerateImageRequest, conn=Depends(get_db)):
    """Generate an image using AI (Flux via Replicate)."""
    from src.lms_agents.tools.image_generator import generate_image

    style_map = {
        "illustration": "educational illustration, clean lines, friendly style",
        "diagram": "scientific diagram, labeled parts, clear lines",
        "cartoon": "cartoon style, colorful, kid-friendly",
        "line_art": "black and white line art, coloring book style",
        "realistic": "realistic photograph style",
    }
    style_suffix = style_map.get(req.style, req.style)
    full_prompt = f"{req.prompt}, {style_suffix}, white background, no text"

    path = generate_image(full_prompt)
    if not path:
        return JSONResponse({"error": "Image generation failed"}, status_code=500)

    # Upload to MinIO
    image_id = str(uuid4())
    filename = f"generated_{image_id}.png"
    key = f"images/{req.teacher_id}/{image_id}/{filename}"

    try:
        s3 = _get_s3()
        with open(path, "rb") as f:
            data = f.read()
        s3.put_object(Bucket="lulia-uploads", Key=key, Body=data, ContentType="image/png")
    except Exception as e:
        return JSONResponse({"error": f"Storage failed: {e}"}, status_code=500)
    finally:
        os.unlink(path)

    endpoint = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    storage_url = f"{endpoint}/lulia-uploads/{key}"

    # Save to library
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO teacher_images (image_id, teacher_id, filename, storage_url, thumbnail_url, source, generation_prompt)
           VALUES (%s, %s::uuid, %s, %s, %s, 'generated', %s)""",
        (image_id, req.teacher_id, filename, storage_url, storage_url, req.prompt),
    )
    conn.commit(); cur.close()

    return {"image_id": image_id, "storage_url": storage_url, "prompt": req.prompt}
