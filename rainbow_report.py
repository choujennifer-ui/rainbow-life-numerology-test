STAGE_ORDER = ("old", "middle", "youth", "teen", "childhood")

STAGE_LABELS = {
    "old": "老年",
    "middle": "中年",
    "youth": "青年",
    "teen": "青少年",
    "childhood": "幼年",
}

COLUMN_LABELS = ("年", "月", "日", "時", "分")


def _stage_notation(stage):
    return stage.notation()


def _date_parts(data):
    """
    Return the five date/time fields used by the Rainbow table.

    The calculation engine already preserves whether hour/minute were
    supplied. Missing time is represented by N/A in the report.
    """
    return (
        data["year"],
        data["month"],
        data["day"],
        data.get("hour"),
        data.get("minute"),
    )


def build_standard_table(calendar_label, date_info, side):
    """
    Build the data model for Format (2).

    IMPORTANT:
    The original Excel blue auxiliary row is intentionally NOT included.
    It has no role in Module 1 calculation/report output.
    """
    stages = side["stages"]
    levels = side["levels"]

    year = date_info["year"]
    month = date_info["month"]
    day = date_info["day"]
    hour = date_info.get("hour")
    minute = date_info.get("minute")

    columns = [
        year,
        month,
        day,
        "N/A" if hour is None else hour,
        "N/A" if minute is None else minute,
    ]

    stage_values = []
    level_values = []

    for stage_name in STAGE_ORDER:
        if stage_name not in stages:
            stage_values.append("N/A")
            level_values.append("N/A")
        else:
            stage_values.append(_stage_notation(stages[stage_name]))
            level_values.append(levels[stage_name])

    return {
        "calendar": calendar_label,
        "columns": columns,
        "column_labels": COLUMN_LABELS,
        "stage_values": stage_values,
        "level_values": level_values,
    }


def calculate_standard_report(report):
    """
    Convert Module 1 calculation output into the Format (2) report model.
    No formulas are recalculated here.
    """
    return {
        "name": report.get("name", ""),
        "solar": build_standard_table(
            "國曆（＋）",
            report["solar_date"],
            report["solar"],
        ),
        "lunar": build_standard_table(
            "農曆（－）",
            report["lunar_date"],
            report["lunar"],
        ),
    }


def _cell(value, width=12):
    text = str(value)
    return text.center(width)


def render_standard_report(report):
    """
    Pure-Python text rendering of Format (2).

    Layout:
      calendar title
      年 / 月 / 日 / 時 / 分
      date values
      divider
      stage numbers + level
      divider

    The blue auxiliary row is deliberately omitted.
    """
    model = calculate_standard_report(report)

    out = []

    if model["name"]:
        out.append(f"A 姓名：{model['name']}")
        out.append("")

    for side in (model["solar"], model["lunar"]):
        out.append(_cell(side["calendar"], 14))

        headers = side["column_labels"]
        values = side["columns"]
        stages = side["stage_values"]
        levels = side["level_values"]

        out.append("  ".join(_cell(x, 13) for x in headers))
        out.append("─" * 72)
        out.append("  ".join(_cell(x, 13) for x in values))
        out.append("─" * 72)

        # Each stage number is followed by its level, matching the
        # compact visual relationship in the user's Format (2).
        stage_cells = []
        for number, level in zip(stages, levels):
            if level == "N/A":
                stage_cells.append(_cell(number, 13))
            else:
                stage_cells.append(_cell(f"{number}  [{level}]", 13))

        out.append("  ".join(stage_cells))
        out.append("")
        out.append("")

    return "\n".join(out).rstrip()


# Backward-compatible alias for the existing report call.
format_rainbow_report = render_standard_report
