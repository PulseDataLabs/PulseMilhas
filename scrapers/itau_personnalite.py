import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from utils.base import BaseScraper, get_logger, agora_brt, nova_session

log = get_logger("itau_personnalite")


class ItauPersonnaliteScraper(BaseScraper):
    name = "itau_personnalite"
    group = "banco"
    enabled = True
    phase = 1
    accumulate = True
    chaves_dedup = ["data_captura", "programa"]

    title = "Itaú Personnalité"
    description = "Taxa de conversão de pontos Itaú Personnalité para milhas (1:1)."
    icon = "🏦"
    icon_class = "icon-banco"
    badge = "Diário"
    badge_class = "badge-daily"
    tags = ["banco", "itau", "personnalite", "pontos"]
    source = "Itaú Personnalité"

    def fetch(self) -> pd.DataFrame:
        data_captura, _ = agora_brt()
        rows = []

        session = nova_session()

        taxa_conversao = 1.0
        valor_ponto = 0.030

        try:
            resp = session.get(
                "https://www.itau.com.br/personnalite/api/programa-de-pontos",
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, dict):
                valor_ponto = float(data.get("valorPonto", data.get("pontos", {}).get("valor", 0.030)))
                taxa_conversao = float(data.get("taxaConversao", data.get("conversao", {}).get("taxa", 1.0)))
        except Exception as e:
            log.warning(f"Erro ao acessar API Itaú Personnalité: {e}")

        valor_milhar = round(valor_ponto * 1000 * taxa_conversao, 6)

        rows.append({
            "data_captura": data_captura,
            "programa": "Itaú Personnalité",
            "categoria": "banco",
            "valor_milhar": valor_milhar,
            "moeda_origem": "BRL",
            "descricao": f"Valor do ponto: R$ {valor_ponto} | Taxa conversão: {taxa_conversao}",
            "data_referencia": data_captura,
        })

        return pd.DataFrame(rows)


if __name__ == "__main__":
    ItauPersonnaliteScraper().run()
