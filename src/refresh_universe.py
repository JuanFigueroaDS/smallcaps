"""Herramienta opcional para (re)construir universe.csv automáticamente.

Descarga la lista de acciones comunes listadas en EE.UU. desde Finnhub y
verifica el market cap de cada una, quedándose solo con las que caen en el
rango configurado (MARKET_CAP_MIN - MARKET_CAP_MAX). Usa la misma cache de
market cap que el scanner para no repetir llamadas.

Pensado para correr 1 vez al día (workflow separado, más lento). Por el
límite de 60 llamadas/min de Finnhub, cada corrida solo procesa hasta
MAX_CALLS_PER_RUN símbolos nuevos; con varias corridas diarias el universo
se va completando y refrescando solo.

Uso:
    python -m src.refresh_universe
"""
import logging
import os
import sys
import time
from typing import List

import requests

from . import config, state, universe

log = logging.getLogger("refresh_universe")

FINNHUB_SYMBOLS_URL = "https://finnhub.io/api/v1/stock/symbol"
MAX_CALLS_PER_RUN = int(os.environ.get("MAX_CALLS_PER_RUN", "1500"))
CALLS_PER_SECOND = 0.9  # deja margen bajo el límite de 60/min de Finnhub


def _fetch_all_us_common_symbols() -> List[str]:
    params = {"exchange": "US", "token": config.FINNHUB_API_KEY}
    try:
        resp = requests.get(FINNHUB_SYMBOLS_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        log.error("No se pudo bajar la lista de símbolos de Finnhub: %s", e)
        return []

    symbols = []
    for row in data:
        if row.get("type") == "Common Stock" and row.get("symbol"):
            sym = row["symbol"]
            if "." in sym or "-" in sym:
                continue  # evita clases especiales / warrants para simplificar
            symbols.append(sym.upper())
    return sorted(set(symbols))


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if not config.FINNHUB_API_KEY:
        log.error("Configura FINNHUB_API_KEY para poder refrescar el universo.")
        return 1

    all_symbols = _fetch_all_us_common_symbols()
    if not all_symbols:
        return 1
    log.info("Símbolos comunes de EE.UU. encontrados: %d", len(all_symbols))

    cache = state.load_json(config.MARKET_CAP_CACHE_FILE)
    now = time.time()
    fresh_cutoff = config.MARKET_CAP_CACHE_HOURS * 3600

    pending = [s for s in all_symbols if now - cache.get(s, {}).get("fetched_at", 0) > fresh_cutoff]
    log.info("Pendientes de refrescar market cap: %d (se procesan hasta %d esta corrida)",
              len(pending), MAX_CALLS_PER_RUN)

    processed = 0
    for sym in pending:
        if processed >= MAX_CALLS_PER_RUN:
            break
        info = None
        try:
            import importlib
            providers = importlib.import_module(".providers", package=__package__)
            info = providers.fetch_finnhub_market_cap(sym)
        except Exception as e:  # defensivo: un símbolo raro no debe tumbar el batch
            log.debug("Error consultando %s: %s", sym, e)
        if info is not None:
            info["fetched_at"] = now
            cache[sym] = info
        processed += 1
        time.sleep(1.0 / CALLS_PER_SECOND)

    state.save_json(config.MARKET_CAP_CACHE_FILE, cache)

    in_range = [
        sym for sym, info in cache.items()
        if info.get("market_cap") and config.MARKET_CAP_MIN <= info["market_cap"] <= config.MARKET_CAP_MAX
    ]
    universe.save_universe(config.UNIVERSE_FILE, in_range)
    log.info("universe.csv actualizado con %d tickers en rango $%.0fM-$%.0fM",
              len(in_range), config.MARKET_CAP_MIN / 1e6, config.MARKET_CAP_MAX / 1e6)
    return 0


if __name__ == "__main__":
    sys.exit(run())
