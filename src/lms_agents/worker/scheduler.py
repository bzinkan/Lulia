"""
Lulia Background Worker — APScheduler
Polls the events table (dev) or SQS (prod) and runs generation jobs.
"""
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Lulia worker started — waiting for jobs")
    while True:
        time.sleep(10)


if __name__ == "__main__":
    main()
