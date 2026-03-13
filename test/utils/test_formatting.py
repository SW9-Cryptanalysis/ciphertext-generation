import pytest
from utils.formatting import clean_spaces, format_text, numbers_to_words


class TestNumbersToWords:
    """Tests covering the number-to-words conversion, including edge cases and safety guards."""

    @pytest.mark.parametrize(
        "input_text, expected_output",
        [
            # Standard integers
            ("I have 3 dogs and 21 cats.", "I have three dogs and twenty-one cats."),
            (
                "The year 2024 will be followed by 2025.",
                "The year two thousand and twenty-four will be followed by two thousand and twenty-five.",
            ),
            # Floats
            (
                "In 2020, the population was 7.8 billion.",
                "In two thousand and twenty, the population was seven point eight billion.",
            ),
            (
                "Mixed 100 and text 42.5.",
                "Mixed one hundred and text forty-two point five.",
            ),
            # Leading zeros
            (
                "Leading zeros 007 should be seven.",
                "Leading zeros seven should be seven.",
            ),
            # Large valid numbers
            (
                "1234567890",
                "one billion, two hundred and thirty-four million, five hundred and sixty-seven thousand, eight hundred and ninety",
            ),
            # Ordinals and dates
            ("May 3rd, 2024", "May third, two thousand and twenty-four"),
            ("He came from the 10th floor.", "He came from the tenth floor."),
            (
                "He was the 1.949th man in the room.",
                "He was the one thousand, nine hundred and forty-ninth man in the room.",
            ),
            # Edge cases (No numbers, empty string)
            ("No numbers here!", "No numbers here!"),
            ("", ""),
        ],
        ids=lambda text: text[:15] + "..." if len(text) > 15 else text,
    )
    def test_valid_conversions(self, input_text, expected_output):
        """Verify that valid numbers, floats, and ordinals are correctly translated."""
        assert numbers_to_words(input_text) == expected_output

    def test_massive_number_guard_logs_and_strips(self, mocker):
        """Verify that numbers over 50 digits are caught, logged, and replaced with an empty string."""
        mock_open = mocker.patch("builtins.open", mocker.mock_open())
        massive_number = "1" * 51
        input_text = f"Here is a matrix dump {massive_number} hidden in text."

        # It should strip the number out completely
        result = numbers_to_words(input_text, source_id="book_123")

        assert result == "Here is a matrix dump  hidden in text."

        # Verify the log file was opened in append mode
        mock_open.assert_called_once_with(
            "arxiv_parsing_errors.log", "a", encoding="utf-8"
        )

        # Verify the log contents
        handle = mock_open()
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        assert "Massive Number Detected" in written_content
        assert "book_123" in written_content

    def test_num2words_exception_handling(self, mocker):
        """Verify that unexpected num2words crashes are caught, logged with context, and skipped."""
        # Force num2words to crash when called
        mocker.patch(
            "utils.formatting.num2words", side_effect=ValueError("Simulated Crash")
        )
        mock_open = mocker.patch("builtins.open", mocker.mock_open())

        input_text = "Before context 42 after context."
        result = numbers_to_words(input_text, source_id="book_456")

        # The failing number '42' should be stripped
        assert result == "Before context  after context."

        # Verify the exception was logged with the text context
        handle = mock_open()
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        assert "num2words failure" in written_content
        assert "book_456" in written_content
        assert "Simulated Crash" in written_content
        assert "Before context 42 after context." in written_content


class TestFormatText:
    """Tests covering full text normalization, diacritic stripping, and punctuation removal."""

    @pytest.mark.parametrize(
        "input_text, expected_output",
        [
            # Standard formatting, lowercasing, and punctuation removal
            (
                "I met a traveller from an antique land, Who said—“Two vast and trunkless legs of stone Stand in the desert...",
                "i met a traveller from an antique land who saidtwo vast and trunkless legs of stone stand in the desert",
            ),
            # Diacritics and accents
            ("Kózuscek Fránçois àéäöåôëëën", "kozuscek francois aeaoaoeeen"),
            # Mixed numbers and symbols
            ("123 ABC def!@#", "one hundred and twentythree abc def"),
            (
                "2024 100 3.14",
                "two thousand and twentyfour one hundred three point one four",
            ),
            # Extreme symbol stripping
            (
                "1234!@#$%^&'*()’_+-=[]{}’|;:',.<>?/`~",
                "one thousand two hundred and thirtyfour",
            ),
            # Multiple spaces and dashed words
            ("Hello---world!!  This   is a    test.", "helloworld this is a test"),
            # Complex punctuation scenarios
            (
                "Wait—did you seriously just say, ‘We’re leaving at 6:00 a.m., no exceptions!’—right after promising this would be a relaxing weekend?",
                "waitdid you seriously just say were leaving at sixzero am no exceptionsright after promising this would be a relaxing weekend",
            ),
            # Empty string
            ("", ""),
        ],
        ids=lambda text: text[:15] + "..." if len(text) > 15 else text,
    )
    def test_format_text_variations(self, input_text, expected_output):
        """Verify that strings are correctly normalized and scrubbed of symbols."""
        assert format_text(input_text) == expected_output

    def test_format_text_raises_type_error(self):
        """Verify that passing non-string parameters raises a strict TypeError."""
        with pytest.raises(
            TypeError,
            match="Parameter 'text' requires type 'str' but received type 'int'.",
        ):
            format_text(12345)  # type: ignore


class TestCleanSpaces:
    """Tests covering the removal of standard whitespace characters."""

    @pytest.mark.parametrize(
        "input_text, expected_output",
        [
            ("This is a test.", "Thisisatest."),
            ("  Leading and trailing spaces  ", "Leadingandtrailingspaces"),
            ("Multiple   spaces   in   between", "Multiplespacesinbetween"),
            ("NoSpacesHere", "NoSpacesHere"),
            ("", ""),
        ],
        ids=[
            "standard_spaces",
            "leading_trailing",
            "multiple_spaces",
            "no_spaces",
            "empty_string",
        ],
    )
    def test_clean_spaces_variations(self, input_text, expected_output):
        """Verify that all spaces are cleanly removed from the string."""
        assert clean_spaces(input_text) == expected_output
