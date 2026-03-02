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
	if os.path.exists(path):
		try:
			with open(path, encoding="utf-8") as f:
				return json.load(f)
		except json.JSONDecodeError:
			if logger:
				logger.warning(f"Failed to parse {path}. Starting fresh.")
	return {}
