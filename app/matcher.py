"""
Foydalanuvchi filtri bilan kelgan xabarni solishtirish (real-time matching).
Viloyat darajasida, shahar darajasida va makro-hududlar (Vodiy, Voha)
bo'yicha to'liq moslashtiradi.
"""
import re

from app import geodata
from app.models import CargoFilter
from app.parser import ParsedCargo


def _location_matches(filter_value: str | None, parsed_value: str | None) -> bool:
    if not filter_value:
        return True
    fv = geodata.normalize(filter_value)
    if not fv or fv in ("istalgan", "barchasi", "har qanday", "hamma", "all", "*", "-", "shart emas"):
        return True

    if not parsed_value:
        return False
    pv = geodata.normalize(parsed_value)
    if not pv:
        return False

    # Aniq nom mosligi
    if fv == pv or fv in pv or pv in fv:
        return True

    region_f = geodata.region_of(fv)
    region_p = geodata.region_of(pv)
    if not region_f or not region_p:
        return False

    # Bir xil viloyat
    if region_f == region_p:
        return True

    # Makro-hudud tekshiruvi (masalan, filtrda 'vodiy' tanlangan bo'lsa)
    if region_f in geodata.MACRO_REGIONS and region_p in geodata.MACRO_REGIONS[region_f]:
        return True
    if region_p in geodata.MACRO_REGIONS and region_f in geodata.MACRO_REGIONS[region_p]:
        return True

    return False


def _vehicle_matches(filter_value: str | None, parsed_types: list[str]) -> bool:
    if not filter_value:
        return True
    fv = geodata.normalize(filter_value)
    if not fv or fv in ("istalgan", "barchasi", "har qanday", "hamma", "shart emas", "-", "all"):
        return True
    if not parsed_types:
        return True  # Xabarda mashina turi yozilmagan bo'lsa, yukni o'tkazib yubormaymiz

    return any(fv in geodata.normalize(pt) or geodata.normalize(pt) in fv for pt in parsed_types)


def _tonnage_bounds(value: str | None) -> tuple[float, float] | None:
    """`20 tonna` yoki `20-24 tonna` qiymatini son oralig'iga aylantiradi."""
    if not value:
        return None
    numbers = [float(item.replace(",", ".")) for item in re.findall(r"\d+(?:[.,]\d+)?", value)]
    if not numbers:
        return None
    return min(numbers), max(numbers)


def _tonnage_matches(filter_value: str | None, parsed_value: str | None) -> bool:
    if not filter_value or geodata.normalize(filter_value) in ("istalgan", "barchasi", "har qanday", "shart emas", "-", "all"):
        return True
    filter_bounds = _tonnage_bounds(filter_value)
    parsed_bounds = _tonnage_bounds(parsed_value)
    if not filter_bounds or not parsed_bounds:
        return True
    return max(filter_bounds[0], parsed_bounds[0]) <= min(filter_bounds[1], parsed_bounds[1])


def matches(cargo_filter: CargoFilter, parsed: ParsedCargo) -> bool:
    """True qaytaradi, agar parsed xabar shu filtrga mos kelsa."""
    # Kamida bitta yo'nalish yoki yuk signali bo'lishi kerak
    if not parsed.is_cargo:
        return False

    if cargo_filter.origin and not _location_matches(cargo_filter.origin, parsed.origin):
        return False
    if cargo_filter.destination and not _location_matches(cargo_filter.destination, parsed.destination):
        return False
    if not _vehicle_matches(cargo_filter.vehicle_type, parsed.vehicle_types):
        return False
    if not _tonnage_matches(cargo_filter.tonnage, parsed.tonnage):
        return False

    return True
