from __future__ import annotations

import io
import json
import re
import time
from datetime import date
from pathlib import Path

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "kdb_public_snapshot.json"
JULY_URL = "https://www.kdb.co.kr/wcmscontents/pdf/KDB_Investor_Presentation_July_2025.pdf"
DEC_URL = "https://www.kdb.co.kr/wcmscontents/pdf/IR_Presentation_2025.pdf"
USER_AGENT = "Banking-RM/0.9 rm-intelligence"


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def pdf_pages(url: str) -> list[str]:
    last_exc = None
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages]
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise last_exc


def source(name: str, url: str, page: int, section: str, reporting_period: str, publication_period: str) -> dict:
    return {"source_name": name, "source_url": url, "source_kind": "investor_presentation", "publication_period": publication_period, "reporting_period": reporting_period, "page": page, "section": section}


def parse_business_framework(page: str) -> dict:
    t = compact(page)
    if "Basic Framework of KDB’s Business Operations" not in t and "Basic Framework of KDB's Business Operations" not in t:
        return {}
    patterns = {
        "wholesale_funding_pct": (68.0, r"68% of funding through wholesale funding"),
        "foreign_currency_industrial_bonds_pct": (17.0, r"17%.*?Industrial.*?Finance.*?Bonds.*?Foreign.*?Currencies"),
        "krw_industrial_bonds_pct": (40.0, r"40%.*?Industrial.*?Finance.*?Bonds.*?KRW"),
        "krw_deposits_pct": (16.0, r"16%.*?Deposits.*?KRW"),
        "foreign_currency_deposits_pct": (6.0, r"6%.*?Deposits.*?Foreign.*?Currencies"),
        "borrowings_pct": (11.0, r"11%.*?Borrowings"),
        "manufacturing_exposure_pct": (45.3, r"45\.3%.*?Manufacturing"),
        "finance_insurance_exposure_pct": (24.4, r"24\.4%.*?Finance.*?Insurance"),
        "transportation_exposure_pct": (6.6, r"6\.6%.*?Transportation"),
        "utilities_exposure_pct": (3.5, r"3\.5%.*?Electric.*?Gas.*?Water.*?Supply"),
        "public_admin_exposure_pct": (0.5, r"Public Administration.*?0\.5%"),
        "other_sector_exposure_pct": (19.7, r"19\.7%.*?Others"),
    }
    return {k: v for k, (v, pat) in patterns.items() if re.search(pat, t, re.I)}


def parse_dec_funding_strategy(page: str) -> dict:
    t = compact(page)
    if "KDB’s Funding Strategy" not in t and "KDB's Funding Strategy" not in t:
        return {}
    out = {}
    if re.search(r"typically 2-3 benchmark USD\s*/\s*EUR bonds annually", t, re.I):
        out["benchmark_bonds_per_year_min"] = 2; out["benchmark_bonds_per_year_max"] = 3
    if re.search(r"relationship-based loans.*?reliable backstop funding source", t, re.I): out["bank_loans_as_backstop"] = True
    return out


def parse_dec_track_record(page: str) -> dict:
    """Keep only explicitly labelled track-record facts.

    The chart's historical bars are intentionally not converted into annual values because
    PDF text ordering can scramble labels and bars. The explicit 2025 target is safe; the
    achieved amount is taken from the separately labelled funding-details table instead.
    """
    t = compact(page)
    if "Foreign Currency Funding Track Record" not in t:
        return {}
    out = {}
    if re.search(r"Funding Target 2025:\s*USD\s*10bn", t, re.I): out["2025_target_usd_bn_equiv"] = 10.0
    return out


def parse_dec_liquidity(page: str) -> dict:
    t = compact(page)
    if "Commitment to Liquidity" not in t:
        return {}
    out = {}
    if re.search(r"Continue issuing an average of 2\s*[–-]\s*3 USD\s*&\s*EUR benchmarks annually", t, re.I):
        out["benchmark_bonds_per_year_min"] = 2; out["benchmark_bonds_per_year_max"] = 3
    if re.search(r"US\$1\.2bn.*?per tranche", t, re.I): out["post_ssa_avg_tranche_usd_bn"] = 1.2
    return out


def parse_dec_outstanding(page: str) -> dict:
    t = compact(page)
    if "Funding Target and Outstanding Funding Details" not in t:
        return {}
    out = {}
    required = [r"Public Offerings USD 6\.3bn", r"Private Placement.*?USD 3\.3bn", r"Bank Loans USD 300mn", r"Total USD 9\.9bn"]
    if all(re.search(p, t, re.I) for p in required):
        out.update({"2025_target_usd_bn_equiv":10.0,"2025_achieved_usd_bn":9.9,"2025_public_offerings_usd_bn":6.3,"2025_private_placement_usd_bn":3.3,"2025_bank_loans_usd_bn":0.3})
    mix = {"usd_share_pct":(65.2,r"USD 65\.2%"),"brl_share_pct":(10.3,r"BRL 10\.3%"),"eur_share_pct":(10.2,r"EUR 10\.2%"),"aud_share_pct":(2.8,r"AUD 2\.8%"),"gbp_share_pct":(2.3,r"GBP 2\.3%"),"other_currency_share_pct":(9.1,r"Others 9\.1%")}
    for k,(v,p) in mix.items():
        if re.search(p,t,re.I): out[k]=v
    if re.search(r"USD 32\.4bn equivalent", t, re.I): out["foreign_currency_bonds_outstanding_usd_bn_equiv"] = 32.4
    if re.search(r"USD 122\.1bn equivalent", t, re.I): out["krw_bonds_outstanding_usd_bn_equiv"] = 122.1
    return out


def parse_jan2025_deal(page: str) -> dict:
    t = compact(page)
    if "KDB’s Offering of USD3.0bn Senior Unsecured Notes" not in t and "KDB's Offering of USD3.0bn Senior Unsecured Notes" not in t: return {}
    checks=[r"Issue Date 23 January, 2025",r"Currency / Size USD 900mn USD 1\.2bn USD 900mn",r"Coupon Rate 4\.625% 4\.875% SOFR\+76bps"]
    if not all(re.search(p,t,re.I) for p in checks): return {}
    return {"issue_date":"2025-01-23","total_size_usd_bn":3.0,"tranches":[{"tenor":"3Y","type":"fixed","size_usd_bn":0.9,"coupon_pct":4.625,"issue_spread_bps":57},{"tenor":"5Y","type":"fixed","size_usd_bn":1.2,"coupon_pct":4.875,"issue_spread_bps":76},{"tenor":"5Y","type":"FRN","size_usd_bn":0.9,"coupon":"SOFR+76bps","issue_spread_bps":76}]}


def validate(info: dict) -> list[dict]:
    checks=[]
    def add(name,ok,detail): checks.append({"check":name,"passed":bool(ok),"detail":detail})
    sec=info.get("sector_exposure",{}); vals=list(sec.values())
    if vals: add("sector_mix_sums_100",abs(sum(vals)-100)<0.11,f"Sector mix sums to {sum(vals):.1f}%")
    out=info.get("outstanding_funding",{}); shares=[out.get(k) for k in ("usd_share_pct","brl_share_pct","eur_share_pct","aud_share_pct","gbp_share_pct","other_currency_share_pct")]
    if all(v is not None for v in shares): add("outstanding_fx_mix_sums_100",abs(sum(shares)-100)<0.11,f"Outstanding FC bond mix sums to {sum(shares):.1f}%")
    deal=info.get("recent_issuance",{})
    if deal: add("jan2025_tranches_sum",abs(sum(x["size_usd_bn"] for x in deal["tranches"])-deal["total_size_usd_bn"])<0.001,"Tranches reconcile to total issue size")
    return checks


def freshness(publication_period: str) -> dict:
    y,m=map(int,publication_period.split("-")); age=(date.today()-date(y,m,1)).days
    return {"latest_core_ir_publication":publication_period,"age_days_approx":age,"status":"fresh" if age<=180 else "stale","policy":"Core IR older than 180 days is flagged. Current official programme/ratings pages remain authoritative for current programme sizes and ratings."}


def enrich(snapshot: dict, july: list[str], dec: list[str]) -> dict:
    framework=parse_business_framework(july[6]) if len(july)>6 else {}
    strategy=parse_dec_funding_strategy(dec[13]) if len(dec)>13 else {}
    track=parse_dec_track_record(dec[14]) if len(dec)>14 else {}
    liquidity=parse_dec_liquidity(dec[15]) if len(dec)>15 else {}
    outstanding=parse_dec_outstanding(dec[17]) if len(dec)>17 else {}
    recent=parse_jan2025_deal(july[18]) if len(july)>18 else {}
    info={
        "freshness":freshness("2025-12"),
        "funding_structure":{k:v for k,v in framework.items() if "funding" in k or "deposits" in k or "borrowings" in k or "industrial_bonds" in k},
        "sector_exposure":{"manufacturing_pct":framework.get("manufacturing_exposure_pct"),"finance_insurance_pct":framework.get("finance_insurance_exposure_pct"),"transportation_pct":framework.get("transportation_exposure_pct"),"utilities_pct":framework.get("utilities_exposure_pct"),"public_admin_pct":framework.get("public_admin_exposure_pct"),"others_pct":framework.get("other_sector_exposure_pct")},
        "funding_strategy":strategy,
        "funding_track_record":track,
        "liquidity_commitment":liquidity,
        "outstanding_funding":outstanding,
        "recent_issuance":recent,
        "provenance":{
            "funding_structure":source("Investor Presentation July 2025",JULY_URL,7,"Basic Framework of KDB’s Business Operations","2024-12","2025-07"),
            "sector_exposure":source("Investor Presentation July 2025",JULY_URL,7,"Basic Framework of KDB’s Business Operations","2024-12","2025-07"),
            "funding_strategy":source("Investor Presentation December 2025",DEC_URL,14,"Foreign Currency Funding Activities","2025-YTD","2025-12"),
            "funding_track_record":source("Investor Presentation December 2025",DEC_URL,15,"Foreign Currency Funding Track Record","2015-2025YTD","2025-12"),
            "liquidity_commitment":source("Investor Presentation December 2025",DEC_URL,16,"Commitment to Liquidity","2025-YTD","2025-12"),
            "outstanding_funding":source("Investor Presentation December 2025",DEC_URL,18,"Funding Target and Outstanding Funding Details","2025-12-02","2025-12"),
            "recent_issuance":source("Investor Presentation July 2025",JULY_URL,19,"Foreign Currency Funding Track Record","2025-01-23","2025-07"),
        },
    }
    info["sector_exposure"]={k:v for k,v in info["sector_exposure"].items() if v is not None}
    info["quality_checks"]=validate(info)
    info["signals"]=[]
    if outstanding.get("2025_achieved_usd_bn"):
        info["signals"].append({"type":"funding","priority":"high","fact":f"KDB had achieved US${outstanding['2025_achieved_usd_bn']:.1f}bn of its US$10bn 2025 funding target by 2 Dec 2025.","rm_angle":"Do not ask how much of the 2025 target remains. Ask what changed in the 2026 funding plan versus 2025 and what currencies/tenors are now preferred."})
    if outstanding.get("usd_share_pct",0)>60:
        info["signals"].append({"type":"fx_ccs","priority":"high","fact":f"USD was {outstanding['usd_share_pct']:.1f}% of foreign-currency bonds outstanding in the Dec-2025 presentation.","rm_angle":"Probe whether USD remains the preferred marginal funding currency or whether EUR/GBP/AUD plus CCS are becoming more competitive."})
    if info["sector_exposure"].get("manufacturing_pct",0)>40:
        info["signals"].append({"type":"sector","priority":"medium","fact":f"Manufacturing was {info['sector_exposure']['manufacturing_pct']:.1f}% of operating exposure as of Dec-2024.","rm_angle":"Use Korean manufacturing outbound investment to explore ASEAN syndication, PF and transaction-banking collaboration."})
    if info["freshness"]["status"]=="stale":
        info["signals"].append({"type":"freshness","priority":"high","fact":"The latest configured core investor presentation is Dec-2025 and is older than 180 days.","rm_angle":"Treat 2025 funding mix as historical context; refresh 2026 plans through current official releases/news and client discovery before pitching."})
    snapshot["rm_intelligence"]=info
    return snapshot


def main():
    snapshot=json.loads(SNAPSHOT.read_text())
    snapshot=enrich(snapshot,pdf_pages(JULY_URL),pdf_pages(DEC_URL))
    failed=[x for x in snapshot["rm_intelligence"]["quality_checks"] if not x["passed"]]
    if failed: raise SystemExit("RM intelligence consistency checks failed: "+json.dumps(failed))
    SNAPSHOT.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False))
    print("Added latest-available KDB RM intelligence, freshness flag and consistency checks")


if __name__=="__main__": main()
