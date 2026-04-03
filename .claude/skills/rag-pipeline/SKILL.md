---
name: rag-pipeline
description: "Use this skill whenever building the RAG Knowledge Base system. Triggers include: setting up pgvector, writing document ingestion pipelines, configuring AWS Bedrock Titan embedding, building semantic search queries, processing uploads (Materials and Curriculum lanes), or troubleshooting content retrieval. Also trigger for Generation History dedup queries that use semantic similarity."
---

# RAG Pipeline — Knowledge Base System

## Architecture

- **Vector DB**: pgvector extension in PostgreSQL (local dev) / RDS (prod)
- **Embedding Model**: AWS Bedrock — Amazon Titan Text Embeddings V2 (1024 dimensions)
- **Why Bedrock**: Data never leaves AWS environment. Uses boto3 (same SDK as S3). FERPA strongest.
- **Chunking**: Intelligent boundary detection (headings, topics, ~300-500 words)
- **Search**: Cosine similarity via pgvector `<=>` operator

## Bedrock Embedding (Replaces OpenAI)

```python
import boto3, json

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

def embed_text(text: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text})
    )
    result = json.loads(response["body"].read())
    return result["embedding"]  # 1024-dimensional vector

def embed_chunks(chunks: list[dict]) -> list[dict]:
    for chunk in chunks:
        chunk["embedding"] = embed_text(chunk["content"])
    return chunks
```

Same boto3 SDK used for S3. No additional API key — uses AWS IAM credentials.
Works from Docker Desktop (needs AWS access key in .env.development) and from Fargate (uses IAM role).

## Database Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL, file_type VARCHAR NOT NULL,
    original_path VARCHAR NOT NULL, subject VARCHAR,
    grade_level VARCHAR, unit VARCHAR,
    standards_covered JSONB DEFAULT '[]',
    upload_lane VARCHAR NOT NULL,  -- 'materials' or 'curriculum'
    chunk_count INT DEFAULT 0,
    processing_status VARCHAR DEFAULT 'pending',
    uploaded_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE knowledge_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES knowledge_sources ON DELETE CASCADE,
    chunk_number INT NOT NULL, content TEXT NOT NULL,
    embedding VECTOR(1024),  -- Titan V2 = 1024 dimensions
    standards_tags JSONB DEFAULT '[]',
    topic VARCHAR, page_number INT, section_heading VARCHAR
);

CREATE INDEX ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

## RAG Search Tool (Used by Content Agent, QA Agent, Video Script Agent)

```python
class RAGSearchTool(BaseTool):
    name = "knowledge_base_search"
    description = "Search uploaded teaching materials for relevant content"

    def _run(self, query: str, subject: str = None, standards_ids: list = None, top_k: int = 5):
        query_embedding = embed_text(query)
        results = db.query("""
            SELECT kc.content, kc.section_heading, kc.page_number,
                   kc.standards_tags, ks.name as source_name,
                   kc.embedding <=> %s::vector as distance
            FROM knowledge_chunks kc
            JOIN knowledge_sources ks ON kc.source_id = ks.source_id
            ORDER BY kc.embedding <=> %s::vector
            LIMIT %s
        """, [query_embedding, query_embedding, top_k])
        return results
```

## Document Processing by Type

- **PDF**: PyMuPDF → extract by headings + 500-word boundaries
- **DOCX**: python-docx → extract by headings
- **YouTube**: youtube_transcript_api → chunk by 60-second segments
- **URLs**: httpx + BeautifulSoup → extract main content
- **Google Docs/Slides**: Drive API → export as text → chunk

## Standards Auto-Tagging

After chunking, Claude Haiku classifies which standards each chunk relates to. Tags stored in `standards_tags` JSONB for filtered search.

## Key Rules

1. Upload Materials → RAG KB only (no calendar entries)
2. Upload Curriculum → RAG KB + Calendar entries (dual pipeline)
3. Upload Standards → Standards DB only (never chunked into RAG)
4. Bedrock embedding: 1024 dimensions (Titan V2), not 1536 (OpenAI)
5. Always embed with Bedrock — never mix embedding models
6. Content Agent searches RAG FIRST when has_kb_coverage is true
7. QA Agent searches RAG for fact-checking generated content
8. Generation History uses content_fingerprint for semantic dedup (separate from RAG)
