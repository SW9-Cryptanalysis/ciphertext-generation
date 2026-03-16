import multiprocessing as mp
from utils.logging import get_logger_tqdm
import os
from typing import Iterable, Any, Literal
from multiprocessing.queues import Queue
import json
from pathlib import Path
import random
import shutil
from utils.constants import PROJECT_ROOT

from cipher_generation.drive_uploader import DriveUploader, DriveUploaderConfig
from cipher_generation.cipher_producer import CipherProducer, ProducerConfig
from dataset_stats import DatasetStatsAggregator
from cipher_generation.config import CipherConfig
from cipher_generation.task import CipherTask, UploadTask

log = get_logger_tqdm("CipherManager", 20)


class CipherManager:
    """Orchestrates the parallel generation using Feeder -> Worker -> Uploader pattern.

    Attributes:
        config (dict[str, dict[str, Any]]): Configuration dictionary mapping splits
            to their folder IDs and target counts.
        text_stream_source (Iterable): The iterable source of text chunks.
        total_count (int): The total number of ciphers to generate across all splits.
        split_folders (dict[str, str]): A mapping of splits to their folder IDs.
        num_workers (int): The number of workers to use.

    Methods:
        execute(): Execute the cipher generation process.

    """

    SENTINEL = "STOP"

    def __init__(
        self,
        config: CipherConfig,
        text_stream_source: Iterable,
    ) -> None:
        """Initialize the CipherManager.

        Args:
            config (CipherConfig): The cipher generation configuration.
            text_stream_source (Iterable): The iterable source of text chunks.

        """
        self.stream = text_stream_source

        test_bins = sum(
            len(diffs) for diffs in config.dataset_config.test_matrix.values()
        )
        test_count = test_bins * config.dataset_config.ciphers_per_bin

        self.total_count = (
            config.dataset_config.training_num
            + config.dataset_config.validation_num
            + test_count
        )

        self.split_folders = {
            "train": config.train_folder,
            "val": config.val_folder,
            "test": config.test_folder,
            "metadata": config.metadata_folder,
        }

        self.test_tracker: dict[int, dict[int, int]] = {
            length: {difficulty: 0 for difficulty in diffs}
            for length, diffs in config.dataset_config.test_matrix.items()
        }
        self.test_samples_per_bin = config.dataset_config.ciphers_per_bin

        self.num_workers = config.num_workers or max(1, (os.cpu_count() or 4) - 2)

        self.job_queue: Queue[CipherTask | Literal["STOP"]] = mp.Queue()  # type: ignore
        self.result_queue: Queue[UploadTask | Literal["STOP"]] = mp.Queue()  # type: ignore
        self.stats_queue: Queue[DatasetStatsAggregator | Literal["STOP"]] = mp.Queue()  # type: ignore
        self.batch_size = config.batch_size

        self.master_stats = DatasetStatsAggregator()
        self._logging_interval = 10000
        self.temp_dir = Path(PROJECT_ROOT / "temp_ciphers")

    def execute(self) -> None:
        """Execute the cipher generation process."""
        log.info(
            f"Starting job. Target: {self.total_count} ciphers "
            f"using {self.num_workers} workers.",
        )

        tqdm_lock = mp.RLock()

        uploader = DriveUploader(
            upload_queue=self.result_queue,
            config=DriveUploaderConfig(
                split_folders=self.split_folders,
                total_ciphers=self.total_count,
                tqdm_lock=tqdm_lock,
            ),
            name="Uploader-Consumer",
        )
        uploader.start()

        workers = []
        for i in range(self.num_workers):
            p = CipherProducer(
                config=ProducerConfig(
                    input_queue=self.job_queue,
                    output_queue=self.result_queue,
                    stats_queue=self.stats_queue,
                    batch_size=self.batch_size,
                    temp_dir=self.temp_dir,
                ),
                name=f"Worker-{i + 1}",
            )
            workers.append(p)
            p.start()

        log.info("Feeder started. Reading stream and filling queues...")

        try:
            count_fed = 0
            try:
                count_fed = self._feeder_stream(tqdm_lock)

            except KeyboardInterrupt:
                log.warning("Job interrupted! Stopping...")
            except Exception as e:
                log.error(f"Stream error: {e}")
            finally:
                log.info(f"Stream finished. Fed {count_fed} items. Stopping workers...")
                for _ in range(self.num_workers):
                    self.job_queue.put(self.SENTINEL)

            log.info("Workers finished. Merging statistics from all workers...")
            self._merge_stats()

            for p in workers:
                p.join()

            self._upload_metadata()
            self.result_queue.put(self.SENTINEL)

            uploader.join()

            log.info("=" * 40)
            log.info("JOB COMPLETE")
            log.info(f"Total ciphers fed: {count_fed}")
            log.info(
                f"Peak homophone ID (Vocab Size): "
                f"{self.master_stats.global_max_homophones}",
            )
            log.info("=" * 40)

        finally:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _merge_stats(self) -> None:
        """Merge the statistics from all workers into the master stats."""
        for _ in range(self.num_workers):
            incoming_stats = self.stats_queue.get()
            if incoming_stats == "STOP":
                break
            self.master_stats.merge(incoming_stats)

    def _upload_metadata(self) -> None:
        """Upload the metadata and statistics files to Google Drive."""
        log.info("Uploading metadata and dataset statistics...")

        metadata_filename = Path("metadata.json")

        os.makedirs(self.temp_dir, exist_ok=True)
        filepath = self.temp_dir / metadata_filename

        metadata_content = {
            "max_symbol_id": self.master_stats.global_max_homophones,
            "statistics": self.master_stats.__json__(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(metadata_content, f, indent=4)

        task = UploadTask(
            filepath=filepath,
            filename=metadata_filename,
            cipher_count=0,
            split="metadata",
        )
        self.result_queue.put(task)

    def _feeder_stream(self, tqdm_lock: Any) -> int:
        """Feed the ciphers to the workers using the job queue.

        Args:
            tqdm_lock (Any): The multiprocessing lock to use for tqdm.

        Returns:
            int: The number of ciphers fed to the workers.

        """
        from tqdm import tqdm

        tqdm.set_lock(tqdm_lock)

        count_fed = 0

        with tqdm(
            total=self.total_count,
            desc="Texts Fed to Workers",
            position=0,
            leave=True,
        ) as pbar:
            for count_fed, (split, text_data) in enumerate(self.stream, start=1):
                target_difficulty = None
                if split == "test":
                    length = text_data.get("target_length", 0)
                    target_difficulty = self._assign_test_difficulty(length)
                    if target_difficulty is None:
                        continue

                task = CipherTask(
                    split=split,
                    text_data=text_data,
                    target_difficulty=target_difficulty,
                )
                self.job_queue.put(task)
                pbar.update(1)

                if count_fed % self._logging_interval == 0:
                    log.debug(f"Crossed {count_fed} texts milestone...")

                if count_fed >= self.total_count:
                    log.info(f"Target of {self.total_count} reached. Stopping feeder.")
                    break

        return count_fed

    def _assign_test_difficulty(self, length: int) -> int | None:
        """Find an available difficulty bin for a given test length.

        Args:
            length (int): The sequence length of the test sample.

        Returns:
            int | None: The assigned difficulty, or None if all bins for
                this length are full or the length is invalid.

        """
        if length not in self.test_tracker:
            log.warning(f"Length {length} not found in test matrix.")
            return None

        available_diffs = [
            diff
            for diff, count in self.test_tracker[length].items()
            if count < self.test_samples_per_bin
        ]

        if not available_diffs:
            return None

        selected_diff = random.choice(available_diffs)
        self.test_tracker[length][selected_diff] += 1

        return selected_diff
