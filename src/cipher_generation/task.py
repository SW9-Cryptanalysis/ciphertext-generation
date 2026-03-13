from dataclasses import dataclass
from pathlib import Path
from utils.text_splits import TextStream

@dataclass
class CipherTask:
    """Task to be processed by the cipher generation process.

    Attributes:
        split (str): The split the cipher is being generated for.
        text_data (dict[str, Any]): The text data to be encrypted.
        target_difficulty (float | int | None, optional): The difficulty level for the
            cipher. Defaults to None (use random difficulty).

    """

    split: str
    text_data: TextStream
    target_difficulty: int | None = None


@dataclass
class UploadTask:
    """Represents a file ready to be uploaded to Google Drive."""

    filepath: Path
    filename: Path
    cipher_count: int
    split: str
