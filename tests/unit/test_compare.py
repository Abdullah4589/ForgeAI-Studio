from typing import Any

import pytest
from pydantic import ValidationError

from forge_api.schemas.compare import CompareRequest
from forge_api.services.compare_service import cell_requests


def request(axis: dict[str, Any], **overrides: Any) -> CompareRequest:
    body: dict[str, Any] = {"prompt": "a fox", "model_id": 1, "axis": axis, **overrides}
    return CompareRequest.model_validate(body)


def test_lora_strength_axis_includes_no_lora_baseline() -> None:
    cells = cell_requests(
        request({"kind": "lora_strength", "values": [None, 0.4, 0.8]}, lora_id=3), seed=9
    )
    assert [(c.lora_id, c.lora_strength) for c in cells] == [(None, 0), (3, 0.4), (3, 0.8)]
    assert {c.seed for c in cells} == {9}
    assert {c.num_images for c in cells} == {1}


def test_seed_axis_varies_only_the_seed() -> None:
    cells = cell_requests(request({"kind": "seed", "values": [0, 5, 7]}), seed=123)
    assert [c.seed for c in cells] == [0, 5, 7]
    assert {c.model_id for c in cells} == {1}


def test_model_axis_varies_only_the_model() -> None:
    compare = request({"kind": "model", "values": [2, 4]}, model_id=None, seed=11)
    cells = cell_requests(compare, seed=11)
    assert [c.model_id for c in cells] == [2, 4]
    assert {c.seed for c in cells} == {11}


@pytest.mark.parametrize(
    ("axis", "overrides", "message"),
    [
        ({"kind": "seed", "values": [1]}, {}, "at least 2"),
        ({"kind": "seed", "values": [1, 2, 3, 4, 5, 6, 7]}, {}, "at most 6"),
        ({"kind": "seed", "values": [1, 1]}, {}, "unique"),
        ({"kind": "seed", "values": [1, 2]}, {"seed": 5}, "Leave seed empty"),
        ({"kind": "seed", "values": [-1, 2]}, {}, "greater than or equal"),
        ({"kind": "model", "values": [1, 2]}, {}, "Leave model_id empty"),
        ({"kind": "lora_strength", "values": [0.5, 1]}, {}, "Choose a LoRA"),
        ({"kind": "lora_strength", "values": [None, 3]}, {"lora_id": 1}, "less than or equal"),
        ({"kind": "steps", "values": [1, 2]}, {}, "does not match any of the expected tags"),
    ],
)
def test_invalid_comparisons_are_rejected(
    axis: dict[str, Any], overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        request(axis, **overrides)


def test_model_id_required_for_non_model_axis() -> None:
    with pytest.raises(ValidationError, match="model_id is required"):
        request({"kind": "seed", "values": [1, 2]}, model_id=None)
