import pytest
import logging
import certifi
from fetching.dataset_extractor import DatasetExtractor
from datasets import IterableDataset


@pytest.fixture
def valid_multi_config():
	"""Provide a valid multi-dataset configuration array."""
	return [
		{
			"path": "common-pile/project_gutenberg_filtered",
			"type": "project_gutenberg",
			"split_name": "train",
			"column": "text",
			"prefix": "pg",
			"fallback_genres": ["Other / Uncategorized"],
		},
		{
			"path": "common-pile/arxiv_papers_filtered",
			"type": "technical",
			"split_name": "train",
			"column": "content",
			"prefix": "arxiv",
			"fallback_genres": ["Academic Papers"],
		},
	]

TITLE_TEST_CASES = [
	# --- 1. The "Happy Paths" (Standard Formatting) ---
	(
		"# My Perfect Title\n\nThis is the first paragraph.", 
		"My Perfect Title", 
		"Standard Markdown H1"
	),
	(
		"A Standard Plaintext Title\n\nAnd here is the body of the paper.", 
		"A Standard Plaintext Title", 
		"Standard plaintext first block"
	),

	# --- 2. Empty and Invalid Inputs ---
	(None, "unknown", "None type input"),
	("", "unknown", "Empty string"),
	("    \n   \t  ", "unknown", "Whitespace-only string"),
	(12345, "unknown", "Integer input (type safety)"),

	# --- 3. Whitespace and Linebreak Chaos ---
	(
		"   #    Title   with   Crazy    Spaces    \n\nBody", 
		"Title with Crazy Spaces", 
		"Extreme internal and leading whitespace"
	),
	(
		"# A Very Long\nTitle That Spans\nMultiple Lines\n\nFirst paragraph.", 
		"A Very Long Title That Spans Multiple Lines", 
		"Multiline markdown title with linebreaks inside the block"
	),
	(
		"\n\n\n# Deeply Pushed Title\n\nBody text.", 
		"Deeply Pushed Title", 
		"Title preceded by multiple blank lines"
	),

	# --- 4. URL Stripping Triggers ---
	(
		"# Title With a Link http://arxiv.org/abs/123\n\nBody", 
		"Title With a Link", 
		"Standard HTTP link stripping"
	),
	(
		"Another Title https://github.com/repo\n\nBody", 
		"Another Title", 
		"HTTPS link stripping (since 'http' is a substring)"
	),
	(
		"http://example.com/no-title-just-link\n\nBody", 
		"unknown", 
		"First block is entirely a URL"
	),

	# --- Markdown Edge Cases ---
	(
		"## A Secondary Header\n\nBody", 
		"A Secondary Header", 
		"H2 header (strips both #s)"
	),
	(
		"#Title Without Space\n\nBody", 
		"Title Without Space", 
		"Markdown H1 missing the space after the hash"
	),

	# --- 6. Current Heuristic Limitations ---
	(
		"Title Without Double Newlines\nThis is immediately followed by the abstract. No blank lines exist.\nWe just keep typing.", 
		"Title Without Double Newlines This is immediately followed by the abstract. No blank lines exist. We just keep typing.", 
		"No double newlines means the entire document is treated as the title block"
	),
	(
		"# Understanding HTTP and FTP Protocols\n\nBody", 
		"Understanding HTTP and FTP Protocols", 
		"'HTTP' is uppercase, so .find('http') misses it (case-sensitivity)"
	),
]


@pytest.fixture(autouse=True)
def mock_token(monkeypatch):
	"""Provide a mock Hugging Face token."""
	monkeypatch.setenv("HF_TOKEN", "fake_mock_token")
	return "fake_mock_token"


@pytest.fixture
def mock_dataset_stream(mocker):
	"""Provide a mock dataset that handles select_columns and iteration."""
	mock_ds = mocker.Mock()
	mock_ds.select_columns.return_value = [
		{"id": 101},
		{"id": 202},
		{"id": 303},
	]
	return mock_ds


def loads_datasets(mock):
	"""Assert that load_dataset was called with the expected baseline arguments."""


class TestDatasetExtractorInit:
	def test_finds_token_from_env(self, mock_token, valid_multi_config):
		"""Test token extraction from environment variables."""
		extractor = DatasetExtractor(valid_multi_config)
		assert getattr(extractor, "configs", None) == valid_multi_config, (
			"Configs should be set to the provided array"
		)
		assert extractor.token is not None, "Token should be found"
		assert extractor.token == mock_token, "Token should be set"

	def test_default_logger(self, valid_multi_config):
		"""Test fallback logger initialization."""
		extractor = DatasetExtractor(valid_multi_config)
		assert extractor.logger is not None, "Logger should be initialized"
		assert isinstance(extractor.logger.handlers[0], logging.NullHandler), (
			"NullHandler should be added to logger"
		)

	def test_custom_logger(self, mocker, valid_multi_config):
		"""Test injected logger handling."""
		mock_logger = mocker.Mock()
		extractor = DatasetExtractor(valid_multi_config, logger=mock_logger)
		assert extractor.logger is mock_logger, "Logger should be initialized"
		mock_logger.addHandler.assert_not_called()

	def fails_on_string_name(self):
		"""Test that a string name fails to initialize."""
		with pytest.raises(
			TypeError, match="Must be a list of dictionaries"
		) as excinfo:
			DatasetExtractor("test")  # type: ignore
		assert "Dataset must be a valid array of dictionaries" in str(excinfo.value)


class TestDatasetExtractorGetFullStream:
	def test_get_full_stream_calls_load_dataset(self, mocker, valid_multi_config):
		"""Test standard dataset loading."""
		mock_load = mocker.patch("fetching.dataset_extractor.load_dataset")
		mock_interleave = mocker.patch("fetching.dataset_extractor.interleave_datasets")
		extractor = DatasetExtractor(valid_multi_config)

		extractor.get_full_stream()

		mock_load.assert_any_call(
			"common-pile/project_gutenberg_filtered",
			split="train",
			streaming=True,
			token="fake_mock_token",
		)
		mock_load.assert_any_call(
			"common-pile/arxiv_papers_filtered",
			split="train",
			streaming=True,
			token="fake_mock_token",
		)

		mock_interleave.assert_called_once()

	def test_get_full_stream_logs_initialization(self, mocker, valid_multi_config):
		"""Test logging during full stream initialization."""
		mocker.patch("fetching.dataset_extractor.load_dataset")
		mocker.patch("fetching.dataset_extractor.interleave_datasets")
		mock_logger = mocker.Mock()
		extractor = DatasetExtractor(valid_multi_config, logger=mock_logger)

		extractor.get_full_stream()

		mock_logger.info.assert_called_once_with(
			"Initializing full Hugging Face stream..."
		)


class TestDatasetExtractorGetIdStream:
	def test_get_id_stream_calls_load_dataset_and_yields_strings(
		self, mocker, mock_dataset_stream, valid_multi_config
	):
		"""Test that the stream properly filters columns and yields string IDs."""
		mock_load = mocker.patch(
			"fetching.dataset_extractor.load_dataset", return_value=mock_dataset_stream
		)
		extractor = DatasetExtractor(valid_multi_config)

		stream_gen = extractor.get_pg_id_stream()
		results = list(stream_gen)

		mock_load.assert_called_once_with(
			"common-pile/project_gutenberg_filtered",
			split="train",
			streaming=True,
			token="fake_mock_token",
		)
		mock_dataset_stream.select_columns.assert_called_once_with(["id"])

		assert results == ["101", "202", "303"], "IDs should be yielded as strings"

	def test_get_pg_id_stream_no_pg(
		self, mocker, mock_dataset_stream, valid_multi_config
	):
		"""Test that the stream properly filters columns and yields string IDs."""
		mocker.patch(
			"fetching.dataset_extractor.load_dataset", return_value=mock_dataset_stream
		)
		new_config = valid_multi_config.copy()
		new_config[0]["type"] = "not_pg"
		extractor = DatasetExtractor(new_config)

		stream = extractor.get_pg_id_stream()

		with pytest.raises(
			ValueError, match="No Project Gutenberg dataset found in config."
		):
			next(stream)
   
class TestDatasetExtractorTitelExtraction:
	@pytest.mark.parametrize("text, expected, description", TITLE_TEST_CASES)
	def test_extract_title_from_text(self, text, expected, description):
		"""Test the extraction of a title from a raw text."""
		extractor = DatasetExtractor([])
		result = extractor._extract_title_from_text(text)
		assert result == expected, f"Failed on: {description}"



@pytest.mark.integration
def test_real_huggingface_stream_interleaves_multiple_sources(monkeypatch):
	"""Verify the extractor successfully interleaves multiple real datasets and normalizes schemas.

	This test requires an active internet connection and valid Hugging Face access.
	"""
	monkeypatch.setenv("SSL_CERT_FILE", certifi.where())
	monkeypatch.delenv("HF_TOKEN", raising=False)

	extractor = DatasetExtractor(
		[
			{
				"path": "common-pile/project_gutenberg_filtered",
				"type": "project_gutenberg",
				"split_name": "train",
				"column": "text",
				"prefix": "pg",
				"fallback_genres": ["Other / Uncategorized"],
			},
			{
				"path": "common-pile/arxiv_papers_filtered",
				"type": "arxiv_papers",
				"split_name": "train",
				"column": "text",
				"prefix": "arxiv",
				"fallback_genres": ["Academic Papers"],
			},
		]
	)

	stream = extractor.get_full_stream()
	assert isinstance(stream, IterableDataset)

	stream_iter = iter(stream)

	expected_keys = {
		"id",
		"text",
		"source_name",
		"prefix",
		"source_type",
		"fallback_genres",
	}

	found_prefixes = set()

	for _ in range(4):
		item = next(stream_iter)

		assert set(item.keys()) == expected_keys
		assert isinstance(item["text"], str)
		assert isinstance(item["id"], str)

		found_prefixes.add(item["prefix"])

	assert "pg" in found_prefixes, "Stream did not yield any Gutenberg records."
	assert "arxiv" in found_prefixes, "Stream did not yield any arXiv records."
