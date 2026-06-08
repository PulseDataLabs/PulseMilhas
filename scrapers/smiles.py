import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import requests
from utils.base import BaseScraper, get_logger, agora_brt, limpar, nova_session

log = get_logger("smiles")


class SmilesScraper(BaseScraper):
    name = "smiles"
    group = "aereo"
    enabled = True
    phase = 1
    accumulate = True
    chaves_dedup = ["data_captura", "programa"]

    title = "Smiles"
    description = "Cotação do milhar Smiles — calculada a partir do menor valor em milhas para trechos domésticos populares."
    icon = "✈️"
    icon_class = "icon-aereo"
    badge = "Diário"
    badge_class = "badge-daily"
    tags = ["aereo", "smiles", "milhas"]
    source = "Smiles"

    def fetch(self) -> pd.DataFrame:
        data_captura, _ = agora_brt()
        rows = []

        session = nova_session()

        try:
            resp = session.get(
                "https://www.smiles.com.br/api/trechos",
                params={"origem": "GRU", "destino": "SDU", "passageiros": 1},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list) and data:
                menor_valor = min(
                    (float(t.get("valorMilhas", 0)) for t in data if t.get("valorMilhas")),
                    default=0
                )
            else:
                menor_valor = 0
        except Exception as e:
            log.warning(f"Erro ao acessar API Smiles: {e}")
            menor_valor = 0

        if menor_valor > 0:
            rows.append({
                "data_captura": data_captura,
                "programa": "Smiles",
                "categoria": "aereo",
                "valor_milhar": round((menor_valor / 1000), 6),
                "moeda_origem": "BRL",
                "descricao": f"Menor trecho GRU→SDU em milhas: {menor_valor}",
                "data_referencia": data_captura,
            })
        else:
            rows.append({
                "data_captura": data_captura,
                "programa": "Smiles",
                "categoria": "aereo",
                "valor_milhar": 0.0,
                "moeda_origem": "BRL",
                "descricao": "Indisponível",
                "data_referencia": data_captura,
            })

        return pd.DataFrame(rows)


if __name__ == "__main__":
    SmilesScraper().run()
