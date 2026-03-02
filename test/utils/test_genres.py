from utils.genres import load_existing_genre_map
from pathlib import Path


class TestLoadExistingGenreMap:
	def test_load_existing_success(self, tmp_path: Path):
		"""Test successfully loading an existing valid JSONL file."""
		test_file = tmp_path / "cache.jsonl"

		test_file.write_text('{"id": "1001", "genres": ["Sci-Fi"]}\n', encoding="utf-8")

		result = load_existing_genre_map(test_file, None)
		assert result == {"1001": ["Sci-Fi"]}

	def test_load_existing_not_found(self, tmp_path: Path):
		"""Test that an empty dictionary is returned if the file does not exist."""
		missing_file = tmp_path / "does_not_exist.json"

		result = load_existing_genre_map(missing_file, None)
		assert result == {}

	def test_load_existing_corrupted_json(self, tmp_path: Path, mocker):
		"""Test that corrupted JSON is safely caught and returns an empty dictionary."""
		mock_logger = mocker.Mock()

		corrupted_file = tmp_path / "corrupted.json"
		corrupted_file.write_text("{broken_json: true", encoding="utf-8")

		result = load_existing_genre_map(corrupted_file, mock_logger)

		assert result == {}
		mock_logger.warning.assert_called_once()
		assert "Expecting property name enclosed in double quotes" in mock_logger.warning.call_args[0][0]
