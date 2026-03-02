from collections import defaultdict
from dataset_stats.split_stats import SplitStats
from typing import TypedDict, Unpack


class UpdateStats(TypedDict):
	"""A TypedDict for updating the DatasetStatsAggregator."""

	length: int
	homophones: int
	difficulty: int
	genres: list[str]


class DatasetStatsAggregator:
	"""A class for aggregating dataset statistics."""

	def __init__(self) -> None:
		"""Initialize the DatasetStatsAggregator with default values."""
		self.splits: defaultdict[str, SplitStats] = defaultdict(SplitStats)

	@property
	def global_max_homophones(self) -> int:
		"""Get the absolute maximum number of homophones across all splits."""
		if not self.splits:
			return 0
		return max(split_stats.max_homophones for split_stats in self.splits.values())

	def record(self, split: str, **kwargs: Unpack[UpdateStats]) -> None:
		"""Record a new item (cipher) in the dataset.

		Args:
			split (str): The split the cipher was generated in.
			**kwargs: Keyword arguments for the SplitStats.update method.

		"""
		self.splits[split].update(**kwargs)

	def merge(self, other: "DatasetStatsAggregator") -> None:
		"""Merge another DatasetStatsAggregator into this one.

		Args:
			other (DatasetStatsAggregator): The other DatasetStatsAggregator to merge
				into this one.

		"""
		for split_name, other_split_stats in other.splits.items():
			self.splits[split_name].merge(other_split_stats)

	def __json__(self) -> dict:
		"""Return a JSON-serializable representation of DatasetStatsAggregator object.

		Returns:
			dict: A dictionary containing DatasetStatsAggregator object's attributes.

		"""
		return {name: s.__json__() for name, s in self.splits.items()}
