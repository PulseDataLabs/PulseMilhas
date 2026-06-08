#!/usr/bin/env python
"""
PulseMilhas – Orquestrador de scrapers

Uso:
  python run_all.py                              # executa todos os scrapers
  python run_all.py --group aereo                # apenas grupo aereo
  python run_all.py --group banco                # apenas grupo banco
  python run_all.py --group marketplace          # apenas grupo marketplace
  python run_all.py --scraper smiles             # apenas um scraper
  python run_all.py --sequential                 # execução sequencial
  python run_all.py --parallel --max-workers 4
  python run_all.py --generate-dashboard         # só regenera dashboard.json
"""

import argparse
import importlib
import json
import logging
import sys
import traceback
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("run_all")

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

from scripts.utils.ux import (
    USE_COLOR, IS_TTY,
    bold, dim, green, yellow, red, cyan, blue, magenta, white,
    b_green, b_yellow, b_red, b_cyan, b_white,
    _line, _progress_bar,
    GROUP_ICON, GROUP_COLOR,
)


def _banner() -> None:
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    print()
    print(_line("═"))
    print(
        bold(white("  ⚡ PulseMilhas")) +
        dim("  Pipeline de Monitoramento de Milhas")
    )
    print(dim(f"  {now}"))
    print(_line("═"))
    print()


def _section(title: str, icon: str = "▶") -> None:
    print()
    print(_line())
    print(f"  {icon}  {bold(title)}")
    print(_line())


def _scraper_start(name: str, group: str, idx: int, total: int) -> None:
    icon  = GROUP_ICON.get(group, "⬜")
    color = GROUP_COLOR.get(group, dim)
    pct   = f"{idx}/{total}"
    print(f"  {dim(pct.rjust(7))}  {icon}  {color(f'{name:<40}')} {dim('iniciando…')}")


def _scraper_done(name: str, group: str, elapsed: float, idx: int, total: int) -> None:
    icon  = GROUP_ICON.get(group, "⬜")
    color = GROUP_COLOR.get(group, dim)
    pct   = f"{idx}/{total}"
    t     = f"{elapsed:6.1f}s"
    print(f"  {dim(pct.rjust(7))}  {icon}  {color(f'{name:<40}')} {b_green('  ✔  ')}{dim(t)}")


def _scraper_fail(name: str, group: str, elapsed: float, idx: int, total: int) -> None:
    icon  = GROUP_ICON.get(group, "⬜")
    pct   = f"{idx}/{total}"
    t     = f"{elapsed:6.1f}s"
    print(f"  {dim(pct.rjust(7))}  {icon}  {b_red(f'{name:<40}')} {b_red('  ✖  ')}{dim(t)}")


def _summary_table(
    results: dict[str, tuple[bool, float, Optional[str]]],
    registry: dict[str, dict],
    total_elapsed: float,
) -> None:
    ok   = [(n, r) for n, r in results.items() if r[0]]
    fail = [(n, r) for n, r in results.items() if not r[0]]

    print()
    print(_line("═"))
    print(f"  {bold('RESUMO FINAL')}")
    print(_line("─"))

    total = len(results)
    print(
        f"  {bold('Total')}: {white(str(total))} scrapers  │  "
        + b_green(f"✔ {len(ok)} ok") + "  │  "
        + (b_red(f"✖ {len(fail)} erro(s)") if fail else dim("0 erros"))
        + "  │  "
        + cyan(f"⏱  {total_elapsed:.1f}s")
    )

    if ok:
        print()
        print(dim("  ── Sucesso " + "─" * 57))
        for name, (_, elapsed, _) in sorted(ok, key=lambda x: -x[1][1]):
            group = registry.get(name, {}).get("group", "misc")
            icon  = GROUP_ICON.get(group, "⬜")
            color = GROUP_COLOR.get(group, dim)
            print(f"    {icon}  {color(name):<50} {b_green('✔')}{dim(f'  {elapsed:5.1f}s')}")

    if fail:
        print()
        print(dim("  ── Erros " + "─" * 59))
        for name, (_, elapsed, err) in fail:
            group = registry.get(name, {}).get("group", "misc")
            icon  = GROUP_ICON.get(group, "⬜")
            print(f"    {icon}  {b_red(name):<50} {b_red('✖')}{dim(f'  {elapsed:5.1f}s')}")
            if err:
                last_line = [l for l in err.strip().splitlines() if l.strip()]
                hint = last_line[-1].strip() if last_line else ""
                if hint:
                    print(f"         {dim('↳')} {red(hint)}")

    print(_line("═"))
    print()


def discover_scrapers() -> dict[str, dict]:
    scrapers: dict[str, dict] = {}
    scrapers_dir = Path(__file__).resolve().parent / "scrapers"

    for file_path in sorted(scrapers_dir.glob("*.py")):
        module_name = file_path.stem
        if module_name in ("__init__",):
            continue
        try:
            mod = importlib.import_module(f"scrapers.{module_name}")
            class_name = "".join(w.capitalize() for w in module_name.split("_")) + "Scraper"
            if hasattr(mod, class_name):
                cls = getattr(mod, class_name)
                scrapers[module_name] = {
                    "group":      getattr(cls, "group", "misc"),
                    "enabled":    getattr(cls, "enabled", True),
                    "phase":      getattr(cls, "phase", 1),
                    "class_name": class_name,
                    "title":      getattr(cls, "title", module_name.replace("_", " ").title()),
                }
        except Exception as e:
            logger.warning(yellow(f"  ⚠  Não foi possível carregar metadados de {module_name}: {e}"))

    return scrapers


def run_scraper(module_name: str) -> tuple[bool, float, Optional[str]]:
    t0 = time.time()
    try:
        mod = importlib.import_module(f"scrapers.{module_name}")
        class_name = "".join(w.capitalize() for w in module_name.split("_")) + "Scraper"
        if hasattr(mod, class_name):
            getattr(mod, class_name)().run()
        elif hasattr(mod, "main"):
            mod.main()
        else:
            msg = f"Módulo {module_name} não possui classe {class_name} nem função main()."
            return False, time.time() - t0, msg
        return True, time.time() - t0, None
    except Exception:
        return False, time.time() - t0, traceback.format_exc()


def run_subset(
    names: list[str],
    registry: dict[str, dict],
    parallel: bool,
    max_workers: int,
    phase_label: str,
) -> dict[str, tuple[bool, float, Optional[str]]]:
    results: dict[str, tuple[bool, float, Optional[str]]] = {}
    if not names:
        return results

    total = len(names)
    _section(f"Fase {phase_label} — {total} scraper{'s' if total > 1 else ''}", "⚙")

    if parallel:
        print(f"  {dim('Modo')} {cyan('paralelo')}  {dim(f'max_workers={max_workers}')}\n")
        done_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            future_map = {ex.submit(run_scraper, n): n for n in names}
            for future in as_completed(future_map):
                name = future_map[future]
                group = registry.get(name, {}).get("group", "misc")
                done_count += 1
                try:
                    success, elapsed, err = future.result()
                except Exception:
                    success, elapsed, err = False, 0.0, traceback.format_exc()

                if success:
                    _scraper_done(name, group, elapsed, done_count, total)
                else:
                    _scraper_fail(name, group, elapsed, done_count, total)

                results[name] = (success, elapsed, err)
                print(f"  {_progress_bar(done_count, total)}", end="\r" if done_count < total else "\n")
    else:
        print(f"  {dim('Modo')} {yellow('sequencial')}\n")
        for idx, name in enumerate(names, 1):
            group = registry.get(name, {}).get("group", "misc")
            _scraper_start(name, group, idx, total)
            success, elapsed, err = run_scraper(name)
            print("\033[1A\033[2K", end="") if USE_COLOR else None
            if success:
                _scraper_done(name, group, elapsed, idx, total)
            else:
                _scraper_fail(name, group, elapsed, idx, total)
            results[name] = (success, elapsed, err)
            print(f"  {_progress_bar(idx, total)}", end="\r" if idx < total else "\n")

    return results


def save_pipeline_status(
    results: dict[str, tuple[bool, float, Optional[str]]],
    total_elapsed: float,
) -> None:
    root_dir = Path(__file__).resolve().parent
    status_path = root_dir / "data" / "pipeline_status.json"
    status_js_path = root_dir / "data" / "pipeline_status.js"
    scrapers_registry = discover_scrapers()
    active_scrapers = {k: v for k, v in scrapers_registry.items() if v["enabled"]}

    status_data: dict = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": total_elapsed,
        "status": "success",
        "summary": {"total": 0, "success": 0, "failed": 0, "drifts": 0},
        "scrapers": {},
        "drifts": {},
    }

    if status_path.exists():
        try:
            with status_path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded.get("scrapers"), dict):
                status_data["scrapers"] = loaded["scrapers"]
        except Exception as e:
            logger.warning(yellow(f"  ⚠  Não foi possível carregar status anterior: {e}"))

    now_iso = datetime.now().isoformat()
    for name, (success, elapsed, err) in results.items():
        status_data["scrapers"][name] = {
            "status": "success" if success else "error",
            "elapsed_seconds": elapsed,
            "error": err,
            "timestamp": now_iso,
        }

    for name in active_scrapers:
        if name not in status_data["scrapers"]:
            status_data["scrapers"][name] = {
                "status": "unknown", "elapsed_seconds": 0.0,
                "error": None, "timestamp": None,
            }

    ok_cnt = sum(1 for s in status_data["scrapers"].values() if s["status"] == "success")
    fail_cnt = sum(1 for s in status_data["scrapers"].values() if s["status"] == "error")
    status_data["summary"] = {
        "total": len(active_scrapers),
        "success": ok_cnt,
        "failed": fail_cnt,
        "drifts": 0,
    }
    status_data["status"] = "error" if fail_cnt > 0 else "success"

    try:
        status_path.parent.mkdir(parents=True, exist_ok=True)
        with status_path.open("w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
        with status_js_path.open("w", encoding="utf-8") as f:
            f.write(f"window.PULSEMILHAS_PIPELINE_STATUS = {json.dumps(status_data, indent=2, ensure_ascii=False)};\n")
        print(f"  {dim('📄 pipeline_status.json atualizado')}")
    except Exception as e:
        logger.error(red(f"  ✖  Erro ao salvar status do pipeline: {e}"))


def list_scrapers(registry: dict[str, dict]) -> None:
    _section("Scrapers disponíveis", "📋")
    by_group: dict[str, list] = {}
    for name, info in sorted(registry.items()):
        by_group.setdefault(info["group"], []).append((name, info))

    for group, items in sorted(by_group.items()):
        icon  = GROUP_ICON.get(group, "⬜")
        color = GROUP_COLOR.get(group, dim)
        print(f"\n  {icon}  {bold(color(group.upper()))}")
        for name, info in items:
            enabled_marker = green("●") if info["enabled"] else dim("○")
            print(f"    {enabled_marker}  {color(name):<42} {dim(info.get('title', ''))}")
    print()


def main(
    group: Optional[str] = None,
    scraper: Optional[str] = None,
    parallel: bool = True,
    max_workers: int = 4,
    list_only: bool = False,
) -> None:
    _banner()
    t0 = time.time()
    registry = discover_scrapers()

    if list_only:
        list_scrapers(registry)
        return

    if scraper:
        if scraper not in registry:
            print(b_red(f"  ✖  Scraper '{scraper}' não encontrado."))
            sys.exit(1)
        targets = {scraper: registry[scraper]}
    else:
        targets = {
            n: info for n, info in registry.items()
            if info["enabled"] and (group is None or info["group"] == group)
        }

    if not targets:
        msg = f"grupo='{group}'" if group else "critério informado"
        print(b_red(f"  ✖  Nenhum scraper encontrado para {msg}."))
        sys.exit(1)

    targets_list = sorted(targets.keys())

    results: dict[str, tuple[bool, float, Optional[str]]] = {}

    if targets_list:
        results.update(run_subset(targets_list, registry, parallel, max_workers, "1"))

    total_elapsed = time.time() - t0

    _section("Pós-processamento", "💾")
    save_pipeline_status(results, total_elapsed)

    if not group and not scraper:
        try:
            from scripts.generate_dashboard import generate
            generate()
            print(f"  {dim('📊 dashboard.json regenerado')}")
        except Exception as e:
            print(yellow(f"  ⚠  Não foi possível regenerar dashboard: {e}"))

    _summary_table(results, registry, total_elapsed)

    if any(not r[0] for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    registry = discover_scrapers()
    available_groups = sorted({i["group"] for i in registry.values() if i["enabled"]})
    available_scrapers = sorted(registry.keys())

    parser = argparse.ArgumentParser(
        description="⚡ PulseMilhas – Orquestrador de scrapers de milhas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--group", choices=available_groups, metavar="GRUPO", help="Filtra por grupo de scrapers")
    parser.add_argument("--scraper", choices=available_scrapers, metavar="SCRAPER", help="Executa um scraper específico")
    parser.add_argument("--parallel", action="store_true", default=True, help="Execução paralela (padrão)")
    parser.add_argument("--sequential", action="store_false", dest="parallel", help="Execução sequencial")
    parser.add_argument("--max-workers", type=int, default=4, metavar="N", help="Threads para modo paralelo")
    parser.add_argument("--list", action="store_true", help="Lista todos os scrapers disponíveis e sai")
    parser.add_argument("--generate-dashboard", action="store_true", help="Regenera dashboard.json e sai")

    args = parser.parse_args()

    if args.generate_dashboard:
        _banner()
        _section("Gerando dashboard", "📊")
        from scripts.generate_dashboard import generate
        generate()
        print(b_green("\n  ✔  dashboard.json atualizado com sucesso.\n"))
        sys.exit(0)

    main(
        group=args.group,
        scraper=args.scraper,
        parallel=args.parallel,
        max_workers=args.max_workers,
        list_only=args.list,
    )
