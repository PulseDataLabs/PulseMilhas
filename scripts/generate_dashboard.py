#!/usr/bin/env python
"""
scripts/generate_dashboard.py
-----------------------------
Lê todos os CSVs em data/ e gera data/dashboard.json para o frontend.
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

CATEGORY_MAP = {
    "aereo": {"label": "Programas Aéreos", "color": "#00d4ff"},
    "banco": {"label": "Bancos", "color": "#00e5a0"},
    "marketplace": {"label": "Marketplaces", "color": "#f0b429"},
}

ORDER = ["aereo", "banco", "marketplace"]


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def generate() -> None:
    all_records = []
    for csv_file in sorted(DATA_DIR.glob("*.csv")):
        rows = _read_csv(csv_file)
        for r in rows:
            try:
                r["valor_milhar"] = float(r.get("valor_milhar", 0) or 0)
            except (ValueError, TypeError):
                r["valor_milhar"] = 0.0
            r["_file"] = csv_file.name
            all_records.append(r)

    all_records.sort(key=lambda x: x.get("data_captura", ""))

    latest_by_program: dict[str, dict] = {}
    by_program: dict[str, list[dict]] = {}

    for r in all_records:
        prog = r.get("programa", "Desconhecido")
        by_program.setdefault(prog, []).append(r)
        dt = r.get("data_captura", "")
        if prog not in latest_by_program or dt > latest_by_program[prog].get("data_captura", ""):
            latest_by_program[prog] = r

    history = {}
    for prog, recs in by_program.items():
        series = {}
        for r in recs:
            dt = r.get("data_captura", "")
            v = r.get("valor_milhar", 0)
            if isinstance(v, (int, float)) and v > 0:
                series[dt] = v
        sorted_dates = sorted(series.keys())
        history[prog] = [{"data_captura": d, "valor_milhar": series[d]} for d in sorted_dates]

    latest_list = [v for v in latest_by_program.values() if v.get("valor_milhar", 0) > 0]

    media_geral = 0
    menor_valor = {"programa": "", "valor": float("inf")}
    maior_valor = {"programa": "", "valor": 0}

    if latest_list:
        vals = [r["valor_milhar"] for r in latest_list]
        media_geral = sum(vals) / len(vals)
        for r in latest_list:
            if r["valor_milhar"] < menor_valor["valor"]:
                menor_valor = {"programa": r["programa"], "valor": r["valor_milhar"]}
            if r["valor_milhar"] > maior_valor["valor"]:
                maior_valor = {"programa": r["programa"], "valor": r["valor_milhar"]}

    if menor_valor["valor"] == float("inf"):
        menor_valor["valor"] = 0

    by_category = {}
    for cat in ORDER:
        info = CATEGORY_MAP.get(cat, {"label": cat, "color": "#fff"})
        programs = []
        for prog, r in sorted(latest_by_program.items()):
            if r.get("categoria") == cat:
                programs.append({
                    "nome": prog,
                    "valor_milhar": r.get("valor_milhar", 0),
                    "data_captura": r.get("data_captura", ""),
                    "descricao": r.get("descricao", ""),
                })
        if programs:
            by_category[cat] = {
                "label": info["label"],
                "color": info["color"],
                "programs": programs,
            }

    dashboard = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_programas": len(latest_by_program),
            "media_geral": round(media_geral, 6),
            "menor_valor": menor_valor,
            "maior_valor": maior_valor,
        },
        "latest": {
            prog: {
                "valor_milhar": r["valor_milhar"],
                "data_captura": r["data_captura"],
                "categoria": r.get("categoria", ""),
                "descricao": r.get("descricao", ""),
            }
            for prog, r in sorted(latest_by_program.items())
        },
        "by_category": by_category,
        "history": history,
        "records_total": len(all_records),
    }

    output_path = DATA_DIR / "dashboard.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)

    js_path = DATA_DIR / "dashboard.js"
    with js_path.open("w", encoding="utf-8") as f:
        f.write(f"window.PULSEMILHAS_DASHBOARD = {json.dumps(dashboard, indent=2, ensure_ascii=False)};\n")

    print(f"  Dashboard salvo em {output_path} ({len(all_records)} registros, {len(latest_by_program)} programas)")


if __name__ == "__main__":
    generate()
