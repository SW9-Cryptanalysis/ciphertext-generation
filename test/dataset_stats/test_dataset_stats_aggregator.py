import pytest
from dataset_stats import DatasetStatsAggregator
from dataset_stats.split_stats import SplitStats


class TestDatasetStatsAggregatorInit:
	def test_dataset_stats_aggregator_init(self):
		"""Test the initialization of the DatasetStatsAggregator."""
		stats_aggregator = DatasetStatsAggregator()

		assert stats_aggregator.splits == {}
		assert stats_aggregator.global_max_homophones == 0


class TestDatasetStatsAggregatorRecord:
	def test_dataset_stats_aggregator_record(self, mock_records, mock_records_expected):
		"""Test the recording of a new item in the DatasetStatsAggregator."""
		stats_aggregator = DatasetStatsAggregator()
		for record in mock_records:
			stats_aggregator.record("train", **record)

		assert (
			stats_aggregator.global_max_homophones
			== mock_records_expected["max_homophones"]
		)

	def test_dataset_stats_aggregator_record_handles_empty_genre(
		self, mock_records, mock_records_expected
	):
		"""Test the recording of a new item in the DatasetStatsAggregator with an empty genre."""
		stats_aggregator = DatasetStatsAggregator()
		for record in mock_records:
			record["genres"] = []
			stats_aggregator.record("train", **record)

		assert (
			stats_aggregator.global_max_homophones
			== mock_records_expected["max_homophones"]
		)

	def test_dataset_stats_aggregator_record_multiple_splits(self, mock_records, mock_records_expected):
		"""Test the recording of a new item in the DatasetStatsAggregator with multiple splits."""
		stats_aggregator = DatasetStatsAggregator()
		for record in mock_records:
			stats_aggregator.record("train", **record)

		stats_aggregator.record("val", **mock_records[0])

		assert (
			stats_aggregator.global_max_homophones
			== mock_records_expected["max_homophones"]
		)
  

class TestDatasetStatsAggregatorMerge:
	def test_dataset_stats_aggregator_merge(self, mock_records, mock_records_expected):
		"""Test the merging of two DatasetStatsAggregator objects."""
		stats_aggregator_1 = DatasetStatsAggregator()
		stats_aggregator_2 = DatasetStatsAggregator()

		for idx, record in enumerate(mock_records):
			if idx % 2 == 0:
				stats_aggregator_1.record("train", **record)
			else:
				stats_aggregator_2.record("train", **record)

		stats_aggregator_1.merge(stats_aggregator_2)

		for key, value in mock_records_expected.items():
			assert getattr(stats_aggregator_1.splits["train"], key) == value


class TestDatasetStatsAggregatorJson:
	def test_dataset_stats_aggregator_json(self, mock_records, mock_records_expected_json):
		"""Test the JSON serialization of the DatasetStatsAggregator class."""
		stats_aggregator = DatasetStatsAggregator()

		for record in mock_records:
			stats_aggregator.record("train", **record)

		json_data = stats_aggregator.__json__()

		assert isinstance(json_data, dict)
		for key, value in mock_records_expected_json.items():
			assert json_data[key] == value

		