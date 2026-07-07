"""
Data Checks / Data Quality Validation Module
Implements cross-dataset checks from the client's Data checks examples doc.
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB", "agenticpharma")


def get_db():
    return MongoClient(MONGODB_URI)[DB_NAME]


def run_all_checks() -> list[dict]:
    """Run all data checks and return list of results."""
    db = get_db()
    results = []
    results += check_fatal_ae_no_death(db)
    results += check_ae_with_meds_no_ae_record(db)
    results += check_disc_ae_no_ae_record(db)
    results += check_sae_not_in_ae(db)
    results += check_missing_lab_values(db)
    return results


def check_fatal_ae_no_death(db) -> list[dict]:
    """
    CHECK 1 (R_AEVBB): AE has death as outcome (AEOUTC=2) but no
    corresponding death record exists for that subject (DEATDI=1).
    """
    check_id = "CHK-001"
    check_name = "Fatal AE without Death Record"
    domain = "R_AEVBB → R_DEATH"
    severity = "CRITICAL"

    # Subjects with fatal AE outcome
    fatal_aes = list(db["adverse_events"].find(
        {"AEOUTC": 2},
        {"_id": 0, "SUBJ": 1, "PT_NAME": 1, "AESDYLTR": 1, "CENT": 1, "TRTSHORT": 1}
    ))
    # Subjects confirmed dead
    died_subjs = {r["SUBJ"] for r in db["death"].find({"DEATDI": 1.0}, {"SUBJ": 1, "_id": 0})}

    # Failures: fatal AE but no death confirmation
    failing = [r for r in fatal_aes if r["SUBJ"] not in died_subjs]

    return [{
        "check_id": check_id,
        "check_name": check_name,
        "domain": domain,
        "severity": severity,
        "description": "AE outcome = Fatal (AEOUTC=2) but no confirmed death record (DEATDI=1) found for this subject.",
        "total_checked": len(fatal_aes),
        "failures": len(failing),
        "pass_rate": round((1 - len(failing) / max(len(fatal_aes), 1)) * 100, 1),
        "status": "PASS" if not failing else "FAIL",
        "failing_records": failing[:50],
    }]


def check_ae_with_meds_no_ae_record(db) -> list[dict]:
    """
    CHECK 2 (R_AEVBB): AE has medications given (AEEVBB01=1) but
    no corresponding medication record exists for that subject.
    """
    check_id = "CHK-002"
    check_name = "AE with Medications Given — No Medication Record"
    domain = "R_AEVBB → R_MED"
    severity = "MAJOR"

    # AEs where treatment/medications were given
    ae_with_meds = list(db["adverse_events"].find(
        {"AEEVBB01": 1},
        {"_id": 0, "SUBJ": 1, "PT_NAME": 1, "AESDYLTR": 1, "CENT": 1, "TRTSHORT": 1}
    ))
    # Subjects with medication records
    med_subjs = {r["SUBJ"] for r in db["medications"].find({}, {"SUBJ": 1, "_id": 0})}

    # Failures: AE says meds given but no med record for subject
    failing = [r for r in ae_with_meds if r["SUBJ"] not in med_subjs]

    return [{
        "check_id": check_id,
        "check_name": check_name,
        "domain": domain,
        "severity": severity,
        "description": "AE record indicates medications were given (AEEVBB01=1) but no corresponding medication record exists for this subject.",
        "total_checked": len(ae_with_meds),
        "failures": len(failing),
        "pass_rate": round((1 - len(failing) / max(len(ae_with_meds), 1)) * 100, 1),
        "status": "PASS" if not failing else "FAIL",
        "failing_records": failing[:50],
    }]


def check_disc_ae_no_ae_record(db) -> list[dict]:
    """
    CHECK 3 (R_DOSDIS): Discontinuation reason = Adverse Event (DISCREA=11)
    but no corresponding AE record exists for that subject.
    """
    check_id = "CHK-003"
    check_name = "Discontinuation due to AE — No AE Record"
    domain = "R_DISC → R_AEVBB"
    severity = "CRITICAL"

    # Subjects who discontinued due to AE
    disc_ae = list(db["discontinuation"].find(
        {"DISCREA": 11},
        {"_id": 0, "SUBJ": 1, "CENT": 1, "TRTSHORT": 1, "IPLDYLTR": 1}
    ))
    # Subjects with any AE record
    ae_subjs = {r["SUBJ"] for r in db["adverse_events"].find({}, {"SUBJ": 1, "_id": 0})}

    # Failures: disc reason=AE but no AE record
    failing = [r for r in disc_ae if r["SUBJ"] not in ae_subjs]

    return [{
        "check_id": check_id,
        "check_name": check_name,
        "domain": domain,
        "severity": severity,
        "description": "Discontinuation reason = Adverse Event (DISCREA=11) but no AE record exists for this subject.",
        "total_checked": len(disc_ae),
        "failures": len(failing),
        "pass_rate": round((1 - len(failing) / max(len(disc_ae), 1)) * 100, 1),
        "status": "PASS" if not failing else "FAIL",
        "failing_records": failing[:50],
    }]


def check_sae_not_in_ae(db) -> list[dict]:
    """
    CHECK 4 (R_SAE → R_AEVBB): Every SAE subject must also have
    an AE record (SAEs are a subset of AEs).
    """
    check_id = "CHK-004"
    check_name = "SAE Subject Missing from AE Table"
    domain = "R_SAE → R_AEVBB"
    severity = "CRITICAL"

    sae_recs = list(db["serious_adverse_events"].find(
        {}, {"_id": 0, "SUBJ": 1, "PT_NAME": 1, "CENT": 1, "TRTSHORT": 1}
    ))
    ae_subjs = {r["SUBJ"] for r in db["adverse_events"].find({}, {"SUBJ": 1, "_id": 0})}

    failing = [r for r in sae_recs if r["SUBJ"] not in ae_subjs]

    return [{
        "check_id": check_id,
        "check_name": check_name,
        "domain": domain,
        "severity": severity,
        "description": "Subject has a Serious Adverse Event (SAE) record but no corresponding AE record. All SAEs must appear in the AE table.",
        "total_checked": len(sae_recs),
        "failures": len(failing),
        "pass_rate": round((1 - len(failing) / max(len(sae_recs), 1)) * 100, 1),
        "status": "PASS" if not failing else "FAIL",
        "failing_records": failing[:50],
    }]


def check_missing_lab_values(db) -> list[dict]:
    """
    CHECK 5 (R_LAB): Lab records with null/missing result values.
    """
    check_id = "CHK-005"
    check_name = "Lab Records with Missing Result Values"
    domain = "R_LAB"
    severity = "MINOR"

    total = db["laboratory"].count_documents({})
    missing = 0
    failing = []

    sample = list(db["laboratory"].find({}, {"_id": 0}).limit(1))
    if sample:
        cols = list(sample[0].keys())
        num_cols = [c for c in cols if any(x in c.upper() for x in ["VALUE","RESULT","STRESN","ORRES"])]
        if num_cols:
            col = num_cols[0]
            missing_recs = list(db["laboratory"].find(
                {col: None},
                {"_id": 0, "SUBJ": 1, "CENT": 1, col: 1}
            ).limit(50))
            missing = db["laboratory"].count_documents({col: None})
            failing = missing_recs

    return [{
        "check_id": check_id,
        "check_name": check_name,
        "domain": domain,
        "severity": severity,
        "description": "Laboratory records where the numeric result value is null/missing.",
        "total_checked": total,
        "failures": missing,
        "pass_rate": round((1 - missing / max(total, 1)) * 100, 1),
        "status": "PASS" if missing == 0 else ("FAIL" if missing > 100 else "WARN"),
        "failing_records": failing[:50],
    }]
