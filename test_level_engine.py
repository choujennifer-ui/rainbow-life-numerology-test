
import json
from pathlib import Path
from engine.five_stage import calculate_five_stages, build_stage, digit_sum
from engine.level_engine import birthday_digit_set, has_detention, calculate_level

CASES = json.loads((Path(__file__).parent/"golden_cases.json").read_text(encoding="utf-8"))

def stages_for(v):
    y,m,d,h,minute=v
    if h is None or minute is None:
        old=build_stage(digit_sum(y))
        middle=build_stage(old.total+digit_sum(m))
        youth=build_stage(middle.total+digit_sum(d))
        return {"old":old,"middle":middle,"youth":youth}
    return calculate_five_stages(y,m,d,h,minute)

def levels_for(v):
    y,m,d,h,minute=v
    stages=stages_for(v)
    bset=birthday_digit_set(y,m,d)
    detention=has_detention(y,m,d)
    return [calculate_level(bset,s,detention) for s in stages.values()]

def test_level_golden_cases():
    for c in CASES:
        assert levels_for(c["solar"])==c["solar_levels"], c["id"]+" solar"
        assert levels_for(c["lunar"])==c["lunar_levels"], c["id"]+" lunar"
