import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from utils.base import BaseScraper, get_logger, agora_brt, nova_session

log = get_logger("latam_pass")


class LatamPassScraper(BaseScraper):
    name = "latam_pass"
    group = "aereo"
    enabled = True
    phase = 1
    accumulate = True
    chaves_dedup = ["data_captura", "programa"]

    title = "Latam Pass"
    description = "Cotação do milhar Latam Pass — calculada a partir de trechos domésticos no programa LATAM Pass."
    icon = "✈️"
    icon_class = "icon-aereo"
    badge = "Diário"
    badge_class = "badge-daily"
    tags = ["aereo", "latam", "milhas"]
    source = "Latam Pass"

    def fetch(self) -> pd.DataFrame:
        data_captura, _ = agora_brt()
        rows = []

        session = nova_session()

        try:
            resp = session.get(
                "https://www.latamairlines.com/br/pt/oferta-voos",
                params={"origin": "GRU", "destination": "CGH", "adults": 1},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            menor_milhas = 0
            if isinstance(data, dict):
                voos = data.get("itineraries", data.get("voos", []))
                if isinstance(voos, list) and voos:
                    menor_milhas = min(
                        (float(v.get("milesPrice", v.get("milhas", 0))) for v in voos if v.get("milesPrice") or v.get("milhas")),
                        default=0
                    )
        except Exception as e:
            log.warning(f"Erro ao acessar API Latam Pass: {e}")
            menor_milhas = 0

        valor_milhar = 0
        if menor_milhas > 0:
            valor_milhar = round((menor_milhas / 1000), 6)

        rows.append({
            "data_captura": data_captura,
            "programa": "Latam Pass",
            "categoria": "aereo",
            "valor_milhar": valor_milhar,
            "moeda_origem": "BRL",
            "descricao": f"Menor trecho GRU→CGH em milhas: {menor_milhas}" if menor_milhas > 0 else "Indisponível",
            "data_referencia": data_captura,
        })

        return pd.DataFrame(rows)


if __name__ == "__main__":
    LatamPassScraper().run()
