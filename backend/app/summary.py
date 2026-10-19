# app/summary.py
import os
from app import db
from app.config import SUMMARY_DIR


def generate_html(session_id: int, round_num: int) -> str:
    """Генерирует автономный HTML-файл и возвращает путь."""
    s = db.get_session(session_id)
    players = db.get_players(session_id)

    color_map = {
        "Татуин":    "green",
        "Мандалор":  "red",
        "Джакку":    "blue",
        "Корусант":  "orange",
        "Альдераан": "purple",
        "Мустафар":  "yellowgreen",
        "Набу":      "darkred",
        "Эндор":     "#3a8f3a",
        "Хот":       "#b8c8e0",
        "Дагоба":    "#5a7a50",
    }

    panels_html = []
    for p in players:
        cities = db.get_cities(p["id"])
        city_names = "".join(f'<div class="city">{c["name"]}</div>' for c in cities)
        percents = "".join(
            f'<div class="percentage">{c["life_level"]}%</div>'
            if not c["is_destroyed"] else
            f'<div class="percentage dead">—</div>'
            for c in cities
        )
        color = color_map.get(p["planet"], "gray")
        panels_html.append(f"""
            <p class="name"><strong>{p["planet"]}</strong></p>
            <div class="panel" style="--panel-color: {color};">
                <div class="upper-half">{city_names}</div>
                <div class="lower-half">{percents}</div>
            </div>
        """)

    data = []
    for p in players:
        cities = db.get_cities(p["id"])
        avg = sum(c["life_level"] for c in cities) / len(cities) if cities else 0
        data.append((p["planet"], avg))
    max_avg = max((d[1] for d in data), default=1) or 1

    bars_html = []
    for name, val in data:
        height_pct = (val / max_avg) * 100
        bars_html.append(f"""
            <div class="bar" style="height: {height_pct}%;">
                <span class="value">{val:.0f}%</span>
                <span class="label">{name}</span>
            </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Итоги раунда {round_num}</title>
<style>
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        padding: 20px;
        font-family: system-ui, -apple-system, "Segoe UI", Arial, sans-serif;
        background: #f5f5f5;
        color: #222;
    }}
    .title {{ font-size: 42px; margin: 0 0 20px 10px; }}
    .wrapper {{ display: flex; align-items: flex-start; gap: 30px; flex-wrap: wrap; }}
    .panels {{ flex: 0 0 700px; }}
    .name {{ font-size: 28px; margin: 16px 0 4px; }}
    .panel {{
        width: 700px;
        height: 100px;
        background: #2f2f2f;
        border-radius: 20px;
        overflow: hidden;
        color: #fff;
        font-size: 24px;
    }}
    .upper-half {{
        height: 50%;
        background: var(--panel-color);
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        align-items: center;
    }}
    .lower-half {{
        height: 50%;
        background: #2f2f2f;
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        align-items: center;
    }}
    .city, .percentage {{ text-align: center; padding: 5px; }}
    .percentage.dead {{ color: #888; }}
    .chart-wrapper {{ flex: 1; min-width: 400px; }}
    .hist-name {{ font-size: 32px; margin: 0 0 10px 20px; }}
    .chart {{
        display: flex;
        height: 600px;
        background: #f0f0f0;
        border-radius: 10px;
        padding: 20px;
        align-items: flex-end;
        justify-content: space-between;
        gap: 10px;
    }}
    .bar {{
        flex: 1;
        background: #007BFF;
        border-radius: 5px;
        position: relative;
        display: flex;
        flex-direction: column-reverse;
        align-items: center;
        min-height: 40px;
    }}
    .value, .label {{ color: #fff; font-weight: bold; margin-bottom: 4px; }}
    .label {{ font-size: 13px; }}
    .eco {{ font-size: 32px; margin: 20px 0 0 20px; }}
</style>
</head>
<body>
    <h1 class="title"><strong>Космическое господство 🚀 — раунд {round_num}</strong></h1>
    <div class="wrapper">
        <div class="panels">
            {"".join(panels_html)}
        </div>
        <div class="chart-wrapper">
            <div class="hist-name">Уровень жизни на планетах</div>
            <div class="chart">
                {"".join(bars_html)}
            </div>
            <div class="eco">Уровень аномалии 🌌: {s["anomaly"]}%</div>
        </div>
    </div>
</body>
</html>"""

    fname = f"{session_id}_round{round_num}.html"
    path = os.path.join(SUMMARY_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def generate_both(session_id: int, round_num: int) -> dict:
    """Оставляем имя функции для совместимости, но генерирует только HTML."""
    generate_html(session_id, round_num)
    return {
        "html_url": f"/static/summary/{session_id}_round{round_num}.html",
    }


def generate_html_string(session_id: int, round_num: int) -> str:
    """Возвращает HTML-сводку как строку (без записи на диск)."""
    s = db.get_session(session_id)
    if not s:
        raise ValueError("Сессия не найдена")
    players = db.get_players(session_id)

    color_map = {
        "Татуин":    "green",
        "Мандалор":  "red",
        "Джакку":    "blue",
        "Корусант":  "orange",
        "Альдераан": "purple",
        "Мустафар":  "yellowgreen",
        "Набу":      "darkred",
        "Эндор":     "#3a8f3a",
        "Хот":       "#b8c8e0",
        "Дагоба":    "#5a7a50",
    }

    panels_html = []
    for p in players:
        cities = db.get_cities(p["id"])
        city_names = "".join(f'<div class="city">{c["name"]}</div>' for c in cities)
        percents = "".join(
            f'<div class="percentage">{c["life_level"]}%</div>'
            if not c["is_destroyed"] else
            f'<div class="percentage dead">—</div>'
            for c in cities
        )
        color = color_map.get(p["planet"], "gray")
        panels_html.append(f"""
            <p class="name"><strong>{p["planet"]}</strong></p>
            <div class="panel" style="--panel-color: {color};">
                <div class="upper-half">{city_names}</div>
                <div class="lower-half">{percents}</div>
            </div>
        """)

    data = []
    for p in players:
        cities = db.get_cities(p["id"])
        avg = sum(c["life_level"] for c in cities) / len(cities) if cities else 0
        data.append((p["planet"], avg))
    max_avg = max((d[1] for d in data), default=1) or 1

    bars_html = []
    for name, val in data:
        height_pct = (val / max_avg) * 100
        bars_html.append(f"""
            <div class="bar" style="height: {height_pct}%;">
                <span class="value">{val:.0f}%</span>
                <span class="label">{name}</span>
            </div>
        """)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Итоги раунда {round_num}</title>
<style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 20px;
        font-family: system-ui, -apple-system, "Segoe UI", Arial, sans-serif;
        background: #f5f5f5; color: #222; }}
    .title {{ font-size: 42px; margin: 0 0 20px 10px; }}
    .wrapper {{ display: flex; align-items: flex-start; gap: 30px; flex-wrap: wrap; }}
    .panels {{ flex: 0 0 700px; }}
    .name {{ font-size: 28px; margin: 16px 0 4px; }}
    .panel {{ width: 700px; height: 100px; background: #2f2f2f;
        border-radius: 20px; overflow: hidden; color: #fff; font-size: 24px; }}
    .upper-half {{ height: 50%; background: var(--panel-color);
        display: grid; grid-template-columns: repeat(4, 1fr); align-items: center; }}
    .lower-half {{ height: 50%; background: #2f2f2f;
        display: grid; grid-template-columns: repeat(4, 1fr); align-items: center; }}
    .city, .percentage {{ text-align: center; padding: 5px; }}
    .percentage.dead {{ color: #888; }}
    .chart-wrapper {{ flex: 1; min-width: 400px; }}
    .hist-name {{ font-size: 32px; margin: 0 0 10px 20px; }}
    .chart {{ display: flex; height: 600px; background: #f0f0f0;
        border-radius: 10px; padding: 20px; align-items: flex-end;
        justify-content: space-between; gap: 10px; }}
    .bar {{ flex: 1; background: #007BFF; border-radius: 5px;
        position: relative; display: flex; flex-direction: column-reverse;
        align-items: center; min-height: 40px; }}
    .value, .label {{ color: #fff; font-weight: bold; margin-bottom: 4px; }}
    .label {{ font-size: 13px; }}
    .eco {{ font-size: 32px; margin: 20px 0 0 20px; }}
</style>
</head>
<body>
    <h1 class="title"><strong>Космическое господство 🚀 — раунд {round_num}</strong></h1>
    <div class="wrapper">
        <div class="panels">
            {"".join(panels_html)}
        </div>
        <div class="chart-wrapper">
            <div class="hist-name">Уровень жизни на планетах</div>
            <div class="chart">
                {"".join(bars_html)}
            </div>
            <div class="eco">Уровень аномалии 🌌: {s["anomaly"]}%</div>
        </div>
    </div>
</body>
</html>"""