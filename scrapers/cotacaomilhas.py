import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from bs4 import BeautifulSoup
from utils.base import BaseScraper, get_logger, agora_brt, nova_session

log = get_logger("cotacaomilhas")


class CotacaomilhasScraper(BaseScraper):
    name = "cotacaomilhas"
    group = "marketplace"
    enabled = True
    phase = 1
    accumulate = True
    chaves_dedup = ["data_captura", "programa"]

    title = "Cotação Milhas"
    description = "Cotações do aggregador cotacaomilhas.com.br — preço de venda do milheiro nos principais programas."
    icon = "🛒"
    icon_class = "icon-marketplace"
    badge = "Diário"
    badge_class = "badge-daily"
    tags = ["marketplace", "cotacaomilhas", "venda", "milheiro"]
    source = "Cotação Milhas"

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

        try:
            resp = session.get("https://cotacaomilhas.com.br/", timeout=20)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            for card in soup.find_all("div", class_="cotacao-card"):
                prog = card.get("data-programa", "").strip()
                if not prog:
                    continue

                price_el = card.find("span", class_="valor-real")
                if not price_el:
                    continue

                price_raw = price_el.get_text(strip=True)
                valor_milhar = self.parse_price(price_raw)

                h3 = card.find("h3")
                prog_name = h3.get_text(strip=True) if h3 else prog

                subtitle_el = card.find("p")
                airline = subtitle_el.get_text(strip=True) if subtitle_el else ""

                rows.append({
                    "data_captura": data_captura,
                    "programa": prog_name,
                    "categoria": "marketplace",
                    "valor_milhar": valor_milhar,
                    "moeda_origem": "BRL",
                    "descricao": f"{prog} ({airline}) — {price_raw}/milheiro" if airline else f"{prog} — {price_raw}/milheiro",
                    "data_referencia": data_captura,
                })
        except Exception as e:
            log.warning(f"Erro ao acessar cotacaomilhas.com.br: {e}")

        if not rows:
            rows.append({
                "data_captura": data_captura,
                "programa": "Cotação Milhas",
                "categoria": "marketplace",
                "valor_milhar": 0.0,
                "moeda_origem": "BRL",
                "descricao": "Indisponível",
                "data_referencia": data_captura,
            })

        return pd.DataFrame(rows)


if __name__ == "__main__":
    CotacaomilhasScraper().run()
