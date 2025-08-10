from enum import Enum


class AutoUpperName(Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name.upper()


class AutoLowerName(Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name.lower()
