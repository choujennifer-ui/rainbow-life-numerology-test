from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from html import escape
import os
import sys
import webbrowser
from pathlib import Path
from threading import Timer
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.calculation_engine import calculate_from_solar
from engine.rainbow_report import calculate_standard_report
from engine.nine_year_cycle import calculate_nine_year_cycle
from engine.calendar_conversion import solar_to_lunar


# Local use stays on 127.0.0.1:8000.  A public host (such as Render)
# supplies PORT and needs 0.0.0.0 so its HTTPS proxy can reach the app.
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", os.environ.get("RAINBOW_PORT", "8000")))
STAGE_LABELS = ("老年", "中年", "青年", "青少年", "幼年")
REPORT_TIMEZONE = os.environ.get("RAINBOW_TIMEZONE", "America/Los_Angeles")


def parse_int(value, label, required=True):
    value = (value or "").strip()
    if not value:
        if required:
            raise ValueError(f"請輸入{label}。")
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{label}必須是數字。")


def run_calculation(form):
    """Collect and validate web-form input, then call the frozen pipeline."""
    year = parse_int(form.get("year"), "出生年份")
    month = parse_int(form.get("month"), "出生月份")
    day = parse_int(form.get("day"), "出生日期")
    hour_raw = (form.get("hour") or "").strip()
    minute_raw = (form.get("minute") or "").strip()

    if not hour_raw and not minute_raw:
        hour = minute = None
    elif hour_raw and minute_raw:
        hour = parse_int(hour_raw, "出生時間（時）")
        minute = parse_int(minute_raw, "出生時間（分）")
    else:
        raise ValueError("若要輸入出生時間，時和分必須一起輸入。")

    if not 1 <= month <= 12:
        raise ValueError("月份必須介於 1–12。")
    if hour is not None and not 0 <= hour <= 23:
        raise ValueError("小時必須介於 0–23。")
    if minute is not None and not 0 <= minute <= 59:
        raise ValueError("分鐘必須介於 0–59。")

    # Calculation pipeline is deliberately unchanged:
    # Solar → Lunar → Five Stage → Level → Line → Report.
    return calculate_from_solar(
        name=form.get("name", "").strip(),
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
    )


def display_report(result):
    """Use the existing Format (2) report model without recalculating data.

    Birth time belongs to the person's original input, so it is displayed on
    both calendar panels. Calendar conversion itself remains date-only.
    """
    view_result = {
        **result,
        "lunar_date": {
            **result["lunar_date"],
            "hour": result["solar_date"].get("hour"),
            "minute": result["solar_date"].get("minute"),
        },
    }
    return calculate_standard_report(view_result)


def value_cell(value, extra_class=""):
    if value == "N/A":
        return f'<td class="empty {extra_class}"><span>—</span></td>'
    return f'<td class="{extra_class}">{escape(str(value))}</td>'


def line_html(lines):
    if not lines:
        return '<span class="line-empty">尚未形成連線</span>'
    return "".join(
        f'<span class="line-chip"><b>{escape(item["id"])}</b>'
        f'<span>{escape(item["name"])}</span></span>'
        for item in lines
    )


def calendar_card(side, lines):
    labels = "".join(f"<th>{escape(label)}</th>" for label in side["column_labels"])
    dates = "".join(value_cell(value, "date-value") for value in side["columns"])
    stages = "".join(value_cell(value, "stage-value") for value in side["stage_values"])
    levels = "".join(
        value_cell(value, "level-value") for value in side["level_values"]
    )
    stage_labels = "".join(f"<span>{label}</span>" for label in STAGE_LABELS)

    return f"""
    <section class="calendar-card">
      <div class="calendar-header">
        <h2>{escape(side["calendar"])}</h2>
        <span class="calendar-mark" aria-hidden="true">{side["calendar"][-2]}</span>
      </div>
      <div class="table-scroll">
        <table class="rainbow-table">
          <thead><tr><th class="row-heading"></th>{labels}</tr></thead>
          <tbody>
            <tr><th class="row-heading">出生資料</th>{dates}</tr>
            <tr class="stage-labels"><th class="row-heading"></th>{''.join('<td>'+label+'</td>' for label in STAGE_LABELS)}</tr>
            <tr class="stage-row"><th class="row-heading">生命數字</th>{stages}</tr>
            <tr><th class="row-heading">功課等級</th>{levels}</tr>
          </tbody>
        </table>
      </div>
      <div class="line-block">
        <span class="line-title">連線</span>
        <div class="line-list">{line_html(lines)}</div>
      </div>
    </section>
    """



NINE_YEAR_MEANINGS = {
    1: {"farming": "選種", "life": "新關係新目標", "meaning": "目標／實力"},
    2: {"farming": "插秧", "life": "契機與貴人", "meaning": "辨真假／重細節"},
    3: {"farming": "除草", "life": "革新與變動", "meaning": "嘗試改變習氣"},
    4: {"farming": "施肥", "life": "決策與行動", "meaning": "鞏固壯大"},
    5: {"farming": "結穗", "life": "主動與出擊", "meaning": "結善緣重行銷"},
    6: {"farming": "助割", "life": "修補與療癒", "meaning": "熱誠服務完美共識"},
    7: {"farming": "曬稻", "life": "休閒與反省", "meaning": "新知充電作回顧"},
    8: {"farming": "結算", "life": "投資策略反省", "meaning": "慎思推演新契機"},
    9: {"farming": "休耕", "life": "沉澱與不做", "meaning": "業力了結／待機變化"},
}


def report_today():
    """Current report date in the configured practice timezone."""
    return datetime.now(ZoneInfo(REPORT_TIMEZONE)).date()


def _find_solar_for_lunar(lunar_year, lunar_month, lunar_day):
    """UI-only helper: locate an ordinary lunar date by scanning Gregorian dates.

    This does not alter the frozen Calendar Conversion Engine.  Leap-month
    recurrence remains intentionally unsupported until its rule is frozen.
    """
    start = date(lunar_year, 1, 1)
    end = date(lunar_year + 1, 3, 31)
    current = start
    while current <= end:
        lunar = solar_to_lunar(current.year, current.month, current.day)
        if (
            lunar["year"] == lunar_year
            and lunar["month"] == lunar_month
            and lunar["day"] == lunar_day
            and not lunar.get("is_leap_month", False)
        ):
            return current
        current += timedelta(days=1)
    raise ValueError("找不到對應的農曆生日日期。")


def _cycle_progress_solar(as_of, birth_month, birth_day, effective_year):
    start = date(effective_year, birth_month, birth_day)
    end = date(effective_year + 1, birth_month, birth_day)
    return max(0.0, min(1.0, (as_of - start).days / max(1, (end - start).days)))


def _cycle_progress_lunar(as_of, birth_month, birth_day, effective_year):
    start = _find_solar_for_lunar(effective_year, birth_month, birth_day)
    end = _find_solar_for_lunar(effective_year + 1, birth_month, birth_day)
    return max(0.0, min(1.0, (as_of - start).days / max(1, (end - start).days)))


TRIANGLE_POINTS = [
    (45, 218),   # position 1, left bottom
    (76, 166),   # position 2
    (106, 113),  # position 3
    (150, 38),   # position 4, top
    (194, 113),  # position 5
    (224, 166),  # position 6
    (255, 218),  # position 7, right bottom
    (185, 218),  # position 8
    (115, 218),  # position 9
]

INNER_POINTS = [
    (66, 198), (91, 159), (116, 119), (150, 72), (184, 119),
    (209, 159), (234, 198), (185, 198), (115, 198),
]

OUTER_LABEL_POINTS = [
    (31, 231), (63, 163), (93, 107), (150, 24), (207, 107),
    (237, 163), (269, 231), (185, 244), (115, 244),
]


def _interpolate_cycle_position(position, progress):
    """Move clockwise from the current annual-number node toward the next node."""
    i = position - 1
    x1, y1 = TRIANGLE_POINTS[i]
    x2, y2 = TRIANGLE_POINTS[(i + 1) % 9]
    return (
        x1 + (x2 - x1) * progress,
        y1 + (y2 - y1) * progress,
    )


def triangle_svg(side, sign, progress):
    sequence = side["sequence"]
    current = side["current"]
    current_pos = current.position
    marker_x, marker_y = _interpolate_cycle_position(current_pos, progress)

    outer_labels = "".join(
        f'<text class="tri-outer" x="{x}" y="{y}">{value}</text>'
        for (x, y), value in zip(OUTER_LABEL_POINTS, sequence)
    )
    inner_labels = "".join(
        f'<text class="tri-inner" x="{x}" y="{y}">{position}</text>'
        for (x, y), position in zip(INNER_POINTS, range(1, 10))
    )

    # Current flow-year label sits near the moving red marker.
    label_x = marker_x + (10 if marker_x < 150 else -10)
    label_y = marker_y - 10
    anchor = "start" if marker_x < 150 else "end"
    current_label = f"{sign}{escape(current.notation)}"

    return f"""
    <svg class="cycle-svg" viewBox="0 0 300 258" role="img"
         aria-label="{escape(sign)}流年九年週期三角形">
      <path class="tri-outline" d="M45 218 L150 38 L255 218 Z"/>
      <line class="tri-tick" x1="70" y1="166" x2="83" y2="174"/>
      <line class="tri-tick" x1="99" y1="113" x2="112" y2="121"/>
      <line class="tri-tick" x1="188" y1="121" x2="201" y2="113"/>
      <line class="tri-tick" x1="217" y1="174" x2="230" y2="166"/>
      <line class="tri-tick" x1="115" y1="210" x2="115" y2="226"/>
      <line class="tri-tick" x1="185" y1="210" x2="185" y2="226"/>
      {outer_labels}
      {inner_labels}
      <circle class="flow-dot" cx="{marker_x:.1f}" cy="{marker_y:.1f}" r="4.2"/>
      <text class="flow-label" x="{label_x:.1f}" y="{label_y:.1f}"
            text-anchor="{anchor}">{current_label}</text>
    </svg>
    """


def cycle_year_strip(side, sign):
    cells = []
    for item in side["years"]:
        active = " current-year-cell" if item.flow_year == side["effective_flow_year"] else ""
        cells.append(
            f'<div class="cycle-year-cell{active}">'
            f'<span class="cycle-number">{sign}{escape(item.notation)}</span>'
            f'<span class="cycle-level">{item.level}</span>'
            f'</div>'
        )
    return "".join(cells)


def nine_year_meaning_html(position):
    item = NINE_YEAR_MEANINGS[position]
    return (
        f'<div class="cycle-meaning">'
        f'<span class="meaning-position">（{position}）</span>'
        f'<span class="meaning-farming">{escape(item["farming"])}</span>'
        f'<span class="meaning-divider">｜</span>'
        f'<span><b>生活上：</b>{escape(item["life"])}</span>'
        f'<span class="meaning-divider">｜</span>'
        f'<span><b>生命意義：</b>{escape(item["meaning"])}</span>'
        f'</div>'
    )


def nine_year_cycle_section(result):
    as_of = report_today()
    solar_youth = result["solar"]["stages"]["youth"].main_digit
    lunar_youth = result["lunar"]["stages"]["youth"].main_digit

    cycle = calculate_nine_year_cycle(
        solar_birth_year=result["solar_date"]["year"],
        solar_birth_month=result["solar_date"]["month"],
        solar_birth_day=result["solar_date"]["day"],
        solar_youth_main_digit=solar_youth,
        lunar_birth_year=result["lunar_date"]["year"],
        lunar_birth_month=result["lunar_date"]["month"],
        lunar_birth_day=result["lunar_date"]["day"],
        lunar_youth_main_digit=lunar_youth,
        as_of=as_of,
        lunar_birth_is_leap_month=result["lunar_date"].get("is_leap_month", False),
    )

    solar_progress = _cycle_progress_solar(
        as_of,
        result["solar_date"]["month"],
        result["solar_date"]["day"],
        cycle["solar"]["effective_flow_year"],
    )
    lunar_progress = _cycle_progress_lunar(
        as_of,
        result["lunar_date"]["month"],
        result["lunar_date"]["day"],
        cycle["lunar"]["effective_flow_year"],
    )

    lunar_today = cycle["as_of_lunar"]
    lunar_today_text = (
        f'{lunar_today["year"]:04d}/{lunar_today["month"]:02d}/{lunar_today["day"]:02d}'
    )

    solar_position = cycle["solar"]["current"].position
    lunar_position = cycle["lunar"]["current"].position

    if solar_position == lunar_position:
        meaning_block = nine_year_meaning_html(solar_position)
    else:
        meaning_block = (
            '<div class="cycle-meaning-stack">'
            '<div class="meaning-side-label">國曆</div>'
            f'{nine_year_meaning_html(solar_position)}'
            '<div class="meaning-side-label">農曆</div>'
            f'{nine_year_meaning_html(lunar_position)}'
            '</div>'
        )

    return f"""
    <section class="cycle-section">
      <div class="cycle-section-heading">
        <p class="eyebrow">NINE-YEAR CYCLE</p>
        <h2>九年週期流年</h2>
        <p>計算日：國曆 {as_of:%Y/%m/%d} · 農曆 {lunar_today_text}</p>
      </div>

      <div class="cycle-grid">
        <article class="cycle-card">
          <h3>國曆流年 <span>＋</span></h3>
          {triangle_svg(cycle["solar"], "+", solar_progress)}
          <div class="cycle-year-strip">
            {cycle_year_strip(cycle["solar"], "+")}
          </div>
        </article>

        <article class="cycle-card">
          <h3>農曆流年 <span>－</span></h3>
          {triangle_svg(cycle["lunar"], "-", lunar_progress)}
          <div class="cycle-year-strip">
            {cycle_year_strip(cycle["lunar"], "-")}
          </div>
        </article>
      </div>

      {meaning_block}

      <p class="cycle-note">外圈＝青年主命數起始的九年數字 · 內圈＝固定 1–9 位格 · 紅字＝目前流年</p>
    </section>
    """

def result_page(result):
    model = display_report(result)
    name = escape(model.get("name") or "")
    return page_shell(
        f"""
        <header class="site-header">
          <a class="brand" href="/" aria-label="回到首頁"><span class="brand-dot"></span>彩虹生命數字</a>
          <div class="header-actions"><a class="text-action" href="/">重新計算</a><button class="print-button" onclick="window.print()">列印／儲存 PDF</button></div>
        </header>
        <main class="report-page">
          <div class="report-intro">
            <p class="eyebrow">MODULE 1 · FORMAT (2)</p>
            <h1>彩虹生命數字計算報告</h1>
            {f'<p class="person-name">{name}</p>' if name else '<p class="person-name">計算結果</p>'}
          </div>
          <div class="calendar-stack">
            {calendar_card(model["solar"], result["solar"]["lines"])}
            {calendar_card(model["lunar"], result["lunar"]["lines"])}
          </div>
          {nine_year_cycle_section(result)}
          <p class="report-note">此頁僅呈現計算結果，不含解讀、AI 判斷或藍色輔助列。</p>
        </main>
        """,
        title="彩虹生命數字｜計算報告",
    )


def error_page(message):
    return page_shell(
        f"""
        <header class="site-header"><a class="brand" href="/"><span class="brand-dot"></span>彩虹生命數字</a></header>
        <main class="form-page"><section class="error-card"><p class="eyebrow">請再確認一次</p><h1>資料輸入有誤</h1><p>{escape(message)}</p><a class="primary-button" href="/">回到輸入頁</a></section></main>
        """,
        title="輸入錯誤｜彩虹生命數字",
    )


def form_page():
    return page_shell(
        """
        <header class="site-header"><a class="brand" href="/"><span class="brand-dot"></span>彩虹生命數字</a><span class="module-label">MODULE 1</span></header>
        <main class="form-page">
          <section class="form-card">
            <div class="form-heading"><p class="eyebrow">CALCULATION TOOL</p><h1>從生日，看見你的生命數字</h1><p>輸入陽曆生日後，系統會完成農曆換算與五階段、功課等級、連線的計算。</p></div>
            <form method="POST" action="/calculate" autocomplete="off">
              <div class="field full"><label for="name">姓名 <span>選填</span></label><input id="name" name="name" autocomplete="off"></div>
              <fieldset><legend>陽曆出生日期</legend><div class="date-fields"><div class="field"><label for="year">年份</label><input id="year" name="year" type="number" inputmode="numeric" min="1900" max="2100" autocomplete="off" required></div><div class="field"><label for="month">月份</label><input id="month" name="month" type="number" inputmode="numeric" min="1" max="12" autocomplete="off" required></div><div class="field"><label for="day">日期</label><input id="day" name="day" type="number" inputmode="numeric" min="1" max="31" autocomplete="off" required></div></div></fieldset>
              <fieldset class="time-fieldset"><legend>出生時間 <span>選填</span></legend><div class="time-fields"><div class="field"><label for="hour">時（24 小時制）</label><input id="hour" name="hour" type="number" inputmode="numeric" min="0" max="23" autocomplete="off"></div><div class="field"><label for="minute">分</label><input id="minute" name="minute" type="number" inputmode="numeric" min="0" max="59" autocomplete="off"></div></div><p class="help-text">不知道出生時間？兩欄都留空即可；系統不會自行猜測。</p></fieldset>
              <button class="primary-button" type="submit">產生計算報告 <span aria-hidden="true">→</span></button>
            </form>
          </section>
        </main>
        """,
        title="彩虹生命數字｜計算工具",
    )


def page_shell(content, title="彩虹生命數字"):
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{ --ink:#25303b; --muted:#697586; --paper:#fffdf9; --bg:#f7f3ee; --line:#dfd8cf; --purple:#775281; --purple-dark:#573660; --lavender:#f0e8f3; --coral:#bb5363; --shadow:0 18px 50px rgba(66,42,72,.10); }}
* {{ box-sizing:border-box; }} html,body {{ max-width:100%; overflow-x:hidden; }} body {{ margin:0; color:var(--ink); background:radial-gradient(circle at 7% 0,#eee4f1 0,transparent 27rem),var(--bg); font-family:"Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif; }}
.site-header {{ min-height:72px; padding:0 clamp(20px,5vw,72px); display:flex; align-items:center; justify-content:space-between; gap:18px; border-bottom:1px solid rgba(119,82,129,.16); background:rgba(255,253,249,.82); backdrop-filter:blur(10px); }} .brand {{ color:var(--ink); text-decoration:none; font-weight:800; letter-spacing:.08em; white-space:nowrap; }} .brand-dot {{ display:inline-block; width:10px; height:10px; margin-right:9px; border-radius:50%; background:linear-gradient(135deg,#e88783,#a966ad); }} .module-label,.eyebrow {{ margin:0; color:var(--purple); font-size:11px; font-weight:800; letter-spacing:.15em; }} .header-actions {{ display:flex; align-items:center; gap:18px; }} .text-action {{ color:var(--purple); font-weight:700; text-decoration:none; }}
.form-page {{ min-height:calc(100vh - 72px); display:grid; place-items:center; padding:42px 20px 60px; }} .form-card,.error-card {{ width:min(680px,100%); background:rgba(255,253,249,.92); border:1px solid rgba(119,82,129,.18); border-radius:24px; box-shadow:var(--shadow); padding:clamp(28px,6vw,52px); }} .form-heading {{ margin-bottom:32px; }} h1 {{ margin:9px 0 12px; font-size:clamp(28px,5vw,42px); line-height:1.25; letter-spacing:.02em; }} .form-heading > p:last-child,.help-text,.error-card p {{ color:var(--muted); line-height:1.75; }}
form {{ display:grid; gap:24px; }} fieldset {{ min-width:0; margin:0; padding:0; border:0; }} legend {{ margin:0 0 11px; font-size:15px; font-weight:800; }} legend span,label span {{ margin-left:5px; color:var(--muted); font-size:12px; font-weight:500; }} .date-fields {{ display:grid; grid-template-columns:1.35fr 1fr 1fr; gap:14px; }} .time-fields {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }} .field label {{ display:block; margin:0 0 7px; color:var(--muted); font-size:13px; font-weight:650; }} input {{ width:100%; min-height:50px; border:1px solid #d7d0c9; border-radius:11px; padding:11px 13px; color:var(--ink); background:#fff; font:inherit; font-size:16px; transition:.15s; }} input:focus {{ outline:3px solid #e6d7ea; border-color:var(--purple); }} .time-fieldset {{ padding-top:23px; border-top:1px solid var(--line); }} .help-text {{ margin:9px 0 0; font-size:13px; }}
.primary-button,.print-button {{ border:0; border-radius:11px; padding:14px 19px; background:var(--purple); color:white; font:inherit; font-weight:800; cursor:pointer; text-decoration:none; transition:background .15s,transform .15s; }} .primary-button {{ justify-self:start; margin-top:4px; }} .primary-button span {{ margin-left:10px; font-size:19px; }} .primary-button:hover,.print-button:hover {{ background:var(--purple-dark); transform:translateY(-1px); }} .print-button {{ padding:9px 13px; font-size:13px; }}
.report-page {{ width:min(1100px,100%); margin:0 auto; padding:52px 20px 64px; }} .report-intro {{ text-align:center; margin:0 auto 34px; }} .report-intro h1 {{ font-size:clamp(27px,4.5vw,38px); }} .person-name {{ margin:0; color:var(--muted); font-size:17px; }} .calendar-stack {{ display:grid; gap:22px; }} .calendar-card {{ overflow:hidden; background:var(--paper); border:1px solid rgba(119,82,129,.18); border-radius:19px; box-shadow:0 12px 30px rgba(66,42,72,.07); }} .calendar-header {{ display:flex; align-items:center; justify-content:center; gap:10px; padding:20px 20px 16px; background:linear-gradient(90deg,#f8f4f9,#fbf7f1); border-bottom:1px solid var(--line); }} .calendar-header h2 {{ margin:0; font-size:21px; }} .calendar-mark {{ display:grid; place-items:center; width:25px; height:25px; border-radius:50%; color:#fff; background:var(--purple); font-weight:800; }} .table-scroll {{ overflow-x:auto; }} .rainbow-table {{ width:100%; min-width:650px; border-collapse:collapse; table-layout:fixed; }} .rainbow-table th,.rainbow-table td {{ padding:13px 8px; text-align:center; border-bottom:1px solid #ece6df; }} .rainbow-table thead th {{ color:var(--muted); font-size:13px; font-weight:700; }} .rainbow-table .row-heading {{ width:128px; color:var(--muted); text-align:left; padding-left:22px; font-size:13px; font-weight:800; background:rgba(251,248,244,.7); }} .date-value {{ font-size:20px; font-weight:800; }} .stage-labels td {{ padding-top:15px; padding-bottom:5px; color:var(--muted); font-size:12px; }} .stage-labels .row-heading {{ border-bottom:0; }} .stage-row td {{ padding-top:5px; padding-bottom:13px; }} .stage-value {{ color:var(--purple-dark); font-size:19px; font-weight:850; }} .level-value {{ color:var(--coral); font-size:18px; font-weight:850; }} .empty {{ color:#a8afb6; }} .line-block {{ display:flex; gap:22px; align-items:flex-start; padding:18px 22px 21px; }} .line-title {{ min-width:42px; padding-top:4px; font-weight:800; }} .line-list {{ display:flex; flex-wrap:wrap; gap:8px; }} .line-chip {{ display:inline-flex; overflow:hidden; border:1px solid #dfd2e3; border-radius:999px; color:#5b4262; background:#faf7fb; font-size:13px; }} .line-chip b {{ padding:5px 8px; color:#fff; background:#a27aac; }} .line-chip span {{ padding:5px 10px 5px 7px; }} .line-empty {{ color:var(--muted); font-size:14px; padding-top:3px; }} .report-note {{ margin:24px 0 0; color:var(--muted); text-align:center; font-size:12px; }} .error-card {{ text-align:center; }}

.cycle-section {{ margin-top:30px; }}
.cycle-section-heading {{ text-align:center; margin:0 0 18px; }}
.cycle-section-heading h2 {{ margin:6px 0 5px; font-size:24px; }}
.cycle-section-heading > p:last-child {{ margin:0; color:var(--muted); font-size:12px; }}
.cycle-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }}
.cycle-card {{ min-width:0; overflow:hidden; padding:16px 14px 12px; background:var(--paper); border:1px solid rgba(119,82,129,.18); border-radius:19px; box-shadow:0 12px 30px rgba(66,42,72,.07); }}
.cycle-card h3 {{ margin:0; text-align:center; font-size:17px; }}
.cycle-card h3 span {{ color:var(--purple); }}
.cycle-svg {{ display:block; width:min(100%,380px); height:auto; margin:4px auto 0; overflow:visible; }}
.tri-outline {{ fill:none; stroke:#222b35; stroke-width:1.7; stroke-linejoin:round; }}
.tri-tick {{ stroke:#222b35; stroke-width:1.5; }}
.tri-outer,.tri-inner,.flow-label {{ font-family:"Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif; dominant-baseline:middle; text-anchor:middle; }}
.tri-outer {{ fill:#202832; font-size:11px; font-weight:700; }}
.tri-inner {{ fill:#202832; font-size:9px; }}
.flow-dot {{ fill:#d63c43; }}
.flow-label {{ fill:#d63c43; font-size:11px; font-weight:900; }}
.cycle-year-strip {{ display:grid; grid-template-columns:repeat(3,1fr); border-top:1px solid var(--line); border-left:1px solid var(--line); }}
.cycle-year-cell {{ display:grid; grid-template-columns:1fr 30px; min-width:0; border-right:1px solid var(--line); border-bottom:1px solid var(--line); background:#fff; }}
.cycle-year-cell.current-year-cell {{ background:#fff8f6; }}
.cycle-number,.cycle-level {{ display:grid; place-items:center; min-height:31px; font-weight:850; }}
.cycle-number {{ min-width:0; padding:3px; font-size:13px; white-space:nowrap; }}
.cycle-level {{ border-left:1px solid var(--line); color:var(--purple-dark); font-size:13px; }}
.current-year-cell .cycle-number {{ color:#d63c43; }}
.current-year-cell .cycle-level {{ color:#d63c43; }}
.cycle-meaning {{
  display:flex;
  flex-wrap:wrap;
  justify-content:center;
  align-items:center;
  gap:5px;
  margin:14px auto 0;
  padding:10px 14px;
  width:fit-content;
  max-width:100%;
  border:1px solid #e2d8e5;
  border-radius:12px;
  background:#fbf8fc;
  color:#4f4053;
  font-size:13px;
  line-height:1.5;
}}
.meaning-position,.meaning-farming {{ color:var(--purple-dark); font-weight:850; }}
.meaning-divider {{ color:#b8aabf; }}
.cycle-meaning b {{ color:var(--ink); }}
.cycle-meaning-stack {{ margin-top:14px; }}
.meaning-side-label {{
  margin:8px 0 4px;
  color:var(--muted);
  text-align:center;
  font-size:11px;
  font-weight:800;
}}
.cycle-note {{ margin:12px 0 0; color:var(--muted); text-align:center; font-size:11px; }}

@media (max-width:620px) {{
  .site-header {{ min-height:62px; padding:0 14px; }}
  .module-label,.text-action {{ display:none; }}
  .header-actions {{ margin-left:auto; }}
  .brand {{ font-size:14px; letter-spacing:.04em; }}
  .form-page {{ padding:24px 14px 40px; align-items:start; }}
  .date-fields {{ grid-template-columns:1.3fr 1fr 1fr; gap:9px; }}
  .time-fields {{ gap:9px; }}
  .form-card,.error-card {{ border-radius:18px; }}

  .report-page {{
    width:100%;
    padding:24px 6px 38px;
    overflow-x:hidden;
  }}

  .report-intro {{ margin-bottom:22px; }}
  .report-intro h1 {{ font-size:22px; }}
  .person-name {{ font-size:14px; }}

  .calendar-stack {{ gap:14px; }}
  .calendar-card {{
    width:100%;
    border-radius:14px;
  }}

  .calendar-header {{ padding:12px 8px 10px; }}
  .calendar-header h2 {{ font-size:16px; }}
  .calendar-mark {{ width:21px; height:21px; font-size:12px; }}

  .table-scroll {{
    width:100%;
    overflow-x:hidden;
  }}

  .rainbow-table {{
    width:100%;
    min-width:0;
    table-layout:fixed;
  }}

  .rainbow-table th,
  .rainbow-table td {{
    padding:7px 1px;
    white-space:nowrap;
  }}

  .rainbow-table thead th {{
    font-size:9px;
    letter-spacing:0;
  }}

  .rainbow-table .row-heading {{
    width:58px;
    padding-left:3px;
    padding-right:3px;
    font-size:9px;
    text-align:center;
  }}

  .date-value {{
    font-size:12px;
    font-weight:800;
  }}

  .stage-labels td {{
    padding-top:8px;
    padding-bottom:2px;
    font-size:8px;
  }}

  .stage-row td {{
    padding-top:2px;
    padding-bottom:7px;
  }}

  .stage-value {{
    font-size:10px;
    letter-spacing:-.02em;
  }}

  .level-value {{
    font-size:11px;
  }}

  .line-block {{
    display:block;
    padding:10px 7px 12px;
  }}

  .line-title {{
    display:block;
    min-width:0;
    padding:0 0 7px;
    font-size:10px;
  }}

  .line-list {{ gap:4px; }}

  .line-chip {{
    font-size:9px;
    border-radius:999px;
  }}

  .line-chip b {{ padding:3px 5px; }}
  .line-chip span {{ padding:3px 6px 3px 4px; }}

  .print-button {{
    padding:7px 8px;
    font-size:10px;
    white-space:nowrap;
  }}


  .cycle-section {{ margin-top:18px; }}
  .cycle-section-heading {{ margin-bottom:12px; }}
  .cycle-section-heading h2 {{ font-size:17px; }}
  .cycle-section-heading > p:last-child {{ font-size:9px; }}
  /* iPhone: keep Solar and Lunar triangles side-by-side */
  .cycle-grid {{
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:6px;
  }}

  .cycle-card {{
    min-width:0;
    padding:7px 3px 6px;
    border-radius:12px;
  }}

  .cycle-card h3 {{
    font-size:11.5px;
    line-height:1.2;
  }}

  .cycle-svg {{
    width:100%;
    max-width:186px;
    margin-top:1px;
  }}

  .tri-outline {{ stroke-width:1.35; }}
  .tri-tick {{ stroke-width:1.1; }}

  .tri-outer {{
    font-size:9px;
    font-weight:750;
  }}

  .tri-inner {{
    font-size:7.2px;
  }}

  .flow-dot {{ r:3; }}

  .flow-label {{
    font-size:8.5px;
    font-weight:900;
  }}

  .cycle-year-strip {{
    grid-template-columns:repeat(3,minmax(0,1fr));
  }}

  .cycle-year-cell {{
    grid-template-columns:minmax(0,1fr) 18px;
  }}

  .cycle-number,
  .cycle-level {{
    min-height:23px;
    font-size:7.5px;
  }}

  .cycle-number {{
    padding:1px;
    letter-spacing:-.03em;
  }}

  .cycle-level {{
    font-size:8px;
  }}

  .cycle-meaning {{
    gap:3px;
    margin-top:9px;
    padding:7px 8px;
    width:100%;
    border-radius:9px;
    font-size:8.5px;
    line-height:1.4;
  }}

  .meaning-divider {{ display:none; }}

  .cycle-meaning span {{
    white-space:normal;
  }}

  .meaning-position,
  .meaning-farming {{
    font-size:9px;
  }}

  .meaning-side-label {{
    margin-top:6px;
    font-size:8px;
  }}

  .cycle-note {{
    padding:0 5px;
    font-size:8px;
    line-height:1.4;
  }}

  .report-note {{
    margin-top:16px;
    padding:0 6px;
    font-size:10px;
    line-height:1.5;
  }}
}}
@media print {{ body {{ background:#fff; }} .site-header {{ display:none; }} .report-page {{ width:100%; padding:0; }} .calendar-card,.cycle-card {{ break-inside:avoid; box-shadow:none; }} .report-note {{ display:none; }} }}
</style>
</head>
<body>{content}<script>window.addEventListener('pageshow', () => document.querySelector('form')?.reset());</script></body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'",
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/":
            self.send_html(form_page())
        else:
            self.send_html(error_page("找不到這個頁面。"), 404)

    def do_POST(self):
        if self.path.split("?")[0] != "/calculate":
            self.send_html(error_page("找不到這個頁面。"), 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            form = {key: values[0] for key, values in parse_qs(raw).items()}
            self.send_html(result_page(run_calculation(form)))
        except Exception as exc:
            self.send_html(error_page(str(exc)), 400)

    def log_message(self, fmt, *args):
        print(fmt % args)


def main():
    server = HTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Rainbow Life Numerology Module 1 Web Interface\nOpen: {url}\nPress Ctrl+C to stop.")
    Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
