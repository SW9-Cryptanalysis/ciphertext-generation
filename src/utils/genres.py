import logging
import os
import json
from pathlib import Path


def load_existing_genre_map(
    path: Path,
    logger: logging.Logger | None,
) -> dict[str, list[str]]:
    """Load an existing genre map from a JSON file.

    Args:
        path (str): The path to the JSON file.
        logger (logging.Logger | None, optional): Logger to use. Defaults to None.

    Returns:
        dict[str, list[str]]: The existing genre map.

    """
    genre_map = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        genre_map[str(item["id"])] = item["genres"]
        except (json.JSONDecodeError, KeyError) as e:
            if logger:
                logger.warning(
                    f"Error parsing {path}: {e}. Continuing with partial data.",
                )
    return genre_map
