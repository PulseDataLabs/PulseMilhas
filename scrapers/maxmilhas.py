import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import requests
from utils.base import BaseScraper, get_logger, agora_brt, nova_session

log = get_logger("maxmilhas")


class MaxmilhasScraper(BaseScraper):
    name = "maxmilhas"
    group = "marketplace"
    enabled = True
    phase = 1
    accumulate = True
    chaves_dedup = ["data_captura", "programa"]

    title = "Maxmilhas"
    description = "Preço de venda de milhas no marketplace Maxmilhas via API."
    icon = "🛒"
    icon_class = "icon-marketplace"
    badge = "Diário"
    badge_class = "badge-daily"
    tags = ["marketplace", "maxmilhas", "venda"]
    source = "Maxmilhas"

    API_BASE = "https://bff-mall.maxmilhas.com.br"
    PROGRAMS = {
        "latam": "Latam Pass",
        "gol": "Smiles",
        "azul": "TudoAzul",
    }
    QUANTIDADE = 10000

    def fetch(self) -> pd.DataFrame:
        data_captura, _ = agora_brt()
        rows = []

        session = nova_session()
        session.headers.update({
            "Origin": "https://www.maxmilhas.com.br",
            "Referer": "https://www.maxmilhas.com.br/",
        })

        for prog_id, prog_name in self.PROGRAMS.items():
            try:
                resp = session.get(
                    f"{self.API_BASE}/v2/hangar/miles/modality-card-info/{prog_id}/{self.QUANTIDADE}",
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()

                modalities = data.get("modalityCards", {}).get("conventional", [])
                recommended = next((m for m in modalities if m.get("recommended")), modalities[0] if modalities else None)

                if recommended:
                    valor_milhar = round(float(recommended["price"]), 6)
                    prazo = recommended['paymentDeadline']
                    unidade = "dia útil" if recommended.get('workingDays') else "dia"
                    descricao = (
                        f"{prog_name} — R$ {valor_milhar:.2f}/milheiro "
                        f"(recomendada: pagamento em {prazo} {unidade}{'s' if prazo > 1 else ''})"
                    )
                else:
                    valor_milhar = 0.0
                    descricao = "Indisponível (sem modalidades)"

                rows.append({
                    "data_captura": data_captura,
                    "programa": prog_name,
                    "categoria": "marketplace",
                    "valor_milhar": valor_milhar,
                    "moeda_origem": "BRL",
                    "descricao": descricao,
                    "data_referencia": data_captura,
                })

            except requests.RequestException as e:
                log.warning(f"Erro ao consultar {prog_name}: {e}")
                rows.append({
                    "data_captura": data_captura,
                    "programa": prog_name,
                    "categoria": "marketplace",
                    "valor_milhar": 0.0,
                    "moeda_origem": "BRL",
                    "descricao": f"Indisponível ({type(e).__name__})",
                    "data_referencia": data_captura,
                })

        return pd.DataFrame(rows)


if __name__ == "__main__":
    MaxmilhasScraper().run()
