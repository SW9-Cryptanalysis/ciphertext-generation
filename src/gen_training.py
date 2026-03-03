import os
from utils.logging import get_logger
from cipher_generation.cipher_manager import CipherManager
from typing import Iterator

from fetching.dataset_extractor import DatasetExtractor
from fetching.corpus_sampler import CorpusSampler
from utils.genres import load_existing_genre_map
from utils.text_splits import randomize_stream, TextStream
from utils.constants import (
	NUM_TRAINING_CIPHERS,
	NUM_VALIDATION_CIPHERS,
	NUM_TEST_CIPHERS,
	GENRE_MAP_PATH,
	DATASET_NAME,
)




def get_text_stream(
    targets: dict[str, int],
    len_bounds: tuple[int, int] = (4000, 10000),
    extractor: DatasetExtractor | None = None,
) -> Iterator[tuple[str, TextStream]]:
    """Initialize dependencies and return the randomized text stream.

    Args:
        targets (dict[str, int]): Target counts for train, val, and test splits.
        len_bounds (tuple[int, int], optional): Min and max length bounds.
        extractor (DatasetExtractor | None, optional): The dataset extractor instance.

    Returns:
        Iterator[tuple[str, TextStream]]: The generated stream of text chunks.

    """
    if extractor is None:
        extractor = DatasetExtractor(DATASET_NAME)

    genre_map = load_existing_genre_map(GENRE_MAP_PATH, None)
    full_stream = randomize_stream(extractor.get_full_stream())
    
    sampler = CorpusSampler(targets, len_bounds, genre_map)
    
    return sampler.generate_stream(full_stream)

if __name__ == "__main__":
	if not os.path.exists(GENRE_MAP_PATH):
		raise FileNotFoundError(f"Genre map not found at {GENRE_MAP_PATH}")


	log = get_logger("TrainingGeneration")
	folder_id_train = os.getenv("FOLDER_ID_TRAIN")
	folder_id_val = os.getenv("FOLDER_ID_VAL")
	folder_id_test = os.getenv("FOLDER_ID_TEST")

	folder_id_metadata = os.getenv("FOLDER_ID_METADATA")

	if not folder_id_metadata:
		raise OSError(
			"FOLDER_ID_METADATA environment variable not set. "
			"Please set it before running.",
		)

	if not folder_id_train:
		raise OSError(
			"FOLDER_ID_TRAIN environment variable not set. "
			"Please set it before running.",
		)

	if not folder_id_val:
		raise OSError(
			"FOLDER_ID_VAL environment variable not set. Please set it before running.",
		)
	if not folder_id_test:
		raise OSError(
			"FOLDER_ID_TEST environment variable not set. "
			"Please set it before running.",
		)

	targets = {
		"train": NUM_TRAINING_CIPHERS,
		"val": NUM_VALIDATION_CIPHERS,
		"test": NUM_TEST_CIPHERS,
	}

	text_stream = get_text_stream(targets=targets)

	config = {
		"train": {"folder_id": folder_id_train, "count": NUM_TRAINING_CIPHERS},
		"val": {"folder_id": folder_id_val, "count": NUM_VALIDATION_CIPHERS},
		"test": {"folder_id": folder_id_test, "count": NUM_TEST_CIPHERS},
		"metadata": {"folder_id": folder_id_metadata, "count": 0},
	}

	manager = CipherManager(
		config=config,
		text_stream_source=text_stream,
	)

	try:
		manager.execute()
	except Exception as e:
		log.critical(
			f"A critical error occurred in the main process: {e}",
			exc_info=True,
		)
