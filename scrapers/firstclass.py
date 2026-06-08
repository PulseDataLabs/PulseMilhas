import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from bs4 import BeautifulSoup
from utils.base import BaseScraper, get_logger, agora_brt, nova_session

log = get_logger("firstclass")


class FirstclassScraper(BaseScraper):
    name = "firstclass"
    group = "marketplace"
    enabled = True
    phase = 1
    accumulate = True
    chaves_dedup = ["data_captura", "programa"]

    title = "FirstClass Milhas"
    description = "Cotações do firstclassmilhas.com.br — valor do milheiro Latam, Smiles e Azul."
    icon = "🛒"
    icon_class = "icon-marketplace"
    badge = "Diário"
    badge_class = "badge-daily"
    tags = ["marketplace", "firstclass", "milheiro"]
    source = "FirstClass Milhas"

    PAGINAS = [
        ("Latam Pass",  "https://firstclassmilhas.com.br/valor-milheiro-latam-calculadora/"),
        ("Smiles",      "https://firstclassmilhas.com.br/valor-milheiro-smiles-calculadora/"),
        ("TudoAzul",    "https://firstclassmilhas.com.br/valor-milheiro-azul-calculadora/"),
    ]

    def parse_price(self, raw: str) -> float:
        clean = raw.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        try:
            return round(float(clean), 6)
        except ValueError:
            return 0.0

    def fetch(self) -> pd.DataFrame:
        data_captura, _ = agora_brt()
        rows = []

        session = nova_session()

        for programa, url in self.PAGINAS:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "html.parser")

                price_el = soup.find("h4", class_="elementor-heading-title")
                if not price_el:
                    log.warning(f"Preço não encontrado em {url}")
                    continue

                price_raw = price_el.get_text(strip=True)
                valor_milhar = self.parse_price(price_raw)

                if valor_milhar <= 0:
                    log.warning(f"Preço inválido em {url}: {price_raw}")
                    continue

                rows.append({
                    "data_captura": data_captura,
                    "programa": programa,
                    "categoria": "marketplace",
                    "valor_milhar": valor_milhar,
                    "moeda_origem": "BRL",
                    "descricao": f"{programa} — {price_raw}/milheiro",
                    "data_referencia": data_captura,
                })

            except Exception as e:
                log.warning(f"Erro ao acessar {url}: {e}")
                rows.append({
                    "data_captura": data_captura,
                    "programa": programa,
                    "categoria": "marketplace",
                    "valor_milhar": 0.0,
                    "moeda_origem": "BRL",
                    "descricao": "Indisponível",
                    "data_referencia": data_captura,
                })

        if not rows:
            rows.append({
                "data_captura": data_captura,
                "programa": "FirstClass",
                "categoria": "marketplace",
                "valor_milhar": 0.0,
                "moeda_origem": "BRL",
                "descricao": "Indisponível",
                "data_referencia": data_captura,
            })

        return pd.DataFrame(rows)


if __name__ == "__main__":
    FirstclassScraper().run()
