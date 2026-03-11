import pytest
import logging
from easy_logging import EasyFormatter

from utils.logging import TqdmLoggingHandler, get_logger, get_logger_tqdm


@pytest.fixture
def log_record():
	"""Provide a standard LogRecord for handler emission testing."""
	return logging.LogRecord(
		name="test_logger",
		level=logging.INFO,
		pathname="test.py",
		lineno=1,
		msg="Test message",
		args=(),
		exc_info=None,
	)


class TestTqdmLoggingHandler:
	"""Tests covering the custom TqdmLoggingHandler."""

	def test_emit_success(self, mocker, log_record):
		"""Verify emit formats the record and correctly routes it to tqdm.write."""
		mock_tqdm_write = mocker.patch("tqdm.tqdm.write")
		handler = TqdmLoggingHandler()
		handler.setFormatter(logging.Formatter("%(message)s"))
		mock_flush = mocker.patch.object(handler, "flush")

		handler.emit(log_record)

		mock_tqdm_write.assert_called_once_with("Test message")
		mock_flush.assert_called_once()

	def test_emit_exception_handling(self, mocker, log_record):
		"""Verify that emit catches internal exceptions and safely delegates to handleError."""
		mocker.patch("tqdm.tqdm.write", side_effect=Exception("Terminal disconnected"))
		handler = TqdmLoggingHandler()
		mock_handle_error = mocker.patch.object(handler, "handleError")

		handler.emit(log_record)

		mock_handle_error.assert_called_once_with(log_record)


class TestLoggerFactories:
	"""Tests covering both logger initialization functions."""

	@pytest.mark.parametrize(
		"factory_func, expected_handler, level, expected_propagate",
		[
			(get_logger, logging.StreamHandler, logging.INFO, True),
			(get_logger_tqdm, TqdmLoggingHandler, logging.WARNING, False),
		],
		ids=["standard_logger", "tqdm_logger"],
	)
	def test_logger_initialization(
		self, factory_func, expected_handler, level, expected_propagate
	):
		"""Verify factory functions attach the correct handler, formatter, and properties."""
		logger_name = f"test_{factory_func.__name__}"
		logger = factory_func(logger_name, level=level)

		assert logger.name == logger_name
		assert logger.level == level
		assert len(logger.handlers) == 1

		handler = logger.handlers[0]
		assert isinstance(handler, expected_handler)
		assert isinstance(handler.formatter, EasyFormatter)

		if not expected_propagate:
			assert logger.propagate is False

	@pytest.mark.parametrize(
		"factory_func",
		[get_logger, get_logger_tqdm],
		ids=["standard_logger", "tqdm_logger"],
	)
	def test_logger_singleton_behavior(self, factory_func):
		"""Verify multiple setup calls do not attach duplicate handlers."""
		logger_name = f"test_singleton_{factory_func.__name__}"

		logger1 = factory_func(logger_name)
		logger2 = factory_func(logger_name)

		assert logger1 is logger2
		assert len(logger1.handlers) == 1
