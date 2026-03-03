import pytest

from utils.validators import (
	in_range,
	strongly_typed_optional,
	lower_case_no_spaces_alpha_string,
	is_alpha_lowercase_no_spaces,
)


class TestInRangeValidator:
	@pytest.fixture
	def validator(self):
		return in_range(10, 20)

	def test_value_within_range(self, validator):
		validator(15, name="test_param", type_hint=int)

	def test_value_equal_to_min(self, validator):
		validator(10, name="test_param", type_hint=int)

	def test_value_equal_to_max(self, validator):
		validator(20, name="test_param", type_hint=int)

	def test_value_below_min(self, validator):
		with pytest.raises(ValueError) as excinfo:
			validator(5, name="test_param", type_hint=int)
		assert "Parameter `test_param` must be between 10 and 20." in str(excinfo.value)

	def test_value_above_max(self, validator):
		with pytest.raises(ValueError) as excinfo:
			validator(25, name="test_param", type_hint=int)
		assert "Parameter `test_param` must be between 10 and 20." in str(excinfo.value)

	def test_non_integer_value(self, validator):
		# Non-integer values should be ignored by the validator
		validator("string_value", name="test_param", type_hint=str)


class TestStronglyTypedOptionalValidator:
	def test_value_is_none(self):
		# None should be accepted
		strongly_typed_optional(None, name="optional_param", type_hint=int)

	def test_value_of_expected_type(self):
		strongly_typed_optional(42, name="optional_param", type_hint=int)

	def test_illegal_type_value(self):
		with pytest.raises(TypeError) as excinfo:
			strongly_typed_optional("not an int", name="optional_param", type_hint=int)
		assert "Parameter `optional_param` must be of type int or None." in str(
			excinfo.value
		)

	def test_value_of_union_type(self):
		type_hint = int | str | None
		strongly_typed_optional(42, name="optional_param", type_hint=type_hint)  # type: ignore
		strongly_typed_optional("a string", name="optional_param", type_hint=type_hint)  # type: ignore

	def test_value_of_unexpected_union_type(self):
		type_hint = int | str | None
		with pytest.raises(TypeError) as excinfo:
			strongly_typed_optional(3.14, name="optional_param", type_hint=type_hint)  # type: ignore
		assert "Parameter `optional_param` must be of type int, str, or None." in str(
			excinfo.value
		)


class TestLowerCaseNoSpacesAlphaStringValidator:
	def test_valid_string(self):
		lower_case_no_spaces_alpha_string(
			"validstring", name="test_param", type_hint=str
		)

	def test_string_with_spaces(self):
		with pytest.raises(ValueError) as excinfo:
			lower_case_no_spaces_alpha_string(
				"invalid string", name="test_param", type_hint=str
			)
		assert (
			"Parameter `test_param` must be a lowercase alphabetic string with no spaces."
			in str(excinfo.value)
		)

	def test_string_with_uppercase(self):
		with pytest.raises(ValueError) as excinfo:
			lower_case_no_spaces_alpha_string(
				"InvalidString", name="test_param", type_hint=str
			)
		assert (
			"Parameter `test_param` must be a lowercase alphabetic string with no spaces."
			in str(excinfo.value)
		)

	def test_string_with_non_alpha(self):
		with pytest.raises(ValueError) as excinfo:
			lower_case_no_spaces_alpha_string(
				"invalid123", name="test_param", type_hint=str
			)
		assert (
			"Parameter `test_param` must be a lowercase alphabetic string with no spaces."
			in str(excinfo.value)
		)

	def test_non_string_value(self):
		with pytest.raises(TypeError) as excinfo:
			lower_case_no_spaces_alpha_string(12345, name="test_param", type_hint=str)
		assert "Parameter `test_param` must be of type str." in str(excinfo.value)

	def test_empty_string(self):
		with pytest.raises(ValueError) as excinfo:
			lower_case_no_spaces_alpha_string("", name="test_param", type_hint=str)
		assert "Parameter `test_param` must be a non-blank string." in str(
			excinfo.value
		)


class TestIsAlphaLowercaseNoSpaces:
	def test_valid_string(self):
		assert is_alpha_lowercase_no_spaces("validstring") is True

	def test_string_with_spaces(self):
		assert is_alpha_lowercase_no_spaces("invalid string") is False

	def test_string_with_uppercase(self):
		assert is_alpha_lowercase_no_spaces("InvalidString") is False

	def test_string_with_non_alpha(self):
		assert is_alpha_lowercase_no_spaces("invalid123") is False

	def test_empty_string(self):
		assert is_alpha_lowercase_no_spaces("") is False
