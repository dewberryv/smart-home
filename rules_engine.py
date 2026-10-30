from __future__ import annotations

import math
import re
from dataclasses import dataclass

NUMERIC_KEYS = ("temperature", "humidity", "light")
CATEGORY_KEYS = ("time_of_day", "motion")
CONDITION_KEYS = NUMERIC_KEYS + CATEGORY_KEYS

CONDITION_LABELS = {
    "temperature": "температура",
    "humidity": "влажность",
    "light": "освещённость",
    "time_of_day": "время суток",
    "motion": "движение",
}

_CONDITION_RE = re.compile(r"^\s*(>=|<=|>|<|=)\s*(-?\d+(?:\.\d+)?)\s*$")


@dataclass(frozen=True)
class Interval:
    """Числовой промежуток с признаком включения границ"""

    low: float = -math.inf
    low_closed: bool = False
    high: float = math.inf
    high_closed: bool = False

    def intersect(self, other: "Interval") -> "Interval":
        if self.low > other.low:
            low, low_closed = self.low, self.low_closed
        elif self.low < other.low:
            low, low_closed = other.low, other.low_closed
        else:
            low, low_closed = self.low, self.low_closed and other.low_closed

        if self.high < other.high:
            high, high_closed = self.high, self.high_closed
        elif self.high > other.high:
            high, high_closed = other.high, other.high_closed
        else:
            high, high_closed = self.high, self.high_closed and other.high_closed

        return Interval(low, low_closed, high, high_closed)

    def is_empty(self) -> bool:
        if self.low > self.high:
            return True
        if self.low == self.high:
            return not (self.low_closed and self.high_closed)
        return False

    def contains(self, value: float) -> bool:
        if value < self.low or value > self.high:
            return False
        if value == self.low and not self.low_closed:
            return False
        if value == self.high and not self.high_closed:
            return False
        return True


def parse_condition(text: str) -> Interval:
    """'>25' -> Interval(25, открыт, +inf). Некорректная строка -> ValueError."""
    match = _CONDITION_RE.match(str(text))
    if not match:
        raise ValueError(f"Некорректное условие: {text!r}")
    operator, raw_value = match.groups()
    value = float(raw_value)
    if operator == ">":
        return Interval(low=value, low_closed=False)
    if operator == ">=":
        return Interval(low=value, low_closed=True)
    if operator == "<":
        return Interval(high=value, high_closed=False)
    if operator == "<=":
        return Interval(high=value, high_closed=True)
    return Interval(low=value, low_closed=True, high=value, high_closed=True)


def condition_matches(text: str, value: float) -> bool:
    """Выполняется ли условие при текущем показании датчика

    Битое условие считается невыполненным: лучше не включить прибор
    чем включить его по ошибке в данных.
    """
    try:
        return parse_condition(text).contains(float(value))
    except ValueError:
        return False


def rule_matches(rule: dict, sensors: dict, time_of_day: str) -> bool:
    """Все ли условия правила выполнены при текущих показаниях"""
    for key in NUMERIC_KEYS:
        if rule.get(key) and not condition_matches(rule[key], sensors[key]):
            return False
    if rule.get("time_of_day") and rule["time_of_day"] != time_of_day:
        return False
    if "motion" in rule and rule["motion"] != bool(sensors["motion"]):
        return False
    return True


def conditions_can_overlap(rule1: dict, rule2: dict) -> bool:
    """Могут ли оба правила сработать одновременно"""
    for key in NUMERIC_KEYS:
        if rule1.get(key) and rule2.get(key):
            try:
                common = parse_condition(rule1[key]).intersect(parse_condition(rule2[key]))
            except ValueError:
                return False
            if common.is_empty():
                return False
    for key in CATEGORY_KEYS:
        if key in rule1 and key in rule2 and rule1[key] != rule2[key]:
            return False
    return True


def rules_conflict(rule1: dict, rule2: dict) -> bool:
    """Конфликт: то же устройство разные действия и условия совместимы"""
    return (
        rule1["device"] == rule2["device"]
        and rule1["action"] != rule2["action"]
        and conditions_can_overlap(rule1, rule2)
    )


def involved_conditions(rule1: dict, rule2: dict) -> list[str]:
    """Названия условий которые задают хотя бы одно из правил"""
    return [CONDITION_LABELS[key] for key in CONDITION_KEYS if key in rule1 or key in rule2]


def find_conflicts(rules: list[dict]) -> list[tuple[int, int, list[str]]]:
    """Все пары конфликтующих правил: (индекс1, индекс2, названия условий)"""
    conflicts = []
    for i in range(len(rules)):
        for j in range(i + 1, len(rules)):
            if rules_conflict(rules[i], rules[j]):
                conflicts.append((i, j, involved_conditions(rules[i], rules[j])))
    return conflicts
