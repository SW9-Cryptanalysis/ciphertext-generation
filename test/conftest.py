import pytest
import multiprocessing as mp


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
