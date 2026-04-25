"""Teacher image library — upload, stock search, manage."""
import logging
import os
from uuid import uuid4

import boto3
import httpx
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
import psycopg2
from src.lms_agents.tools.db import get_connection as _pool_get_connection
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

log = logging.getLogger(__name__)
router = APIRouter(prefix="/images", tags=["Images"])


def _public_endpoint():
    """Return the S3 endpoint reachable from the browser (not the Docker-internal one)."""
    return os.environ.get("S3_PUBLIC_ENDPOINT", "http://localhost:9000")


def get_db():
    # Borrowed from the shared pool (tools/db.py). `conn.close()` below
    # releases the connection back rather than tearing the socket down.
    conn = _pool_get_connection()
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

    pub = _public_endpoint()
    storage_url = f"{pub}/lulia-uploads/{key}"
    thumbnail_url = f"{pub}/lulia-uploads/{thumb_key}"

    cur = conn.cursor()
    cur.execute(
        """INSERT INTO teacher_images (image_id, teacher_id, filename, storage_url, thumbnail_url, source, file_size, width, height)
           VALUES (%s, %s::uuid, %s, %s, %s, 'upload', %s, %s, %s)""",
        (image_id, teacher_id, file.filename, storage_url, thumbnail_url, len(content), w, h),
    )
    conn.commit(); cur.close()

    # Fire-and-forget vision caption so this image is searchable at
    # generation time. Non-fatal: the row is already persisted — if Gemini
    # is slow or unavailable, description stays NULL and a backfill job
    # can fill it in later.
    import threading
    def _caption():
        try:
            from src.lms_agents.tools.image_captioner import caption_teacher_image
            caption_teacher_image(image_id)
        except Exception as e:
            log.warning(f"[Images] Caption thread failed for {image_id}: {e}")
    threading.Thread(target=_caption, daemon=True).start()

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


@router.get("/search")
async def search_images(
    q: str = Query(..., description="Search query"),
    source: str = Query("all", description="Source: all, wikimedia, pixabay, openstax"),
    page: int = Query(1, ge=1),
):
    """
    Search educational images from multiple free sources.
    Wikimedia Commons (diagrams) + Pixabay (photos) + OpenStax (textbook figures).
    All results are free for educational use.
    """
    results = []

    # ── Wikimedia Commons — best for educational diagrams ──────────────
    if source in ("all", "wikimedia"):
        try:
            resp = httpx.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": f"{q} diagram OR illustration",
                    "gsrnamespace": 6,  # File namespace
                    "gsrlimit": 12 if source == "all" else 24,
                    "prop": "imageinfo",
                    "iiprop": "url|mime|extmetadata",
                    "iiurlwidth": 400,
                    "format": "json",
                },
                timeout=10,
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for pid, page_data in pages.items():
                info = (page_data.get("imageinfo") or [{}])[0]
                mime = info.get("mime", "")
                if not mime.startswith("image/"):
                    continue
                thumb = info.get("thumburl", "")
                full = info.get("url", "")
                if not thumb or not full:
                    continue
                meta = info.get("extmetadata", {})
                artist = meta.get("Artist", {}).get("value", "Wikimedia Commons")
                # Strip HTML from artist
                import re
                artist = re.sub(r"<[^>]+>", "", artist).strip()[:60]
                results.append({
                    "id": f"wiki_{pid}",
                    "url": full,
                    "thumb": thumb,
                    "source": "Wikimedia",
                    "attribution": f"{artist} — Wikimedia Commons",
                    "page_url": f"https://commons.wikimedia.org/wiki/File:{page_data.get('title', '').replace('File:', '')}",
                })
        except Exception as e:
            log.warning(f"[Images] Wikimedia search failed: {e}")

    # ── Pixabay — stock photos ─────────────────────────────────────────
    pixabay_key = os.environ.get("PIXABAY_API_KEY")
    if pixabay_key and source in ("all", "pixabay"):
        try:
            resp = httpx.get(
                "https://pixabay.com/api/",
                params={
                    "key": pixabay_key,
                    "q": q,
                    "image_type": "all",
                    "safesearch": "true",
                    "order": "popular",
                    "min_width": 400,
                    "per_page": 12 if source == "all" else 24,
                    "page": page,
                },
                timeout=10,
            )
            resp.raise_for_status()
            for hit in resp.json().get("hits", []):
                results.append({
                    "id": f"pixabay_{hit['id']}",
                    "url": hit["webformatURL"],
                    "thumb": hit["previewURL"],
                    "source": "Pixabay",
                    "attribution": f"Image by {hit.get('user', 'Pixabay')} on Pixabay",
                    "page_url": hit.get("pageURL", ""),
                })
        except Exception as e:
            log.warning(f"[Images] Pixabay search failed: {e}")

    return {"images": results, "total": len(results), "sources": ["wikimedia", "pixabay"]}


# ── OpenStax Textbook Image Search ─────────────────────────────────────────

# Map of HS/AP subjects to OpenStax book CNX IDs
OPENSTAX_BOOKS = {
    "Biology": "185cbf87-c72e-48f5-94f1-fe3c10b9a220",
    "AP Biology": "6c322e32-9b0f-4c7d-b389-4e0a3b29269e",
    "Chemistry": "7fccc9cf-9b71-44f6-800b-f9457fd64335",
    "AP Chemistry": "d9b85ee6-c57f-4861-8208-5ddf261e9c5f",
    "Physics": "031da8d3-b525-429c-80cf-6c8ed997733a",
    "AP Physics": "896a1f67-9498-40dc-8a58-292e4b66a740",
    "Algebra & Trigonometry": "13ac107a-f15f-49d2-97e8-60ab2e3b519c",
    "Pre-Calculus": "fd53eae1-fa23-47c7-bb1b-972349835c3c",
    "Calculus Vol 1": "8b89d172-2927-466f-8661-01abc7ccdba4",
    "Statistics": "b56bb972-978b-4e24-9a22-14cab3e0d7b1",
    "US History": "a7ba2fb8-8925-4987-b182-5f4429d48daa",
    "American Government": "9d8df601-4f12-4ac1-8b59-2a15a566e726",
    "Economics": "bc498e1f-efe9-43a0-8dea-d3569ad09a82",
    "Psychology": "4abf04bf-93a0-45c3-9cbc-2cefd46e68cc",
    "Sociology": "02040312-72c8-441e-a685-20e9333f3e1d",
    "Anatomy & Physiology": "14fb4ad7-39a1-4eee-ab6e-3ef2482e3e22",
    "Astronomy": "2e737be8-ea65-48c3-aa0a-9f35b4c6a966",
}


@router.get("/openstax/books")
async def list_openstax_books():
    """List available OpenStax textbooks for image browsing."""
    return {"books": [{"id": v, "name": k} for k, v in OPENSTAX_BOOKS.items()]}


@router.get("/openstax/search")
async def search_openstax_images(
    book_id: str = Query(..., description="OpenStax CNX book UUID"),
    q: str = Query("", description="Search within book content"),
):
    """
    Search for images within an OpenStax textbook.
    Fetches the book TOC, finds pages matching the query, extracts image URLs.
    """
    try:
        # Get book TOC
        resp = httpx.get(f"https://archive.cnx.org/contents/{book_id}.json", timeout=15)
        resp.raise_for_status()
        book = resp.json()

        # Collect page IDs from TOC tree
        page_ids = []
        def walk_tree(node):
            if "contents" in node:
                for child in node["contents"]:
                    walk_tree(child)
            elif "id" in node:
                title = node.get("title", "")
                if not q or q.lower() in title.lower():
                    page_ids.append({"id": node["id"], "title": title})
        for item in book.get("tree", {}).get("contents", []):
            walk_tree(item)

        # Fetch first 3 matching pages and extract images
        results = []
        for page_info in page_ids[:3]:
            try:
                page_resp = httpx.get(f"https://archive.cnx.org/contents/{page_info['id']}.json", timeout=10)
                page_resp.raise_for_status()
                page_data = page_resp.json()
                html = page_data.get("content", "")

                # Extract image URLs from HTML
                import re
                img_matches = re.findall(r'src="([^"]*?/resources/[^"]+)"', html)
                for img_path in img_matches:
                    if img_path.startswith(".."):
                        img_url = f"https://archive.cnx.org{img_path.replace('..', '')}"
                    elif img_path.startswith("/"):
                        img_url = f"https://archive.cnx.org{img_path}"
                    else:
                        img_url = img_path
                    results.append({
                        "id": f"openstax_{hash(img_url) & 0xFFFFFF:06x}",
                        "url": img_url,
                        "thumb": img_url,
                        "source": "OpenStax",
                        "attribution": f"OpenStax — {page_info['title']}",
                        "page_url": f"https://openstax.org/books/{book_id}/pages/{page_info['id']}",
                    })
            except Exception:
                continue

        return {"images": results, "total": len(results), "chapter_count": len(page_ids)}
    except Exception as e:
        log.error(f"[Images] OpenStax search failed: {e}")
        return JSONResponse({"error": f"OpenStax search failed: {e}"}, status_code=500)


class GenerateImageRequest(BaseModel):
    prompt: str
    style: str = "educational_diagram"
    subject: str = "General"
    grade: str = "4"
    size: str = "1024x1024"
    teacher_id: str = "00000000-0000-0000-0000-000000000001"


@router.post("/generate")
async def generate_image_endpoint(req: GenerateImageRequest, conn=Depends(get_db)):
    """Generate an educational image using DALL-E 3."""
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        return JSONResponse({"error": "OPENAI_API_KEY not set"}, status_code=503)

    # Build an educational prompt with style guidance
    style_instructions = {
        "educational_diagram": "Create a clear, labeled educational diagram. Use arrows, labels, and numbered steps. Textbook illustration style.",
        "scientific_illustration": "Create a detailed scientific illustration with accurate cross-sections, labeled structures, and proper proportions. Textbook quality.",
        "worksheet_clipart": "Create simple, clean black-outline clipart suitable for a printed worksheet. Minimal color, bold lines, easy to photocopy.",
        "infographic": "Create a colorful infographic with icons, clear visual hierarchy, and organized sections. Suitable for a classroom poster.",
        "line_art": "Create a black and white line drawing with clean outlines and no shading. Suitable for a coloring activity or worksheet.",
    }.get(req.style, "Create a clear educational illustration suitable for a classroom worksheet.")

    grade_note = (
        "Use simple shapes, bright colors, large elements, and minimal detail — suitable for young children."
        if req.grade in ("K", "1", "2") else
        "Use age-appropriate complexity and clear visuals."
        if req.grade in ("3", "4", "5") else
        "Use detailed, accurate representations suitable for secondary students."
    )

    full_prompt = (
        f"{style_instructions}\n\n"
        f"Topic: {req.prompt}\n"
        f"Subject: {req.subject}, Grade {req.grade}\n"
        f"{grade_note}\n"
        f"The image must be educationally accurate. White background. No watermarks."
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        response = client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size=req.size,
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url

        # Download the image and store in MinIO
        img_resp = httpx.get(image_url, follow_redirects=True, timeout=60)
        img_resp.raise_for_status()
        image_data = img_resp.content

    except Exception as e:
        log.error(f"[Images] DALL-E generation failed: {e}")
        return JSONResponse({"error": f"Image generation failed: {e}"}, status_code=500)

    # Upload to MinIO
    image_id = str(uuid4())
    filename = f"generated_{image_id}.png"
    key = f"images/{req.teacher_id}/{image_id}/{filename}"

    try:
        s3 = _get_s3()
        s3.put_object(Bucket="lulia-uploads", Key=key, Body=image_data, ContentType="image/png")
    except Exception as e:
        return JSONResponse({"error": f"Storage failed: {e}"}, status_code=500)

    pub = _public_endpoint()
    storage_url = f"{pub}/lulia-uploads/{key}"

    # Save to teacher's library automatically
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO teacher_images (image_id, teacher_id, filename, storage_url, thumbnail_url, source, generation_prompt)
           VALUES (%s, %s::uuid, %s, %s, %s, 'generated', %s)""",
        (image_id, req.teacher_id, filename, storage_url, storage_url, req.prompt),
    )
    conn.commit(); cur.close()

    return {"image_id": image_id, "storage_url": storage_url, "prompt": req.prompt}


@router.post("/inpaint")
async def inpaint_image(
    image: UploadFile = File(..., description="Original image to edit (PNG/JPG)"),
    mask: UploadFile = File(..., description="Mask PNG (white = change this region, black = keep)"),
    prompt: str = Form(..., description="Describe what to put in the masked area"),
    teacher_id: str = Form("00000000-0000-0000-0000-000000000001"),
    save_to_library: bool = Form(True),
    conn=Depends(get_db),
):
    """
    Leonardo Canvas inpaint. Teacher brushes over a region on the original image
    (client-side), the browser exports the mask as a PNG, both are uploaded here,
    and Leonardo fills the masked area with AI-generated content matching `prompt`.

    Flow:
      1. Receive image + mask + prompt from the dashboard
      2. Upload both to Leonardo (init-image presigned upload)
      3. Call Leonardo inpaint API, poll for completion
      4. Download result, persist to MinIO/S3, add to teacher_images library
      5. Return the new image URL so the frontend can preview
    """
    from src.lms_agents.tools.leonardo_client import upload_init_image, inpaint as leo_inpaint

    image_bytes = await image.read()
    mask_bytes = await mask.read()
    if len(image_bytes) > 10 * 1024 * 1024 or len(mask_bytes) > 10 * 1024 * 1024:
        return JSONResponse({"error": "Image or mask exceeds 10MB"}, status_code=400)

    img_ext = (image.filename or "upload.png").rsplit(".", 1)[-1].lower()
    if img_ext not in ("png", "jpg", "jpeg", "webp"):
        img_ext = "png"

    # Step 1: upload original + mask to Leonardo
    init_up = upload_init_image(image_bytes, extension=img_ext)
    if not init_up["success"]:
        return JSONResponse({"error": f"Image upload failed: {init_up['error']}"}, status_code=502)
    mask_up = upload_init_image(mask_bytes, extension="png")
    if not mask_up["success"]:
        return JSONResponse({"error": f"Mask upload failed: {mask_up['error']}"}, status_code=502)

    # Step 2: call inpaint
    result = leo_inpaint(
        init_image_id=init_up["image_id"],
        mask_image_id=mask_up["image_id"],
        prompt=prompt,
    )
    if not result.get("success"):
        return JSONResponse({"error": result.get("error", "Inpaint failed")}, status_code=502)

    result_url = result["images"][0]

    # Step 3: optionally persist to teacher's library
    storage_url = result_url
    image_id = None
    if save_to_library:
        try:
            with httpx.Client(timeout=60.0) as http_client:
                r = http_client.get(result_url)
                if r.status_code == 200:
                    image_id = str(uuid4())
                    filename = f"inpaint_{image_id}.png"
                    key = f"images/{teacher_id}/{image_id}/{filename}"
                    s3 = _get_s3()
                    s3.put_object(
                        Bucket=os.environ.get("S3_BUCKET_GENERATED", "lulia-generated"),
                        Key=key,
                        Body=r.content,
                        ContentType="image/png",
                    )
                    storage_url = f"{_public_endpoint()}/{os.environ.get('S3_BUCKET_GENERATED', 'lulia-generated')}/{key}"
                    cur = conn.cursor()
                    cur.execute(
                        """INSERT INTO teacher_images (image_id, teacher_id, filename, storage_url, thumbnail_url, source, generation_prompt)
                           VALUES (%s, %s::uuid, %s, %s, %s, 'inpaint', %s)""",
                        (image_id, teacher_id, filename, storage_url, storage_url, prompt),
                    )
                    conn.commit()
                    cur.close()
        except Exception as e:
            log.warning(f"[Inpaint] Library save failed (returning Leonardo URL anyway): {e}")

    return {
        "image_id": image_id,
        "storage_url": storage_url,
        "leonardo_url": result_url,
        "generation_id": result.get("generation_id"),
        "prompt": prompt,
    }
