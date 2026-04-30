import pandas as pd

df = pd.read_excel("Sandloads 2026.xlsx")
df.columns = df.columns.str.strip()
df["STATUS"] = df["STATUS"].str.strip()

trec = df[df["STATUS"] == "ACTIVO"]

resumen = trec.groupby("RUTA")["Qty"].sum()
print("Resumen de cargas TREC:")
print(resumen)
