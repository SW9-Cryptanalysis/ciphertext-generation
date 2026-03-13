import pytest
from fetching.corpus_sampler import CorpusSampler
from utils.text_splits import Book


@pytest.fixture
def default_targets():
	"""Provides a valid targets dictionary."""
	return {"train": 100, "val": 10, "test": 10}


@pytest.fixture
def default_genre_map():
	"""Provides a sample genre mapping."""
	return {"1": ["Fiction"], "2": ["Science Fiction"]}


@pytest.fixture
def mock_constants(mocker):
	"""Mocks global constants to ensure deterministic tests."""
	mocker.patch("fetching.corpus_sampler.TOTAL_BOOKS", 100)
	mocker.patch("fetching.corpus_sampler.BOOK_IDS_VALIDATION", ["999"])


class TestCorpusSamplerInit:
	def test_init_calculates_means_correctly(
		self, mock_constants, default_targets, default_genre_map
	):
		"""Test that the sampler properly calculates mathematical targets upon initialization."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)

		expected_train_mean = 100 / (100 * 0.98)
		expected_val_mean = 10 / (100 * 0.01)

		assert sampler.means["train"] == expected_train_mean
		assert sampler.means["val"] == expected_val_mean
		assert sampler.targets == default_targets
		assert sampler.len_bounds == (500, 1000)

	def test_init_raises_value_error_on_invalid_targets(self, default_genre_map):
		"""Test that the parameter validator intercepts incorrect dictionary keys."""
		invalid_targets = {"train": 100, "validation": 10}

		with pytest.raises(
			ValueError, match="Missing required keys in targets: 'test', 'val'"
		):
			CorpusSampler(invalid_targets, (500, 1000), default_genre_map)  # type: ignore


class TestCorpusSamplerIsComplete:
	def test_is_complete_returns_false_initially(
		self, mock_constants, default_targets, default_genre_map
	):
		"""Test that a fresh sampler is not marked as complete."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
		assert not sampler.is_complete()

	def test_is_complete_returns_true_when_quotas_met(
		self, mock_constants, default_targets, default_genre_map
	):
		"""Test that the sampler correctly identifies when all targets are exactly met."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
		sampler.counts = {"train": 100, "val": 10, "test": 10}
		assert sampler.is_complete()

	def test_is_complete_handles_overfulfillment(
		self, mock_constants, default_targets, default_genre_map
	):
		"""Test that exceeding the target counts still correctly triggers completion."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
		sampler.counts = {"train": 150, "val": 12, "test": 11}
		assert sampler.is_complete()


class TestCorpusSamplerGenerateStream:
	def test_generate_stream_stops_when_complete(
		self, mocker, mock_constants, default_targets, default_genre_map
	):
		"""Test that iteration halts immediately if quotas are full."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
		mocker.patch.object(sampler, "is_complete", return_value=True)
		mock_process = mocker.patch.object(sampler, "_process_book")

		dummy_stream = [{"id": "1", "text": "dummy"}]
		results = list(sampler.generate_stream(dummy_stream))

		assert len(results) == 0
		mock_process.assert_not_called()

	def test_generate_stream_skips_validation_ids(
		self, mocker, mock_constants, default_targets, default_genre_map
	):
		"""Test that the sampler explicitly ignores books in the validation blocklist."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
		mock_process = mocker.patch.object(sampler, "_process_book")

		dummy_stream = [{"id": "999", "text": "dummy"}]
		list(sampler.generate_stream(dummy_stream))

		mock_process.assert_not_called()

	def test_generate_stream_yields_from_process_book(
		self, mocker, mock_constants, default_targets, default_genre_map
	):
		"""Test that valid books are correctly passed to the processing method."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
		mocker.patch("fetching.corpus_sampler.get_split", return_value="train")

		expected_yield = ("train", {"text": "chunk"})
		mocker.patch.object(
			sampler, "_process_book", return_value=iter([expected_yield])
		)

		dummy_stream = [{"id": "1", "text": "dummy"}]
		results = list(sampler.generate_stream(dummy_stream))

		assert results == [expected_yield]

	def test_generate_stream_continues_on_none_split(
		self, mocker, mock_constants, default_targets, default_genre_map
	):
		"""Test that the loop executes 'continue' and moves to the next book if split is None."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)

		# Force the loop to run twice before checking completion
		mocker.patch.object(sampler, "is_complete", side_effect=[False, False, True])

		# First book gets None (triggering continue), second book gets "train"
		mocker.patch.object(
			sampler, "_get_available_split", side_effect=[None, "train"]
		)

		expected_yield = ("train", {"text": "chunk"})
		mock_process = mocker.patch.object(
			sampler, "_process_book", return_value=iter([expected_yield])
		)

		dummy_stream = [
			{"id": "1", "text": "skip_me"},
			{"id": "2", "text": "process_me"},
		]

		results = list(sampler.generate_stream(dummy_stream))

		# Assert process_book was only called once, specifically for the second book
		assert mock_process.call_count == 1
		assert mock_process.call_args[0][0]["id"] == "2"
		assert results == [expected_yield]


class TestCorpusSamplerGetAvailableSplit:
	"""Tests covering the split fallback routing logic."""

	def test_returns_initial_when_not_full(self, default_targets, default_genre_map):
		"""Verify it returns the requested split if the quota is not met."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
		sampler.counts["train"] = 50  # Target is 100

		assert sampler._get_available_split("train") == "train"

	def test_returns_backup_when_initial_full(self, default_targets, default_genre_map):
		"""Verify it falls back to the defined backup order ('val', 'test', 'train')."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)

		# Max out the train split
		sampler.counts["train"] = 100

		# Should fall back to the first available backup in the list: 'val'
		assert sampler._get_available_split("train") == "val"

		# Max out 'val' too
		sampler.counts["val"] = 10

		# Now it should fall back to 'test'
		assert sampler._get_available_split("train") == "test"

	def test_returns_none_when_all_full(self, default_targets, default_genre_map):
		"""Verify it returns None when absolutely all splits are at capacity."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)

		# Max out everything
		sampler.counts = {"train": 100, "val": 10, "test": 10}

		assert sampler._get_available_split("train") is None


class TestCorpusSamplerProcessBook:
	def test_process_book_zero_capacity_returns_early(
		self, mocker, mock_constants, default_targets, default_genre_map
	):
		"""Test that short texts yielding zero capacity do not alter the stream or state."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
		mocker.patch("fetching.corpus_sampler.get_usable_text", return_value="short")
		mocker.patch("fetching.corpus_sampler.get_actual_take", return_value=0)

		book = Book(
			id="1",
			text="short",
			source_name="Test Title",
			source_type="project_gutenberg",
			fallback_genres=["Other / Uncategorized"],
		)
		results = list(sampler._process_book(book, "train"))

		assert len(results) == 0

	def test_process_book_yields_chunks_and_updates_state(
		self, mocker, mock_constants, default_targets, default_genre_map
	):
		"""Test that the sampler successfully yields formatted chunks and updates its tracking variables."""
		sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)

		mocker.patch(
			"fetching.corpus_sampler.get_usable_text", return_value="long valid text"
		)
		mocker.patch("fetching.corpus_sampler.get_actual_take", return_value=2)

		mock_chunks = [("chunk1", "chunk1_bound"), ("chunk2", "chunk2_bound")]
		mocker.patch(
			"fetching.corpus_sampler.get_book_chunks", return_value=iter(mock_chunks)
		)

		book = Book(
			id="1",
			text="long valid text",
			source_name="Test Title",
			source_type="project_gutenberg",
			fallback_genres=["Other / Uncategorized"],
		)

		initial_debt = sampler.debts["train"]
		results = list(sampler._process_book(book, "train"))

		assert len(results) == 2
		assert results[0][1]["text"] == "chunk1"
		assert results[0][1]["genres"] == ["Fiction"]
		assert sampler.counts["train"] == 2
		assert sampler.debts["train"] == initial_debt + sampler.means["train"] - 2
