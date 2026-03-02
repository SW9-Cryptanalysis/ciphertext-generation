import logging
import os
import json
from utils.constants import DATASET_NAME, GENRE_MAP_PATH
from utils.logging import get_logger
from pathlib import Path

from genre_mapping.gutendex_client import GutendexClient
from fetching.dataset_extractor import DatasetExtractor
from genre_mapping.taxonomy_mapper import TaxonomyMapper
from utils.genres import load_existing_genre_map


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
		output_path: Path,
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
		final_genre_map = load_existing_genre_map(output_path, self.logger)
		id_stream = self.extractor.get_id_stream()

		batch_buffer = []
		newly_mapped_count = 0

		for book_id in id_stream:
			if book_id not in final_genre_map:
				batch_buffer.append(book_id)

			if len(batch_buffer) >= flush_size:
				new_data = self._process_batch(batch_buffer)
				self._append_to_jsonl(new_data, output_path)
				final_genre_map.update(new_data)
				newly_mapped_count += len(new_data)
				batch_buffer = []

		if batch_buffer:
			new_data = self._process_batch(batch_buffer)
			self._append_to_jsonl(new_data, output_path)
			final_genre_map.update(new_data)
			newly_mapped_count += len(new_data)

		self.logger.info(
			f"Successfully mapped genres for {len(final_genre_map)} books in total!",
		)

		return final_genre_map

	def _process_batch(self, batch_buffer: list[str]) -> dict[str, list[str]]:
		"""Fetch raw data and extract genres for a specific batch.

		Returns:
			dict[str, list[str]]: A dictionary of newly mapped book IDs.

		"""
		raw_shelves_map = self.api_client.fetch_raw_bookshelves(batch_buffer)
		new_mappings = {}

		for book_id, raw_shelves in raw_shelves_map.items():
			new_mappings[str(book_id)] = self.mapper.extract_mapped_genres(raw_shelves)

		self.logger.info(f"Fetched and parsed {len(new_mappings)} books from API.")
		return new_mappings

	def _append_to_jsonl(self, data_batch: dict[str, list[str]], path: Path) -> None:
		"""Append a batch of new mappings to the JSONL file.

		Args:
			data_batch (dict): Dictionary of {id: [genres]} to append.
			path (str): Path to the .jsonl file.

		"""
		os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

		# 'a' opens for appending without truncating the existing file
		with open(path, "a", encoding="utf-8") as f:
			for book_id, genres in data_batch.items():
				line = json.dumps({"id": str(book_id), "genres": genres})
				f.write(line + "\n")

		self.logger.info(f"Appended {len(data_batch)} mappings to {path}")


if __name__ == "__main__":
	logger = get_logger("GenreMapper")

	extractor = DatasetExtractor(DATASET_NAME, logger=logger)
	api_client = GutendexClient(logger=logger)
	mapper = TaxonomyMapper()
	genre_mapper = GenreMapper(extractor, api_client, mapper, logger=logger)

	genre_map = genre_mapper.run(output_path=GENRE_MAP_PATH)
	mapper.dump_unmapped_to_file()
