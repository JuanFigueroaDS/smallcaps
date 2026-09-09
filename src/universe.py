"""Carga del universo de tickers a monitorear (archivo CSV simple, una columna 'ticker')."""
import csv
import logging
import os
from typing import List

log = logging.getLogger(__name__)


def load_universe(path: str) -> List[str]:
    if not os.path.exists(path):
        log.warning("No existe el archivo de universo '%s'; usando lista vacía.", path)
        return []

    tickers = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get("ticker") or "").strip().upper()
            if t and not t.startswith("#"):
                tickers.append(t)
    return sorted(set(tickers))


def save_universe(path: str, tickers: List[str]) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker"])
        for t in sorted(set(tickers)):
            writer.writerow([t])
