import logging
import os
import inngest

_is_dev = os.environ.get("INNGEST_DEV") == "1"

inngest_client = inngest.Inngest(
    app_id="lulia-lms",
    event_key=os.environ.get("INNGEST_EVENT_KEY"),
    signing_key=os.environ.get("INNGEST_SIGNING_KEY") if not _is_dev else None,
    is_production=not _is_dev,
    logger=logging.getLogger("uvicorn.inngest"),
)
