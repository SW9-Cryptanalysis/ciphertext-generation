from datasets import load_dataset
import os
import dotenv
import logging
from itertools import islice
from datasets import IterableDataset

dotenv.load_dotenv()


class DatasetExtractor:
	"""A class for extracting dataset from Hugging Face."""

	def __init__(self, dataset_name: str, logger: logging.Logger | None = None) -> None:
		"""Initialize the DatasetExtractor with the dataset name and split.

		Args:
			dataset_name (str): The name of the dataset to extract.
			split (str): The split of the dataset to extract.
			logger (logging.Logger | None, optional): Logger to use. Defaults to None.

		"""
		self.dataset_name = dataset_name
		self.token = os.environ.get("HF_TOKEN")
		# If no logger is provided, create a mock one which will not log anywhere
		if not logger:
			self.logger = logging.Logger("DatasetExtractor")
			self.logger.addHandler(logging.NullHandler())
			self.logger.setLevel(logging.CRITICAL)
		else:
			self.logger = logger

	def get_full_stream(self) -> IterableDataset:
		"""Get the full Hugging Face stream.

		Returns:
			IterableDataset: The full Hugging Face stream.

		"""
		if hasattr(self, "logger"):
			self.logger.info("Initializing full Hugging Face stream...")

		return load_dataset(
			self.dataset_name,
			split="train",
			streaming=True,
			token=self.token,
		)

	def get_all_book_ids(self, limit: int | None = None) -> list[str]:
		"""Extract book IDs from the dataset while skipping the text payload."""
		self.logger.info("Initializing Hugging Face stream...")

		stream = load_dataset(
			self.dataset_name,
			split="train",
			streaming=True,
			token=self.token,
		).select_columns(["id"])

		book_ids = []
		self.logger.info("Extracting IDs (this will be very fast)...")

		# Apply the limit if one is provided, otherwise process the whole stream
		stream_iter = islice(stream, 0, limit) if limit else stream

		for row in stream_iter:
			book_ids.append(str(row["id"]))

			if len(book_ids) % 5000 == 0:
				self.logger.info(f"Extracted {len(book_ids)} IDs...")

		unique_ids = list(set(book_ids))
		self.logger.info(f"Finished! Total distinct books: {len(unique_ids)}")
		return unique_ids
