import logging
import sys

def setup_logging():
    """Configures logging to write to both console and a file."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("chat_debug.log", mode="a", encoding="utf-8"),
        ],
    )
    # Ensure specific loggers are also propagating or handled
    logging.getLogger("uvicorn").handlers = []  # Avoid double logging if uvicorn sets its own
    logging.getLogger("uvicorn").propagate = True
