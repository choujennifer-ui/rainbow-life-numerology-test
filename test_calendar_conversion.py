import json
from pathlib import Path
from engine.calendar_conversion import solar_to_lunar

CASES = json.loads(
    (Path(__file__).parent/"calendar_golden_cases.json").read_text(
        encoding="utf-8"
    )
)

def test_calendar_golden_cases():
    for case in CASES:
        r = solar_to_lunar(*case["solar"])
        assert [r["year"],r["month"],r["day"]] == case["lunar_expected"], case["id"]
