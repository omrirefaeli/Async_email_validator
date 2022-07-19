import logging

formatting = "%(asctime)s | %(levelname)s | %(message)s"
logging_level = logging.DEBUG
logging.basicConfig(
    handlers=[
        logging.StreamHandler(),  # Print to console
    ],
    level=logging._checkLevel(logging_level),
    format=formatting,
    datefmt="%Y-%m-%d %H:%M:%S",
)
