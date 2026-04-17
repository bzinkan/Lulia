import logging
import os
import inngest

_is_dev = os.environ.get("INNGEST_DEV") == "1"
_base_url = os.environ.get("INNGEST_BASE_URL")

inngest_client = inngest.Inngest(
    app_id="lulia-lms",
    api_base_url=_base_url,
    event_api_base_url=_base_url,
    event_key=os.environ.get("INNGEST_EVENT_KEY"),
    signing_key=os.environ.get("INNGEST_SIGNING_KEY") if not _is_dev else None,
    is_production=not _is_dev,
    logger=logging.getLogger("uvicorn.inngest"),
)
