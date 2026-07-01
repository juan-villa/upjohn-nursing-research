"""Shared constants and helpers for data pull modules."""
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "data" / "cache"
PROCESSED = ROOT / "data" / "processed"
CACHE.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "GSE580-Research juanmvilla09@gmail.com"}
YEARS = list(range(2011, 2025))

# Michigan MSA CBSA codes (must match build_master.py)
CBSA = {
    "Ann Arbor, MI": "11460",
    "Battle Creek, MI": "12980",
    "Bay City, MI": "13020",
    "Detroit-Warren-Dearborn, MI": "19820",
    "Flint, MI": "22420",
    "Grand Rapids-Wyoming-Kentwood, MI": "24340",
    "Jackson, MI": "27100",
    "Kalamazoo-Portage, MI": "28020",
    "Lansing-East Lansing, MI": "29620",
    "Midland, MI": "33220",
    "Monroe, MI": "33780",
    "Muskegon-Norton Shores, MI": "34740",
    "Niles, MI": "35660",
    "Saginaw, MI": "40980",
}

# Michigan county FIPS → MSA name. From OMB delineations + 2024 revisions.
# Counties not listed are nonmetro and dropped from MSA analysis.
MI_COUNTY_TO_MSA = {
    # Ann Arbor MSA
    "26161": "Ann Arbor, MI",                       # Washtenaw
    # Battle Creek MSA
    "26025": "Battle Creek, MI",                    # Calhoun
    # Bay City MSA
    "26017": "Bay City, MI",                        # Bay
    # Detroit-Warren-Dearborn MSA
    "26087": "Detroit-Warren-Dearborn, MI",         # Lapeer
    "26093": "Detroit-Warren-Dearborn, MI",         # Livingston
    "26099": "Detroit-Warren-Dearborn, MI",         # Macomb
    "26125": "Detroit-Warren-Dearborn, MI",         # Oakland
    "26147": "Detroit-Warren-Dearborn, MI",         # St. Clair
    "26163": "Detroit-Warren-Dearborn, MI",         # Wayne
    # Flint MSA
    "26049": "Flint, MI",                           # Genesee
    # Grand Rapids-Wyoming-Kentwood MSA
    "26015": "Grand Rapids-Wyoming-Kentwood, MI",   # Barry
    "26067": "Grand Rapids-Wyoming-Kentwood, MI",   # Ionia
    "26081": "Grand Rapids-Wyoming-Kentwood, MI",   # Kent
    "26117": "Grand Rapids-Wyoming-Kentwood, MI",   # Montcalm
    "26139": "Grand Rapids-Wyoming-Kentwood, MI",   # Ottawa
    # Jackson MSA
    "26075": "Jackson, MI",                         # Jackson
    # Kalamazoo-Portage MSA
    "26077": "Kalamazoo-Portage, MI",               # Kalamazoo
    # Lansing-East Lansing MSA
    "26037": "Lansing-East Lansing, MI",            # Clinton
    "26045": "Lansing-East Lansing, MI",            # Eaton
    "26065": "Lansing-East Lansing, MI",            # Ingham
    "26155": "Lansing-East Lansing, MI",            # Shiawassee
    # Midland MSA
    "26111": "Midland, MI",                         # Midland
    # Monroe MSA
    "26115": "Monroe, MI",                          # Monroe
    # Muskegon-Norton Shores MSA
    "26121": "Muskegon-Norton Shores, MI",          # Muskegon
    # Niles MSA (Berrien post-2018; Cass added in some delineations)
    "26021": "Niles, MI",                           # Berrien
    # Saginaw MSA
    "26145": "Saginaw, MI",                         # Saginaw
}


def cache_get(url, filename, timeout=600):
    """Download with cache. Returns path."""
    path = CACHE / filename
    if path.exists() and path.stat().st_size > 0:
        return path
    r = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    return path
