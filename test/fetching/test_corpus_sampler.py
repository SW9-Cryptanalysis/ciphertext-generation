import pytest
from fetching.corpus_sampler import CorpusSampler


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

        with pytest.raises(ValueError, match="must contain exactly keys"):
            CorpusSampler(invalid_targets, (500, 1000), default_genre_map)


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

    def test_generate_stream_skips_fulfilled_splits(
        self, mocker, mock_constants, default_targets, default_genre_map
    ):
        """Test that books assigned to an already-full split are discarded."""
        sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
        sampler.counts["val"] = 10

        mocker.patch("fetching.corpus_sampler.get_split", return_value="val")
        mock_process = mocker.patch.object(sampler, "_process_book")

        dummy_stream = [{"id": "1", "text": "dummy"}]
        list(sampler.generate_stream(dummy_stream))

        mock_process.assert_not_called()

    def test_generate_stream_yields_from_process_book(
        self, mocker, mock_constants, default_targets, default_genre_map
    ):
        """Test that valid books are correctly passed to the processing method."""
        sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
        mocker.patch("fetching.corpus_sampler.get_split", return_value="train")

        expected_yield = ("train", {"text": "chunk"})
        mocker.patch.object(sampler, "_process_book", return_value=iter([expected_yield]))

        dummy_stream = [{"id": "1", "text": "dummy"}]
        results = list(sampler.generate_stream(dummy_stream))

        assert results == [expected_yield]


class TestCorpusSamplerProcessBook:
    def test_process_book_zero_capacity_returns_early(
        self, mocker, mock_constants, default_targets, default_genre_map
    ):
        """Test that short texts yielding zero capacity do not alter the stream or state."""
        sampler = CorpusSampler(default_targets, (500, 1000), default_genre_map)
        mocker.patch("fetching.corpus_sampler.get_usable_text", return_value="short")
        mocker.patch("fetching.corpus_sampler.get_actual_take", return_value=0)

        book = {"id": "1", "text": "short", "metadata": {}}
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

        book = {"id": "1", "text": "long valid text", "metadata": {"title": "Test Title"}}

        initial_debt = sampler.debts["train"]
        results = list(sampler._process_book(book, "train"))

        assert len(results) == 2
        assert results[0][1]["text"] == "chunk1"
        assert results[0][1]["genres"] == ["Fiction"]
        assert sampler.counts["train"] == 2
        assert sampler.debts["train"] == initial_debt + sampler.means["train"] - 2