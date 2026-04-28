from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file if it exists
load_dotenv()

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[1]
logger.info(f"PROJ_ROOT path is: {PROJ_ROOT}")

DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

SCENARIOS = ["carnet", "scalability/1-50subs_x_1pub"]


def get_config_for_pubsub_count(pub_count: int, sub_count: int) -> str:
    # Generate config string based on pub_count and sub_count of a scenario configuration
    # Assuming config format is "p{PUBCOUNT}_s{SUBCOUNT}"
    return f"p{pub_count}_s{sub_count}"


def get_pubsub_count_from_config(config: str) -> tuple[int, int]:
    # Parse config string to extract pub_count and sub_count of a scenario configuration
    # Assuming config format is "p{PUBCOUNT}_s{SUBCOUNT}"
    parts = config.split("_")
    pub_count = int(parts[0][1:])  # Extract PUBCOUNT
    sub_count = int(parts[1][1:])  # Extract SUBCOUNT
    return pub_count, sub_count


REPORTS_DIR = PROJ_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"


# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

    logger.remove(0)
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)
except ModuleNotFoundError:
    pass
