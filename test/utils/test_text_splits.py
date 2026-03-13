import pytest
from dataclasses import dataclass
from utils.text_splits import (
    find_boundaries,
    find_spaceless_target_index,
    extract_random_chunk,
    get_split,
    get_book_chunks,
    get_usable_text,
    get_actual_take,
    randomize_stream,
    get_source_genres,
    Book,
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
        mocker.patch("utils.text_splits.format_text", side_effect=lambda x: x)

        chunk, bounded_chunk = extract_random_chunk(text, 0, len(text), (10, 20))

        assert " " not in chunk
        assert chunk == "wordonewordtwo"
        assert bounded_chunk == "wordone_wordtwo"

    def test_get_book_chunks_filters_length(
        self, mocker, sample_text, sample_text_with_boundaries
    ):
        min_bound = int(len(sample_text) - 0.05 * len(sample_text))

        mocker.patch(
            "utils.text_splits.extract_random_chunk",
            side_effect=[
                (sample_text, sample_text_with_boundaries),
                (sample_text, sample_text_with_boundaries),
            ],
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
            "utils.text_splits.extract_random_chunk",
            return_value=(long_chunk, long_chunk),
        )

        chunks = list(get_book_chunks("text", 1, (10, max_bound)))

        assert len(chunks) == 0

    def test_extract_random_chunk_reaches_end_of_text(self, mocker):
        short_text = "This is very short."
        mocker.patch("random.randint", side_effect=[100, 0, 0])
        mocker.patch("utils.text_splits.format_text", side_effect=lambda x: x)

        chunk = extract_random_chunk(short_text, 0, 10, (5, 150))
        assert len(chunk) > 0

    def test_extract_random_chunk_too_small_returns_immediately(self, mocker):
        text = "tiny"
        mocker.patch("random.randint", side_effect=[10, 0, 0])
        mocker.patch("utils.text_splits.format_text", side_effect=lambda x: x)

        chunk, chunk_bounded = extract_random_chunk(text, 0, 5, (5, 15))
        assert chunk == "tiny"
        assert chunk_bounded == "tiny"


class TestGetSourceGenres:
    @dataclass
    class GetSourceTestCase:
        book: Book
        genre_map: dict[str, list[str]]
        expected_genres: list[str]
        desc: str

    TEST_CASES_GET_SOURCES = [
        GetSourceTestCase(
            book={
                "id": "pg:123",
                "source_type": "project_gutenberg",
                "fallback_genres": ["Fiction"],
                "text": "...",
                "source_name": "Gutenberg",
            },
            genre_map={"123": ["Sci-Fi", "Adventure"]},
            expected_genres=["Sci-Fi", "Adventure"],
            desc="Gutenberg source: ID found in map",
        ),
        GetSourceTestCase(
            book={
                "id": "pg:456",
                "source_type": "project_gutenberg",
                "fallback_genres": ["Classic"],
                "text": "...",
                "source_name": "Gutenberg",
            },
            genre_map={"123": ["Sci-Fi"]},
            expected_genres=["Classic"],
            desc="Gutenberg source: ID NOT in map (uses fallback)",
        ),
        GetSourceTestCase(
            book={
                "id": "other:789",
                "source_type": "local_library",
                "fallback_genres": ["History"],
                "text": "...",
                "source_name": "Local",
            },
            genre_map={"789": ["Biography"]},
            expected_genres=["History"],
            desc="Non-Gutenberg source: ignores map, uses fallback",
        ),
        GetSourceTestCase(
            book={
                "id": "pg:999",
                "source_type": "project_gutenberg",
                "fallback_genres": [],
                "text": "...",
                "source_name": "Gutenberg",
            },
            genre_map={},
            expected_genres=[],
            desc="Gutenberg source: empty map and empty fallback",
        ),
        GetSourceTestCase(
            book={
                "id": "123",  # No prefix to remove
                "source_type": "project_gutenberg",
                "fallback_genres": ["Drama"],
                "text": "...",
                "source_name": "Gutenberg",
            },
            genre_map={"123": ["Drama (Mapped)"]},
            expected_genres=["Drama (Mapped)"],
            desc="Gutenberg source: ID exists without prefix",
        ),
    ]

    @pytest.mark.parametrize("case", TEST_CASES_GET_SOURCES, ids=lambda c: c.desc)
    def test_get_source_genres_returns_fallback(self, case: GetSourceTestCase):
        assert get_source_genres(case.book, case.genre_map) == case.expected_genres
