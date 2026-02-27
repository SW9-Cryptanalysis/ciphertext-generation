import logging
import time
import requests


class GutendexClient:
	"""Handles network requests to the Gutendex API."""

	def __init__(
		self,
		batch_size: int = 35,
		timeout: int = 15,
		sleep_time: float = 1.0,
		logger: logging.Logger | None = None,
	) -> None:
		"""Initialize the GutendexClient.

		Args:
			batch_size (int, optional): Number of books to fetch in each batch.
				Defaults to 35.
			timeout (int, optional): Timeout for each request (in seconds).
				Defaults to 15.
			sleep_time (float, optional): Sleep time between requests (in seconds).
				Defaults to 1.0.
			logger (logging.Logger | None, optional): Logger to use. Defaults to None.

		"""
		self.batch_size = batch_size
		self.timeout = timeout
		self.sleep_time = sleep_time
		self.base_url = "https://gutendex.com/books/"
		# If no logger is provided, create a mock one which will not log anywhere
		if not logger:
			self.logger = logging.Logger("GutendexClient")
			self.logger.addHandler(logging.NullHandler())
		else:
			self.logger = logger

	def fetch_raw_bookshelves(self, book_ids: list[str]) -> dict[str, list[str]]:
		"""Fetch raw bookshelves from the API in batches."""
		raw_map = {}
		total_batches = (len(book_ids) + self.batch_size - 1) // self.batch_size

		self.logger.info(
			f"Starting batch extraction ({total_batches} total network "
			"requests needed)...",
		)

		for i in range(0, len(book_ids), self.batch_size):
			batch = book_ids[i : i + self.batch_size]
			ids_param = ",".join(batch)
			url = f"{self.base_url}?ids={ids_param}"

			current_batch_num = (i // self.batch_size) + 1

			try:
				response = requests.get(url, timeout=self.timeout)
				response.raise_for_status()
				data = response.json()

				for book in data.get("results", []):
					book_id = str(book["id"])
					raw_map[book_id] = book.get("bookshelves", [])

			except requests.exceptions.RequestException as e:
				self.logger.warning(
					f"\nNetwork error on batch {current_batch_num}: {e}",
				)
				self.logger.warning(
					"Skipping this batch and continuing to the next one...",
				)

			if current_batch_num % 50 == 0 or current_batch_num == total_batches:
				self.logger.info(
					f"Processed batch {current_batch_num}/{total_batches}...",
				)

			time.sleep(self.sleep_time)

		return raw_map
