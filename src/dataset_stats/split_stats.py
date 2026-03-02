from collections import Counter
from dataclasses import dataclass


@dataclass
class BucketSizes:
	"""A dataclass to store the bucket sizes for length and homophones."""

	length: int = 500
	homophones: int = 100
	redundancy: int = 1

	def __post_init__(self) -> None:
		"""Validate the bucket sizes."""
		for size in [self.length, self.homophones, self.redundancy]:
			if size <= 0:
				raise ValueError(f"Bucket size must be greater than 0: {size}")


class SplitStats:
	"""A class for keeping track of split-specific statistics (each dataset).

	Attributes:
		total_count (int): The total number of items in the dataset.
		length_distribution (Counter): A Counter object for the length distribution.
		homophone_distribution (Counter): A Counter object for the homophone
			distribution.
		redundancy_distribution (Counter): A Counter object for the redundancy
			distribution.
		genre_distribution (Counter): A Counter object for the genre distribution.
		min_length (int): The minimum length in the dataset.
		max_length (int): The maximum length in the dataset.
		min_homophones (int): The minimum number of homophones in the dataset.
		max_homophones (int): The maximum number of homophones in the dataset.

	"""

	def __init__(self) -> None:
		"""Initialize the DatasetStatsAggregator with default values."""
		self._bucket_sizes = BucketSizes()

		self.total_count = 0
		self.length_distribution = Counter()
		self.homophone_distribution = Counter()
		self.redundancy_distribution = Counter()
		self.genre_distribution = Counter()
		self.min_homophones = float("inf")
		self.max_homophones = 0
		self.min_length = float("inf")
		self.max_length = 0

	def _get_bucket(self, value: int, size: int) -> int:
		"""Get the bucket index for a given value and size.

		Args:
			value (int): The value to get the bucket for.
			size (int): The size of the buckets.

		Returns:
			int: The bucket index.

		"""
		return (value // size) * size

	def update(
		self, length: int, homophones: int, difficulty: int, genres: list[str],
	) -> None:
		"""Update the dataset statistics with a new item (cipher).

		Args:
			length (int): The length of the cipher.
			homophones (int): The number of homophones in the cipher.
			difficulty (int): The difficulty level of the cipher.
			genres (list[str]): The genres of the book used to generate the
				cipher.

		"""
		self.total_count += 1
		self.length_distribution[
			self._get_bucket(length, self._bucket_sizes.length)
		] += 1
		self.homophone_distribution[
			self._get_bucket(homophones, self._bucket_sizes.homophones)
		] += 1
		self.redundancy_distribution[
			self._get_bucket(difficulty, self._bucket_sizes.redundancy)
		] += 1

		self.min_length = min(self.min_length, length)
		self.max_length = max(self.max_length, length)
		self.min_homophones = min(self.min_homophones, homophones)
		self.max_homophones = max(self.max_homophones, homophones)

		for genre in genres:
			self.genre_distribution[genre] += 1

	def merge(self, other: "SplitStats") -> None:
		"""Merge another SplitStats into this one.

		Args:
			other (SplitStats): The other SplitStats to merge into this one.

		"""
		self.total_count += other.total_count
		self.length_distribution.update(other.length_distribution)
		self.homophone_distribution.update(other.homophone_distribution)
		self.redundancy_distribution.update(other.redundancy_distribution)
		self.genre_distribution.update(other.genre_distribution)
		self.min_length = min(self.min_length, other.min_length)
		self.max_length = max(self.max_length, other.max_length)
		self.min_homophones = min(self.min_homophones, other.min_homophones)
		self.max_homophones = max(self.max_homophones, other.max_homophones)

	def __json__(self) -> dict:
		"""Return a JSON-serializable representation of DatasetStatsAggregator object.

		Returns:
			dict: A dictionary containing DatasetStatsAggregator object's attributes.

		"""
		return {
			"total_count": self.total_count,
			"length_distribution": self._format_dist(
				self.length_distribution, self._bucket_sizes.length,
			),
			"homophone_distribution": self._format_dist(
				self.homophone_distribution, self._bucket_sizes.homophones,
			),
			"redundancy_distribution": self._format_dist(
				self.redundancy_distribution, self._bucket_sizes.redundancy,
			),
			"genre_distribution": dict(self.genre_distribution),
			"min_length": self.min_length,
			"max_length": self.max_length,
			"min_homophones": self.min_homophones,
			"max_homophones": self.max_homophones,
		}

	def _format_dist(self, counter: Counter, size: int) -> dict:
		"""Format a Counter object into a dictionary with buckets.

		Args:
			counter (Counter): The Counter object to format.
			size (int): The size of the buckets.

		Returns:
			dict: A dictionary with buckets as keys and counts as values.

		"""
		if not size > 1:
			return {f"{k}": v for k, v in sorted(counter.items())}
		return {f"{k}-{k + size - 1}": v for k, v in sorted(counter.items())}
