"""
Feature I: Геолокация для доставки
- Клиент вводит адрес текстом
- Менеджер получает адрес + ссылку на Яндекс.Карты (геокодирование на сервере)
- Настройки провайдера геокодирования в админ-панели
"""
import logging
import urllib.parse
import aiohttp

from database.db import db

logger = logging.getLogger(__name__)

# Router не нужен — этот модуль только утилиты + экспортируемые функции
router = None


def yandex_maps_search_link(address: str) -> str:
    """Ссылка на Яндекс.Карты с текстовым поиском."""
    encoded = urllib.parse.quote(address)
    return f"https://yandex.ru/maps/?text={encoded}"


async def geocode_address_yandex(address: str, api_key: str):
    """Прямое геокодирование: адрес → (lat, lon) через Яндекс.Геокодер."""
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": api_key,
        "geocode": address,
        "format": "json",
        "results": 1,
        "lang": "ru_RU",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params,
                                   timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    members = (data.get("response", {})
                               .get("GeoObjectCollection", {})
                               .get("featureMember", []))
                    if members:
                        pos = (members[0].get("GeoObject", {})
                               .get("Point", {})
                               .get("pos", ""))
                        if pos:
                            lon_str, lat_str = pos.split()
                            return float(lat_str), float(lon_str)
    except Exception as e:
        logger.warning(f"Yandex geocode error: {e}")
    return None, None


async def geocode_address_osm(address: str):
    """Прямое геокодирование: адрес → (lat, lon) через OSM Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1, "accept-language": "ru"}
    headers = {"User-Agent": "AioBot-Delivery/1.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    results = await resp.json()
                    if results:
                        return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        logger.warning(f"OSM geocode error: {e}")
    return None, None


async def get_maps_link(address: str) -> str:
    """
    Основная функция. Возвращает ссылку на Яндекс.Карты для адреса.
    Если геокодирование включено и удалось — ссылка с точкой на карте.
    Иначе — ссылка с текстовым поиском (всегда работает без API).
    """
    geo_enabled = await db.get_setting("geo_enabled")
    if geo_enabled == "1":
        provider = await db.get_setting("geo_provider") or "osm"
        lat, lon = None, None

        if provider == "yandex":
            api_key = await db.get_setting("geo_yandex_key") or ""
            if api_key:
                lat, lon = await geocode_address_yandex(address, api_key)

        if lat is None:
            lat, lon = await geocode_address_osm(address)

        if lat is not None and lon is not None:
            encoded = urllib.parse.quote(address)
            return (f"https://yandex.ru/maps/?ll={lon},{lat}&z=17"
                    f"&pt={lon},{lat}&text={encoded}")

    # Fallback — текстовый поиск, работает без координат
    return yandex_maps_search_link(address)
