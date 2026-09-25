import copy

import pytest

from structured_extraction import merge_jev_fields

RULE = {"numberOfPatients": 1, "consciousness": "unconscious", "weapons": False, "departments": ["Police"]}


def _merge(jev, rule=None):
    return merge_jev_fields(copy.deepcopy(rule if rule is not None else RULE), jev)


@pytest.mark.parametrize("p, expected", [(0.7, True), (0.95, True), (0.3, False), (0.05, False)])
def test_weapon_confident_band_overrides_rule(p, expected):
    rule = {**RULE, "weapons": not expected}
    fields, sources = _merge({"weapon": p}, rule)
    assert fields["weapons"] is expected
    assert sources == {"weapons": "jev"}


@pytest.mark.parametrize("p", [0.31, 0.5, 0.69])
@pytest.mark.parametrize("rule_value", [True, False])
def test_weapon_uncertain_band_keeps_rule(p, rule_value):
    fields, sources = _merge({"weapon": p}, {**RULE, "weapons": rule_value})
    assert fields["weapons"] is rule_value
    assert sources == {}


@pytest.mark.parametrize("p, expected", [(0.7, "unconscious"), (0.3, "conscious"), (0.9, "unconscious"), (0.1, "conscious")])
def test_unconscious_maps_to_consciousness_label(p, expected):
    rule = {**RULE, "consciousness": None}
    fields, sources = _merge({"unconscious": p}, rule)
    assert fields["consciousness"] == expected
    assert sources == {"consciousness": "jev"}


def test_unconscious_uncertain_keeps_rule():
    fields, sources = _merge({"unconscious": 0.5})
    assert fields["consciousness"] == "unconscious"
    assert sources == {}


def test_agreeing_confident_answer_gives_no_source():
    fields, sources = _merge({"unconscious": 0.99, "weapon": 0.01})
    assert fields == RULE
    assert sources == {}


@pytest.mark.parametrize("choice, expected", [("0", 0), ("10", 10), ("3", 3)])
def test_patients_confident_choice_used(choice, expected):
    fields, sources = _merge({"patients": (choice, 0.9)})
    assert fields["numberOfPatients"] == expected
    assert isinstance(fields["numberOfPatients"], int)
    assert sources == {"numberOfPatients": "jev"}


def test_patients_boundary_0_7_is_used():
    fields, sources = _merge({"patients": ("2", 0.7)})
    assert fields["numberOfPatients"] == 2
    assert sources == {"numberOfPatients": "jev"}


def test_patients_0_69_is_ignored():
    fields, sources = _merge({"patients": ("2", 0.69)})
    assert fields["numberOfPatients"] == 1
    assert sources == {}


def test_patients_replaces_rule_none():
    fields, sources = _merge({"patients": ("4", 0.8)}, {**RULE, "numberOfPatients": None})
    assert fields["numberOfPatients"] == 4
    assert sources == {"numberOfPatients": "jev"}


def test_patients_same_as_rule_gives_no_source():
    fields, sources = _merge({"patients": ("1", 0.95)})
    assert fields["numberOfPatients"] == 1
    assert sources == {}


def test_department_added_at_boundary_0_7():
    fields, sources = _merge({"fire": 0.7})
    assert fields["departments"] == ["Police", "Fire"]
    assert sources == {"departments": "jev"}


def test_department_removed_at_boundary_0_3():
    fields, sources = _merge({"police": 0.3})
    assert fields["departments"] == []
    assert sources == {"departments": "jev"}


def test_department_uncertain_keeps_rule():
    fields, sources = _merge({"police": 0.5, "ems": 0.69, "fire": 0.31})
    assert fields["departments"] == ["Police"]
    assert sources == {}


def test_departments_canonical_order_regardless_of_add_order():
    rule = {**RULE, "departments": []}
    fields, _ = _merge({"fire": 0.9, "ems": 0.9, "police": 0.9}, rule)
    assert fields["departments"] == ["Police", "Emergency Medical", "Fire"]
    fields, _ = _merge({"ems": 0.9, "fire": 0.9}, rule)
    assert fields["departments"] == ["Emergency Medical", "Fire"]


def test_rule_added_department_can_be_removed():
    rule = {**RULE, "departments": ["Police", "Emergency Medical"]}
    fields, sources = _merge({"ems": 0.02}, rule)
    assert fields["departments"] == ["Police"]
    assert sources == {"departments": "jev"}


def test_department_confirming_rule_gives_no_source():
    fields, sources = _merge({"police": 0.99, "fire": 0.1})
    assert fields["departments"] == ["Police"]
    assert sources == {}


@pytest.mark.parametrize("jev", [None, {}])
def test_no_answers_returns_equal_copy_and_no_sources(jev):
    rule = copy.deepcopy(RULE)
    fields, sources = merge_jev_fields(rule, jev)
    assert fields == RULE
    assert sources == {}
    assert fields is not rule
    assert fields["departments"] is not rule["departments"]


def test_partial_answers_only_touch_their_fields():
    fields, sources = _merge({"weapon": 0.95})
    assert fields == {**RULE, "weapons": True}
    assert sources == {"weapons": "jev"}


def test_inputs_are_not_mutated():
    rule = copy.deepcopy(RULE)
    jev = {"weapon": 0.9, "unconscious": 0.1, "police": 0.1, "fire": 0.9, "patients": ("5", 0.9)}
    rule_before, jev_before = copy.deepcopy(rule), copy.deepcopy(jev)
    fields, _ = merge_jev_fields(rule, jev)
    assert rule == rule_before
    assert jev == jev_before
    assert fields["departments"] == ["Fire"]
    assert rule["departments"] == ["Police"]


def test_result_keys_equal_rule_field_keys():
    jev = {"weapon": 0.9, "unconscious": 0.1, "police": 0.1, "ems": 0.9, "fire": 0.9, "patients": ("5", 0.9)}
    fields, _ = _merge(jev)
    assert set(fields) == set(RULE)


def test_sample_call_only_patients_changes():
    rule = {"numberOfPatients": 1, "consciousness": "unconscious", "weapons": True,
            "departments": ["Police", "Emergency Medical"]}
    jev = {"weapon": 0.96, "unconscious": 0.97, "police": 0.99, "ems": 0.99, "fire": 0.21, "patients": ("2", 0.98)}
    fields, sources = _merge(jev, rule)
    assert fields == {**rule, "numberOfPatients": 2}
    assert sources == {"numberOfPatients": "jev"}


def test_no_injury_gas_leak_scenario():
    rule = {"numberOfPatients": 1, "consciousness": "conscious", "weapons": False,
            "departments": ["Emergency Medical"]}
    jev = {"weapon": 0.02, "unconscious": 0.03, "police": 0.05, "ems": 0.02, "fire": 0.95, "patients": ("0", 0.98)}
    fields, sources = _merge(jev, rule)
    assert fields["numberOfPatients"] == 0
    assert fields["departments"] == ["Fire"]
    assert sources == {"numberOfPatients": "jev", "departments": "jev"}
