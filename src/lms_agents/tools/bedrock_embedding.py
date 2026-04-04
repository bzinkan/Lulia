"""
Bedrock Embedding — Amazon Titan Text Embeddings V2 (1024 dimensions).

Uses boto3 with AWS credentials from .env. In dev, connects to Bedrock
remotely. In prod (Fargate), uses IAM role — same code, no config change.
"""
import json
import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

log = logging.getLogger(__name__)

_client: Optional[object] = None


def _get_client():
    """Lazy-init the Bedrock Runtime client."""
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
    return _client


def embed_text(text: str) -> list[float] | None:
    """
    Embed a single text string using Bedrock Titan V2.
    Returns a 1024-dimensional vector, or None on failure.
    """
    if not text or not text.strip():
        return None

    # Titan V2 has a 8192 token limit; truncate long text to ~30k chars
    truncated = text[:30000]

    try:
        client = _get_client()
        model_id = os.environ.get(
            "BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"
        )
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps({"inputText": truncated}),
        )
        result = json.loads(response["body"].read())
        return result["embedding"]
    except NoCredentialsError:
        log.warning("AWS credentials not configured — embedding skipped")
        return None
    except ClientError as e:
        log.warning(f"Bedrock embedding failed: {e}")
        return None
    except Exception as e:
        log.warning(f"Unexpected embedding error: {e}")
        return None


def embed_batch(texts: list[str]) -> list[list[float] | None]:
    """
    Embed a batch of texts. Titan V2 doesn't support native batching,
    so we call embed_text sequentially.

    Returns list of embeddings (or None for failures) in same order as input.
    """
    results = []
    for i, text in enumerate(texts):
        embedding = embed_text(text)
        results.append(embedding)
        if (i + 1) % 50 == 0:
            log.info(f"  Embedded {i + 1}/{len(texts)} chunks")
    return results
