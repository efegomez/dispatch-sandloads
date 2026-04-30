import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import matplotlib.widgets as widgets
import numpy as np
import gspread
import requests
import base64
import json
from datetime import date
import time
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ── GitHub config ──────────────────────────────────────────────────────────────
_gh_cfg    = json.loads((Path(__file__).parent / ".github_config.json").read_text())
GH_TOKEN   = _gh_cfg["token"]
GH_REPO    = _gh_cfg["repo"]
GH_FILE    = _gh_cfg["file_path"]
GH_HEADERS    = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
GH_WORKFLOW_ID = 268929470  # Auto Update Chart

def trigger_actions():
    """Dispara GitHub Actions en cloud — más rápido que push directo desde red lenta."""
    r = requests.post(
        f"https://api.github.com/repos/{GH_REPO}/actions/workflows/{GH_WORKFLOW_ID}/dispatches",
        headers=GH_HEADERS, json={"ref": "main"}, timeout=15
    )
    if r.status_code == 204:
        print("GitHub Actions disparado — imagen actualizada en ~30s.")
    else:
        print(f"Error Actions: {r.status_code} {r.text[:100]}")

def _gh_put(path, content_b64, message):
    url  = f"https://api.github.com/repos/{GH_REPO}/contents/{path}"
    resp = requests.get(url, headers=GH_HEADERS)
    sha  = resp.json().get("sha") if resp.status_code == 200 else None
    payload = {"message": message, "content": content_b64}
    if sha:
        payload["sha"] = sha
    return requests.put(url, headers=GH_HEADERS, json=payload)

def push_to_github(png_path):
    # push PNG, capture commit SHA
    content = base64.b64encode(Path(png_path).read_bytes()).decode()
    r = _gh_put(GH_FILE, content, f"Actualizar grafico {date.today()}")
    if r.status_code not in (200, 201):
        print(f"Error GitHub PNG: {r.status_code} {r.text[:200]}")
        return

    # SHA único por commit → URL única → CDN siempre miss → imagen fresca
    commit_sha = r.json().get("commit", {}).get("sha", str(int(time.time())))
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <title>Cargas TREC - Dispatch</title>
  <style>
    body {{ margin: 0; background: #1a1a2e; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; font-family: Arial, sans-serif; color: white; }}
    img {{ max-width: 100%; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }}
    p {{ font-size: 12px; color: #888; margin-top: 10px; }}
  </style>
</head>
<body>
  <img id="chart">
  <p id="ts">Cargando...</p>
  <script>
    function reload() {{
      var t = Date.now();
      document.getElementById('chart').src = 'cargas_por_chofer.png?t=' + t;
      document.getElementById('ts').textContent = 'Actualizado: ' + new Date(t).toLocaleTimeString();
    }}
    reload();
    setInterval(reload, 60000);
  </script>
</body>
</html>"""
    html_b64 = base64.b64encode(html.encode()).decode()
    r2 = _gh_put("index.html", html_b64, f"Actualizar pagina {date.today()}")
    if r2.status_code in (200, 201):
        print(f"GitHub Pages actualizado: https://efegomez.github.io/dispatch-sandloads/")
    else:
        print(f"Error GitHub HTML: {r2.status_code} {r2.text[:200]}")

SPREADSHEET_ID = "1FlPvLr6eHExUb14CqPtPTUQmlHgUokIjLHFsidWzk-Y"
ALL_SHEETS     = []  # se detecta dinámicamente desde el Sheet
CREDS_FILE     = str(Path(__file__).parent / "credentials.json")
TOKEN_FILE     = str(Path(__file__).parent / "token.json")
SCOPES         = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]

def get_credentials():
    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds
NAME_MAP       = {
    "Jesus Peña":       "Jesus Pena Valdes",
    "Yanquiel Mendoza": "Yanquiel Gomez",
}
ROUTE_COLORS = {"PB": "#2196F3", "Vista Crane": "#FF5722"}

def classify_ruta(val):
    return "Vista Crane" if isinstance(val, str) and "vista" in val.lower() else "PB"

def is_red(bg):
    if not bg:
        return False
    return bg.get("red", 0) > 0.8 and bg.get("green", 0) < 0.2 and bg.get("blue", 0) < 0.2

def get_cell_value(cell):
    uev = cell.get("userEnteredValue", {})
    if "numberValue" in uev:
        return uev["numberValue"]
    if "stringValue" in uev:
        return uev["stringValue"]
    return None

def _get(url, headers, params=None, retries=3, timeout=45):
    for i in range(retries):
        try:
            return requests.get(url, headers=headers, params=params, timeout=timeout)
        except Exception as e:
            print(f"  Intento {i+1}/{retries} fallido: {e}")
            if i == retries - 1:
                raise
            import time; time.sleep(3)

def load_data(sheets):
    print("  Obteniendo credenciales...")
    creds = get_credentials()
    print("  Credenciales OK. Llamando API (nombres de hojas)...")
    token = creds.token
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}"

    # first fetch sheet names only (fast)
    meta = _get(url, headers, timeout=30).json()
    import re
    available = sorted([
        s["properties"]["title"] for s in meta.get("sheets", [])
        if re.match(r"^\d{2}\.\d{2}$", s["properties"]["title"])
    ])
    sheets = available  # override passed-in sheets with live list

    print(f"  {len(sheets)} hojas encontradas. Descargando datos completos...")
    params = (
        [("includeGridData", "true")]
        + [("ranges", s) for s in sheets]
        + [("fields", "sheets(properties/title,data/rowData/values(userEnteredValue,userEnteredFormat/backgroundColor))")]
    )
    resp = _get(url, headers, params=params, timeout=60)
    resp.raise_for_status()
    print("  Datos descargados. Procesando...")
    raw = resp.json()

    sheet_data = {s["properties"]["title"]: s for s in raw.get("sheets", [])}
    records = []

    for sheet_name in sheets:
        if sheet_name not in sheet_data:
            continue
        grid_rows = sheet_data[sheet_name]["data"][0].get("rowData", [])
        if not grid_rows:
            continue

        # parse header row -> col index map
        header_row = grid_rows[0].get("values", [])
        col_map = {}
        for i, cell in enumerate(header_row):
            val = get_cell_value(cell)
            key = str(val).strip() if val is not None else f"_col{i}"
            col_map[key] = i

        # find day columns (numeric 1-16)
        day_col_indices = {}
        for k, i in col_map.items():
            try:
                n = int(float(k))
                if 1 <= n <= 16:
                    day_col_indices[n] = i
            except (ValueError, TypeError):
                pass

        # find key columns
        def find_col(names):
            for n in names:
                if n in col_map:
                    return col_map[n]
            return None

        idx_driver = find_col(["Driver name", "driver name"])
        idx_truck  = find_col(["Truck #", "Truck#"])
        idx_ruta   = find_col(["RUTA", "Ruta"])
        idx_status = find_col(["STATUS", "Status", "STATUS "])

        for row_cells in grid_rows[1:]:
            values = row_cells.get("values", [])

            def get(idx):
                if idx is None or idx >= len(values):
                    return None
                return get_cell_value(values[idx])

            driver = get(idx_driver)
            if not driver or str(driver).strip() == "":
                continue

            driver = str(driver).strip()
            driver = " ".join(driver.split())  # collapse spaces
            driver = NAME_MAP.get(driver, driver)

            truck  = get(idx_truck)
            ruta   = get(idx_ruta)
            ruta_tipo = classify_ruta(ruta)

            # count valid (non-red) tickets
            cargas = 0
            for day_n, col_i in day_col_indices.items():
                if col_i >= len(values):
                    continue
                cell = values[col_i]
                val  = get_cell_value(cell)
                if val is None or str(val).strip() == "":
                    continue
                bg = cell.get("userEnteredFormat", {}).get("backgroundColor")
                if not is_red(bg):
                    cargas += 1

            records.append({
                "dia":       sheet_name,
                "Driver name": driver,
                "Truck #":   truck,
                "cargas":    cargas,
                "ruta_tipo": ruta_tipo,
            })

    if not records:
        return pd.DataFrame(columns=["dia","Driver name","Truck #","cargas","ruta_tipo","label"]), sheets

    data = pd.DataFrame(records)
    data = data[data["cargas"] > 0]

    truck_lookup = (data.dropna(subset=["Truck #"])
                    .groupby("Driver name")["Truck #"]
                    .agg(lambda x: x.mode()[0])
                    .apply(lambda t: f"#{int(t)}"))
    data["label"] = (data["Driver name"].str.split().str[0]
                     + " (" + data["Driver name"].map(truck_lookup) + ")")
    return data, sheets

def draw(ax_main, ax_bar, sheets, data):
    ax_main.clear()
    ax_bar.clear()

    dia_labels      = [f"Abr {s.split('.')[1]}" for s in sheets]
    y_labels        = sorted(data["label"].unique())
    y_pos           = {label: i for i, label in enumerate(y_labels)}
    x_pos           = {s: i for i, s in enumerate(sheets)}
    total_by_driver = data.groupby("label")["cargas"].sum()
    total_by_day    = data.groupby("dia")["cargas"].sum().reindex(sheets, fill_value=0)
    today_sheet     = date.today().strftime("%m.%d")

    for _, row in data.iterrows():
        x     = x_pos[row["dia"]]
        y     = y_pos[row["label"]]
        color = ROUTE_COLORS[row["ruta_tipo"]]
        edge  = "gold" if row["dia"] == today_sheet else "white"
        lw    = 2.5   if row["dia"] == today_sheet else 0.8
        ax_main.scatter(x, y, s=row["cargas"] * 450, color=color,
                        alpha=0.85, edgecolors=edge, linewidth=lw, zorder=3)
        ax_main.text(x, y, str(int(row["cargas"])), ha="center", va="center",
                     fontsize=9, fontweight="bold", color="white", zorder=4)

    for s, total in total_by_day.items():
        x  = x_pos[s]
        fc = "#FFF9C4" if s == today_sheet else "#E3F2FD"
        ec = "#F9A825" if s == today_sheet else "#90CAF9"
        ax_main.text(x, -0.85, f"Total\n{int(total)}", ha="center", va="top",
                     fontsize=8.5, fontweight="bold", color="#333333",
                     bbox=dict(boxstyle="round,pad=0.3", facecolor=fc, edgecolor=ec, linewidth=1.2))

    ax_main.set_xticks(range(len(sheets)))
    ax_main.set_xticklabels(dia_labels, fontsize=11)
    ax_main.set_yticks(range(len(y_labels)))
    ax_main.set_yticklabels(y_labels, fontsize=9)
    ax_main.set_ylim(-1.6, len(y_labels) - 0.3)
    ax_main.set_xlabel("Fecha", fontsize=11, labelpad=10)
    ax_main.grid(alpha=0.2, linestyle="--", zorder=0)
    ax_main.spines[["top", "right"]].set_visible(False)

    pb_patch = mpatches.Patch(color=ROUTE_COLORS["PB"],          label="PB To Nash")
    vc_patch = mpatches.Patch(color=ROUTE_COLORS["Vista Crane"], label="Vista Crane To Nash")
    for leg in ax_main.figure.legends[:]:
        leg.remove()
    ax_main.figure.legend(handles=[pb_patch, vc_patch], fontsize=9, title="Ruta",
                          loc="lower left", bbox_to_anchor=(0.52, 0.06),
                          framealpha=0.95, ncol=2, borderpad=0.6)

    totals_ordered = [int(total_by_driver.get(lbl, 0)) for lbl in y_labels]
    bars = ax_bar.barh(range(len(y_labels)), totals_ordered,
                       color="#546E7A", edgecolor="white", height=0.6)
    for bar, val in zip(bars, totals_ordered):
        ax_bar.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                    str(val), va="center", fontsize=9, fontweight="bold", color="#333333")
    ax_bar.set_xlabel("Total\nSemana", fontsize=10, labelpad=5)
    ax_bar.set_yticks([])
    ax_bar.set_ylim(-1.6, len(y_labels) - 0.3)
    ax_bar.set_xlim(0, max(totals_ordered) * 1.3 if totals_ordered else 1)
    ax_bar.spines[["top", "right", "left"]].set_visible(False)
    ax_bar.grid(axis="x", alpha=0.2, linestyle="--")
    ax_bar.tick_params(left=False)

    ax_main.figure.canvas.draw()
    ax_main.figure.canvas.flush_events()

# ── figure setup ───────────────────────────────────────────────────────────────
import threading, datetime
plt.rcParams['toolbar'] = 'None'
fig = plt.figure(figsize=(18, 9))
fig.suptitle("Cargas TREC por Día y Chofer — Abril 2026",
             fontsize=15, fontweight="bold")
gs      = gridspec.GridSpec(1, 2, width_ratios=[5, 1], wspace=0.05)
ax_main = fig.add_subplot(gs[0])
ax_bar  = fig.add_subplot(gs[1])
fig.subplots_adjust(left=0.12, right=0.97, top=0.90, bottom=0.22)

PNG_PATH = Path(__file__).parent / "cargas_por_chofer.png"

# mostrar PNG cacheado inmediatamente si existe
if PNG_PATH.exists():
    ax_main.imshow(plt.imread(str(PNG_PATH)), aspect="auto")
    ax_main.axis("off")
    ax_bar.axis("off")

# ── botón y estado ─────────────────────────────────────────────────────────────
ax_btn  = fig.add_axes([0.38, 0.06, 0.12, 0.08])
btn     = widgets.Button(ax_btn, "↺  Actualizar", color="#E3F2FD", hovercolor="#BBDEFB")
btn.label.set_fontsize(11)
btn.label.set_fontweight("bold")
ts_text = fig.text(0.38, 0.02, "Cargando...", fontsize=9, color="#E65100", ha="left", va="center")

# resultado compartido entre threads (solo main thread dibuja)
_result  = [None]   # (data, sheets) o Exception
_loading = [False]

def _fetch_worker():
    try:
        fresh, sheets_now = load_data([])
        _result[0] = (fresh, sheets_now)
    except Exception as e:
        _result[0] = e

def _apply_result():
    """Llamado desde main thread por timer cada 500ms."""
    if _result[0] is None:
        return
    result = _result[0]
    _result[0] = None
    _loading[0] = False
    btn.label.set_text("↺  Actualizar")
    if isinstance(result, Exception):
        ts_text.set_text(f"Error: {result}")
        ts_text.set_color("#C62828")
        fig.canvas.draw()
        return
    fresh, sheets_now = result
    ax_main.clear(); ax_bar.clear()
    draw(ax_main, ax_bar, sheets_now, fresh)
    ts_text.set_text(f"Actualizado: {datetime.datetime.now().strftime('%H:%M:%S')}")
    ts_text.set_color("#2E7D32")
    fig.canvas.draw()
    fig.savefig(str(PNG_PATH), dpi=150, bbox_inches="tight")
    threading.Thread(target=trigger_actions, daemon=True).start()
    print("Listo. Actions disparado en background.")

def _start_fetch():
    if _loading[0]:
        return
    _loading[0] = True
    _result[0] = None
    btn.label.set_text("Cargando...")
    ts_text.set_text("Descargando datos (~2 min)...")
    ts_text.set_color("#E65100")
    fig.canvas.draw()
    threading.Thread(target=_fetch_worker, daemon=True).start()

def on_refresh(event):
    _start_fetch()

btn.on_clicked(on_refresh)

# timer que aplica resultados en main thread
poll_timer = fig.canvas.new_timer(interval=500)
poll_timer.add_callback(_apply_result)
poll_timer.start()

# auto-refresh de datos al arrancar + cada 5 min
_start_fetch()
auto_timer = fig.canvas.new_timer(interval=5 * 60 * 1000)
auto_timer.add_callback(lambda: _start_fetch())
auto_timer.start()

print("Ventana abierta. PNG cacheado visible. Datos frescos cargando en background (~2 min).")
plt.show()
