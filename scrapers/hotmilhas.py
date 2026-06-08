import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from bs4 import BeautifulSoup
from utils.base import BaseScraper, get_logger, agora_brt, nova_session

log = get_logger("hotmilhas")


class HotmilhasScraper(BaseScraper):
    name = "hotmilhas"
    group = "marketplace"
    enabled = True
    phase = 1
    accumulate = True
    chaves_dedup = ["data_captura", "programa"]

    title = "Hotmilhas"
    description = "Preço de venda de milhas no marketplace Hotmilhas (média das ofertas)."
    icon = "🛒"
    icon_class = "icon-marketplace"
    badge = "Diário"
    badge_class = "badge-daily"
    tags = ["marketplace", "hotmilhas", "venda"]
    source = "Hotmilhas"

    def fetch(self) -> pd.DataFrame:
        data_captura, _ = agora_brt()
        rows = []

        session = nova_session()
        precos = []

        try:
            resp = session.get("https://www.hotmilhas.com.br/comprar-milhas", timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            for card in soup.select('[class*="card"], [class*="oferta"], [class*="milhas"]'):
                texto = card.get_text(strip=True)
                import re
                matches = re.findall(r'R?\$?\s*(\d+[.,]\d{2})', texto)
                for m in matches:
                    try:
                        valor = float(m.replace(".", "").replace(",", "."))
                        precos.append(valor)
                    except ValueError:
                        continue
        except Exception as e:
            log.warning(f"Erro ao acessar Hotmilhas: {e}")

        if precos:
            media = sum(precos) / len(precos)
            valor_milhar = round(media, 6)
        else:
            valor_milhar = 0

        rows.append({
            "data_captura": data_captura,
            "programa": "Hotmilhas",
            "categoria": "marketplace",
            "valor_milhar": valor_milhar,
            "moeda_origem": "BRL",
            "descricao": f"Média de {len(precos)} ofertas" if precos else "Indisponível",
            "data_referencia": data_captura,
        })

        return pd.DataFrame(rows)


if __name__ == "__main__":
    HotmilhasScraper().run()
