import csv
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

_orig_request = requests.Session.request

def _patched_request(self, method, url, *args, **kwargs):
    timeout = kwargs.get("timeout")
    if timeout is None:
        kwargs["timeout"] = (10, 30)
    elif isinstance(timeout, (int, float)):
        conn = min(timeout, 10)
        read = min(timeout, 30)
        kwargs["timeout"] = (conn, read)
    elif isinstance(timeout, tuple):
        conn, read = timeout
        conn_val = min(conn, 10) if conn is not None else 10
        read_val = min(read, 30) if read is not None else 30
        kwargs["timeout"] = (conn_val, read_val)
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            resp = _orig_request(self, method, url, *args, **kwargs)
            if resp.status_code in (502, 503, 504) and attempt < max_attempts:
                time.sleep(1.0)
                continue
            return resp
        except requests.exceptions.ConnectTimeout as e:
            raise e
        except requests.RequestException as e:
            if attempt == max_attempts:
                raise e
            time.sleep(1.0)

requests.Session.request = _patched_request

DRIFTS = []

FUSO = ZoneInfo("America/Sao_Paulo")

HEADERS_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


def get_logger(name: str) -> logging.Logger:
    try:
        from scripts.utils.ux import ColorLogger
        return ColorLogger(name)
    except Exception:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        return logging.getLogger(name)


def agora_brt() -> tuple[str, str]:
    now = datetime.now(FUSO)
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


def limpar(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def nova_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS_HTTP)
    return s


def read_existing_header(arquivo: Path) -> list[str]:
    if not arquivo.exists() or arquivo.stat().st_size == 0:
        return []
    try:
        with arquivo.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            return [col.strip() for col in header if col.strip()]
    except Exception:
        return []


def salvar_csv(
    arquivo: Path,
    registros: list[dict],
    cabecalho: list[str],
    chaves_dedup: list[str] | None = None,
    acumular: bool = True,
) -> None:
    log = get_logger("utils.salvar_csv")

    if not registros:
        log.warning("Nenhum registro para salvar — abortando.")
        sys.exit(1)

    arquivo.parent.mkdir(parents=True, exist_ok=True)

    if acumular and arquivo.exists():
        header_existente = read_existing_header(arquivo)
        merged = []
        for col in header_existente + cabecalho:
            if col and col not in merged:
                merged.append(col)
        cabecalho = merged

    datas_novas = {r.get("data_captura") for r in registros}

    chaves_novas: set[tuple] | None = None
    if chaves_dedup:
        chaves_novas = {
            tuple(r.get(c, "") for c in chaves_dedup)
            for r in registros
        }

    linhas_anteriores: list[dict] = []
    substituidas = 0

    if acumular and arquivo.exists():
        with arquivo.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for linha in reader:
                if chaves_novas is not None:
                    chave = tuple(linha.get(c, "") for c in chaves_dedup)
                    if chave in chaves_novas:
                        substituidas += 1
                        continue
                else:
                    if linha.get("data_captura") in datas_novas:
                        substituidas += 1
                        continue
                linhas_anteriores.append(linha)

    todas = linhas_anteriores + registros

    with arquivo.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cabecalho, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(todas)

    try:
        last_updates_path = arquivo.parent / "last_updates.json"
        last_updates = {}
        if last_updates_path.exists():
            try:
                with last_updates_path.open("r", encoding="utf-8") as lf:
                    last_updates = json.load(lf)
            except Exception:
                pass
        if registros:
            date_col = None
            for candidate in ["data_captura", "data_referencia", "data"]:
                if candidate in cabecalho:
                    date_col = candidate
                    break
            if date_col:
                datas = [r.get(date_col) for r in todas if r.get(date_col)]
                if datas:
                    last_updates[arquivo.name] = {
                        "min": min(datas),
                        "max": max(datas)
                    }
                    with last_updates_path.open("w", encoding="utf-8") as lf:
                        json.dump(last_updates, lf, indent=2, ensure_ascii=False)
                    last_updates_js_path = arquivo.parent / "last_updates.js"
                    with last_updates_js_path.open("w", encoding="utf-8") as lf:
                        lf.write(f"window.PULSEMILHAS_LAST_UPDATES = {json.dumps(last_updates, indent=2, ensure_ascii=False)};\n")
    except Exception as e:
        log.warning(f"Não foi possível atualizar last_updates: {e}")

    log.info(
        f"CSV atualizado → {arquivo} | "
        f"{len(registros)} novos registros salvos"
        + (f" | {substituidas} linha(s) antigas substituídas" if substituidas else "")
    )


class BaseScraper:
    name: str = ""
    accumulate: bool = True
    chaves_dedup: list[str] | None = None

    title: str = ""
    description: str = ""
    icon: str = "📊"
    icon_class: str = ""
    badge: str = ""
    badge_class: str = ""
    tags: list[str] = []
    source: str = ""

    group: str = ""
    enabled: bool = True
    phase: int = 1

    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__.lower().replace("scraper", "")
        self.logger = get_logger(self.name)
        root_dir = Path(__file__).resolve().parents[1]
        self.output_file = root_dir / "data" / f"{self.name}.csv"

    def fetch(self) -> pd.DataFrame:
        raise NotImplementedError("Cada scraper deve implementar o método fetch.")

    def run(self) -> None:
        from scripts.utils.ux import banner, print_done, print_fail

        is_pipeline = any("run_all" in str(getattr(m, "__file__", "")) for m in sys.modules.values())

        if not is_pipeline:
            banner(self.title or self.name.replace("_", " ").title())

        t0 = time.time()
        try:
            df = self.fetch()
            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                self.logger.warning("Nenhum dado retornado para salvar.")
                return

            if "data_captura" not in df.columns:
                data_captura, _ = agora_brt()
                df.insert(0, "data_captura", data_captura)

            df_cleaned = df.fillna("")

            def clean_value(val):
                if val is None or pd.isna(val):
                    return ""
                val_str = str(val).strip()
                if not val_str:
                    return ""

                match = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', val_str)
                if match:
                    d, m, y = match.groups()
                    return f"{y}-{m}-{d}"
                match_short = re.match(r'^(\d{2})/(\d{2})/(\d{2})$', val_str)
                if match_short:
                    d, m, y = match_short.groups()
                    return f"20{y}-{m}-{d}"

                if ',' in val_str and val_str.count(',') == 1:
                    clean_num = val_str.replace('.', '').replace(',', '').replace('%', '').replace('-', '').replace('+', '').strip()
                    if clean_num.isdigit():
                        parts = val_str.split(',')
                        left = parts[0].replace('.', '')
                        right = parts[1]
                        return f"{left}.{right}"

                return val_str

            for col in df_cleaned.columns:
                if pd.api.types.is_datetime64_any_dtype(df_cleaned[col]):
                    df_cleaned[col] = df_cleaned[col].dt.strftime("%Y-%m-%d")
                else:
                    df_cleaned[col] = df_cleaned[col].apply(clean_value)

            registros = df_cleaned.to_dict(orient="records")
            cabecalho = list(df_cleaned.columns)

            data_captura, _ = agora_brt()
            for r in registros:
                if "data_captura" not in r:
                    r["data_captura"] = data_captura

            if "data_captura" not in cabecalho:
                cabecalho.insert(0, "data_captura")

            salvar_csv(
                arquivo=self.output_file,
                registros=registros,
                cabecalho=cabecalho,
                chaves_dedup=self.chaves_dedup,
                acumular=self.accumulate,
            )

            elapsed = time.time() - t0
            if not is_pipeline:
                print_done(f"{len(registros)} registros salvos em {self.output_file.name}", elapsed=elapsed)

        except Exception as e:
            elapsed = time.time() - t0
            self.logger.error(f"Erro ao executar scraper {self.name}: {e}", exc_info=True)
            raise e
