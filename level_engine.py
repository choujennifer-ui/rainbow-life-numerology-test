
from collections import Counter
from .five_stage import StageNumber

def birthday_digit_set(year: int, month: int, day: int) -> set[int]:
    digits = [int(ch) for ch in f"{year:04d}{month:02d}{day:02d}"]
    return set(digits)

def has_detention(year: int, month: int, day: int) -> bool:
    digits = [int(ch) for ch in f"{year:04d}{month:02d}{day:02d}"]
    counts = Counter(digits)
    for digit, count in counts.items():
        if digit == 0:
            continue
        if count >= 3:
            return True
    return False

def calculate_level(
    birthday_set: set[int],
    stage: StageNumber,
    detention: bool
) -> int:
    main_exists = stage.main_digit in birthday_set
    acquired_unique = set(stage.acquired_digits)
    acquired_found = acquired_unique & birthday_set
    found_count = len(acquired_found)
    all_have = acquired_unique <= birthday_set

    if not main_exists:
        if found_count == 0:
            return 1
        if all_have:
            return 3
        return 2

    if found_count == 0:
        return 4
    if all_have:
        if detention:
            return 6
        return 7
    return 5
