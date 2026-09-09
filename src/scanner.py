"""Scanner de noticias de small caps.

Flujo por cada corrida:
  1. Trae noticias "catalizadoras" de Alpha Vantage (ya vienen etiquetadas por topic).
  2. Trae noticias por ticker desde Finnhub para el universo de small caps vigilado
     (universe.csv), filtrando por palabras clave de catalizador.
  3. Para cada candidato, valida market cap ($50M-$2B por defecto) vía Finnhub,
     usando una cache local para no golpear la API en cada corrida.
  4. Deduplica contra el estado local y envía lo nuevo a Telegram.

Pensado para correr cada ~5 minutos vía GitHub Actions (ver README).
"""
import hashlib
import logging
import re
import sys
import time
from typing import Any, Dict, List, Optional

from . import config, providers, state, telegram_notifier, universe

log = logging.getLogger("scanner")

NON_EQUITY_PREFIXES = ("FOREX:", "CRYPTO:")


def _dedup_key(ticker: str, url: str) -> str:
    return hashlib.sha256(f"{ticker}|{url}".encode("utf-8")).hexdigest()


def _normalize_av_ticker(raw: str) -> Optional[str]:
    if raw.startswith(NON_EQUITY_PREFIXES):
        return None
    if ":" in raw:
        raw = raw.split(":")[-1]
    return raw.strip().upper() or None


def _match_keywords(text: str) -> List[str]:
    text_l = text.lower()
    return [kw for kw in config.CATALYST_KEYWORDS if kw in text_l]


AV_CATALYST_TOPICS = {"mergers_and_acquisitions", "earnings", "ipo", "life_sciences"}


def _av_candidates(lookback_minutes: int) -> List[Dict[str, Any]]:
    candidates = []
    articles = providers.fetch_alphavantage_news(lookback_minutes)
    for art in articles:
        title = art.get("title", "")
        summary = art.get("summary", "")
        url = art.get("url", "")
        source = art.get("source", "Alpha Vantage")
        topics = {t.get("topic") for t in art.get("topics", []) if t.get("topic")}
        matched_topics = list(topics & AV_CATALYST_TOPICS)
        keyword_hits = _match_keywords(f"{title} {summary}")
        tags = matched_topics or keyword_hits
        if not tags:
            continue

        for ts in art.get("ticker_sentiment", []):
            raw_ticker = ts.get("ticker", "")
            try:
                relevance = float(ts.get("relevance_score", 0))
            except (TypeError, ValueError):
                relevance = 0.0
            if relevance < config.AV_MIN_RELEVANCE:
                continue
            ticker = _normalize_av_ticker(raw_ticker)
            if not ticker:
                continue
            candidates.append({
                "ticker": ticker,
                "headline": title,
                "url": url,
                "source": source,
                "tags": tags,
                "sentiment": ts.get("ticker_sentiment_label", ""),
            })
    return candidates


def _finnhub_candidates(tickers: List[str], lookback_minutes: int) -> List[Dict[str, Any]]:
    candidates = []
    for ticker in tickers:
        items = providers.fetch_finnhub_company_news(ticker, lookback_minutes)
        for item in items:
            text = f"{item.get('headline', '')} {item.get('summary', '')}"
            tags = _match_keywords(text)
            if not tags:
                continue
            candidates.append({
                "ticker": ticker,
                "headline": item.get("headline", ""),
                "url": item.get("url", ""),
                "source": item.get("source", "Finnhub"),
                "tags": tags,
                "sentiment": "",
            })
        # Pequeña pausa para respetar el límite de 60 req/min de Finnhub.
        time.sleep(0.3)
    return candidates


def _get_market_cap(ticker: str, cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cached = cache.get(ticker)
    if cached and (time.time() - cached.get("fetched_at", 0)) < config.MARKET_CAP_CACHE_HOURS * 3600:
        return cached

    info = providers.fetch_finnhub_market_cap(ticker)
    if info is None:
        return None

    info["fetched_at"] = time.time()
    cache[ticker] = info
    return info


def run() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.error("Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID antes de correr el scanner.")
        return 1

    tickers = universe.load_universe(config.UNIVERSE_FILE)
    log.info("Universo vigilado: %d tickers", len(tickers))

    seen = state.load_json(config.STATE_FILE)
    cap_cache = state.load_json(config.MARKET_CAP_CACHE_FILE)

    candidates = []
    candidates.extend(_av_candidates(config.LOOKBACK_MINUTES))
    candidates.extend(_finnhub_candidates(tickers, config.LOOKBACK_MINUTES))
    log.info("Candidatos con catalizador detectado (antes de filtrar por market cap/dedup): %d", len(candidates))

    sent = 0
    for c in candidates:
        if not c["url"]:
            continue
        key = _dedup_key(c["ticker"], c["url"])
        if key in seen:
            continue

        cap_info = _get_market_cap(c["ticker"], cap_cache)
        if cap_info is None:
            log.info("Sin market cap para %s (símbolo inválido o Finnhub sin datos); se omite.", c["ticker"])
            seen[key] = time.time()
            continue

        market_cap = cap_info["market_cap"]
        if not (config.MARKET_CAP_MIN <= market_cap <= config.MARKET_CAP_MAX):
            seen[key] = time.time()  # no re-evaluar este mismo artículo
            continue

        message = telegram_notifier.format_alert(
            ticker=c["ticker"],
            company=cap_info.get("name", c["ticker"]),
            market_cap=market_cap,
            headline=c["headline"],
            url=c["url"],
            source=c["source"],
            catalyst_tags=c["tags"],
            sentiment=c.get("sentiment", ""),
        )
        ok = telegram_notifier.send_message(message)
        seen[key] = time.time()
        if ok:
            sent += 1
            log.info("Alerta enviada: %s — %s", c["ticker"], c["headline"][:80])
        else:
            log.warning("No se pudo enviar la alerta de %s a Telegram.", c["ticker"])

    seen = state.prune_seen(seen, config.STATE_RETENTION_HOURS)
    cap_cache = state.prune_cache(cap_cache, config.MARKET_CAP_CACHE_HOURS * 3)
    state.save_json(config.STATE_FILE, seen)
    state.save_json(config.MARKET_CAP_CACHE_FILE, cap_cache)

    log.info("Corrida completa. Alertas enviadas: %d", sent)
    return 0


if __name__ == "__main__":
    sys.exit(run())
