import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

sheets = ['04.24', '04.25', '04.26', '04.27', '04.28', '04.29']
day_cols = [str(i) for i in range(1, 17)]
NAME_MAP = {"Jesus Peña": "Jesus Pena Valdes", "Yanquiel Mendoza": "Yanquiel Gomez"}

def classify_ruta(val):
    if isinstance(val, str) and "vista" in val.lower():
        return "Vista Crane"
    return "PB"

records = []
for sheet in sheets:
    df = pd.read_excel("Sandloads 2026.xlsx", sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]
    drivers_df = df[df["Driver name"].notna()].copy()
    available = [c for c in day_cols if c in df.columns]
    drivers_df["cargas"] = drivers_df[available].notna().sum(axis=1)
    drivers_df["dia"] = sheet
    drivers_df["ruta_tipo"] = drivers_df["RUTA"].apply(classify_ruta)
    truck_map = drivers_df.dropna(subset=["Truck #"]).set_index("Driver name")["Truck #"].to_dict()
    drivers_df["truck"] = drivers_df["Driver name"].map(truck_map)
    records.append(drivers_df[["dia", "Driver name", "Truck #", "cargas", "ruta_tipo"]])

data = pd.concat(records, ignore_index=True)
data["Driver name"] = data["Driver name"].str.strip().str.replace(r'\s+', ' ', regex=True)
data["Driver name"] = data["Driver name"].replace(NAME_MAP)

# Build truck label per driver (most frequent truck #)
truck_lookup = (data.dropna(subset=["Truck #"])
                .groupby("Driver name")["Truck #"]
                .agg(lambda x: x.mode()[0])
                .apply(lambda t: f"#{int(t)}"))
data["label"] = data["Driver name"] + " (" + data["Driver name"].map(truck_lookup) + ")"
data = data[data["cargas"] > 0]

dia_labels = [f"Abr {s.split('.')[1]}" for s in sheets]
all_labels = sorted(data["label"].unique())
colors_tab = plt.cm.tab20.colors
driver_color = {d: colors_tab[i % len(colors_tab)] for i, d in enumerate(all_labels)}
route_colors = {"PB": "#2196F3", "Vista Crane": "#FF5722"}

# ── OPCIÓN 1: HEATMAP ──────────────────────────────────────────────────────────
fig1, axes = plt.subplots(1, 2, figsize=(16, 7))
fig1.suptitle("Opción 1 — Heatmap: Cargas por Chofer y Día", fontsize=14, fontweight="bold")

for ax, ruta in zip(axes, ["PB", "Vista Crane"]):
    subset = data[data["ruta_tipo"] == ruta]
    pivot = subset.pivot_table(index="label", columns="dia", values="cargas",
                               aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(columns=sheets, fill_value=0)
    pivot.columns = dia_labels

    im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd", vmin=0)
    ax.set_xticks(range(len(dia_labels)))
    ax.set_xticklabels(dia_labels, fontsize=9)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title(f"{'PB To Nash' if ruta == 'PB' else 'Vista Crane To Nash'}", fontsize=11, fontweight="bold")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = int(pivot.values[i, j])
            ax.text(j, i, str(val) if val > 0 else "", ha="center", va="center",
                    fontsize=10, fontweight="bold",
                    color="white" if val >= 4 else "black")
    plt.colorbar(im, ax=ax, shrink=0.8)

plt.tight_layout()
plt.savefig("opcion1_heatmap.png", dpi=150, bbox_inches="tight")
print("Guardado: opcion1_heatmap.png")

# ── OPCIÓN 2: BARRAS APILADAS ──────────────────────────────────────────────────
fig2, axes = plt.subplots(2, 1, figsize=(14, 10))
fig2.suptitle("Opción 2 — Barras Apiladas por Día", fontsize=14, fontweight="bold")

for ax, ruta in zip(axes, ["PB", "Vista Crane"]):
    subset = data[data["ruta_tipo"] == ruta]
    pivot = subset.pivot_table(index="dia", columns="label", values="cargas",
                               aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(sheets, fill_value=0)
    pivot.index = dia_labels
    x = np.arange(len(dia_labels))
    bottom = np.zeros(len(dia_labels))
    for driver in pivot.columns:
        vals = pivot[driver].values
        bars = ax.bar(x, vals, bottom=bottom, label=driver,
                      color=driver_color[driver], edgecolor="white", linewidth=0.4)
        for bar, val, bot in zip(bars, vals, bottom):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bot + val / 2,
                        str(int(val)), ha="center", va="center", fontsize=7, fontweight="bold", color="white")
        bottom += vals
    ax.set_title(f"{'PB To Nash' if ruta == 'PB' else 'Vista Crane To Nash'}", fontsize=11, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(dia_labels, fontsize=10)
    ax.set_ylabel("Cargas", fontsize=10)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=7, title="Chofer")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

plt.tight_layout()
plt.savefig("opcion2_barras_apiladas.png", dpi=150, bbox_inches="tight")
print("Guardado: opcion2_barras_apiladas.png")

# ── OPCIÓN 3: PEQUEÑOS MÚLTIPLOS POR CHOFER ───────────────────────────────────
drivers_sorted = sorted(data["label"].unique())
n_drivers = len(drivers_sorted)
ncols = 4
nrows = (n_drivers + ncols - 1) // ncols
fig3, axes = plt.subplots(nrows, ncols, figsize=(16, nrows * 3), sharey=False)
fig3.suptitle("Opción 3 — Pequeños Múltiplos por Chofer", fontsize=14, fontweight="bold")
axes_flat = axes.flatten()

for i, driver in enumerate(drivers_sorted):
    ax = axes_flat[i]
    sub = data[data["label"] == driver]
    for ruta, color in route_colors.items():
        rpivot = sub[sub["ruta_tipo"] == ruta].groupby("dia")["cargas"].sum().reindex(sheets, fill_value=0)
        rpivot.index = dia_labels
        offset = -0.2 if ruta == "PB" else 0.2
        x = np.arange(len(dia_labels))
        bars = ax.bar(x + offset, rpivot.values, width=0.35, label=ruta, color=color, edgecolor="white")
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.05,
                        str(int(h)), ha="center", va="bottom", fontsize=7, fontweight="bold")
    ax.set_title(driver, fontsize=8, fontweight="bold")
    ax.set_xticks(np.arange(len(dia_labels)))
    ax.set_xticklabels([d.replace("Abr ", "") for d in dia_labels], fontsize=7)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

for j in range(i + 1, len(axes_flat)):
    axes_flat[j].set_visible(False)

pb_patch = mpatches.Patch(color=route_colors["PB"], label="PB To Nash")
vc_patch = mpatches.Patch(color=route_colors["Vista Crane"], label="Vista Crane To Nash")
fig3.legend(handles=[pb_patch, vc_patch], loc="lower right", fontsize=10, title="Ruta")
plt.tight_layout()
plt.savefig("opcion3_multiples.png", dpi=150, bbox_inches="tight")
print("Guardado: opcion3_multiples.png")

# ── OPCIÓN 4: BURBUJA ─────────────────────────────────────────────────────────
fig4, ax = plt.subplots(figsize=(14, 8))
fig4.suptitle("Opción 4 — Burbuja: Chofer vs Día", fontsize=14, fontweight="bold")

y_labels = sorted(data["label"].unique())
y_pos = {label: i for i, label in enumerate(y_labels)}
x_pos = {s: i for i, s in enumerate(sheets)}

for _, row in data.iterrows():
    x = x_pos[row["dia"]]
    y = y_pos[row["label"]]
    size = row["cargas"] * 400
    color = route_colors[row["ruta_tipo"]]
    ax.scatter(x, y, s=size, color=color, alpha=0.7, edgecolors="white", linewidth=0.8)
    ax.text(x, y, str(int(row["cargas"])), ha="center", va="center",
            fontsize=8, fontweight="bold", color="white")

ax.set_xticks(range(len(sheets)))
ax.set_xticklabels(dia_labels, fontsize=10)
ax.set_yticks(range(len(y_labels)))
ax.set_yticklabels(y_labels, fontsize=9)
ax.set_xlabel("Fecha", fontsize=11)
ax.grid(alpha=0.2, linestyle="--")
ax.spines[["top", "right"]].set_visible(False)

pb_patch = mpatches.Patch(color=route_colors["PB"], label="PB To Nash")
vc_patch = mpatches.Patch(color=route_colors["Vista Crane"], label="Vista Crane To Nash")
ax.legend(handles=[pb_patch, vc_patch], fontsize=10, title="Ruta", loc="lower right")

plt.tight_layout()
plt.savefig("opcion4_burbuja.png", dpi=150, bbox_inches="tight")
print("Guardado: opcion4_burbuja.png")
