import pytest
import multiprocessing as mp
from test_data import dataset_bookstream


@pytest.fixture()
def sample_text():
	return (
		"thisisatestplaintextthatneedstobeencrypteditisjustarandomstringoflowercaselettersthatshouldworkfineanditislong"
		"enoughtotestthecipherwiththelengthshouldbeoverfourhundredcharactersmaybeevenfivehundredduetothisweneedtoensure"
		"thecipherworksasexpectedandcanhandlelargerinputswithoutanyissuesandthatthistextisextremelylongsoitcanbeusedtotest"
		"theperformanceoftheciphergenerationprocess"
	)


@pytest.fixture()
def sample_text_with_boundaries():
	return (
		"this_is_a_test_plaintext_that_needs_to_be_encrypted_it_is_just_a_random_string_of_lowercase_letters_that_should_work_fine_and_it_is_long"
		"_enough_to_test_the_cipher_with_the_length_should_be_over_four_hundred_characters_maybe_even_five_hundred_due_to_this_we_need_to_ensure"
		"_the_cipher_works_as_expected_and_can_handle_larger_inputs_without_any_issues_and_that_this_text_is_extremely_long_it_can_be_used_to_test"
		"_the_performance_of_the_cipher_generation_process"
	)


@pytest.fixture()
def sample_text_with_spaces():
	return (
		"this is a test plaintext that needs to be encrypted it is just a random string of lowercase letters that should work fine and it is long"
		" enough to test the cipher with the length should be over four hundred characters maybe even five hundred due to this we need to ensure"
		" the cipher works as expected and can handle larger inputs without any issues and that this text is extremely long it can be used to test"
		" the performance of the cipher generation process"
	)


@pytest.fixture()
def valid_text_stream(sample_text, sample_text_with_boundaries):
	"""Returns a valid TextStream dictionary for HomophonicCipher."""
	return {
		"text": sample_text,
		"text_with_boundaries": sample_text_with_boundaries,
		"source_id": "book_123",
		"source_name": "Test Book",
		"length": len(sample_text),
		"genres": ["Sci-Fi & Fantasy"],
	}


@pytest.fixture
def queue_factory():
	"""Returns a factory function that creates fresh queues."""
	manager = mp.Manager()
	queues = []

	def _create_queue():
		q = manager.Queue()
		queues.append(q)
		return q

	return _create_queue


@pytest.fixture
def mock_tracker(mocker):
	"""Provides a mock tracker object for CipherProducer."""
	tracker = mocker.Mock()
	tracker.value = 0
	tracker.lock = mocker.MagicMock()
	return tracker, tracker.lock


@pytest.fixture
def mock_dataset_stream(mocker):
	"""Provides a mock dataset stream for DatasetExtractor."""
	mock_stream = mocker.Mock()
	mock_stream.select_columns = mocker.Mock()

	book_stream = dataset_bookstream.BOOK_STREAM_HF

	# Only return id columns
	def dynamic_select_columns(column_names):
		"""Simulates Hugging Face by returning only the requested keys."""
		filtered_stream = []
		for book in book_stream:
			# Keep only the keys that were asked for
			filtered_book = {k: v for k, v in book.items() if k in column_names}
			filtered_stream.append(filtered_book)
		return filtered_stream

	mock_stream.select_columns.side_effect = dynamic_select_columns

	mock_stream.select_columns.return_value = book_stream
	return mock_stream


@pytest.fixture
def mock_dataset_stream_long(mocker):
	"""Provides a mock dataset stream for DatasetExtractor."""
	mock_stream = mocker.Mock()
	mock_stream.select_columns = mocker.Mock()

	book_stream = dataset_bookstream.BOOK_STREAM_HF
	book_stream.extend(book_stream)

	# Only return id columns
	def dynamic_select_columns(column_names):
		"""Simulates Hugging Face by returning only the requested keys."""
		return [{"id": str(i)} for i in range(5000)]

	mock_stream.select_columns.side_effect = dynamic_select_columns
	return mock_stream


@pytest.fixture
def mock_gutendex_bookshelves() -> list[dict]:
	"""Provide a diverse set of mocked book metadata to test the TaxonomyMapper.

	This includes standard categories, missing prefixes, multiple genres,
	unknown categories, empty lists, and complex edge cases.
	"""
	return [
		{
			"id": "1001",
			"title": "The Standard Genre Book",
			"bookshelves": ["Category: Science Fiction", "Category: Fantasy"],
		},
		{
			"id": "1002",
			"title": "The Prefix-less Book",
			"bookshelves": ["Mystery", "Crime", "Detective Fiction"],
		},
		{
			"id": "1003",
			"title": "The Multi-Genre Book",
			"bookshelves": ["Category: Historical Fiction", "Category: Romance"],
		},
		{
			"id": "1004",
			"title": "The Completely Unknown Book",
			"bookshelves": [
				"Category: 19th Century Basket Weaving",
				"My Custom Book Club",
			],
		},
		{
			"id": "1005",
			"title": "The Mixed Bag Book",
			"bookshelves": ["Category: Science", "Some Highly Specific Niche Topic"],
		},
		{"id": "1006", "title": "The Empty Metadata Book", "bookshelves": []},
		{
			"id": "1007",
			"title": "The Edge Case Periodical",
			"bookshelves": ["Punchinello", "Category: Humour"],
		},
		{
			"id": "1008",
			"title": "The Complex Academic Text",
			"bookshelves": [
				"Banned Books from Anne Haight's list",
				"Category: Psychiatry/Psychology",
				"Psychology",
			],
		},
		{
			"id": "1009",
			"title": "The Case Insensitivity Test",
			"bookshelves": ["category: BRITISH literature", "ART"],
		},
	]


@pytest.fixture
def expected_taxonomy_mappings() -> dict[str, list[str]]:
	"""Provide the expected mapped outputs for the mock_gutendex_bookshelves fixture."""
	return {
		"1001": ["Sci-Fi & Fantasy"],
		"1002": ["Mystery & Fiction"],
		"1003": ["History", "Romance"],
		"1004": ["Other / Uncategorized"],
		"1005": ["Science & Tech"],
		"1006": ["Other / Uncategorized"],
		"1007": ["Journalism & Periodicals", "Humor"],
		"1008": ["Classic & General Literature", "Psychology & Health"],
		"1009": ["Classic & General Literature", "Fine Arts & Architecture"],
	}
