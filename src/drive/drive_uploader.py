import multiprocessing as mp
from multiprocessing.queues import Queue as MPQueue
from utils.logging import get_colored_logger
from dataclasses import dataclass
# We now rely solely on the single-file upload function:
from utils.drive import authenticate_drive_terminal, upload_to_drive # <-- REMOVED execute_batch_upload
import time
from tqdm import tqdm
from typing import Any
# BATCH_SIZE is no longer used for upload size, but keeping import is fine
from utils.constants import BATCH_SIZE 

log = get_colored_logger("drive_uploader")
SENTINEL = 'STOP'

@dataclass
class DriveUploaderConfig:
    folder_id: str
    total_ciphers: int

class DriveUploader (mp.Process):
    def __init__(self, queue: MPQueue[Any], config: DriveUploaderConfig, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = queue
        self.folder_id = config.folder_id
        self.total_ciphers = config.total_ciphers
        self.drive_service = None
  
    def run(self):
        process_name = self.name
        try:
            self.drive_service = authenticate_drive_terminal()
        except Exception as e:
            log.critical(f"{process_name}: Error authenticating drive service: {e}", exc_info=True)
            return

        # current_batch_list is no longer needed
        uploaded_count = 0
        
        with tqdm(total=self.total_ciphers, desc="Total Ciphers Uploaded") as pbar:
            # We must set a timeout here, or the process will hang if the queue is empty
            # and no sentinel arrives (e.g., if a producer crashed).
            while uploaded_count < self.total_ciphers:
                try:
                    # Use a short timeout to check if the overall job is done
                    item = self.queue.get(timeout=10) 
                except mp.Queue.empty:
                    # If the queue is empty after waiting, check if all ciphers are done
                    if uploaded_count >= self.total_ciphers:
                        break
                    else:
                        # Otherwise, wait a bit more for producers to catch up
                        continue 
                
                if item == SENTINEL:
                    break
                    
                filename, file_bytes = item
                
                # --- START OF SERIAL UPLOAD LOGIC ---
                
                # 1. Upload the single file (relies on upload_to_drive's internal backoff)
                try:
                    # upload_to_drive must contain the Exponential Backoff and Retry logic
                    file_id = upload_to_drive(
                        self.drive_service, 
                        file_bytes, 
                        filename, 
                        self.folder_id
                    )
                    
                    if file_id:
                        # 2. Update status only on success
                        uploaded_count += 1
                        pbar.update(1)
                    else:
                        # The file failed after all retries in upload_to_drive; log and skip
                        log.warning(f"File {filename} failed all upload attempts and was skipped.")

                except Exception as e:
                    # Catch any rare, unexpected external error and log it
                    log.error(f"FATAL: Unexpected error during upload of {filename}: {e}", exc_info=True)
                    # Do not crash the process; continue to the next item

            # No final partial batch logic needed since we upload one by one.

        log.info(f"{process_name} finished. Total uploaded: {uploaded_count} files.")