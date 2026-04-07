"""
Lulings Generator — creates 50 custom avatar characters using Flux 1.1 Pro on Replicate.

Run: docker compose exec api python scripts/generate_lulings.py

Each character: 1024x1024 PNG + 128x128 thumbnail.
Estimated cost: 50 × ~$0.04 = ~$2 total.
"""
import io
import logging
import os
import sys
import tempfile
from uuid import uuid4

import boto3
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [lulings] %(message)s")
log = logging.getLogger(__name__)

# Character definitions: (name, category, description, subject_affinity, rarity)
LULINGS = [
    # Book Buddies (10)
    ("Reading Riley", "book_buddies", "a friendly orange book with big cute eyes, tiny arms, and small legs, pages slightly open, happy expression", "reading", "common"),
    ("Library Lou", "book_buddies", "a blue hardcover book with glasses, big eyes, a warm smile, holding a smaller book", "reading", "common"),
    ("Story Sam", "book_buddies", "a green storybook with a bookmark sticking out, excited eyes, waving one arm", "reading", "common"),
    ("Chapter Charlie", "book_buddies", "a thick red encyclopedia with round glasses, wise expression, standing tall", "reading", "rare"),
    ("Plot Penny", "book_buddies", "a pink picture book with sparkly eyes, pigtail bookmarks, dancing pose", "reading", "common"),
    ("Page Pete", "book_buddies", "a yellow notepad character with a spiral binding crown, scribbling with a tiny pencil", "reading", "common"),
    ("Tale Tilly", "book_buddies", "a purple fairytale book with a tiara, magic sparkles around, dreamy eyes", "reading", "rare"),
    ("Verse Violet", "book_buddies", "a lavender poetry book with musical notes floating around, serene smile", "reading", "common"),
    ("Word Will", "book_buddies", "a dictionary book with magnifying glass, curious expression, teal colored", "reading", "common"),
    ("Read Ruby", "book_buddies", "a red reading book with a cozy scarf, holding hot cocoa, warm smile", "reading", "legendary"),

    # Pencil Pals (8)
    ("Pencil Pete", "pencil_pals", "a smiling yellow pencil with arms and legs, wooden body, pink eraser hat, waving", "all", "common"),
    ("Crayon Cara", "pencil_pals", "a rainbow crayon set character, multiple colors blended together, joyful face", "all", "common"),
    ("Marker Max", "pencil_pals", "a bold blue marker with a cap hat, confident pose, strong arms", "all", "common"),
    ("Eraser Ellie", "pencil_pals", "a cute pink eraser with sparkly dust around, apologetic smile, bouncy", "all", "common"),
    ("Brush Buddy", "pencil_pals", "a paintbrush with colorful bristle hair, artistic pose, paint palette shield", "all", "rare"),
    ("Sketch Sue", "pencil_pals", "a mechanical pencil with tiny click top, sleek silver body, precise expression", "all", "common"),
    ("Ink Iggy", "pencil_pals", "a fountain pen character with a monocle, fancy, dripping ink drops like sweat", "all", "rare"),
    ("Doodle Dan", "pencil_pals", "a chunky crayon with doodle patterns all over body, goofy grin, messy hair", "all", "common"),

    # Math Monsters (8)
    ("Number Nora", "math_monsters", "a cute number 7 character with big round eyes, tiny crown, purple body", "math", "common"),
    ("Plus Pip", "math_monsters", "a plus sign character with bouncy personality, green body, arms wide open in a hug", "math", "common"),
    ("Equal Eli", "math_monsters", "an equals sign character with two parallel body segments, calm balanced expression, blue", "math", "common"),
    ("Square Sid", "math_monsters", "a square shape with stubby legs, confident expression, red body, geometric patterns", "math", "common"),
    ("Triangle Tina", "math_monsters", "a triangle character with three pointy hairstyle tips, sassy pose, orange body", "math", "rare"),
    ("Circle Cody", "math_monsters", "a circle character rolling like a ball, happy dizzy eyes, yellow body", "math", "common"),
    ("Decimal Dot", "math_monsters", "a tiny dot character with huge eyes relative to body, precise expression, black", "math", "rare"),
    ("Fraction Fern", "math_monsters", "a fraction bar character with a top half and bottom half, friendly divided expression", "math", "legendary"),

    # Science Sprites (8)
    ("Beaker Bea", "science_sprites", "a glass beaker with bubbling green liquid inside, goggles on head, excited expression", "science", "common"),
    ("Atom Andy", "science_sprites", "an atom with orbiting electrons, central nucleus face, energetic spinning pose", "science", "common"),
    ("Planet Pat", "science_sprites", "a small Saturn-like planet with rings, peaceful expression, stars around", "science", "common"),
    ("Comet Coby", "science_sprites", "a comet with a fiery tail, zooming pose, determined expression", "science", "rare"),
    ("Molecule Mo", "science_sprites", "a water molecule H2O character, three connected spheres with faces, bouncy", "science", "common"),
    ("Crystal Kit", "science_sprites", "a crystal/gem character with faceted body, sparkling, purple and teal", "science", "rare"),
    ("Volcano Vee", "science_sprites", "a small volcano character with lava hair, warm expression, rumbling slightly", "science", "common"),
    ("Galaxy Gus", "science_sprites", "a spiral galaxy character with swirling arms, cosmic expression, deep purple", "science", "legendary"),

    # Nature Friends (8)
    ("Tree Toby", "nature_friends", "a small oak tree with a face in the trunk, leaf arms, acorn friends nearby", "science", "common"),
    ("Mushroom Mia", "nature_friends", "a red spotted mushroom with big eyes under the cap, tiny legs, forest setting", "science", "common"),
    ("Leaf Levi", "nature_friends", "an autumn leaf character with red-orange gradient, floating gently, peaceful", "science", "common"),
    ("Flower Flora", "nature_friends", "a sunflower with a face in the center, petal hair, cheerful pose, green stem body", "science", "common"),
    ("Acorn Ace", "nature_friends", "a small acorn with a beret cap, adventurous expression, tiny backpack", "science", "rare"),
    ("Sprout Sky", "nature_friends", "a seedling just emerging from soil, bright green, optimistic upward gaze", "science", "common"),
    ("Berry Belle", "nature_friends", "a cluster of berries as a character, group of friends, blueberry colored", "science", "common"),
    ("Pinecone Pat", "nature_friends", "a pinecone character with layered scale armor, woodland warrior pose", "science", "rare"),

    # Lab Critters (8)
    ("Microscope Milo", "lab_critters", "a microscope with one big eye lens, curious leaning forward pose, white lab coat", "science", "common"),
    ("Telescope Tess", "lab_critters", "a telescope character looking up at stars, dreamy expression, night sky themed", "science", "common"),
    ("Gear Gabe", "lab_critters", "a mechanical gear with teeth as a smile, spinning slightly, bronze colored", "science", "common"),
    ("Magnet Marv", "lab_critters", "a horseshoe magnet with red and blue ends, attracting paper clips, strong pose", "science", "common"),
    ("Compass Cleo", "lab_critters", "a compass with a spinning needle nose, always pointing north, adventurous", "science", "rare"),
    ("Clock Casey", "lab_critters", "a clock with hands as arms, numbers around face, always on time expression", "math", "common"),
    ("Lens Lily", "lab_critters", "a magnifying glass with a big eye through the lens, detective pose, curious", "science", "common"),
    ("Ruler Ronnie", "lab_critters", "a wooden ruler with measurement marks as freckles, tall and straight, precise", "math", "legendary"),
]

STYLE_PROMPT = (
    "kawaii illustration, friendly big eyes, simple rounded shapes, "
    "warm color palette featuring peach cream soft orange and warm browns, "
    "flat illustration style, white background, centered composition, "
    "Blooket and Class Dojo inspired design, sticker-ready, "
    "no text, no watermark, soft shadows, pastel highlights, "
    "ages 6-12 friendly, expressive face, full body view"
)


def get_db():
    import psycopg2
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )


def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )


def check_existing():
    """Check if Lulings already exist in the database."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM lulings")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def make_thumbnail(image_path: str) -> str:
    """Create a 128x128 thumbnail."""
    img = Image.open(image_path)
    img.thumbnail((128, 128), Image.LANCZOS)
    thumb_path = image_path.replace(".png", "_thumb.png")
    img.save(thumb_path, "PNG")
    return thumb_path


def generate_all():
    """Generate all 50 Lulings."""
    existing = check_existing()
    if existing >= len(LULINGS):
        log.info(f"Already have {existing} Lulings in database — skipping generation")
        return

    log.info(f"Generating {len(LULINGS)} Lulings...")

    import sys
    sys.path.insert(0, "/app")
    from src.lms_agents.tools.image_generator import generate_image

    s3 = get_s3()
    conn = get_db()
    cur = conn.cursor()
    preview_items = []
    total_cost = 0

    import time

    for i, (name, category, desc, affinity, rarity) in enumerate(LULINGS, 1):
        log.info(f"Generating {name} ({i}/{len(LULINGS)})...")

        # Check if this specific Luling exists
        cur.execute("SELECT luling_id FROM lulings WHERE name = %s", (name,))
        if cur.fetchone():
            log.info(f"  Already exists, skipping")
            continue

        # Rate limit: wait 12 seconds between requests (5 per minute safe)
        if i > 1:
            time.sleep(12)

        prompt = f"A cute chibi-style mascot character: {desc}, {STYLE_PROMPT}"
        char_id = f"{category}_{name.lower().replace(' ', '_')}"

        # Generate image
        img_path = generate_image(prompt)
        if not img_path:
            log.warning(f"  FAILED to generate {name} — using placeholder")
            # Create a simple colored placeholder
            img = Image.new("RGB", (1024, 1024), (254, 249, 242))
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle([(200, 200), (824, 824)], radius=100, fill=(249, 115, 22))
            draw.text((512, 512), name[0], fill=(255, 255, 255), anchor="mm")
            img_path = tempfile.mktemp(suffix=".png")
            img.save(img_path)

        # Create thumbnail
        thumb_path = make_thumbnail(img_path)

        # Upload to MinIO
        file_key = f"avatars/{char_id}.png"
        thumb_key = f"avatars/{char_id}_thumb.png"
        try:
            with open(img_path, "rb") as f:
                s3.put_object(Bucket="lulia-generated", Key=file_key, Body=f, ContentType="image/png")
            with open(thumb_path, "rb") as f:
                s3.put_object(Bucket="lulia-generated", Key=thumb_key, Body=f, ContentType="image/png")
        except Exception as e:
            log.warning(f"  Upload failed: {e}")
            file_key = None
            thumb_key = None

        # Store in DB
        luling_id = str(uuid4())
        endpoint = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
        file_url = f"{endpoint}/lulia-generated/{file_key}" if file_key else None
        thumb_url = f"{endpoint}/lulia-generated/{thumb_key}" if thumb_key else None

        cur.execute(
            """INSERT INTO lulings (luling_id, name, category, file_url, thumbnail_url, subject_affinity, rarity)
               VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
            (luling_id, name, category, file_url, thumb_url, affinity, rarity),
        )
        conn.commit()

        preview_items.append({"name": name, "category": category, "thumb_url": thumb_url or ""})
        total_cost += 0.04

        # Cleanup temp files
        for p in [img_path, thumb_path]:
            try:
                os.unlink(p)
            except Exception:
                pass

    cur.close()
    conn.close()

    # Generate preview HTML
    html = "<html><head><style>body{font-family:sans-serif;background:#F5DEC3;padding:20px;}"
    html += ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;}"
    html += ".card{background:white;border-radius:14px;padding:12px;text-align:center;}"
    html += ".card img{width:100px;height:100px;border-radius:10px;}"
    html += ".card p{font-size:12px;margin-top:6px;}</style></head><body>"
    html += f"<h1>Lulings Preview ({len(preview_items)} characters)</h1>"
    html += f"<p>Estimated cost: ${total_cost:.2f}</p>"
    html += '<div class="grid">'
    for item in preview_items:
        html += f'<div class="card"><img src="{item["thumb_url"]}" onerror="this.style.background=\'#FDBA74\'"><p><strong>{item["name"]}</strong><br><small>{item["category"]}</small></p></div>'
    html += "</div></body></html>"

    with open("/tmp/lulings_preview.html", "w") as f:
        f.write(html)

    log.info(f"\n=== Generation Complete ===")
    log.info(f"  Characters: {len(preview_items)}")
    log.info(f"  Estimated cost: ${total_cost:.2f}")
    log.info(f"  Preview: /tmp/lulings_preview.html")


if __name__ == "__main__":
    generate_all()
