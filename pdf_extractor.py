#!/usr/bin/env python3

import os, re, pickle, logging, warnings
from datetime import datetime
from typing import Dict, List, Any, Optional

import pdfplumber
import pandas as pd
import redis
import camelot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

class PDFTableExtractor:
    """PDF table extractor with robust regex parsing and Redis support."""
    def __init__(self, redis_host="localhost", redis_port=6379, redis_db=0):
        try:
            self.redis_client = redis.Redis(
                host=redis_host, port=redis_port, db=redis_db, decode_responses=False
            )
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as exc:
            logger.error(f"Redis connection failed: {exc}")
            raise

    def extract_metadata(self, pdf_path: str) -> Dict[str, Any]:
        meta = {
            "group_number": None,
            "overall_limit": 1_000_000,
            "policy_expiry": None,
            "end_date": "2023-02-16",
            "class": "B",
            "deductible": None,
        }

        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()

        patterns = {
            "group_number": r"group\s*number\s+(\d+)",
            "overall_limit": r"overall\s*benefit\s*limit\s+([\d,]+)",
            "policy_expiry": r"policy\s*expiry\s*date\s+(\w+\s+\d+,\s+\d+)",
            "class": r"class\s+([A-Z])",
            "deductible": r"deductible\s+([\d%\s\w.]+)",
        }

        for key, pat in patterns.items():
            m = re.search(pat, text, re.I)
            if m:
                if key == "overall_limit":
                    meta[key] = int(m.group(1).replace(",", ""))
                else:
                    meta[key] = m.group(1).strip()

        if meta["policy_expiry"]:
            try:
                meta["end_date"] = datetime.strptime(
                    meta["policy_expiry"], "%b %d, %Y"
                ).strftime("%Y-%m-%d")
            except ValueError:
                logger.warning(f"Could not parse date: {meta['policy_expiry']}")

        logger.info(f"Extracted metadata: {meta}")
        return meta

    def extract_claims_data(self, pdf_path: str) -> pd.DataFrame:
        claims: List[Dict[str, Any]] = []
        meta = self.extract_metadata(pdf_path)

        with pdfplumber.open(pdf_path) as pdf:
            lines = pdf.pages[0].extract_text().split("\n")

        current_section, lives_start = None, 0

        for line in lines:
            line = line.strip()

            if re.search(r"policy\s*year\s*[-–]?\s*2\s*years\s*prior", line, re.I):
                current_section = "2 years Prior"
            elif re.search(r"prior\s*policy\s*year", line, re.I):
                current_section = "Prior Policy Year"
            elif re.search(r"last\s*policy\s*year", line, re.I):
                current_section = "Last Policy Year"

            if not current_section:
                continue

            if re.match(r"^\d{6}", line):
                parts = line.split()
                if len(parts) >= 5:
                    if parts[3].strip() == "" or parts[4].strip() == "":
                        continue
                    try:
                        claims.append(
                            {
                                "Monthly_Claims": parts[0],
                                "Number_of_Insured_Lives": int(parts[1]),
                                "Number_of_Claims": int(parts[2]),
                                "Amount_of_Paid_Claims": float(parts[3].replace(",", "")),
                                "Amount_of_Paid_Claims_VAT": float(
                                    parts[4].replace(",", "")
                                ),
                                "Policy_Year": current_section,
                                "End_Date": meta["end_date"],
                                "Class": meta["class"],
                                "Overall_Limit": meta["overall_limit"],
                            }
                        )
                    except ValueError as exc:
                        logger.warning(f"Could not parse claims line: {line} – {exc}")

        logger.info(f"Extracted {len(claims)} claims records")
        required_cols = [
            "Monthly_Claims",
            "Number_of_Insured_Lives",
            "Number_of_Claims",
            "Amount_of_Paid_Claims",
            "Amount_of_Paid_Claims_VAT",
            "Policy_Year",
            "End_Date",
            "Class",
            "Overall_Limit",
        ]
        return pd.DataFrame(claims, columns=required_cols)

    def _process_notes(self, txt: str, full_line: str) -> str:
        combined = f"{txt} {full_line}".lower()
        for pat in [r"paid\s+(\d+)\s*%", r"(\d+)\s*%\s*up\s*to", r"(\d+)\s*%"]:
            m = re.search(pat, combined)
            if m:
                return f"{m.group(1)}%"
        if "cesarean" in combined:
            return "yes"
        return "No info"

    import camelot

    def extract_benefits_data(self, pdf_path: str) -> pd.DataFrame:
        """Use Camelot to pull the benefits grid (last table on the page)."""
        meta = self.extract_metadata(pdf_path)

        tables = camelot.read_pdf(pdf_path, pages="1", flavor="lattice")
        ben_df = tables[-1].df                         

        ben_df.columns = [
            "Benefit_Sama",        
            "Number_of_Claims",    
            "Amount_of_Claims",    
            "Amount_of_Claims_VAT",
            "Notes_raw",           
        ]

        ben_df = ben_df[ben_df["Number_of_Claims"].str.match(r"\d+")].copy()

        ben_df["Notes"] = ben_df["Notes_raw"].apply(
            lambda x: self._process_notes(x, x)
        )
        ben_df.drop(columns="Notes_raw", inplace=True)

        ben_df["Policy_Year"] = "Last Policy Year"
        ben_df["End_Date"]      = meta["end_date"]
        ben_df["Class"]         = meta["class"]
        ben_df["Overall_Limit"] = meta["overall_limit"]

        for col in ["Number_of_Claims", "Amount_of_Claims", "Amount_of_Claims_VAT"]:
            ben_df[col] = (
                ben_df[col].str.replace(",", "").astype(float, errors="ignore")
            )

        return ben_df[
            [
                "Benefit_Sama",
                "Number_of_Claims",
                "Amount_of_Claims",
                "Amount_of_Claims_VAT",
                "Notes",
                "Policy_Year",
                "End_Date",
                "Class",
                "Overall_Limit",
            ]
        ]

    def process_pdf(self, pdf_path: str) -> Dict[str, pd.DataFrame]:
        logger.info(f"Processing PDF: {pdf_path}")
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(pdf_path)

        claims_df = self.extract_claims_data(pdf_path)
        ben_df = self.extract_benefits_data(pdf_path)
        return {"claims": claims_df, "benefits": ben_df}

    def save_to_pickle(self, data: Dict[str, pd.DataFrame], fname="dataframes.txt"):
        payload = {"claim_experiences": data}
        with open(fname, "wb") as fh:
            pickle.dump(payload, fh)
        logger.info(f"Data saved to {fname}")

    def save_to_redis(self, data: Dict[str, pd.DataFrame], key="pdf_extraction_results"):
        payload = {
            "claim_experiences": {
                "claims": data["claims"].to_dict("records"),
                "benefits": data["benefits"].to_dict("records"),
            }
        }
        self.redis_client.set(key, pickle.dumps(payload))
        logger.info(f"Data saved to Redis key: {key}")

    def run(self, pdf_path: str) -> Dict[str, pd.DataFrame]:
        data = self.process_pdf(pdf_path)
        self.save_to_pickle(data)
        self.save_to_redis(data)
        self._display_summary(data)
        logger.info("PDF extraction completed successfully!")
        return data

    def _display_summary(self, d: Dict[str, pd.DataFrame]):
        claims, ben = d["claims"], d["benefits"]
        print("\n" + "=" * 60)
        print("EXTRACTION SUMMARY")
        print("=" * 60)

        if not claims.empty:
            print(f"Claims records   : {len(claims)}")
            print(f"Policy years     : {claims['Policy_Year'].unique().tolist()}")
            print(
                f"Total paid claims: {claims['Amount_of_Paid_Claims'].sum():,.2f}"
            )

        if not ben.empty:
            print(f"\nBenefits records : {len(ben)}")
            print(f"Benefit types    : {ben['Benefit_Sama'].tolist()}")
            print(f"Total amount     : {ben['Amount_of_Claims'].sum():,.2f}")
        print("=" * 60)


def validate_dataframes(claims: pd.DataFrame, ben: pd.DataFrame) -> bool:
    req_claims = [
        "Monthly_Claims",
        "Number_of_Insured_Lives",
        "Number_of_Claims",
        "Amount_of_Paid_Claims",
        "Amount_of_Paid_Claims_VAT",
        "Policy_Year",
        "End_Date",
        "Class",
        "Overall_Limit",
    ]
    req_ben = [
        "Benefit_Sama",
        "Number_of_Claims",
        "Amount_of_Claims",
        "Amount_of_Claims_VAT",
        "Notes",
        "Policy_Year",
        "End_Date",
        "Class",
        "Overall_Limit",
    ]

    ok = True
    for col in req_claims:
        if col not in claims.columns:
            logger.error(f"Missing claims column: {col}")
            ok = False
    for col in req_ben:
        if col not in ben.columns:
            logger.error(f"Missing benefits column: {col}")
            ok = False
    return ok
