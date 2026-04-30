import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_excel("Sandloads 2026.xlsx")
df.columns = [str(c).strip() for c in df.columns]
df["STATUS"] = df["STATUS"].str.strip()

activo = df[df["STATUS"] == "ACTIVO"]

day_cols = [str(i) for i in range(1, 17)]
available = [c for c in day_cols if c in df.columns]

cargas_por_dia = activo[available].notna().sum()
cargas_por_dia.index = [int(c) for c in cargas_por_dia.index]

fig, ax = plt.subplots(figsize=(12, 6))
bars = ax.bar(cargas_por_dia.index, cargas_por_dia.values, color="#2196F3", edgecolor="white", width=0.7)

for bar, val in zip(bars, cargas_por_dia.values):
    if val > 0:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                str(int(val)), ha="center", va="bottom", fontweight="bold", fontsize=10)

ax.set_title("Cargas TREC por Día — 2026", fontsize=16, fontweight="bold", pad=15)
ax.set_xlabel("Día del Mes", fontsize=12)
ax.set_ylabel("Número de Cargas", fontsize=12)
ax.set_xticks(cargas_por_dia.index)
ax.set_ylim(0, cargas_por_dia.max() + 1)
ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
ax.grid(axis="y", alpha=0.3, linestyle="--")
ax.spines[["top", "right"]].set_visible(False)

plt.tight_layout()
plt.savefig("cargas_trec_por_dia.png", dpi=150, bbox_inches="tight")
print("Guardado: cargas_trec_por_dia.png")
print(cargas_por_dia[cargas_por_dia > 0].to_string())
