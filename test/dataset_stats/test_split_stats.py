from dataset_stats import SplitStats, BucketSizes
from collections import Counter
import pytest


def seed_stats(updates: list[dict]) -> SplitStats:
	"""Helper to quickly bulk-load a SplitStats object without repetitive calls."""
	stats = SplitStats()
	for kwargs in updates:
		stats.update(**kwargs)
	return stats


class TestBucketSizesInit:
	def test_bucket_sizes_init(self):
		"""Test the initialization of the BucketSizes class."""
		bucket_sizes = BucketSizes()

		assert bucket_sizes.length == 500
		assert bucket_sizes.homophones == 100
		assert bucket_sizes.redundancy == 1

	def test_bucket_sizes_init_custom(self):
		"""Test the initialization of the BucketSizes class with custom values."""
		bucket_sizes = BucketSizes(length=1000, homophones=200, redundancy=2)

		assert bucket_sizes.length == 1000
		assert bucket_sizes.homophones == 200
		assert bucket_sizes.redundancy == 2

	def test_bucket_sizes_validation(self):
		"""Test the validation of the BucketSizes class."""
		with pytest.raises(ValueError) as excinfo:
			BucketSizes(length=0)
		assert "Bucket size must be greater than 0" in str(excinfo.value)


class TestSplitStatsInit:
	def test_split_stats_init(self):
		"""Test the initialization of the SplitStats class."""
		split_stats = SplitStats()

		assert split_stats.total_count == 0
		assert split_stats.length_distribution == Counter()
		assert isinstance(split_stats.length_distribution, Counter)
		assert isinstance(split_stats.homophone_distribution, Counter)
		assert isinstance(split_stats.redundancy_distribution, Counter)
		assert isinstance(split_stats.genre_distribution, Counter)
		assert split_stats.min_length == float("inf")
		assert split_stats.max_length == 0
		assert split_stats.min_homophones == float("inf")
		assert split_stats.max_homophones == 0
		assert isinstance(split_stats._bucket_sizes, BucketSizes)


class TestSplitStatsUpdate:
	@pytest.fixture
	def steps(self):
		return [
			{
				"input": {
					"length": 4018,
					"homophones": 213,
					"difficulty": 5,
					"genre": "Sci-Fi & Fantasy",
				},
				"expected": {
					"total_count": 1,
					"length_distribution": {4000: 1},
					"homophone_distribution": {200: 1},
					"redundancy_distribution": {5: 1},
					"genre_distribution": {"Sci-Fi & Fantasy": 1},
					"min_length": 4018,
					"max_length": 4018,
					"min_homophones": 213,
					"max_homophones": 213,
				},
			},
			{
				"input": {
					"length": 5051,
					"homophones": 59,
					"difficulty": 25,
					"genre": "Romance",
				},
				"expected": {
					"total_count": 2,
					"length_distribution": {4000: 1, 5000: 1},
					"homophone_distribution": {0: 1, 200: 1},
					"redundancy_distribution": {5: 1, 25: 1},
					"genre_distribution": {"Sci-Fi & Fantasy": 1, "Romance": 1},
					"min_length": 4018,
					"max_length": 5051,
					"min_homophones": 59,
					"max_homophones": 213,
				},
			},
			{
				"input": {
					"length": 6518,
					"homophones": 32,
					"difficulty": 15,
					"genre": "Romance",
				},
				"expected": {
					"total_count": 3,
					"length_distribution": {4000: 1, 5000: 1, 6500: 1},
					"homophone_distribution": {0: 2, 200: 1},
					"redundancy_distribution": {5: 1, 15: 1, 25: 1},
					"genre_distribution": {"Sci-Fi & Fantasy": 1, "Romance": 2},
					"min_length": 4018,
					"max_length": 6518,
					"min_homophones": 32,
					"max_homophones": 213,
				},
			},
		]

	def test_split_stats_update_state_progression(self, steps):
		"""Test that the internal state correctly accumulates over multiple updates."""
		split_stats = SplitStats()

		for step in steps:
			split_stats.update(**step["input"])
			exp = step["expected"]

			assert split_stats.total_count == exp["total_count"]
			assert split_stats.length_distribution == Counter(
				exp["length_distribution"]
			)
			assert split_stats.homophone_distribution == Counter(
				exp["homophone_distribution"]
			)
			assert split_stats.redundancy_distribution == Counter(
				exp["redundancy_distribution"]
			)
			assert split_stats.genre_distribution == Counter(exp["genre_distribution"])
			assert split_stats.min_length == exp["min_length"]
			assert split_stats.max_length == exp["max_length"]
			assert split_stats.min_homophones == exp["min_homophones"]
			assert split_stats.max_homophones == exp["max_homophones"]


class TestSplitStatsMerge:
	def test_split_stats_merge(self):
		"""Test the merge method of the SplitStats class."""
		split_stats_1 = SplitStats()
		split_stats_1.update(
			length=4018, homophones=213, difficulty=5, genre="Sci-Fi & Fantasy"
		)
		split_stats_1.update(length=5051, homophones=59, difficulty=25, genre="Romance")
		split_stats_1.update(length=6518, homophones=32, difficulty=15)
		split_stats_1.update(
			length=8000, homophones=100, difficulty=10, genre="Romance"
		)

		split_stats_2 = SplitStats()
		split_stats_2.update(
			length=4018, homophones=213, difficulty=5, genre="Sci-Fi & Fantasy"
		)
		split_stats_2.update(length=5051, homophones=59, difficulty=25, genre="Romance")

		split_stats_1.merge(split_stats_2)

		assert split_stats_1.total_count == 6
		assert split_stats_1.length_distribution == Counter(
			{4000: 2, 5000: 2, 6500: 1, 8000: 1}
		)
		assert split_stats_1.homophone_distribution == Counter({0: 3, 100: 1, 200: 2})
		assert split_stats_1.redundancy_distribution == Counter(
			{5: 2, 25: 2, 15: 1, 10: 1}
		)
		assert split_stats_1.genre_distribution == Counter(
			{"Sci-Fi & Fantasy": 2, "Romance": 3}
		)
		assert split_stats_1.min_length == 4018
		assert split_stats_1.max_length == 8000
		assert split_stats_1.min_homophones == 32
		assert split_stats_1.max_homophones == 213


class TestSplitStatsJson:
	def test_split_stats_json(self):
		"""Test the JSON serialization of the SplitStats class."""
		split_stats = SplitStats()
		split_stats.update(
			length=4018, homophones=213, difficulty=5, genre="Sci-Fi & Fantasy"
		)
		split_stats.update(length=5051, homophones=59, difficulty=25, genre="Romance")
		split_stats.update(length=6518, homophones=32, difficulty=15)
		split_stats.update(length=8000, homophones=100, difficulty=10, genre="Romance")
		split_stats.update(
			length=6618, homophones=45, difficulty=25, genre="Sci-Fi & Fantasy"
		)

		json_data = split_stats.__json__()

		assert isinstance(json_data, dict)
		assert json_data["total_count"] == 5
		assert json_data["length_distribution"] == {
			"4000-4499": 1,
			"5000-5499": 1,
			"6500-6999": 2,
			"8000-8499": 1,
		}
		assert json_data["homophone_distribution"] == {
			"0-99": 3,
			"100-199": 1,
			"200-299": 1,
		}
		assert json_data["redundancy_distribution"] == {
			"5": 1,
			"10": 1,
			"15": 1,
			"25": 2,
		}
		assert json_data["genre_distribution"] == {"Romance": 2, "Sci-Fi & Fantasy": 2}
