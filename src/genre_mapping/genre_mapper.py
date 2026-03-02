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

	def __init__(
		self,
		extractor: DatasetExtractor,
		api_client: GutendexClient,
		mapper: TaxonomyMapper,
		logger: logging.Logger | None = None,
	) -> None:
		"""Initialize the GenreMapper with the default taxonomy and logger.

		Args:
			extractor (DatasetExtractor): Extractor to use for fetching the dataset.
			api_client (GutendexClient): GutendexClient to use for fetching the API.
			mapper (TaxonomyMapper): TaxonomyMapper to use for mapping the API data.
			logger (logging.Logger | None, optional): Logger to use. Defaults to None.

		"""
		self.extractor = extractor
		self.api_client = api_client
		self.mapper = mapper
		if not logger:
			self.logger = logging.Logger("GenreMapper")
			self.logger.addHandler(logging.NullHandler())
		else:
			self.logger = logger

	def run(
		self,
		output_path: str = "data/book_genres.json",
		flush_size: int = 35,
	) -> dict[str, list[str]]:
		"""Run the full ETL pipeline to build and save the genre map.

		Args:
			output_path (str, optional): The path to save the genre map to.
				Defaults to "data/book_genres.json".
			flush_size (int, optional): The number of book IDs to process at a time.
				Defaults to 35.

		Returns:
			dict[str, list[str]]: The final genre map.

		"""
		final_genre_map = self._load_existing_genre_map(output_path)
		id_stream = self.extractor.get_id_stream()

		batch_buffer = []
		newly_mapped_books = 0

		for book_id in id_stream:
			if book_id not in final_genre_map:
				batch_buffer.append(book_id)

			if len(batch_buffer) >= flush_size:
				newly_mapped_books += self._process_batch(batch_buffer, final_genre_map)
				self._save_to_json(final_genre_map, output_path)
				batch_buffer.clear()

		if batch_buffer:
			newly_mapped_books += self._process_batch(batch_buffer, final_genre_map)

		self._save_to_json(final_genre_map, output_path)
		self.logger.info(
			f"Successfully mapped genres for {len(final_genre_map)} books!",
		)

		return final_genre_map

	def _process_batch(
		self, batch_buffer: list[str], genre_map: dict[str, list[str]],
	) -> int:
		"""Process a batch of book IDs and extract genre data.

		Args:
			batch_buffer (list[str]): The list of book IDs to process.
			genre_map (dict[str, list[str]]): The genre map to update.

		"""
		raw_shelves_map = self.api_client.fetch_raw_bookshelves(batch_buffer)

		count = 0
		for book_id, raw_shelves in raw_shelves_map.items():
			genre_map[str(book_id)] = self.mapper.extract_mapped_genres(raw_shelves)
			count += 1

		self.logger.info(f"Successfully mapped genres for {count} new book ids!")

		return count

	def _load_existing_genre_map(self, path: str) -> dict[str, list[str]]:
		"""Load an existing genre map from a JSON file.

		Args:
			path (str): The path to the JSON file.

		Returns:
			dict[str, list[str]]: The existing genre map.

		"""
		if os.path.exists(path):
			try:
				with open(path, encoding="utf-8") as f:
					return json.load(f)
			except json.JSONDecodeError:
				self.logger.warning(f"Failed to parse {path}. Starting fresh.")
		return {}

	def _save_to_json(self, data: dict, path: str) -> None:
		"""Save the final dictionary to a JSON file.

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

	genre_map = genre_mapper.run(output_path="data/book_genres.json")
	mapper.dump_unmapped_to_file()
