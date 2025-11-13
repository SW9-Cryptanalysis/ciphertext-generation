import pytest
import json
import os
from utils.check_cipher_overlap import (
    get_jaccard_similarity,
    get_ciphers,
    check_cipher_overlap,
)
import utils.check_cipher_overlap as target_module  # Imported to monkeypatch module-level attributes


# --- Fixtures ---

@pytest.fixture
def sample_ciphers_list():
    return [
        {"name": "c_1.json", "plaintext": "hello world", "id": 1},
        {"name": "c_2.json", "plaintext": "hello earth", "id": 2},  # Overlaps "hello"
        {"name": "c_3.json", "plaintext": "apple banana", "id": 3}, # No overlap
        {"name": "c_4.json", "plaintext": "hello world", "id": 4},  # Identical (should be skipped)
    ]


@pytest.fixture
def mock_logger(monkeypatch):
    """Replaces the logger with a simple list-based capture."""
    logs = []

    class FakeLogger:
        def info(self, msg):
            logs.append(msg)

    monkeypatch.setattr(target_module, "logger", FakeLogger())
    return logs


# --- Tests ---

class TestJaccardSimilarity:
    @pytest.mark.parametrize(
        "str1, str2, expected",
        [
            ("a b c", "a b c", 1.0),       # Identical
            ("a b c", "d e f", 0.0),       # No overlap
            ("a b", "b c", 0.333),         # Intersection 1 / Union 3 = 0.33...
            ("", "a", 0.0),                # Empty handling
        ],
    )
    def test_calculation(self, str1, str2, expected):
        # Using approx for floating point comparison
        assert get_jaccard_similarity(str1, str2) == pytest.approx(expected, abs=0.01)


class TestGetCiphers:
    def test_get_ciphers_reads_files(self, tmp_path, monkeypatch):
        # 1. Create a temporary directory structure
        d = tmp_path / "ciphers"
        d.mkdir()
        
        # 2. Create dummy json files
        cipher1 = {"plaintext": "test one", "data": 1}
        cipher2 = {"plaintext": "test two", "data": 2}
        
        # Correct naming convention (starts with c_ and ends with .json)
        (d / "c_valid1.json").write_text(json.dumps(cipher1), encoding="utf-8")
        (d / "c_valid2.json").write_text(json.dumps(cipher2), encoding="utf-8")
        
        # Invalid files (should be ignored)
        (d / "readme.txt").write_text("ignore me", encoding="utf-8")
        (d / "other.json").write_text("{}", encoding="utf-8") # Doesn't start with c_

        # 3. Monkeypatch os.listdir or change directory so the function finds the files
        # Since the function uses relative path "ciphers", we switch cwd to tmp_path
        monkeypatch.chdir(tmp_path)

        # 4. Execution
        results = get_ciphers()

        # 5. Assertions
        assert len(results) == 2
        names = sorted([r["name"] for r in results])
        assert names == ["c_valid1.json", "c_valid2.json"]
        
        # Verify content was loaded
        assert results[0]["plaintext"] in ["test one", "test two"]

    def test_get_ciphers_empty(self, tmp_path, monkeypatch):
        d = tmp_path / "ciphers"
        d.mkdir()
        monkeypatch.chdir(tmp_path)

        assert get_ciphers() == []


class TestCheckCipherOverlap:
    def test_detects_overlaps(self, monkeypatch, sample_ciphers_list, mock_logger):
        # Monkeypatch get_ciphers to avoid file I/O and return controlled data
        monkeypatch.setattr(
            target_module, 
            "get_ciphers", 
            lambda: sample_ciphers_list
        )

        result = check_cipher_overlap()

        # c_1 overlaps with c_2 ("hello" in common)
        # c_1 skips c_4 (identical text)
        assert "c_1.json" in result
        overlaps_for_1 = result["c_1.json"]
        
        assert len(overlaps_for_1) == 1
        assert overlaps_for_1[0]["name"] == "c_2.json"

        # Verify Logging
        # We expect 4 log messages (one per cipher processed)
        assert len(mock_logger) == 4
        assert "Found 1 overlapping ciphers for c_1.json" in mock_logger

    def test_filters_identical_plaintext(self, monkeypatch, mock_logger):
        ciphers = [
            {"name": "A", "plaintext": "same text"},
            {"name": "B", "plaintext": "same text"},
        ]
        
        monkeypatch.setattr(target_module, "get_ciphers", lambda: ciphers)
        
        result = check_cipher_overlap()
        
        # Should be empty because they are identical and the code 'continues' on identical text
        assert result == {}
        assert "Found 0 overlapping ciphers for A" in mock_logger

    def test_filters_low_similarity(self, monkeypatch):
        # Intersection: 1 word ("common"). Union: 101 words. 
        # Jaccard = ~0.0099 ( < 0.01 threshold )
        t1 = "common " + " ".join(str(i) for i in range(50))
        t2 = "common " + " ".join(str(i) for i in range(50, 100))
        
        ciphers = [
            {"name": "A", "plaintext": t1},
            {"name": "B", "plaintext": t2},
        ]

        monkeypatch.setattr(target_module, "get_ciphers", lambda: ciphers)
        
        result = check_cipher_overlap()
        
        assert result == {}
