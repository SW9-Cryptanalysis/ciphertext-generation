import pytest
import logging
from fetching.dataset_extractor import DatasetExtractor


@pytest.fixture
def mock_token(mocker):
    """Provide a mock Hugging Face token."""
    mocker.patch("os.environ.get", return_value="hf_token")
    return "hf_token"


@pytest.fixture
def mock_dataset_stream(mocker):
    """Provide a mock dataset that handles select_columns and iteration."""
    mock_ds = mocker.Mock()
    mock_ds.select_columns.return_value = [
        {"id": 101},
        {"id": "202"},
        {"id": 303},
    ]
    return mock_ds


def loads_dataset(mock):
    """Assert that load_dataset was called with the expected baseline arguments."""
    mock.assert_called_once_with(
        "test_dataset", split="train", streaming=True, token="hf_token"
    )


class TestDatasetExtractorInit:
    def test_finds_token_from_env(self, mock_token):
        """Test token extraction from environment variables."""
        extractor = DatasetExtractor("test")
        assert extractor.dataset_name == "test", "Dataset name should be set"
        assert extractor.token is not None, "Token should be found"
        assert extractor.token == mock_token, "Token should be set"

    def test_default_logger(self, mocker):
        """Test fallback logger initialization."""
        extractor = DatasetExtractor("test")
        assert extractor.logger is not None, "Logger should be initialized"
        assert isinstance(extractor.logger.handlers[0], logging.NullHandler), (
            "NullHandler should be added to logger"
        )

    def test_custom_logger(self, mocker):
        """Test injected logger handling."""
        mock_logger = mocker.Mock()
        extractor = DatasetExtractor("test", logger=mock_logger)
        assert extractor.logger is mock_logger, "Logger should be initialized"
        mock_logger.addHandler.assert_not_called()


class TestDatasetExtractorGetFullStream:
    def test_get_full_stream_calls_load_dataset(self, mocker, mock_token):
        """Test standard dataset loading."""
        mock_load = mocker.patch("fetching.dataset_extractor.load_dataset")
        extractor = DatasetExtractor("test_dataset")

        stream = extractor.get_full_stream()

        loads_dataset(mock_load)
        assert stream == mock_load.return_value

    def test_get_full_stream_logs_initialization(self, mocker, mock_token):
        """Test logging during full stream initialization."""
        mocker.patch("fetching.dataset_extractor.load_dataset")
        mock_logger = mocker.Mock()
        extractor = DatasetExtractor("test_dataset", logger=mock_logger)

        extractor.get_full_stream()

        mock_logger.info.assert_called_once_with(
            "Initializing full Hugging Face stream..."
        )


class TestDatasetExtractorGetIdStream:
    def test_get_id_stream_calls_load_dataset_and_yields_strings(
        self, mocker, mock_token, mock_dataset_stream
    ):
        """Test that the stream properly filters columns and yields string IDs."""
        mock_load = mocker.patch(
            "fetching.dataset_extractor.load_dataset", return_value=mock_dataset_stream
        )
        extractor = DatasetExtractor("test_dataset")

        stream_gen = extractor.get_id_stream()
        results = list(stream_gen)

        loads_dataset(mock_load)
        mock_dataset_stream.select_columns.assert_called_once_with(["id"])

        assert results == ["101", "202", "303"], "IDs should be yielded as strings"
