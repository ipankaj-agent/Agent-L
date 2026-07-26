import logging
import logging.config
from pathlib import Path

import yaml


def setup_logging() -> None:
    config_file = (
        Path(__file__).resolve()
        .parents[3]          # LinkAgent/
        / "config"
        / "logging.yaml"
    )

    with config_file.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logging.config.dictConfig(config)