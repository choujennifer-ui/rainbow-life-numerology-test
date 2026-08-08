# Rainbow Life Numerology — Module 1 Web Interface

## Run

From this project folder:

```bash
python web_app.py
```

The browser will open to:

`http://127.0.0.1:8000/`

If it does not open automatically, paste that address into your browser.

## Input

- Solar/Gregorian year
- month
- day
- birth hour (optional)
- birth minute (optional)
- name (optional)

The web interface then runs:

Solar date
→ Lunar conversion
→ Five Stage Engine
→ Level Engine
→ Line Engine
→ Format (2) calculation report

## Important

The calculation engines are not rewritten by the web layer.

The web layer is only an interface around the existing Module 1 engine.

It does not add:
- interpretation
- Western numerology
- AI judgment
- guessed birth time

The blue auxiliary row from the original spreadsheet is not displayed.
