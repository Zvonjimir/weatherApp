import tkinter as tk
from tkinter import messagebox, ttk
from database import init_db, getForecastDB, getForecastAround
from datetime import datetime

# ---------------- INIT ----------------

init_db()

root = tk.Tk()
root.title("Weather Interface")
root.geometry("800x520")

# ---------------- TABS ----------------

tab_control = ttk.Notebook(root)
tab_map = ttk.Frame(tab_control)
tab_around = ttk.Frame(tab_control)
tab_prognoza = ttk.Frame(tab_control)

tab_control.add(tab_map, text="Prognoza županije")
tab_control.add(tab_around, text="Prognoza oko grada")
tab_control.add(tab_prognoza, text="Prognoza grada")

tab_control.pack(expand=1, fill="both")

#----------------------PREGLED PO ZUPANIJAMA ------------------------------#
# mapa županija na gradove (primjer, možeš dodati sve)
ZUPANIJE_GRADOVI = {
    "Zagrebačka": ["Zagreb", "Velika Gorica", "Samobor"],
    "Krapinsko-zagorska": ["Zabok", "Krapina", "Donja Stubica"],
    "Sisačko-moslavačka": ["Sisak", "Novska", "Kutina"],
    "Karlovačka": ["Karlovac", "Ogulin", "Duga Resa"],
    "Primorsko-goranska": ["Rijeka", "Crikvenica", "Delnice"],
    "Zadarska": ["Zadar", "Biograd", "Obrovac"],
    "Splitsko-dalmatinska": ["Split", "Trogir", "Makarska"],
    "Istarska": ["Pula", "Rovinj", "Poreč"],
    "Grad Zagreb": ["Zagreb"]
}

tk.Label(tab_map, text="Županija:").pack(pady=5)
zupanija_combo = ttk.Combobox(tab_map, values=list(ZUPANIJE_GRADOVI.keys()), state="readonly")
zupanija_combo.pack(pady=5)
zupanija_combo.set(list(ZUPANIJE_GRADOVI.keys())[0])

def show_map():
    zupanija = zupanija_combo.get()
    output_text.delete("1.0", tk.END)
    output_text.insert(tk.END, f"Prognoza za županiju {zupanija} (danas):\n\n")

    gradovi = ZUPANIJE_GRADOVI.get(zupanija, [])
    if not gradovi:
        output_text.insert(tk.END, "Nema definiranih gradova za ovu županiju.\n")
        return

    for grad in gradovi:
        try:
            data = getForecastDB(grad)
        except Exception as e:
            output_text.insert(tk.END, f"{grad}: greška pri dohvaćanju prognoze ({e})\n")
            continue

        # filtriraj samo današnji dan
        today_str = datetime.now().date().isoformat()
        today_data = [d for d in data if str(d["date"]) == today_str]

        if not today_data:
            output_text.insert(tk.END, f"{grad}: nema podataka za danas\n")
            continue

        # uzmi prvi zapis (ako ima više izvora)
        day = today_data[0]
        temp = day.get("temperature")
        cond = day.get("condition")
        wind = f"{day.get('wind_speed') or '-'} km/h {day.get('wind_direction') or '-'}"
        output_text.insert(
            tk.END,
            f"{grad}: {temp}°C, {cond}, Vjetar: {wind}\n"
        )

tk.Button(
    tab_map,
    text="Prikaži prognozu županije",
    command=show_map
).pack(pady=5)

# ---- PROGNOZA OKO GRADA ----

tk.Label(tab_around, text="Grad:").pack(pady=5)

around_entry = tk.Entry(tab_around, width=30)
around_entry.pack(pady=5)


def show_around():
    grad = around_entry.get().strip()
    if not grad:
        messagebox.showwarning("Upozorenje", "Unesi ime grada")
        return

    output_text.delete("1.0", tk.END)

    try:
        # prvo osiguraj da baza ima podatke za taj grad
        getForecastDB(grad)

        # zatim dohvat okolnih gradova
        rows = getForecastAround(grad)

    except Exception as e:
        messagebox.showerror("Greška", str(e))
        return

    if not rows:
        output_text.insert(
            tk.END,
            f"Nema okolnih gradova s dostupnim podacima za {grad}.\n"
        )
        return

    output_text.insert(
        tk.END,
        f"📍 Prognoza okolnih gradova za {grad} (danas)\n"
        f"{'-'*50}\n\n"
    )

    for r in rows:
        output_text.insert(
            tk.END,
            f"🏙️ {r['city']}\n"
            f"   🌡️ Temperatura: {r['temperature']} °C\n"
            f"   ☁️ Vrijeme: {r['condition']}\n"
            f"   💧 Vlaga: {r['humidity']} %\n"
            f"   🌬️ Vjetar: {r['wind_speed']} km/h\n\n"
        )


tk.Button(
    tab_around,
    text="Prikaži prognozu okolnih gradova",
    command=show_around,
    width=35
).pack(pady=10)

# ---------------- PROGNOZA GRADA ----------------

tk.Label(tab_prognoza, text="Grad:").pack(pady=5)
prognoza_entry = tk.Entry(tab_prognoza)
prognoza_entry.pack(pady=5)

def show_prognoza():
    grad = prognoza_entry.get().strip()
    if not grad:
        messagebox.showwarning("Upozorenje", "Unesi ime grada")
        return

    try:
        data = getForecastDB(grad)
    except Exception as e:
        messagebox.showerror("Greška", str(e))
        return

    output_text.delete("1.0", tk.END)
    output_text.insert(
        tk.END,
        f"Prognoza za {grad}:\n\n"
    )

    if not data:
        output_text.insert(tk.END, "Nema dostupnih podataka.\n")
        return

    for d in data:
        datum = d["date"].strftime("%Y-%m-%d")
        output_text.insert(
            tk.END,
            f"{datum} | {d['temperature']}°C | {d['condition']} | "
            f"Vjetar: {d['wind_speed']} km/h | "
            f"Izvor: {d['source']}\n"
        )

tk.Button(
    tab_prognoza,
    text="Dohvati prognozu",
    command=show_prognoza
).pack(pady=5)

# ---------------- OUTPUT ----------------

output_text = tk.Text(root)
output_text.pack(expand=True, fill="both")

root.mainloop()
