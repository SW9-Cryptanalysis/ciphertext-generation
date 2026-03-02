import pytest
from fetching.text_splits import (
    find_boundaries,
    find_spaceless_target_index,
    extract_random_chunk,
    get_split,
    get_book_chunks,
    get_usable_text,
    get_actual_take,
    validate_targets,
    text_streams_generator,
    get_text_stream,
    randomize_stream,
)

# --- Fixtures ---

@pytest.fixture
def mock_book_stream():
    return [
        {
            "id": "1",
            "text": "Book One content " * 500,
            "metadata": {"title": "Book One"},
        },
        {
            "id": "2",
            "text": "Book Two content " * 500,
            "metadata": {"title": "Book Two"},
        },
        {
            "id": "3",
            "text": "Book Three content " * 500,
            "metadata": {"title": "Book Three"},
        },
    ]

# --- Helper Function Tests ---

class TestTextHelpers:
    def test_find_boundaries_standard(self, sample_text_with_spaces):
        start, end = find_boundaries(sample_text_with_spaces, 10, 11)
        assert sample_text_with_spaces[start:end] == "test plaintext"

    def test_find_spaceless_target_index(self):
        text = "a b c d e"
        assert find_spaceless_target_index(text, 3) == 4
        assert find_spaceless_target_index(text, 10) == len(text)

    def test_get_split(self):
        assert get_split(0) == "val"
        assert get_split(1) == "test"
        assert get_split(2) == "train"
        assert get_split(100) == "val"

    def test_validate_targets_valid(self):
        targets = {"train": 100, "val": 10, "test": 10}
        validate_targets(targets)

    def test_validate_targets_invalid(self):
        with pytest.raises(ValueError, match="must contain exactly keys"):
            validate_targets({"train": 100})

    def test_get_actual_take_logic(self):
        debts = {"train": 10.5}
        assert get_actual_take("train", debts, 5) == 5
        assert get_actual_take("train", debts, 20) == 10
        assert get_actual_take("train", debts, 0) == 0

    def test_get_usable_text_trimming(self):
        raw = "A" * 100_000
        usable = get_usable_text(raw, (4000, 10000))
        assert len(usable) == 97_000

    def test_get_usable_text_short_book(self):
        raw = "Short book content"
        usable = get_usable_text(raw, (4000, 10000))
        assert usable == raw

    def test_randomize_stream(self, mocker):
        mock_stream = mocker.Mock()
        randomize_stream(mock_stream)
        mock_stream.shuffle.assert_called_once_with(seed=42, buffer_size=100)

# --- Core Logic Tests ---

class TestChunkExtraction:
    def test_extract_random_chunk_logic_flow(self, mocker):
        text = "wordone wordtwo wordthree wordfour"
        mocker.patch("random.randint", side_effect=[12, 0, 0, 0])
        mocker.patch("fetching.text_splits.format_text", side_effect=lambda x: x)

        chunk, bounded_chunk = extract_random_chunk(text, 0, len(text), (10, 20))

        assert " " not in chunk
        assert chunk == "wordonewordtwo"
        assert bounded_chunk == "wordone_wordtwo"

    def test_get_book_chunks_filters_length(self, mocker, sample_text, sample_text_with_boundaries):
        min_bound = int(len(sample_text) - 0.05 * len(sample_text))

        mocker.patch(
            "fetching.text_splits.extract_random_chunk",
            side_effect=[(sample_text, sample_text_with_boundaries), (sample_text, sample_text_with_boundaries)],
        )

        chunks = list(
            get_book_chunks("dummy text", actual_take=2, len_bounds=(min_bound, 2000))
        )

        assert len(chunks) == 2
        assert chunks[0][0] == sample_text
        assert chunks[0][1] == sample_text_with_boundaries
        assert chunks[1][0] == sample_text
        assert chunks[1][1] == sample_text_with_boundaries

    def test_get_book_chunks_drops_oversized(self, mocker):
        max_bound = 50
        long_chunk = "a" * 100
        mocker.patch(
            "fetching.text_splits.extract_random_chunk",
            return_value=(long_chunk, long_chunk),
        )

        chunks = list(get_book_chunks("text", 1, (10, max_bound)))

        assert len(chunks) == 0

    def test_extract_random_chunk_reaches_end_of_text(self, mocker):
        short_text = "This is very short."
        mocker.patch("random.randint", side_effect=[100, 0, 0])
        mocker.patch("fetching.text_splits.format_text", side_effect=lambda x: x)

        chunk = extract_random_chunk(short_text, 0, 10, (5, 150))
        assert len(chunk) > 0

    def test_extract_random_chunk_too_small_returns_immediately(self, mocker):
        text = "tiny"
        mocker.patch("random.randint", side_effect=[10, 0, 0])
        mocker.patch("fetching.text_splits.format_text", side_effect=lambda x: x)

        chunk, chunk_bounded = extract_random_chunk(text, 0, 5, (5, 15))
        assert chunk == "tiny"
        assert chunk_bounded == "tiny"

# --- Stream Generator Tests ---

class TestStreamGenerator:
    @pytest.fixture
    def mock_constants(self, mocker):
        mocker.patch("fetching.text_splits.TOTAL_BOOKS", 100)
        mocker.patch("fetching.text_splits.BOOK_IDS_VALIDATION", ["999"])

    def test_text_streams_generator_skips_blacklisted_ids(self, mocker, mock_constants):
        stream = [
            {"id": "good_id", "text": "valid content " * 1000, "metadata": {"title": "Good"}},
            {"id": "bad_id", "text": "invalid content " * 1000, "metadata": {"title": "Bad"}},
        ]
        mocker.patch("fetching.text_splits.BOOK_IDS_VALIDATION", ["bad_id"])
        targets = {"train": 1, "val": 0, "test": 0}
        len_bounds = (500, 1000)
        mocker.patch("fetching.text_splits.get_split", return_value="train")

        results = list(text_streams_generator(stream, targets, len_bounds, genre_map={}))

        assert len(results) > 0
        assert all(data["source_id"] == "good_id" for _, data in results)

    def test_text_streams_generator_skips_validation_ids(self, mocker, mock_constants):
        stream = [
            {"id": "999", "text": "content " * 1000, "metadata": {}},
            {"id": "valid", "text": "content " * 1000, "metadata": {}}
        ]
        targets = {"train": 1, "val": 0, "test": 0}
        mocker.patch("fetching.text_splits.get_split", return_value="train")

        gen = text_streams_generator(stream, targets, (500, 1000), genre_map={})
        results = list(gen)

        assert len(results) == 1
        assert results[0][1]["source_id"] == "valid"

    def test_text_streams_generator_debt_and_take(self, mocker, mock_constants):
        stream = [
            {"id": "1", "text": "content " * 2000, "metadata": {"title": "B1"}},
        ]
        targets = {"train": 100, "val": 1, "test": 1}
        len_bounds = (500, 1000)
        mocker.patch("fetching.text_splits.get_split", return_value="train")

        results = list(text_streams_generator(stream, targets, len_bounds, genre_map={}))
        assert len(results) > 0

    def test_text_streams_generator_capacity_handling(self, mock_constants):
        stream = [{"id": "1", "text": "short", "metadata": {}}]
        targets = {"train": 1, "val": 1, "test": 1}

        gen = text_streams_generator(stream, targets, (4000, 10000), genre_map={})
        assert len(list(gen)) == 0

    def test_text_streams_generator_full_and_zero_capacity(self, mocker, mock_constants):
        stream = [
            {"id": "full", "text": "content " * 1000, "metadata": {}},
            {"id": "small", "text": "short", "metadata": {}},
        ]
        targets = {"train": 0, "val": 10, "test": 10}
        mocker.patch("fetching.text_splits.get_split", side_effect=["train", "val"])

        gen = text_streams_generator(stream, targets, (500, 1000), genre_map={})
        results = list(gen)

        assert len(results) == 0

    def test_text_streams_generator_assigns_genres(self, mocker, mock_constants):
        """Test that the genre map correctly populates the output stream, handling missing IDs gracefully."""
        stream = [
            {"id": 123, "text": "content " * 1000, "metadata": {"title": "Book 1"}},
            {"id": 456, "text": "content " * 1000, "metadata": {"title": "Book 2"}},
        ]
        targets = {"train": 2, "val": 0, "test": 0}
        genre_map = {"123": ["Sci-Fi & Fantasy"]}

        mocker.patch("fetching.text_splits.get_split", return_value="train")

        gen = text_streams_generator(stream, targets, (500, 1000), genre_map=genre_map)
        results = list(gen)

        assert results[0][1]["genres"] == ["Sci-Fi & Fantasy"]
        assert results[1][1]["genres"] == []


class TestGetTextStream:
    def test_get_text_stream_integration(self, mocker):
        mock_extractor_cls = mocker.patch("fetching.text_splits.DatasetExtractor")
        mock_extractor_instance = mock_extractor_cls.return_value
        mock_extractor_instance.get_full_stream.return_value = ["dummy_stream_data"]

        mocker.patch("fetching.text_splits.randomize_stream")
        mocker.patch("fetching.text_splits.load_existing_genre_map", return_value={})
        mock_gen = mocker.patch("fetching.text_splits.text_streams_generator")

        result = get_text_stream(targets={"train": 10, "val": 1, "test": 1})

        assert result == mock_gen.return_value
        mock_gen.assert_called_once()
        mock_extractor_cls.assert_called_once()
        mock_extractor_instance.get_full_stream.assert_called_once()

    def test_get_text_stream_with_injected_extractor(self, mocker):
        mock_extractor = mocker.Mock()
        mock_extractor.get_full_stream.return_value = ["dummy_stream_data"]

        mocker.patch("fetching.text_splits.randomize_stream")
        mocker.patch("fetching.text_splits.load_existing_genre_map", return_value={})
        mocker.patch("fetching.text_splits.text_streams_generator")

        get_text_stream(
            targets={"train": 1, "val": 1, "test": 1},
            extractor=mock_extractor
        )

        mock_extractor.get_full_stream.assert_called_once()
