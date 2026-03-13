from utils.logging import get_logger
from genre_mapping.gutendex_client import GutendexClient
from fetching.dataset_extractor import DatasetExtractor
from genre_mapping.taxonomy_mapper import TaxonomyMapper
from utils.constants import DATASETS, GENRE_MAP_PATH
from genre_mapping.genre_mapper import GenreMapper


if __name__ == "__main__":
    logger = get_logger("GenreMapper")

    extractor = DatasetExtractor(DATASETS, logger=logger)
    api_client = GutendexClient(logger=logger)
    mapper = TaxonomyMapper()
    genre_mapper = GenreMapper(extractor, api_client, mapper, logger=logger)

    genre_map = genre_mapper.run(output_path=GENRE_MAP_PATH)
    mapper.dump_unmapped_to_file()
