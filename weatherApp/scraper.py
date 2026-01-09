from __future__ import annotations

import os
import re
import json
import html as _html
from datetime import date, datetime
from typing import Optional, Dict, List

import requests


def openWeatherApi(city: str, api_key: Optional[str] = None, units: str = "metric", timeout: int = 10) -> Dict:
    if api_key is None:
        api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise ValueError("OpenWeather API key required. Set OPENWEATHER_API_KEY or pass api_key parameter.")

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": units}
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    today = date.today()
    result = {
        "source": "openweathermap",
        "city": city,
        "date": today.isoformat(),
        "temperature": j.get("main", {}).get("temp"),
        "condition": (j.get("weather") or [{}])[0].get("description"),
        "humidity": j.get("main", {}).get("humidity"),
        "wind_speed": j.get("wind", {}).get("speed"),
        "raw": j,
    }
    return result


def _deg_to_cardinal(deg: Optional[float]) -> Optional[str]:
    if deg is None:
        return None
    try:
        d = float(deg) % 360
    except Exception:
        return None
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ix = int((d + 22.5) // 45) % 8
    return dirs[ix]


def _map_openweather_to_datajson(city: str, ow: Dict) -> Dict:
    raw = ow.get("raw", {})
    sys = raw.get("sys", {})
    coord = raw.get("coord", {})
    wind = raw.get("wind", {})
    clouds = raw.get("clouds", {})
    rain = raw.get("rain", {}) or {}
    snow = raw.get("snow", {}) or {}

    city_info = {
        "name": raw.get("name") or city,
        "country": sys.get("country"),
        "provider": "OpenWeather",
        "latitude": coord.get("lat"),
        "longitude": coord.get("lon"),
    }

    # precipitation (last 1h if present)
    precip = 0
    for k in ("1h", "3h"):
        v = rain.get(k) or snow.get(k)
        if v:
            try:
                precip = max(precip, float(v))
            except Exception:
                pass

    # hourly (only current hour available from current weather API)
    now = datetime.utcnow()
    hour_str = now.strftime("%H:00")
    temp = ow.get("temperature")
    hourly = [{
        "time": hour_str,
        "temperature": int(round(temp)) if temp is not None else None,
        "precipitation": precip,
        "cloudiness": clouds.get("all"),
    }]

    day = {
        "date": date.today().isoformat(),
        "condition": (ow.get("condition") or "").capitalize(),
        "humidity": ow.get("humidity"),
        "windSpeed": ow.get("wind_speed"),
        "windDirection": _deg_to_cardinal(wind.get("deg")),
        "precipitation": precip,
        "hourly": hourly,
    }

    return {"city": city_info, "forecast": [day]}


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html)
    return _html.unescape(text).strip()


def _parse_date_from_string(s: str) -> Optional[str]:
    s = s or ""
    # ISO first
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    # full dotted date
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mo, y = m.groups()
        try:
            return date(int(y), int(mo), int(d)).isoformat()
        except Exception:
            return None
    # day.month. (assume current year)
    m = re.search(r"(\d{1,2})\.(?:\s*)(\d{1,2})\.", s)
    if m:
        d, mo = m.groups()
        y = date.today().year
        try:
            return date(y, int(mo), int(d)).isoformat()
        except Exception:
            return None
    return None


def scrapeDhmz(city: str) -> Dict:
    url = f"https://meteo.hr/prognoze.php?Code={city}&id=prognoza&section=prognoze_model&param=3d"
    filename = f"meteo_{city}.html"

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        html = r.text

        # privremeno snimanje HTML-a (debug / razvoj)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

        txt = re.sub(r"\s+", " ", html)

        tables = re.findall(r"<table[^>]*>(.*?)</table>", txt, flags=re.I | re.S)
        days: List[Dict] = []
        seen_dates = set()

        def extract_cells(row_html: str) -> List[str]:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, flags=re.I | re.S)
            return [_strip_tags(c) for c in cells]

        for table_html in tables:
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.I | re.S)
            if not rows:
                continue

            parsed_rows = [(rhtml, extract_cells(rhtml)) for rhtml in rows]

            # header times (npr. 01:00 04:00 07:00 ...)
            header_times: List[str] = []
            for rhtml, cells in parsed_rows:
                times = []
                for c in cells:
                    times += re.findall(r"\b\d{1,2}:\d{2}\b", c)
                if len(times) >= 3:
                    header_times = times
                    break
            if not header_times:
                continue

            for i, (rhtml, cells) in enumerate(parsed_rows):
                date_iso = None
                date_col_idx = None
                for idx, c in enumerate(cells):
                    d = _parse_date_from_string(c)
                    if d:
                        date_iso = d
                        date_col_idx = idx
                        break
                if not date_iso or date_iso in seen_dates:
                    continue

                temps: List[str] = []
                temp_row_html = ""

                if i + 1 < len(parsed_rows):
                    r2html, c2 = parsed_rows[i + 1]
                    for cc in c2:
                        m = re.search(r"([-+]?\d{1,3})\s*°[CF]?", cc)
                        if m:
                            temps.append(m.group(1))
                    temp_row_html = r2html

                if not temps and i + 2 < len(parsed_rows):
                    r3html, c3 = parsed_rows[i + 2]
                    for cc in c3:
                        m = re.search(r"([-+]?\d{1,3})\s*°[CF]?", cc)
                        if m:
                            temps.append(m.group(1))
                    if temps:
                        temp_row_html = r3html

                if not temps:
                    for cc in cells:
                        m = re.search(r"([-+]?\d{1,3})\s*°[CF]?", cc)
                        if m:
                            temps.append(m.group(1))

                if not temps:
                    continue

                n = min(len(header_times), len(temps))
                hourly: List[Dict] = []
                for k in range(n):
                    try:
                        tempv = int(temps[k])
                    except Exception:
                        tempv = None
                    hourly.append({
                        "time": header_times[k],
                        "temperature": tempv,
                        "precipitation": 0,
                        "cloudiness": 0
                    })

                region = rhtml + temp_row_html

                m_cond = re.search(r"<span[^>]*title=\"([^\"]+)\"", region, flags=re.I)
                if not m_cond:
                    m_cond = re.search(r"<img[^>]*(?:alt|title)=\"([^\"]+)\"", region, flags=re.I)
                cond = _strip_tags(m_cond.group(1)) if m_cond else None

                wind_speed = None
                wind_dir = None

                if date_col_idx is not None:
                    for j in range(i + 1, min(i + 4, len(parsed_rows))):
                        rjhtml, _ = parsed_rows[j]
                        raw_cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', rjhtml, flags=re.I | re.S)
                        if date_col_idx < len(raw_cells):
                            cell_html = raw_cells[date_col_idx]
                            m_img = re.search(
                                r'icons/([A-Za-z]+)(\d+)\.svg',
                                cell_html,
                                flags=re.I
                            )
                            if m_img:
                                wind_dir = m_img.group(1).upper()
                                wind_speed = int(m_img.group(2)) * 5
                                break

                day = {
                    "date": date_iso,
                    "condition": cond,
                    "humidity": None,
                    "windSpeed": wind_speed,
                    "windDirection": wind_dir,
                    "precipitation": 0,
                    "hourly": hourly,
                }

                days.append(day)
                seen_dates.add(date_iso)

        city_info = {
            "name": city,
            "country": "HR",
            "provider": "DHMZ",
            "latitude": None,
            "longitude": None
        }

        return {"city": city_info, "forecast": days}

    finally:
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass


def getForecast(city: str) -> List[Dict]:

    result: List[Dict] = []

    # use OpenWeather (current weather) and convert into data.json structure
    ow = openWeatherApi(city, api_key="064cf0a7cf4688c66173c448c4c5d5f5")
    mapped = _map_openweather_to_datajson(city, ow)
    result.append({"source": "openweathermap", "city": city, "date": date.today().isoformat(), "data": mapped})

    # for non-today dates, fetch DHMZ only
    data = scrapeDhmz(city)
    result.append({"source": "dhmz", "city": city, "date": date.today().isoformat(), "data": data})

    return result


if __name__ == "__main__":
    # simple demo
    try:
        print("getForecast for Zadar (today):")
        res = getForecast("Zadar")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        # scrapeDhmz("Zagreb")
    except Exception as e:
        print("Demo failed:", e)