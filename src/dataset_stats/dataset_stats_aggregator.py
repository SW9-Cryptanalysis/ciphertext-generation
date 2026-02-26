from collections import defaultdict
from split_stats import SplitStats

class DatasetStatsAggregator:
	"""A class for aggregating dataset statistics."""
 
	def __init__(self) -> None:
		"""Initialize the DatasetStatsAggregator with default values."""
		self.splits = defaultdict(SplitStats)

	def record(self, split: str, **kwargs) -> None:
		"""Record a new item (cipher) in the dataset.

		Args:
			split (str): The split the cipher was generated in.
			**kwargs: Keyword arguments for the SplitStats.update method.
		"""
		self.splits[split].update(**kwargs)

	def merge (self, other: "DatasetStatsAggregator") -> None:
		"""Merge another DatasetStatsAggregator into this one.

		Args:
			other (DatasetStatsAggregator): The other DatasetStatsAggregator to merge into this one.
		"""
		for split_name, other_split_stats in other.splits.items():
			self.splits[split_name].merge(other_split_stats)

	def __json__(self) -> dict:
		"""Return a JSON-serializable representation of the DatasetStatsAggregator object.

		Returns:
			dict: A dictionary containing the DatasetStatsAggregator object's attributes.

		"""
		return {
			name: s.__json__()
			for name, s in self.splits.items()
		}