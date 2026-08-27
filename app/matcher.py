"""
Foydalanuvchi filtri bilan kelgan xabarni solishtirish (real-time matching).
Viloyat darajasida, shahar darajasida va makro-hududlar (Vodiy, Voha)
bo'yicha to'liq moslashtiradi.
"""
import re

from app import geodata
from app.models import CargoFilter
from app.parser import ParsedCargo


def _is_wildcard(val: str | None) -> bool:
    if not val:
        return True
    norm = geodata.normalize(val)
    if not norm:
        return True
    if any(w in norm for w in ("istalgan", "barchasi", "har qanday", "hamma", "shart emas", "all", "*", "yoq", "yo'q")):
        return True
    return norm in ("-", "")


def _location_matches(filter_value: str | None, parsed_value: str | None) -> bool:
    if _is_wildcard(filter_value):
        return True
    if not parsed_value:
        return False

    fv = geodata.normalize(filter_value)
    pv = geodata.normalize(parsed_value)
    if not fv or not pv:
        return False

    # Aniq nom yoki qisman nom mosligi
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
    if _is_wildcard(filter_value):
        return True
    if not parsed_types:
        return True  # Xabarda mashina ko'rsatilmagan bo'lsa, yukni o'tkazib yubormaymiz

    fv = geodata.normalize(filter_value)
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
    if _is_wildcard(filter_value):
        return True
    if not parsed_value:
        return True  # Xabarda tonnaj yozilmagan bo'lsa, yukni o'tkazib yubormaymiz

    filter_bounds = _tonnage_bounds(filter_value)
    parsed_bounds = _tonnage_bounds(parsed_value)
    if not filter_bounds or not parsed_bounds:
        return True
    return max(filter_bounds[0], parsed_bounds[0]) <= min(filter_bounds[1], parsed_bounds[1])


def matches(cargo_filter: CargoFilter, parsed: ParsedCargo) -> bool:
    """
    Keng qamrovli va moslashuvchan moslik tekshiruvi.
    Faqat 100% qat'iy emas, balki qisman va yo'nalish bo'yicha mos yuklarni ham
    foydalanuvchiga yetkazadi.
    """
    if not parsed.is_cargo:
        return False

    orig_wild = _is_wildcard(cargo_filter.origin)
    dest_wild = _is_wildcard(cargo_filter.destination)

    # Agar ikkala yo'nalish ham wildcard bo'lsa -> barcha yuklar mos keladi
    if not (orig_wild and dest_wild):
        # 1. Qayerdan filtri
        orig_matched = orig_wild or _location_matches(cargo_filter.origin, parsed.origin) or _location_matches(cargo_filter.origin, parsed.destination)
        # 2. Qayerga filtri
        dest_matched = dest_wild or _location_matches(cargo_filter.destination, parsed.destination) or _location_matches(cargo_filter.destination, parsed.origin)

        if not orig_wild and not dest_wild:
            # Agar e'londa ikkala shahar ham bo'lsa -> ikkalasi mos bo'lishi kerak
            if parsed.origin and parsed.destination:
                if not (orig_matched and dest_matched):
                    return False
            # Agar e'londa faqat bitta shahar ko'rsatilgan bo'lsa va u mos kelsa -> mos deb olamiz
            elif parsed.origin:
                if not orig_matched:
                    return False
            elif parsed.destination:
                if not dest_matched:
                    return False
            else:
                # E'londa umuman shahar yo'q bo'lsa
                return False
        else:
            if not (orig_matched and dest_matched):
                return False

    # 3. Mashina turi filtri
    if not _is_wildcard(cargo_filter.vehicle_type):
        if parsed.vehicle_types and not _vehicle_matches(cargo_filter.vehicle_type, parsed.vehicle_types):
            return False

    # 4. Tonnaj filtri
    if not _is_wildcard(cargo_filter.tonnage):
        if parsed.tonnage and not _tonnage_matches(cargo_filter.tonnage, parsed.tonnage):
            return False

    return True
