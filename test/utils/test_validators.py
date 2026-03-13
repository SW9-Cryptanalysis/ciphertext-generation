import pytest
from dataclasses import dataclass
from typing import Any, TypedDict
from contextlib import nullcontext as does_not_raise

from utils.validators import (
    in_range,
    strongly_typed_optional,
    lower_case_no_spaces_alpha_string,
    validate_typed_dict,
)


@dataclass
class RangeTestCase:
    """Encapsulates parameters for in_range validation tests."""

    desc: str
    value: Any
    min_val: int
    max_val: int
    expected_context: Any
    match: str | None = None


@dataclass
class TypeTestCase:
    """Encapsulates parameters for type validation tests."""

    desc: str
    value: Any
    type_hint: Any
    expected_context: Any
    match: str | None = None


@dataclass
class ValueTestCase:
    """Encapsulates parameters for generic value validation tests."""

    desc: str
    value: Any
    expected_context: Any
    match: str | None = None


class DummyTextStream(TypedDict):
    """Mock TypedDict to simulate TextStream annotations."""

    id: str
    text: str
    source_name: str


class DummyConfig(TypedDict):
    """Mock TypedDict to test validate_typed_dict."""

    name: str
    items: list[int]


IN_RANGE_CASES = [
    RangeTestCase(
        desc="Valid: Inside range",
        value=5,
        min_val=1,
        max_val=10,
        expected_context=does_not_raise(),
    ),
    RangeTestCase(
        desc="Valid: Exact minimum boundary",
        value=1,
        min_val=1,
        max_val=10,
        expected_context=does_not_raise(),
    ),
    RangeTestCase(
        desc="Valid: Exact maximum boundary",
        value=10,
        min_val=1,
        max_val=10,
        expected_context=does_not_raise(),
    ),
    RangeTestCase(
        desc="Invalid: Below minimum",
        value=0,
        min_val=1,
        max_val=10,
        expected_context=pytest.raises(ValueError),
        match="must be between",
    ),
    RangeTestCase(
        desc="Invalid: Above maximum",
        value=11,
        min_val=1,
        max_val=10,
        expected_context=pytest.raises(ValueError),
        match="must be between",
    ),
    RangeTestCase(
        desc="Ignored: Non-integer types safely return early",
        value="5",
        min_val=1,
        max_val=10,
        expected_context=does_not_raise(),
    ),
]


@pytest.mark.parametrize("case", IN_RANGE_CASES, ids=lambda c: c.desc)
def test_in_range(case: RangeTestCase):
    """Test the integer range boundary validator using a single case object.

    The target value must be passed positionally, while the parameter name
    is supplied as a keyword argument to satisfy the @validator wrapper.
    """
    validator_func = in_range(case.min_val, case.max_val)
    with case.expected_context as exc_info:
        validator_func(case.value, name="test_param", type_hint=int)
    if case.match and exc_info:
        assert case.match in str(exc_info.value)


STRONGLY_TYPED_OPTIONAL_CASES = [
    TypeTestCase(
        desc="Valid: None passes for any expected type",
        value=None,
        type_hint=int,
        expected_context=does_not_raise(),
    ),
    TypeTestCase(
        desc="Valid: Exact type match",
        value=5,
        type_hint=int,
        expected_context=does_not_raise(),
    ),
    TypeTestCase(
        desc="Valid: Matches one of UnionType options",
        value=5,
        type_hint=str | int,
        expected_context=does_not_raise(),
    ),
    TypeTestCase(
        desc="Invalid: Type mismatch",
        value="5",
        type_hint=int,
        expected_context=pytest.raises(TypeError),
        match="must be of type int",
    ),
    TypeTestCase(
        desc="Invalid: UnionType mismatch",
        value=[1, 2],
        type_hint=str | int,
        expected_context=pytest.raises(TypeError),
        match="must be of type str, int",
    ),
]


@pytest.mark.parametrize("case", STRONGLY_TYPED_OPTIONAL_CASES, ids=lambda c: c.desc)
def test_strongly_typed_optional(case: TypeTestCase):
    """Test the strongly typed optional parameter validator using a single case object."""
    with case.expected_context as exc_info:
        strongly_typed_optional(case.value, name="test_param", type_hint=case.type_hint)
    if case.match and exc_info:
        assert case.match in str(exc_info.value)


LOWER_CASE_ALPHA_CASES = [
    TypeTestCase(
        desc="Valid: Lowercase alpha string without spaces",
        value="helloworld",
        type_hint=str,
        expected_context=does_not_raise(),
    ),
    TypeTestCase(
        desc="Invalid: Not a string",
        value=123,
        type_hint=str,
        expected_context=pytest.raises(TypeError),
        match="must be of type str",
    ),
    TypeTestCase(
        desc="Invalid: Empty string",
        value="",
        type_hint=str,
        expected_context=pytest.raises(ValueError),
        match="non-blank",
    ),
    TypeTestCase(
        desc="Invalid: Contains spaces",
        value="hello world",
        type_hint=str,
        expected_context=pytest.raises(ValueError),
        match="lowercase alphabetic",
    ),
    TypeTestCase(
        desc="Invalid: Contains uppercase characters",
        value="HelloWorld",
        type_hint=str,
        expected_context=pytest.raises(ValueError),
        match="lowercase alphabetic",
    ),
]


@pytest.mark.parametrize("case", LOWER_CASE_ALPHA_CASES, ids=lambda c: c.desc)
def test_lower_case_no_spaces_alpha_string(case: TypeTestCase):
    """Test the strictly constrained string validator using a single case object."""
    with case.expected_context as exc_info:
        lower_case_no_spaces_alpha_string(
            case.value, name="test_param", type_hint=case.type_hint
        )
    if case.match and exc_info:
        assert case.match in str(exc_info.value)


VALIDATE_TYPED_DICT_CASES = [
    TypeTestCase(
        desc="Valid: Dictionary perfectly matches TypedDict schema",
        value={"name": "test", "items": [1, 2, 3]},
        type_hint=DummyConfig,
        expected_context=does_not_raise(),
    ),
    TypeTestCase(
        desc="Invalid: Missing key",
        value={"items": [1, 2, 3]},
        type_hint=DummyConfig,
        expected_context=pytest.raises(ValueError),
        match="Missing required key",
    ),
    TypeTestCase(
        desc="Invalid: Root key type mismatch",
        value={"name": 123, "items": [1, 2, 3]},
        type_hint=DummyConfig,
        expected_context=pytest.raises(ValueError),
        match="Invalid type for key 'name'",
    ),
    TypeTestCase(
        desc="Invalid: Generic list sub-type mismatch",
        value={"name": "test", "items": [1, "two", 3]},
        type_hint=DummyConfig,
        expected_context=pytest.raises(ValueError),
        match="All elements in",
    ),
    TypeTestCase(
        desc="Invalid: Not a dictionary",
        value="not a dict",
        type_hint=DummyConfig,
        expected_context=pytest.raises(TypeError),
        match="must be of type dict",
    ),
]


@pytest.mark.parametrize("case", VALIDATE_TYPED_DICT_CASES, ids=lambda c: c.desc)
def test_validate_typed_dict(case: TypeTestCase):
    """Test the recursive TypedDict schema validator using a single case object."""
    with case.expected_context as exc_info:
        validate_typed_dict(case.value, name="test_dict", type_hint=case.type_hint)
    if case.match and exc_info:
        assert case.match in str(exc_info.value)
