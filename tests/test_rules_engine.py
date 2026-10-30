import pytest

from rules_engine import (
    condition_matches, conditions_can_overlap, find_conflicts,
    parse_condition, rule_matches, rules_conflict,
)

SENSORS = {"temperature": 26.0, "humidity": 40.0, "light": 10, "motion": False}


def rule(action="Включить", device="Кондиционер", **conditions):
    return {"device": device, "action": action, **conditions}


class TestParseAndMatch:
    @pytest.mark.parametrize("cond, value, expected", [
        (">25", 26, True), (">25", 25, False),
        (">=25", 25, True), ("<25", 25, False),
        ("<=25", 25, True), ("=25", 25, True), ("=25", 25.1, False),
    ])
    def test_operators(self, cond, value, expected):
        assert condition_matches(cond, value) is expected

    def test_invalid_condition_does_not_match(self):
        assert condition_matches("примерно 25", 25) is False

    def test_parse_rejects_garbage(self):
        with pytest.raises(ValueError):
            parse_condition("25")


class TestRuleMatches:
    def test_no_conditions_always_matches(self):
        assert rule_matches(rule(), SENSORS, "день")

    def test_motion_false_requires_no_motion(self):
        # раньше правило "движения нет" срабатывало только при наличии движения
        assert rule_matches(rule(motion=False), SENSORS, "день")
        assert not rule_matches(rule(motion=True), SENSORS, "день")

    def test_time_of_day(self):
        assert rule_matches(rule(time_of_day="день"), SENSORS, "день")
        assert not rule_matches(rule(time_of_day="ночь"), SENSORS, "день")


class TestConflicts:
    def test_same_action_is_not_conflict(self):
        assert not rules_conflict(rule("Включить", temperature=">25"),
                                  rule("Включить", temperature=">25"))

    def test_different_devices_not_conflict(self):
        assert not rules_conflict(rule(device="Свет"), rule("Выключить", device="Обогреватель"))

    def test_overlapping_ranges_conflict(self):
        # >25 и <30 одновременно истинны при 27 - раньше это не находилось
        assert rules_conflict(rule("Включить", temperature=">25"),
                              rule("Выключить", temperature="<30"))

    def test_disjoint_ranges_not_conflict(self):
        assert not rules_conflict(rule("Включить", temperature=">25"),
                                  rule("Выключить", temperature="<20"))

    def test_touching_open_boundaries_not_conflict(self):
        assert not rules_conflict(rule("Включить", temperature=">25"),
                                  rule("Выключить", temperature="<25"))

    def test_touching_closed_boundaries_conflict(self):
        assert rules_conflict(rule("Включить", temperature=">=25"),
                              rule("Выключить", temperature="<=25"))

    def test_different_time_of_day_not_conflict(self):
        # раньше совпадение температуры делало такую пару "конфликтом"
        assert not rules_conflict(rule("Включить", temperature=">25", time_of_day="день"),
                                  rule("Выключить", temperature=">25", time_of_day="ночь"))

    def test_rule_without_conditions_conflicts_with_any(self):
        assert rules_conflict(rule("Включить"), rule("Выключить", humidity=">50"))

    def test_motion_difference_not_conflict(self):
        assert not rules_conflict(rule("Включить", motion=True), rule("Выключить", motion=False))

    def test_find_conflicts_returns_indexes(self):
        rules = [rule("Включить", temperature=">25"),
                 rule("Включить", device="Свет"),
                 rule("Выключить", temperature="<30")]
        assert [(i, j) for i, j, _ in find_conflicts(rules)] == [(0, 2)]
        assert find_conflicts(rules)[0][2] == ["температура"]

    def test_overlap_is_symmetric(self):
        a, b = rule(temperature=">25"), rule("Выключить", temperature="<30")
        assert conditions_can_overlap(a, b) == conditions_can_overlap(b, a)
