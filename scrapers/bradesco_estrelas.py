import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from utils.base import BaseScraper, get_logger, agora_brt, nova_session

log = get_logger("bradesco_estrelas")


class BradescoEstrelasScraper(BaseScraper):
    name = "bradesco_estrelas"
    group = "banco"
    enabled = True
    phase = 1
    accumulate = True
    chaves_dedup = ["data_captura", "programa"]

    title = "Bradesco Estrelas"
    description = "Taxa de conversão do programa Bradesco Estrelas para milhas."
    icon = "🏦"
    icon_class = "icon-banco"
    badge = "Diário"
    badge_class = "badge-daily"
    tags = ["banco", "bradesco", "estrelas", "pontos"]
    source = "Bradesco Estrelas"

    def fetch(self) -> pd.DataFrame:
        data_captura, _ = agora_brt()
        rows = []

        session = nova_session()

        valor_estrela = 0.025

        try:
            resp = session.get(
                "https://banco.bradesco/api/estrelas/cotacao",
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, dict):
                valor_estrela = float(data.get("valor", data.get("cotacao", {}).get("valor", 0.025)))
        except Exception as e:
            log.warning(f"Erro ao acessar API Bradesco Estrelas: {e}")

        valor_milhar = round(valor_estrela * 1000, 6)

        rows.append({
            "data_captura": data_captura,
            "programa": "Bradesco Estrelas",
            "categoria": "banco",
            "valor_milhar": valor_milhar,
            "moeda_origem": "BRL",
            "descricao": f"Valor da estrela: R$ {valor_estrela}",
            "data_referencia": data_captura,
        })

        return pd.DataFrame(rows)


if __name__ == "__main__":
    BradescoEstrelasScraper().run()
