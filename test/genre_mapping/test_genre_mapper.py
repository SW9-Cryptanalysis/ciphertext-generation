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
    def test_run_orchestrates_streaming_pipeline(self, mocker, mock_dependencies):
        """Test the streaming batch logic and intermediate checkpoint saving."""
        mock_dependencies["extractor"].get_id_stream.return_value = iter(
            ["1001", "1002", "1003"]
        )

        def mock_fetch(batch):
            """Simulate the Gutendex API returning raw shelves based on the batch."""
            return {bid: [f"Raw {bid}"] for bid in batch}

        mock_dependencies["api_client"].fetch_raw_bookshelves.side_effect = mock_fetch

        mock_dependencies["mapper"].extract_mapped_genres.side_effect = (
            lambda x: [f"Mapped {x[0]}"]
        )

        genre_mapper = GenreMapper(**mock_dependencies)

        mocker.patch.object(genre_mapper, "_load_existing_genre_map", return_value={})
        mock_save = mocker.patch.object(genre_mapper, "_save_to_json")

        result = genre_mapper.run(output_path="dummy.json", flush_size=2)

        expected_result = {
            "1001": ["Mapped Raw 1001"],
            "1002": ["Mapped Raw 1002"],
            "1003": ["Mapped Raw 1003"],
        }
        assert result == expected_result

        assert mock_dependencies["api_client"].fetch_raw_bookshelves.call_count == 2
        mock_dependencies["api_client"].fetch_raw_bookshelves.assert_any_call(
            ["1001", "1002"]
        )
        mock_dependencies["api_client"].fetch_raw_bookshelves.assert_any_call(["1003"])

        assert mock_save.call_count == 2

    def test_run_skips_existing_cached_ids(self, mocker, mock_dependencies):
        """Test that the cache prevents duplicate API calls for known books."""
        mock_dependencies["extractor"].get_id_stream.return_value = iter(
            ["1001", "1002"]
        )

        genre_mapper = GenreMapper(**mock_dependencies)

        mocker.patch.object(
            genre_mapper,
            "_load_existing_genre_map",
            return_value={"1001": ["Cached Genre"]},
        )
        mocker.patch.object(genre_mapper, "_save_to_json")

        mock_dependencies["api_client"].fetch_raw_bookshelves.return_value = {
            "1002": ["Raw 1002"]
        }
        mock_dependencies["mapper"].extract_mapped_genres.return_value = ["Mapped 1002"]

        result = genre_mapper.run(output_path="dummy.json", flush_size=5)

        mock_dependencies["api_client"].fetch_raw_bookshelves.assert_called_once_with(
            ["1002"]
        )

        assert result == {
            "1001": ["Cached Genre"],
            "1002": ["Mapped 1002"],
        }


class TestGenreMapperLoadExisting:
    def test_load_existing_success(self, tmp_path: Path, mock_dependencies):
        """Test successfully loading an existing valid JSON file."""
        genre_mapper = GenreMapper(**mock_dependencies)
        test_file = tmp_path / "cache.json"

        test_data = {"1001": ["Sci-Fi"]}
        test_file.write_text(json.dumps(test_data), encoding="utf-8")

        result = genre_mapper._load_existing_genre_map(str(test_file))
        assert result == test_data

    def test_load_existing_not_found(self, tmp_path: Path, mock_dependencies):
        """Test that an empty dictionary is returned if the file does not exist."""
        genre_mapper = GenreMapper(**mock_dependencies)
        missing_file = tmp_path / "does_not_exist.json"

        result = genre_mapper._load_existing_genre_map(str(missing_file))
        assert result == {}

    def test_load_existing_corrupted_json(self, tmp_path: Path, mock_dependencies):
        """Test that corrupted JSON is safely caught and returns an empty dictionary."""
        genre_mapper = GenreMapper(**mock_dependencies)
        genre_mapper.logger = logging.getLogger("dummy")
        
        corrupted_file = tmp_path / "corrupted.json"
        corrupted_file.write_text("{broken_json: true", encoding="utf-8")

        result = genre_mapper._load_existing_genre_map(str(corrupted_file))
        assert result == {}


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

        with open(test_file_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data == test_data, (
            "The saved JSON should perfectly match the input dictionary"
        )