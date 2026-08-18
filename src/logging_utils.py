import logging
import json
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(message)s",
)
logger = logging.getLogger("edikte")

def log_event(event : str, **fields):
    """emit one structured queryable log line in JSON format"""
    logger.info(json.dumps({event: event, **fields},default=str))
    # default=str handles datetime/Decimal objects that aren't natively JSON-serializable