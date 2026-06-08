import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from utils.base import BaseScraper, get_logger, agora_brt, nova_session

log = get_logger("livelo")


class LiveloScraper(BaseScraper):
    name = "livelo"
    group = "aereo"
    enabled = True
    phase = 1
    accumulate = True
    chaves_dedup = ["data_captura", "programa"]

    title = "Livelo"
    description = "Cotação do milhar Livelo — valor do ponto na compra de milhas com bônus."
    icon = "✈️"
    icon_class = "icon-aereo"
    badge = "Diário"
    badge_class = "badge-daily"
    tags = ["aereo", "livelo", "milhas"]
    source = "Livelo"

    def fetch(self) -> pd.DataFrame:
        data_captura, _ = agora_brt()
        rows = []

        session = nova_session()

        try:
            resp = session.get(
                "https://www.livelo.com.br/api/compra-milhas",
                params={"origem": "GRU", "destino": "CGH", "passageiros": 1},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, dict) and "milhas" in data:
                valor_ponto = float(data.get("milhas", {}).get("valorPonto", 0))
            elif isinstance(data, list) and data:
                menor_valor = min(
                    (float(t.get("valorPonto", 0)) for t in data if t.get("valorPonto")),
                    default=0
                )
                valor_ponto = menor_valor
            else:
                valor_ponto = 0
        except Exception as e:
            log.warning(f"Erro ao acessar API Livelo: {e}")
            valor_ponto = 0

        rows.append({
            "data_captura": data_captura,
            "programa": "Livelo",
            "categoria": "aereo",
            "valor_milhar": round(valor_ponto * 1000, 6),
            "moeda_origem": "BRL",
            "descricao": f"Valor do ponto Livelo: R$ {valor_ponto}" if valor_ponto > 0 else "Indisponível",
            "data_referencia": data_captura,
        })

        return pd.DataFrame(rows)


if __name__ == "__main__":
    LiveloScraper().run()
