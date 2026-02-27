import logging
import os
import json
from utils.constants import DATASET_NAME
from utils.logging import get_logger

from genre_mapping.gutendex_client import GutendexClient
from fetching.dataset_extractor import DatasetExtractor
from genre_mapping.taxonomy_mapper import TaxonomyMapper

class GenreMapper:
	"""Orchestrates the extraction, API requests, and taxonomy mapping."""

	def __init__(self, extractor: DatasetExtractor, api_client: GutendexClient, mapper: TaxonomyMapper, logger: logging.Logger | None = None):
		"""Initialize the GenreMapper with the default taxonomy and logger."""
		self.extractor = extractor
		self.api_client = api_client
		self.mapper = mapper
		if not logger:
			self.logger = logging.Logger("GenreMapper")
			self.logger.addHandler(logging.NullHandler())
		else:
			self.logger = logger

	def run(
		self, limit: int | None = None, output_path: str = "data/book_genres.json"
	) -> dict[str, list[str]]:
		"""Run the full ETL pipeline to build and save the genre map.

		Args:
			limit (int | None, optional): The limit to apply to the dataset extractor. Defaults to None.
			output_path (str, optional): The path to save the genre map to. Defaults to "data/book_genres.json".

		Returns:
			dict[str, list[str]]: The final genre map.
		"""
		book_ids = self.extractor.get_all_book_ids(limit=limit)

		raw_shelves_map = self.api_client.fetch_raw_bookshelves(book_ids)

		final_genre_map = {}
		for book_id, raw_shelves in raw_shelves_map.items():
			final_genre_map[book_id] = self.mapper.extract_mapped_genres(raw_shelves)

		self.logger.info(f"Successfully mapped genres for {len(final_genre_map)} books!")

		self._save_to_json(final_genre_map, output_path)

		return final_genre_map

	def _save_to_json(self, data: dict, path: str) -> None:
		"""Helper to save the final dictionary to a JSON file.

		Args:
			data (dict): The dictionary to save.
			path (str): The path to save the dictionary to.
		"""
		os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
		with open(path, "w", encoding="utf-8") as f:
			json.dump(data, f, indent=4)
		self.logger.info(f"Genre map saved to {path}")


if __name__ == "__main__":
	logger = get_logger("GenreMapper")

	extractor = DatasetExtractor(DATASET_NAME, logger=logger)
	api_client = GutendexClient(logger=logger)
	mapper = TaxonomyMapper()
	genre_mapper = GenreMapper(extractor, api_client, mapper, logger=logger)

	genre_map = genre_mapper.run(limit=100, output_path="data/book_genres.json")