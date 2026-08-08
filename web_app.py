
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from html import escape
import traceback
import webbrowser
from threading import Timer
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.calculation_engine import calculate_from_solar


HOST = "127.0.0.1"
PORT = 8000


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
        raise ValueError("如果要輸入出生時間，時和分必須一起輸入。")

    if not (1 <= month <= 12):
        raise ValueError("月份必須介於 1–12。")
    if not (0 <= hour <= 23) if hour is not None else False:
        raise ValueError("小時必須介於 0–23。")
    if not (0 <= minute <= 59) if minute is not None else False:
        raise ValueError("分鐘必須介於 0–59。")

    return calculate_from_solar(
        name=form.get("name", "").strip(),
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
    )


def stage_rows(side):
    order = ("old", "middle", "youth", "teen", "childhood")
    labels = {
        "old": "老年",
        "middle": "中年",
        "youth": "青年",
        "teen": "青少年",
        "childhood": "幼年",
    }

    rows = []
    for key in order:
        if key in side["stages"]:
            rows.append(
                f"""
                <tr>
                  <th>{escape(labels[key])}</th>
                  <td>{escape(side["stages"][key].notation())}</td>
                  <td class="level">{side["levels"][key]}</td>
                </tr>
                """
            )
        else:
            rows.append(
                f"""
                <tr>
                  <th>{escape(labels[key])}</th>
                  <td class="na">N/A</td>
                  <td class="na">N/A</td>
                </tr>
                """
            )
    return "".join(rows)


def line_html(side):
    if not side["lines"]:
        return '<div class="no-lines">無</div>'

    return "".join(
        f'<div class="line-item"><span class="line-id">{escape(x["id"])}</span>'
        f'<span class="line-name">{escape(x["name"])}</span></div>'
        for x in side["lines"]
    )


def calendar_card(title, date_info, side):
    y = date_info["year"]
    m = date_info["month"]
    d = date_info["day"]
    h = date_info.get("hour")
    minute = date_info.get("minute")

    values = [
        str(y),
        f"{m:02d}",
        f"{d:02d}",
        "N/A" if h is None else f"{h:02d}",
        "N/A" if minute is None else f"{minute:02d}",
    ]

    return f"""
    <section class="calendar-card">
      <div class="calendar-title">{escape(title)}</div>

      <div class="date-grid labels">
        <div>年</div><div>月</div><div>日</div><div>時</div><div>分</div>
      </div>

      <div class="date-grid date-values">
        {"".join(f"<div>{escape(v)}</div>" for v in values)}
      </div>

      <div class="rule"></div>

      <div class="stage-table-wrap">
        <table class="stage-table">
          <thead>
            <tr>
              <th>階段</th>
              <th>生命數字</th>
              <th>等級</th>
            </tr>
          </thead>
          <tbody>
            {stage_rows(side)}
          </tbody>
        </table>
      </div>

      <div class="lines-title">連線</div>
      <div class="lines">
        {line_html(side)}
      </div>
    </section>
    """


def result_page(result):
    name = escape(result.get("name") or "")
    lunar = result["lunar_date"]

    # The calculation engine intentionally keeps birth time separate
    # from calendar conversion. The report displays the original time
    # on both calendar sides.
    solar_date = result["solar_date"]
    solar_date["hour"] = solar_date.get("hour")
    solar_date["minute"] = solar_date.get("minute")

    lunar_date = {
        "year": lunar["year"],
        "month": lunar["month"],
        "day": lunar["day"],
        "hour": solar_date.get("hour"),
        "minute": solar_date.get("minute"),
    }

    return page_shell(
        f"""
        <div class="topbar">
          <a class="back" href="/">← 重新計算</a>
          <div class="brand">彩虹生命數字</div>
        </div>

        <main class="report">
          <div class="report-heading">
            <div class="eyebrow">MODULE 1 · CALCULATION REPORT</div>
            <h1>彩虹生命數字計算報告</h1>
            {f'<div class="person-name">{name}</div>' if name else ''}
          </div>

          <div class="cards">
            {calendar_card("國曆（＋）", solar_date, result["solar"])}
            {calendar_card("農曆（－）", lunar_date, result["lunar"])}
          </div>

          <div class="report-note">
            本報告為純計算結果。沒有加入解讀、西方數字學或 AI 判斷。
          </div>
        </main>
        """,
        title="彩虹生命數字｜計算報告",
    )


def error_page(message):
    return page_shell(
        f"""
        <div class="topbar">
          <a class="back" href="/">← 返回</a>
          <div class="brand">彩虹生命數字</div>
        </div>
        <main class="form-page">
          <div class="error-box">
            <h2>資料輸入有誤</h2>
            <p>{escape(message)}</p>
            <a class="button" href="/">重新輸入</a>
          </div>
        </main>
        """,
        title="輸入錯誤",
    )


def page_shell(content, title="彩虹生命數字"):
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{
  --ink:#1f2937;
  --muted:#6b7280;
  --line:#d8dee7;
  --paper:#ffffff;
  --bg:#f4f6f8;
  --accent:#7b4f88;
  --accent-dark:#5f3b6a;
  --soft:#f1eaf4;
  --level:#c93f52;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0;
  background:var(--bg);
  color:var(--ink);
  font-family: "Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif;
}}
.topbar {{
  height:64px;
  background:white;
  border-bottom:1px solid var(--line);
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:0 28px;
}}
.brand {{ font-weight:700; letter-spacing:.08em; }}
.back {{ color:var(--accent); text-decoration:none; font-weight:600; }}
.form-page {{
  min-height:calc(100vh - 64px);
  display:flex;
  align-items:center;
  justify-content:center;
  padding:32px 18px;
}}
.form-card {{
  width:min(640px,100%);
  background:white;
  border:1px solid var(--line);
  border-radius:18px;
  padding:36px;
  box-shadow:0 12px 35px rgba(30,40,55,.07);
}}
.eyebrow {{
  color:var(--accent);
  font-size:12px;
  letter-spacing:.16em;
  font-weight:700;
}}
h1 {{ margin:8px 0 8px; font-size:30px; }}
.subtitle {{ color:var(--muted); line-height:1.7; margin-bottom:28px; }}
.form-grid {{
  display:grid;
  grid-template-columns:1.3fr 1fr 1fr;
  gap:14px;
}}
label {{ display:block; font-size:13px; color:var(--muted); margin-bottom:7px; }}
input {{
  width:100%;
  padding:12px 13px;
  border:1px solid #cfd6df;
  border-radius:9px;
  font-size:16px;
  background:white;
}}
input:focus {{ outline:2px solid #d9c8df; border-color:var(--accent); }}
.time-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:14px;
  margin-top:14px;
}}
.name-field {{ margin-bottom:18px; }}
.time-note {{ color:var(--muted); font-size:13px; margin-top:8px; }}
.button {{
  display:inline-block;
  margin-top:24px;
  padding:13px 22px;
  background:var(--accent);
  color:white;
  border:0;
  border-radius:9px;
  font-size:16px;
  font-weight:700;
  cursor:pointer;
  text-decoration:none;
}}
.button:hover {{ background:var(--accent-dark); }}
.report {{
  max-width:1120px;
  margin:0 auto;
  padding:46px 24px 60px;
}}
.report-heading {{ text-align:center; margin-bottom:34px; }}
.report-heading h1 {{ font-size:32px; margin:7px 0; }}
.person-name {{ color:var(--muted); font-size:17px; }}
.cards {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:24px;
}}
.calendar-card {{
  background:var(--paper);
  border:1px solid var(--line);
  border-radius:14px;
  padding:25px;
  box-shadow:0 8px 24px rgba(30,40,55,.05);
}}
.calendar-title {{
  text-align:center;
  font-weight:800;
  font-size:20px;
  margin-bottom:22px;
}}
.date-grid {{
  display:grid;
  grid-template-columns:repeat(5,1fr);
  text-align:center;
}}
.labels {{
  color:var(--muted);
  font-size:13px;
  margin-bottom:8px;
}}
.date-values {{
  font-size:25px;
  font-weight:750;
  letter-spacing:.02em;
}}
.rule {{
  border-top:1px solid #253247;
  margin:18px 0 16px;
}}
.stage-table {{
  width:100%;
  border-collapse:collapse;
  table-layout:fixed;
}}
.stage-table th {{
  text-align:left;
  color:var(--muted);
  font-size:12px;
  font-weight:600;
  padding:7px 8px;
  border-bottom:1px solid var(--line);
}}
.stage-table td {{
  padding:11px 8px;
  border-bottom:1px solid #edf0f3;
  font-size:16px;
}}
.stage-table th:first-child,.stage-table td:first-child {{ width:23%; }}
.stage-table th:nth-child(2),.stage-table td:nth-child(2) {{ width:57%; }}
.stage-table th:last-child,.stage-table td:last-child {{
  width:20%; text-align:center;
}}
.level {{
  color:var(--level);
  font-weight:800;
}}
.na {{ color:#9aa3af; }}
.lines-title {{
  margin-top:22px;
  margin-bottom:9px;
  font-weight:800;
  border-bottom:1px solid var(--line);
  padding-bottom:8px;
}}
.line-item {{
  display:flex;
  gap:14px;
  padding:7px 0;
  border-bottom:1px solid #f0f2f4;
}}
.line-id {{ font-weight:800; min-width:62px; }}
.line-name {{ color:var(--muted); }}
.no-lines {{ color:var(--muted); padding:7px 0; }}
.report-note {{
  text-align:center;
  color:var(--muted);
  font-size:12px;
  margin-top:22px;
}}
.error-box {{
  width:min(540px,100%);
  background:white;
  border:1px solid #ead0d4;
  border-radius:16px;
  padding:32px;
  text-align:center;
}}
.error-box h2 {{ margin-top:0; }}
@media(max-width:800px) {{
  .cards {{ grid-template-columns:1fr; }}
}}
@media(max-width:560px) {{
  .form-card {{ padding:24px; }}
  .form-grid {{ grid-template-columns:1fr; }}
  .date-values {{ font-size:19px; }}
  .calendar-card {{ padding:18px; }}
  .report {{ padding:30px 12px 45px; }}
}}
</style>
</head>
<body>
{content}
</body>
</html>"""


def form_page():
    return page_shell(
        """
        <div class="topbar">
          <div class="brand">彩虹生命數字</div>
          <div class="eyebrow">MODULE 1</div>
        </div>

        <main class="form-page">
          <section class="form-card">
            <div class="eyebrow">CALCULATION ENGINE</div>
            <h1>彩虹生命數字計算工具</h1>
            <div class="subtitle">
              輸入陽曆生日即可自動轉換農曆，並計算五階段生命數字、功課等級及連線。
              出生時間為選填。
            </div>

            <form method="POST" action="/calculate">
              <div class="name-field">
                <label for="name">姓名（選填）</label>
                <input id="name" name="name" placeholder="例如：Jennifer">
              </div>

              <div class="form-grid">
                <div>
                  <label for="year">出生年份</label>
                  <input id="year" name="year" type="number"
                         min="1900" max="2100" placeholder="1956" required>
                </div>
                <div>
                  <label for="month">月份</label>
                  <input id="month" name="month" type="number"
                         min="1" max="12" placeholder="12" required>
                </div>
                <div>
                  <label for="day">日期</label>
                  <input id="day" name="day" type="number"
                         min="1" max="31" placeholder="13" required>
                </div>
              </div>

              <div class="time-grid">
                <div>
                  <label for="hour">出生時間：時（選填）</label>
                  <input id="hour" name="hour" type="number"
                         min="0" max="23" placeholder="12">
                </div>
                <div>
                  <label for="minute">出生時間：分（選填）</label>
                  <input id="minute" name="minute" type="number"
                         min="0" max="59" placeholder="30">
                </div>
              </div>

              <div class="time-note">
                不知道出生時間？兩欄都留空即可。程式不會自行猜測。
              </div>

              <button class="button" type="submit">產生計算報告</button>
            </form>
          </section>
        </main>
        """,
        title="彩虹生命數字｜計算工具",
    )


class Handler(BaseHTTPRequestHandler):
    def send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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
            parsed = parse_qs(raw)
            form = {k: v[0] for k, v in parsed.items()}

            result = run_calculation(form)
            self.send_html(result_page(result))

        except Exception as exc:
            self.send_html(error_page(str(exc)), 400)

    def log_message(self, fmt, *args):
        print(fmt % args)


def main():
    server = HTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"

    print("=" * 70)
    print("Rainbow Life Numerology — Module 1 Web Interface")
    print("=" * 70)
    print(f"Open in your browser: {url}")
    print("Press Ctrl+C to stop the server.")
    print("=" * 70)

    Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
