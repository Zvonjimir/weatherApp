import mysql.connector
from datetime import datetime
from scraper import getForecast

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "admin",
    "password": "admin",
    "database": "weatherDB"
}


# ---------------- CONNECTION ----------------

def get_connection(create_db=False):
    config = MYSQL_CONFIG.copy()
    if create_db:
        config.pop("database")
    return mysql.connector.connect(**config)


# ---------------- INIT DB ----------------

def init_db():
    conn = get_connection(create_db=True)
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS weatherDB")
    conn.close()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forecasts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            city VARCHAR(100) NOT NULL,
            date DATE NOT NULL,
            temperature DECIMAL(4,1),
            `condition` VARCHAR(100),
            humidity INT,
            wind_speed INT,
            wind_direction VARCHAR(5),
            precipitation DECIMAL(5,2),
            lat DOUBLE,
            lon DOUBLE,
            source VARCHAR(20),
            UNIQUE(city, date)
        )
    """)
    conn.commit()
    conn.close()


# ---------------- HELPERS ----------------

def does_exist(city, date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM forecasts WHERE city=%s AND date=%s",
        (city, date)
    )
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def insert_day(city, source, city_info, day):
    conn = get_connection()
    cur = conn.cursor()

    # uzmi prvu hourly temperaturu ako postoji
    temp = None
    if day.get("hourly"):
        temp = day["hourly"][0].get("temperature")

    cur.execute("""
        INSERT INTO forecasts
        (city, date, temperature, `condition`, humidity,
         wind_speed, wind_direction, precipitation,
         lat, lon, source)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            temperature=VALUES(temperature),
            `condition`=VALUES(`condition`),
            humidity=VALUES(humidity),
            wind_speed=VALUES(wind_speed),
            wind_direction=VALUES(wind_direction),
            precipitation=VALUES(precipitation),
            source=VALUES(source)
    """, (
        city,
        day["date"],
        temp,
        day.get("condition"),
        day.get("humidity"),
        day.get("windSpeed"),
        day.get("windDirection"),
        day.get("precipitation"),
        city_info.get("latitude"),
        city_info.get("longitude"),
        source
    ))

    conn.commit()
    conn.close()


# ---------------- MAIN API ----------------

def getForecastDB(city):
    """
    Vraća prognozu za sljedeća 4 dana (danas + DHMZ)
    Ako ne postoji u bazi → zove scraper
    """
    today = datetime.now().date().isoformat()

    if not does_exist(city, today):
        results = getForecast(city)

        for entry in results:
            source = entry["source"]
            data = entry["data"]
            city_info = data["city"]

            for day in data["forecast"]:
                insert_day(
                    city=city,
                    source=source,
                    city_info=city_info,
                    day=day
                )

    # dohvat iz baze
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT city, date, temperature, `condition`,
               humidity, wind_speed, wind_direction,
               precipitation, lat, lon, source
        FROM forecasts
        WHERE city=%s
        ORDER BY date
    """, (city,))
    rows = cur.fetchall()
    conn.close()

    return rows


def getForecastAround(city, radius_km=50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT lat, lon
        FROM forecasts
        WHERE city = %s
          AND lat IS NOT NULL
          AND lon IS NOT NULL
        ORDER BY date DESC
        LIMIT 1
    """, (city,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise ValueError(
            f"Grad '{city}' nema nijednu prognozu s koordinatama."
        )

    lat0, lon0 = row

    delta = 0.05 * radius_km / 5

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT city, date, temperature, `condition`,
               humidity, wind_speed, wind_direction,
               precipitation, lat, lon
        FROM forecasts
        WHERE lat BETWEEN %s AND %s
          AND lon BETWEEN %s AND %s
          AND date = CURDATE()
        ORDER BY city
    """, (
        lat0 - delta, lat0 + delta,
        lon0 - delta, lon0 + delta
    ))

    rows = cur.fetchall()
    conn.close()
    return rows


