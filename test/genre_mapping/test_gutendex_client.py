from math import ceil

from genre_mapping.gutendex_client import GutendexClient
import pytest
import logging
import requests


class TestGutendexClientInit:
	def test_gutendex_client_init(self, mocker):
		"""Test the initialization of the GutendexClient."""
		gutendex_client = GutendexClient()

		assert isinstance(gutendex_client.batch_size, int), "Batch size should be set"
		assert isinstance(gutendex_client.timeout, int), "Timeout should be set"
		assert isinstance(gutendex_client.sleep_time, float), "Sleep time should be set"
		assert isinstance(gutendex_client.base_url, str), "Base URL should be set"
		assert isinstance(gutendex_client.logger, logging.Logger), (
			"Logger should be set"
		)
		assert isinstance(gutendex_client.logger.handlers[0], logging.NullHandler), (
			"NullHandler should be added to logger"
		)

	def test_gutendex_client_init_handles_custom_batch_size(self, mocker):
		"""Test the initialization of the GutendexClient with a custom batch size."""
		gutendex_client = GutendexClient(batch_size=10)

		assert gutendex_client.batch_size == 10, "Batch size should be set"

	def test_gutendex_client_init_handles_custom_timeout(self, mocker):
		"""Test the initialization of the GutendexClient with a custom timeout."""
		gutendex_client = GutendexClient(timeout=15)

		assert gutendex_client.timeout == 15, "Timeout should be set"

	def test_gutendex_client_init_handles_custom_sleep_time(self, mocker):
		"""Test the initialization of the GutendexClient with a custom sleep time."""
		gutendex_client = GutendexClient(sleep_time=0.5)

		assert gutendex_client.sleep_time == 0.5, "Sleep time should be set"

	def test_gutendex_client_init_handles_custom_logger(self, mocker):
		"""Test the initialization of the GutendexClient with a custom logger."""
		mock_logger = mocker.Mock()
		gutendex_client = GutendexClient(logger=mock_logger)

		assert gutendex_client.logger is mock_logger, "Logger should be set"
		mock_logger.addHandler.assert_not_called()


class TestGutendexClientFetchRawBookshelves:
	@pytest.fixture
	def gutendex_results_dynamic(self, mocker, mock_gutendex_bookshelves):
		"""Provide a dynamic set of Gutendex results for testing."""

		def _gutendex_results_dynamic(url, *args, **kwargs):
			"""Dynamically generate Gutendex results for testing."""
			ids = url.split("?ids=")[-1].split(",")
			results = []
			for book in mock_gutendex_bookshelves:
				if book["id"] in ids:
					results.append(
						{
							"id": book["id"],
							"bookshelves": book["bookshelves"],
						}
					)
			result_obj = mocker.Mock()
			result_obj.json.return_value = {
				"results": results,
			}
			result_obj.raise_for_status.return_value = None
			return result_obj

		return mocker.patch(
			"genre_mapping.gutendex_client.requests.get",
			side_effect=_gutendex_results_dynamic,
		)

	def test_fetch_raw_bookshelves(
		self, mocker, gutendex_results_dynamic, mock_gutendex_bookshelves
	):
		"""Test the fetching of raw bookshelves from the Gutendex API."""
		mocker.patch("genre_mapping.gutendex_client.time.sleep")
		gutendex_client = GutendexClient(batch_size=2)
		book_ids = [book["id"] for book in mock_gutendex_bookshelves]

		raw_bookshelves = gutendex_client.fetch_raw_bookshelves(book_ids)

		assert gutendex_results_dynamic.call_count == ceil(len(book_ids) / 2), (
			"fetch_raw_bookshelves should call the API for each batch "
			f"with a batch size of {gutendex_client.batch_size}, and "
			f"{len(book_ids)} books, the API should be called "
			f"{ceil(len(book_ids) / gutendex_client.batch_size)} times. "
			f"It was called {gutendex_results_dynamic.call_count} times."
		)
		assert len(raw_bookshelves) == len(book_ids), (
			"Raw bookshelves should be a dictionary of book IDs to bookshelves"
		)

	def test_fetch_raw_bookshelves_empty_list(self, mocker):
		"""Test the handling of an empty list of book IDs."""

		def _gutendex_results_empty(url, *args, **kwargs):
			"""Dynamically generate Gutendex results for testing."""
			result_obj = mocker.Mock()
			result_obj.json.return_value = {
				"results": [],
			}
			result_obj.raise_for_status.return_value = None
			return result_obj

		mocker.patch(
			"genre_mapping.gutendex_client.requests.get",
			side_effect=_gutendex_results_empty,
		)

		gutendex_client = GutendexClient(batch_size=2)

		raw_bookshelves = gutendex_client.fetch_raw_bookshelves([])

		assert raw_bookshelves == {}, "Raw bookshelves should be an empty dictionary"

	errors = [
		{
			"error_type": requests.exceptions.ConnectionError,
			"error_message": "Simulated Connection Error",
		},
		{
			"error_type": requests.exceptions.Timeout,
			"error_message": "Simulated Timeout",
		},
		{
			"error_type": requests.exceptions.HTTPError,
			"error_message": "Simulated HTTP Error",
		},
	]

	@pytest.mark.parametrize("error", [error for error in errors])
	def test_fetch_raw_bookshelves_request_exception(
		self, mocker, mock_gutendex_bookshelves, error
	):
		"""Test the handling of a request exception from the Gutendex API."""
		mocker.patch("genre_mapping.gutendex_client.time.sleep")
		mock_get = mocker.patch("genre_mapping.gutendex_client.requests.get")
		if error["error_type"] == requests.exceptions.HTTPError:
			mock_response = mocker.Mock()
			mock_response.raise_for_status.side_effect = error["error_type"](error["error_message"])
			mock_get.return_value = mock_response
		else:
			mock_get.side_effect = error["error_type"](error["error_message"])
		gutendex_client = GutendexClient(batch_size=2)
		gutendex_client.logger = mocker.Mock()
		book_ids = [book["id"] for book in mock_gutendex_bookshelves]

		raw_bookshelves = gutendex_client.fetch_raw_bookshelves(book_ids)

		assert raw_bookshelves == {}, "Raw bookshelves should be an empty dictionary"

		gutendex_client.logger.warning.assert_has_calls(
			[
				mocker.call(f"\nNetwork error on batch 1: {error['error_message']}"),
				mocker.call("Skipping this batch and continuing to the next one..."),
			]
		)
