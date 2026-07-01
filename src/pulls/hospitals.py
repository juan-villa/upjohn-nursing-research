"""
hospitals.py — CMS Hospital General Information → hospital_id → MSA crosswalk.

Output: data/processed/mi_hospitals.csv
Columns: facility_id (CCN), facility_name, address, city, zip, county,
         county_fips, msa_name, cbsa.
"""
import pandas as pd
import requests, io, re
from ._common import HEADERS, PROCESSED, MI_COUNTY_TO_MSA, CBSA

URL = ("https://data.cms.gov/provider-data/sites/default/files/resources/"
       "893c372430d9d71a1c52737d01239d47_1770163599/Hospital_General_Information.csv")

# Michigan county name → county FIPS (last 3 digits of state-county fips)
COUNTY_NAME_TO_FIPS = {
    "ALCONA":"26001","ALGER":"26003","ALLEGAN":"26005","ALPENA":"26007",
    "ANTRIM":"26009","ARENAC":"26011","BARAGA":"26013","BARRY":"26015",
    "BAY":"26017","BENZIE":"26019","BERRIEN":"26021","BRANCH":"26023",
    "CALHOUN":"26025","CASS":"26027","CHARLEVOIX":"26029","CHEBOYGAN":"26031",
    "CHIPPEWA":"26033","CLARE":"26035","CLINTON":"26037","CRAWFORD":"26039",
    "DELTA":"26041","DICKINSON":"26043","EATON":"26045","EMMET":"26047",
    "GENESEE":"26049","GLADWIN":"26051","GOGEBIC":"26053","GRAND TRAVERSE":"26055",
    "GRATIOT":"26057","HILLSDALE":"26059","HOUGHTON":"26061","HURON":"26063",
    "INGHAM":"26065","IONIA":"26067","IOSCO":"26069","IRON":"26071",
    "ISABELLA":"26073","JACKSON":"26075","KALAMAZOO":"26077","KALKASKA":"26079",
    "KENT":"26081","KEWEENAW":"26083","LAKE":"26085","LAPEER":"26087",
    "LEELANAU":"26089","LENAWEE":"26091","LIVINGSTON":"26093","LUCE":"26095",
    "MACKINAC":"26097","MACOMB":"26099","MANISTEE":"26101","MARQUETTE":"26103",
    "MASON":"26105","MECOSTA":"26107","MENOMINEE":"26109","MIDLAND":"26111",
    "MISSAUKEE":"26113","MONROE":"26115","MONTCALM":"26117","MONTMORENCY":"26119",
    "MUSKEGON":"26121","NEWAYGO":"26123","OAKLAND":"26125","OCEANA":"26127",
    "OGEMAW":"26129","ONTONAGON":"26131","OSCEOLA":"26133","OSCODA":"26135",
    "OTSEGO":"26137","OTTAWA":"26139","PRESQUE ISLE":"26141","ROSCOMMON":"26143",
    "SAGINAW":"26145","ST CLAIR":"26147","ST. CLAIR":"26147","SAINT CLAIR":"26147",
    "ST JOSEPH":"26149","ST. JOSEPH":"26149","SAINT JOSEPH":"26149",
    "SANILAC":"26151","SCHOOLCRAFT":"26153","SHIAWASSEE":"26155","TUSCOLA":"26157",
    "VAN BUREN":"26159","WASHTENAW":"26161","WAYNE":"26163","WEXFORD":"26165",
}


def normalize_county(name):
    if not isinstance(name, str):
        return None
    n = name.strip().upper().replace(".", "")
    return COUNTY_NAME_TO_FIPS.get(n)


def main():
    r = requests.get(URL, headers=HEADERS, timeout=120)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), dtype=str)
    df = df[df["State"] == "MI"].copy()

    df["county_fips"] = df["County/Parish"].apply(normalize_county)
    df["msa_name"] = df["county_fips"].map(MI_COUNTY_TO_MSA)
    df["cbsa"] = df["msa_name"].map(CBSA)

    out = df[["Facility ID", "Facility Name", "Address", "City/Town",
              "ZIP Code", "County/Parish", "county_fips",
              "msa_name", "cbsa", "Hospital Type", "Hospital Ownership"]]
    out.columns = ["facility_id", "facility_name", "address", "city",
                   "zip", "county", "county_fips", "msa_name", "cbsa",
                   "hospital_type", "ownership"]
    out_path = PROCESSED / "mi_hospitals.csv"
    out.to_csv(out_path, index=False)
    print(f"Wrote {out_path}: {out.shape}")
    print(f"In MSAs: {out['msa_name'].notna().sum()} / {len(out)}")
    print(out["msa_name"].value_counts(dropna=False).head(20))


if __name__ == "__main__":
    main()
