import pytest

from fetching.dataset_extractor import DatasetExtractor
import logging


@pytest.fixture
def mock_token(mocker):
	mocker.patch("os.environ.get", return_value="hf_token")
	return "hf_token"


@pytest.fixture
def mock_stream(mocker):
	mocker.patch("fetching.dataset_extractor.load_dataset", return_value=["test"])
	return ["test"]


class TestDatasetExtractorInit:
	def test_finds_token_from_env(self, mock_token):
		extractor = DatasetExtractor("test")
		assert extractor.dataset_name == "test", "Dataset name should be set"
		assert extractor.token is not None, "Token should be found"
		assert extractor.token == mock_token, "Token should be set"

	def test_default_logger(self, mocker):
		extractor = DatasetExtractor("test")
		assert extractor.logger is not None, "Logger should be initialized"
		assert isinstance(extractor.logger.handlers[0], logging.NullHandler), (
			"NullHandler should be added to logger"
		)

	def test_custom_logger(self, mocker):
		mock_logger = mocker.Mock()
		extractor = DatasetExtractor("test", logger=mock_logger)
		assert extractor.logger is mock_logger, "Logger should be initialized"
		mock_logger.addHandler.assert_not_called()


def loads_dataset(mock):
	mock.assert_called_once_with(
		"test_dataset", split="train", streaming=True, token="hf_token"
	)


class TestDatasetExtractorGetFullStream:
	def test_get_full_stream_calls_load_dataset(self, mocker, mock_token):
		mock_load = mocker.patch("fetching.dataset_extractor.load_dataset")
		extractor = DatasetExtractor("test_dataset")

		stream = extractor.get_full_stream()

		loads_dataset(mock_load)
		assert stream == mock_load.return_value

	def test_get_full_stream_logs_initialization(self, mocker, mock_token):
		mocker.patch("fetching.dataset_extractor.load_dataset")
		mock_logger = mocker.Mock()
		extractor = DatasetExtractor("test_dataset", logger=mock_logger)

		extractor.get_full_stream()

		mock_logger.info.assert_called_once_with(
			"Initializing full Hugging Face stream..."
		)


class TestDatasetExtractorGetAllBookIds:
	def test_get_all_book_ids_calls_load_dataset(self, mocker, mock_token):
		mock_load = mocker.patch("fetching.dataset_extractor.load_dataset")
		extractor = DatasetExtractor("test_dataset")
		extractor.get_all_book_ids()

		loads_dataset(mock_load)

	def test_get_all_book_ids_logs_initialization(self, mocker, mock_token):
		mocker.patch("fetching.dataset_extractor.load_dataset")
		mock_logger = mocker.Mock()
		extractor = DatasetExtractor("test_dataset", logger=mock_logger)

		extractor.get_all_book_ids()

		mock_logger.info.assert_has_calls(
			[
				mocker.call("Initializing Hugging Face stream..."),
				mocker.call("Extracting IDs (this will be very fast)..."),
				mocker.call("Finished! Total distinct books: 0"),
			]
		)

	def test_get_all_book_ids_limit(self, mocker, mock_token, mock_dataset_stream):
		mock_load = mocker.patch("fetching.dataset_extractor.load_dataset")
		mock_load.return_value = mock_dataset_stream
		extractor = DatasetExtractor("test_dataset")
		book_ids = extractor.get_all_book_ids(limit=3)

		loads_dataset(mock_load)
		mock_load.return_value.select_columns.assert_called_once_with(["id"])
		assert len(book_ids) == 3

	def test_logs_every_5000_books(self, mocker, mock_dataset_stream_long):
		mock_load = mocker.patch("fetching.dataset_extractor.load_dataset")
		mock_load.return_value = mock_dataset_stream_long
  
		extractor = DatasetExtractor("test_dataset")
		extractor.logger = mocker.Mock()

		extractor.get_all_book_ids()

		extractor.logger.info.assert_has_calls(
			[
				mocker.call("Extracting IDs (this will be very fast)..."),
				mocker.call("Extracted 5000 IDs..."),
				mocker.call("Finished! Total distinct books: 5000"),
			]	
		)