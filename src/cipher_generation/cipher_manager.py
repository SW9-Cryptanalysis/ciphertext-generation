import multiprocessing as mp
from utils.logging import get_logger_tqdm
import os
from typing import Iterable, Any
import json
from pathlib import Path
import shutil
from utils.constants import PROJECT_ROOT

from cipher_generation.drive_uploader import DriveUploader, DriveUploaderConfig
from cipher_generation.cipher_producer import CipherProducer, ProducerConfig
from utils.constants import BATCH_SIZE
from dataset_stats import DatasetStatsAggregator

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
        config: dict[str, dict[str, Any]],
        text_stream_source: Iterable,
        num_workers: int | None = None,
    ) -> None:
        """Initialize the CipherManager.

        Args:
            config (dict[str, dict[str, Any]]): Configuration dictionary mapping splits
                to their folder IDs and target counts.
            text_stream_source (Iterable): The iterable source of text chunks.
            num_workers (int | None, optional): The number of workers to use.
                Defaults to None (use all available CPUs).

        """
        self.config = config
        self.stream = text_stream_source

        self.total_count = sum(split_data["count"] for split_data in config.values())
        self.split_folders = {
            split: split_data["folder_id"] for split, split_data in config.items()
        }

        self.num_workers = num_workers or max(1, (os.cpu_count() or 4) - 2)

        self.job_queue = mp.Queue(maxsize=1000)
        self.result_queue = mp.Queue()
        self.stats_queue = mp.Queue()

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
                    batch_size=BATCH_SIZE,
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

            for p in workers:
                p.join()

            log.info("Workers finished. Merging statistics from all workers...")
            for _ in range(self.num_workers):
                incoming_stats = self.stats_queue.get()
                self.master_stats.merge(incoming_stats)

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

        self.result_queue.put(("metadata", filepath, metadata_filename, 0))

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
                self.job_queue.put((split, text_data))
                pbar.update(1)

                if count_fed % self._logging_interval == 0:
                    log.debug(f"Crossed {count_fed} texts milestone...")

                if count_fed >= self.total_count:
                    log.info(f"Target of {self.total_count} reached. Stopping feeder.")
                    break

        return count_fed
