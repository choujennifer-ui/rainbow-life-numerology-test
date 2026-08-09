from dataclasses import dataclass
from datetime import date

from .calendar_conversion import solar_to_lunar
from .five_stage import StageNumber, build_stage, digit_sum
from .level_engine import birthday_digit_set, has_detention, calculate_level


@dataclass(frozen=True)
class AnnualYear:
    flow_year: int
    number: StageNumber
    level: int
    position: int

    @property
    def notation(self) -> str:
        return self.number.notation()


def nine_digit_sequence(start_digit: int) -> list[int]:
    """Nine-year outer cycle, clockwise, beginning at the Youth main digit."""
    if not 1 <= start_digit <= 9:
        raise ValueError("主命數必須介於 1–9。")
    return [((start_digit - 1 + offset) % 9) + 1 for offset in range(9)]


def annual_number(flow_year: int, birth_month: int, birth_day: int) -> StageNumber:
    """
    流年數 = 流年年份四碼 + 出生月兩碼 + 出生日兩碼 的 8 個數字相加，
    並完全沿用 Five Stage Engine 的完整鏈寫法。
    """
    total = (
        digit_sum(flow_year)
        + digit_sum(birth_month)
        + digit_sum(birth_day)
    )
    return build_stage(total)


def annual_level(
    birth_year: int,
    birth_month: int,
    birth_day: int,
    number: StageNumber,
) -> int:
    """Reuse the frozen Level Engine for each annual number."""
    bset = birthday_digit_set(birth_year, birth_month, birth_day)
    detention = has_detention(birth_year, birth_month, birth_day)
    return calculate_level(bset, number, detention)


def cycle_position(sequence: list[int], main_digit: int) -> int:
    """
    位格固定為 1–9，左下角為 1，順時鐘增加。
    回傳該流年主數所在的位格。
    """
    return sequence.index(main_digit) + 1


def _solar_effective_year(as_of: date, birth_month: int, birth_day: int) -> int:
    """
    當年陽曆生日已到（包含生日當天）→ 使用當年；
    尚未到 → 使用前一年。
    """
    return as_of.year if (as_of.month, as_of.day) >= (birth_month, birth_day) else as_of.year - 1


def _lunar_effective_year(
    as_of_lunar: dict,
    birth_month: int,
    birth_day: int,
    birth_is_leap_month: bool,
) -> int:
    """
    農曆生日獨立判斷。
    Leap-month recurrence rules have not yet been frozen, so the engine
    deliberately refuses to guess for a leap-month birth.
    """
    if birth_is_leap_month:
        raise ValueError("閏月生日的九年週期規則尚未凍結，不能自行猜測。")

    current_month = as_of_lunar["month"]
    current_day = as_of_lunar["day"]

    return (
        as_of_lunar["year"]
        if (current_month, current_day) >= (birth_month, birth_day)
        else as_of_lunar["year"] - 1
    )


def _three_year_window(
    effective_year: int,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    sequence: list[int],
) -> list[AnnualYear]:
    """
    Report window shown in the teaching chart:
    previous year / current year / next year.
    """
    result = []
    for flow_year in (effective_year - 1, effective_year, effective_year + 1):
        number = annual_number(flow_year, birth_month, birth_day)
        result.append(
            AnnualYear(
                flow_year=flow_year,
                number=number,
                level=annual_level(
                    birth_year,
                    birth_month,
                    birth_day,
                    number,
                ),
                position=cycle_position(sequence, number.main_digit),
            )
        )
    return result


def calculate_nine_year_cycle(
    solar_birth_year: int,
    solar_birth_month: int,
    solar_birth_day: int,
    solar_youth_main_digit: int,
    lunar_birth_year: int,
    lunar_birth_month: int,
    lunar_birth_day: int,
    lunar_youth_main_digit: int,
    as_of: date,
    lunar_birth_is_leap_month: bool = False,
) -> dict:
    """
    Deterministic Nine-Year Cycle Engine.

    Calculation only:
      1. 主命數定位
      2. 流年數計算與定位
      3. 位格數定位
      4. 前／今／後三個流年及其功課等級

    Triangle drawing is intentionally left to the report/UI layer.
    """
    current_lunar = solar_to_lunar(as_of.year, as_of.month, as_of.day)

    solar_sequence = nine_digit_sequence(solar_youth_main_digit)
    lunar_sequence = nine_digit_sequence(lunar_youth_main_digit)

    solar_effective_year = _solar_effective_year(
        as_of,
        solar_birth_month,
        solar_birth_day,
    )
    lunar_effective_year = _lunar_effective_year(
        current_lunar,
        lunar_birth_month,
        lunar_birth_day,
        lunar_birth_is_leap_month,
    )

    solar_window = _three_year_window(
        solar_effective_year,
        solar_birth_year,
        solar_birth_month,
        solar_birth_day,
        solar_sequence,
    )
    lunar_window = _three_year_window(
        lunar_effective_year,
        lunar_birth_year,
        lunar_birth_month,
        lunar_birth_day,
        lunar_sequence,
    )

    return {
        "as_of_solar": {
            "year": as_of.year,
            "month": as_of.month,
            "day": as_of.day,
        },
        "as_of_lunar": current_lunar,
        "solar": {
            "sign": "+",
            "youth_main_digit": solar_youth_main_digit,
            "sequence": solar_sequence,
            "position_numbers": list(range(1, 10)),
            "effective_flow_year": solar_effective_year,
            "years": solar_window,
            "current": solar_window[1],
        },
        "lunar": {
            "sign": "-",
            "youth_main_digit": lunar_youth_main_digit,
            "sequence": lunar_sequence,
            "position_numbers": list(range(1, 10)),
            "effective_flow_year": lunar_effective_year,
            "years": lunar_window,
            "current": lunar_window[1],
        },
    }
