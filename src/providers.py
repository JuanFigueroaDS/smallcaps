"""Wrappers de las APIs externas: Alpha Vantage (NEWS_SENTIMENT) y Finnhub
(company-news + profile2 para market cap)."""
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from . import config

log = logging.getLogger(__name__)

AV_URL = "https://www.alphavantage.co/query"
FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"
FINNHUB_PROFILE_URL = "https://finnhub.io/api/v1/stock/profile2"


def _get(url: str, params: Dict[str, Any], timeout: int = 20) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code != 200:
            log.warning("GET %s -> %s: %s", url, resp.status_code, resp.text[:200])
            return None
        return resp.json()
    except requests.RequestException as e:
        log.warning("Error de red llamando a %s: %s", url, e)
        return None
    except ValueError:
        log.warning("Respuesta no-JSON de %s", url)
        return None


def fetch_alphavantage_news(lookback_minutes: int) -> List[Dict[str, Any]]:
    """Trae noticias etiquetadas por tema (catalizadores) desde Alpha Vantage.

    Cada item devuelto incluye 'ticker_sentiment': lista de {ticker, relevance_score,
    ticker_sentiment_label}. Ojo: el free tier de Alpha Vantage tiene una cuota diaria
    baja (revisa el README) — si se agota, esta función simplemente devuelve [].
    """
    if not config.ALPHAVANTAGE_API_KEY:
        log.info("ALPHAVANTAGE_API_KEY no configurada; se omite esta fuente.")
        return []

    time_from = (datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)).strftime("%Y%m%dT%H%M")
    params = {
        "function": "NEWS_SENTIMENT",
        "topics": config.AV_TOPICS,
        "time_from": time_from,
        "sort": "LATEST",
        "limit": 200,
        "apikey": config.ALPHAVANTAGE_API_KEY,
    }
    data = _get(AV_URL, params)
    if not data:
        return []

    if "Note" in data or "Information" in data:
        # Mensajes típicos de rate-limit / cuota agotada.
        log.warning("Alpha Vantage: %s", data.get("Note") or data.get("Information"))
        return []

    return data.get("feed", [])


def fetch_finnhub_company_news(ticker: str, lookback_minutes: int) -> List[Dict[str, Any]]:
    """Noticias específicas de un ticker vía Finnhub (requiere símbolo conocido)."""
    if not config.FINNHUB_API_KEY:
        return []

    today = datetime.now(timezone.utc).date()
    from_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    params = {
        "symbol": ticker,
        "from": from_date.isoformat(),
        "to": today.isoformat(),
        "token": config.FINNHUB_API_KEY,
    }
    data = _get(FINNHUB_NEWS_URL, params)
    if not data:
        return []

    cutoff = time.time() - lookback_minutes * 60
    recent = [item for item in data if item.get("datetime", 0) >= cutoff]
    return recent


def fetch_finnhub_market_cap(ticker: str) -> Optional[Dict[str, Any]]:
    """Devuelve {'market_cap': float_en_usd, 'name': str} o None si falla."""
    if not config.FINNHUB_API_KEY:
        return None

    params = {"symbol": ticker, "token": config.FINNHUB_API_KEY}
    data = _get(FINNHUB_PROFILE_URL, params)
    if not data or "marketCapitalization" not in data:
        return None

    # Finnhub devuelve marketCapitalization en millones de USD.
    try:
        cap_millions = float(data["marketCapitalization"])
    except (TypeError, ValueError):
        return None

    return {
        "market_cap": cap_millions * 1_000_000,
        "name": data.get("name", ticker),
    }
