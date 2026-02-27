import os
import json
import logging
import pytest
from pathlib import Path

from genre_mapping.genre_mapper import GenreMapper
from fetching.dataset_extractor import DatasetExtractor
from genre_mapping.gutendex_client import GutendexClient
from genre_mapping.taxonomy_mapper import TaxonomyMapper


@pytest.fixture
def mock_dependencies(mocker):
	"""Provides mocked instances of the three main dependencies."""
	return {
		"extractor": mocker.Mock(spec=DatasetExtractor),
		"api_client": mocker.Mock(spec=GutendexClient),
		"mapper": mocker.Mock(spec=TaxonomyMapper),
	}


class TestGenreMapperInit:
	def test_init_without_logger(self, mock_dependencies):
		"""Test initialization falls back to a NullHandler if no logger is provided."""
		genre_mapper = GenreMapper(
			mock_dependencies["extractor"],
			mock_dependencies["api_client"],
			mock_dependencies["mapper"],
		)

		assert genre_mapper.logger.name == "GenreMapper", (
			"Should set default logger name"
		)
		assert any(
			isinstance(h, logging.NullHandler) for h in genre_mapper.logger.handlers
		), "Should safely attach a NullHandler"

	def test_init_with_logger(self, mock_dependencies):
		"""Test initialization correctly attaches an injected logger."""
		custom_logger = logging.getLogger("CustomTestLogger")
		genre_mapper = GenreMapper(
			mock_dependencies["extractor"],
			mock_dependencies["api_client"],
			mock_dependencies["mapper"],
			logger=custom_logger,
		)

		assert genre_mapper.logger == custom_logger, "Should use the injected logger"


class TestGenreMapperRun:
	def test_run_orchestrates_pipeline(self, mocker, mock_dependencies):
		"""Test that run() correctly calls the dependencies in the right order."""

		mock_dependencies["extractor"].get_all_book_ids.return_value = ["1001", "1002"]
		mock_dependencies["api_client"].fetch_raw_bookshelves.return_value = {
			"1001": ["Category: Science Fiction"],
			"1002": ["Mystery"],
		}

		def mock_extract_genres(shelves):
			if "Mystery" in shelves:
				return ["Mystery & Fiction"]
			return ["Sci-Fi & Fantasy"]

		mock_dependencies[
			"mapper"
		].extract_mapped_genres.side_effect = mock_extract_genres

		genre_mapper = GenreMapper(**mock_dependencies)
		genre_mapper.logger = mocker.Mock()
		mock_save_to_json = mocker.patch.object(genre_mapper, "_save_to_json")

		result = genre_mapper.run(limit=50, output_path="dummy_path.json")

		mock_dependencies["extractor"].get_all_book_ids.assert_called_once_with(
			limit=50
		)
		mock_dependencies["api_client"].fetch_raw_bookshelves.assert_called_once_with(
			["1001", "1002"]
		)

		assert mock_dependencies["mapper"].extract_mapped_genres.call_count == 2

		expected_result = {"1001": ["Sci-Fi & Fantasy"], "1002": ["Mystery & Fiction"]}
		assert result == expected_result

		mock_save_to_json.assert_called_once_with(expected_result, "dummy_path.json")
		genre_mapper.logger.info.assert_called_once_with(
			"Successfully mapped genres for 2 books!"
		)


class TestGenreMapperSaveToJson:
	def test_save_to_json_creates_directories_and_file(
		self, tmp_path: Path, mock_dependencies
	):
		"""Test that data is correctly serialized to disk and nested folders are created."""
		genre_mapper = GenreMapper(**mock_dependencies)
		genre_mapper.logger = logging.getLogger("dummy")

		test_file_path = tmp_path / "deeply" / "nested" / "folder" / "test_output.json"

		test_data = {"1001": ["History", "Romance"]}

		genre_mapper._save_to_json(test_data, str(test_file_path))

		assert test_file_path.exists(), "The JSON file should have been created on disk"

		with open(test_file_path, "r", encoding="utf-8") as f:
			saved_data = json.load(f)

		assert saved_data == test_data, (
			"The saved JSON should perfectly match the input dictionary"
		)
