import csv, json, os

CSV_PATH = os.path.join('data', 'ais_raw.csv')
OUT_PATH = os.path.join('data_pipeline', 'csv_info.json')

with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    cols = reader.fieldnames
    rows = []
    for i, row in enumerate(reader):
        if i >= 3:
            break
        rows.append(dict(row))

with open(OUT_PATH, 'w', encoding='utf-8') as out:
    json.dump({'columns': cols, 'sample_rows': rows}, out, indent=2)

print("Done. Wrote", OUT_PATH)
