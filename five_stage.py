
from dataclasses import dataclass

@dataclass(frozen=True)
class StageNumber:
    total: int
    main_digit: int
    acquired_digits: list[int]

    def notation(self) -> str:
        if self.total < 10:
            return f"{self.total:02d}/{self.main_digit}"

        reduced = sum(int(d) for d in str(self.total))
        if reduced == 11:
            return f"{self.total}/11/2"
        if reduced == 22:
            return f"{self.total}/22/4"
        if reduced > 9:
            final_digit = sum(int(d) for d in str(reduced))
            return f"{self.total}/{reduced}/{final_digit}"
        return f"{self.total}/{reduced}"

def digit_sum(value: int) -> int:
    return sum(int(d) for d in str(abs(value)))

def reduce_to_main(n: int) -> int:
    while n > 9 and n not in (11, 22):
        n = digit_sum(n)
    if n == 11:
        return 2
    if n == 22:
        return 4
    return n

def acquired_digits(total: int) -> list[int]:
    # Preserve the two-digit Rainbow representation for 01-09.
    digit_text = f"{total:02d}" if total < 10 else str(total)
    digits = [int(d) for d in digit_text]

    reduced = sum(digits)

    # 10/1 and 11/2 both carry an acquired 1.
    # 22/4 is intentionally NOT appended with 4.
    if reduced in (10, 11):
        digits.append(1)

    return digits

def build_stage(total: int) -> StageNumber:
    return StageNumber(
        total=total,
        main_digit=reduce_to_main(total),
        acquired_digits=acquired_digits(total),
    )

def calculate_five_stages(year, month, day, hour, minute):
    old = build_stage(digit_sum(year))
    middle = build_stage(old.total + digit_sum(month))
    youth = build_stage(middle.total + digit_sum(day))
    teen = build_stage(youth.total + digit_sum(hour))
    childhood = build_stage(teen.total + digit_sum(minute))
    return {
        "old": old,
        "middle": middle,
        "youth": youth,
        "teen": teen,
        "childhood": childhood,
    }
