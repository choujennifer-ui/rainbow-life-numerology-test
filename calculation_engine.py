from .calendar_conversion import solar_to_lunar
from .five_stage import calculate_five_stages, build_stage, digit_sum
from .level_engine import birthday_digit_set, has_detention, calculate_level
from .line_engine import calculate_lines

def _stages(year, month, day, hour=None, minute=None):
    if hour is None or minute is None:
        old = build_stage(digit_sum(year))
        middle = build_stage(old.total + digit_sum(month))
        youth = build_stage(middle.total + digit_sum(day))
        return {"old": old, "middle": middle, "youth": youth}
    return calculate_five_stages(year, month, day, hour, minute)

def _side(year, month, day, hour=None, minute=None):
    stages = _stages(year, month, day, hour, minute)
    bset = birthday_digit_set(year, month, day)
    detention = has_detention(year, month, day)
    levels = {
        name: calculate_level(bset, stage, detention)
        for name, stage in stages.items()
    }
    birthday_digits = [int(ch) for ch in f"{year:04d}{month:02d}{day:02d}"]
    lines = calculate_lines(birthday_digits, stages["youth"].acquired_digits)
    return {"stages": stages, "levels": levels, "lines": lines}

def calculate_from_solar(name, year, month, day, hour=None, minute=None):
    lunar = solar_to_lunar(year, month, day)
    return {
        "name": name,
        "solar_date": {
            "year": year, "month": month, "day": day,
            "hour": hour, "minute": minute,
        },
        "lunar_date": lunar,
        "solar": _side(year, month, day, hour, minute),
        "lunar": _side(
            lunar["year"], lunar["month"], lunar["day"],
            hour, minute
        ),
    }
