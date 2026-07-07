"""
Patient Data Entry forms — renders Streamlit forms for key RDB datasets.
Schema sourced from NCT00617669_schema.draft.json (SnapSoft) + RDB Standards.
Writes to MongoDB with full audit trail.
"""
import datetime
import streamlit as st
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB", "agenticpharma")
AUDIT_COLLECTION = "audit_trail"


def get_db():
    return MongoClient(MONGODB_URI)[DB_NAME]


def write_audit(db, user: dict, collection: str, subj, action: str, before: dict, after: dict):
    db[AUDIT_COLLECTION].insert_one({
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "user": user.get("username"),
        "user_name": user.get("name"),
        "role": user.get("role"),
        "collection": collection,
        "subject": subj,
        "action": action,
        "before": before,
        "after": after,
    })


# ── Value lists (from RDB Standards) ─────────────────────────────────────────
SEX_VALUES = {1: "Male", 2: "Female"}
RACE_VALUES = {1: "White/Caucasian", 2: "Black/African American", 3: "Asian", 4: "Other", 5: "Not reported"}
AEOUTC_VALUES = {0: "Not recovered/not resolved", 1: "Recovered/resolved", 2: "Fatal", 3: "Recovering/resolving", 4: "Sequelae", 9: "Unknown"}
AESEV_VALUES = {1: "Mild", 2: "Moderate", 3: "Severe", 4: "Life-threatening", 5: "Fatal"}
CTCG_VALUES = {0: "Grade 0", 1: "Grade 1", 2: "Grade 2", 3: "Grade 3", 4: "Grade 4", 5: "Grade 5"}
YESNO = {0: "No", 1: "Yes"}
TRTCODE_VALUES = {"A": "Zibotentan (ZD4054)", "B": "Placebo"}


def render_demographics_form(db, user: dict):
    st.subheader("Demographics (R_DEM)")
    st.caption("Enter baseline demographic data for a new subject.")

    with st.form("dem_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            subj = st.number_input("Subject ID (SUBJ)*", min_value=1, max_value=9999, step=1)
            cent = st.text_input("Centre Number (CENT)*", placeholder="e.g. 001")
            study = st.text_input("Study (STUDY)", value="D4320C00033")
        with col2:
            sex = st.selectbox("Sex (SEX)*", options=list(SEX_VALUES.keys()), format_func=lambda x: SEX_VALUES[x])
            age = st.number_input("Age (AGE)*", min_value=18, max_value=100, step=1, value=65)
            agegrp = st.selectbox("Age Group (AGEGRP)", options=["<65", "65-75", ">75"])
        with col3:
            race = st.selectbox("Race (RACE)", options=list(RACE_VALUES.keys()), format_func=lambda x: RACE_VALUES[x])
            trtcode = st.selectbox("Treatment Code (TRTCODE)", options=list(TRTCODE_VALUES.keys()), format_func=lambda x: TRTCODE_VALUES[x])
            trtshort = TRTCODE_VALUES.get(trtcode, "")

        col4, col5 = st.columns(2)
        with col4:
            height = st.number_input("Height cm (BL_HGHT)", min_value=100.0, max_value=220.0, value=175.0, step=0.1)
            weight = st.number_input("Weight kg (BL_WGHT)", min_value=30.0, max_value=200.0, value=80.0, step=0.1)
        with col5:
            bmi = round(weight / ((height / 100) ** 2), 1) if height > 0 else 0
            st.metric("BMI (calculated)", bmi)
            safe_set = st.selectbox("Safety Set (SAFE_SET)", [1, 0], format_func=lambda x: YESNO[x])

        submitted = st.form_submit_button("Save Demographics", type="primary")
        if submitted:
            if not cent:
                st.error("Centre Number is required.")
                return
            record = {
                "SUBJ": int(subj), "CENT": cent, "STUDY": study,
                "SEX": sex, "AGE": int(age), "AGEGRP": agegrp,
                "RACE": race, "TRTCODE": trtcode, "TRTSHORT": trtshort,
                "BL_HGHT": height, "BL_WGHT": weight, "BL_BMI": bmi,
                "SAFE_SET": safe_set,
                "_entered_by": user.get("username"),
                "_entered_at": datetime.datetime.utcnow().isoformat(),
            }
            existing = db["demographics"].find_one({"SUBJ": int(subj)}, {"_id": 0})
            db["demographics"].update_one({"SUBJ": int(subj)}, {"$set": record}, upsert=True)
            write_audit(db, user, "demographics", int(subj), "upsert", existing or {}, record)
            st.success(f"✅ Demographics saved for Subject {int(subj)}")


def render_ae_form(db, user: dict):
    st.subheader("Adverse Event (R_AEVBB)")
    st.caption("Record an adverse event for a subject.")

    # List existing subjects for quick lookup
    subjs = sorted([r["SUBJ"] for r in db["demographics"].find({}, {"SUBJ": 1, "_id": 0})])

    with st.form("ae_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            if subjs:
                subj = st.selectbox("Subject ID (SUBJ)*", options=subjs)
            else:
                subj = st.number_input("Subject ID (SUBJ)*", min_value=1, step=1)
            cent = st.text_input("Centre (CENT)", placeholder="e.g. 001")
            ae_term = st.text_input("AE Preferred Term (PT_NAME)*", placeholder="e.g. Nausea")
            soc = st.text_input("Body System (SOC_NAME)", placeholder="e.g. Gastrointestinal disorders")
        with col2:
            ctcgmax = st.selectbox("Max CTC Grade (CTCGMAX)*", options=list(CTCG_VALUES.keys()), format_func=lambda x: CTCG_VALUES[x])
            aeoutc = st.selectbox("AE Outcome (AEOUTC)*", options=list(AEOUTC_VALUES.keys()), format_func=lambda x: AEOUTC_VALUES[x])
            aesev = st.selectbox("Severity (AESEV)", options=list(AESEV_VALUES.keys()), format_func=lambda x: AESEV_VALUES[x])
            aeser = st.selectbox("Serious AE? (AESER)", [0, 1], format_func=lambda x: YESNO[x])

        col3, col4 = st.columns(2)
        with col3:
            ae_start = st.date_input("AE Start Date")
            aesdyltr = st.number_input("Days from last dose (AESDYLTR)", value=0, step=1)
        with col4:
            ae_end = st.date_input("AE End Date (leave as start if ongoing)")
            aeevbb01 = st.selectbox("Medications Given? (AEEVBB01)", [0, 1], format_func=lambda x: YESNO[x])

        trtshort_val = "Placebo"
        dem = db["demographics"].find_one({"SUBJ": subj}, {"TRTSHORT": 1, "CENT": 1, "_id": 0})
        if dem:
            trtshort_val = dem.get("TRTSHORT", "Placebo")
            cent = dem.get("CENT", cent)

        submitted = st.form_submit_button("Save Adverse Event", type="primary")
        if submitted:
            if not ae_term:
                st.error("AE Preferred Term is required.")
                return
            record = {
                "SUBJ": subj, "CENT": cent, "PT_NAME": ae_term, "SOC_NAME": soc,
                "CTCGMAX": ctcgmax, "AEOUTC": aeoutc, "AESEV": aesev, "AESER": aeser,
                "AESTDAT": str(ae_start), "AEENDAT": str(ae_end),
                "AESDYLTR": aesdyltr, "AEEVBB01": aeevbb01,
                "TRTSHORT": trtshort_val,
                "_entered_by": user.get("username"),
                "_entered_at": datetime.datetime.utcnow().isoformat(),
            }
            db["adverse_events"].insert_one({k: v for k, v in record.items() if k != "_id"})
            write_audit(db, user, "adverse_events", subj, "insert", {}, record)
            st.success(f"✅ AE '{ae_term}' recorded for Subject {subj}")


def render_discontinuation_form(db, user: dict):
    st.subheader("Discontinuation (R_DISC)")
    st.caption("Record subject discontinuation from the study.")

    DISCREA_VALUES = {
        11: "Adverse Event", 51: "Withdrawal of Consent", 61: "Protocol Deviation",
        71: "Investigator Decision", 99: "Other"
    }

    subjs = sorted([r["SUBJ"] for r in db["demographics"].find({}, {"SUBJ": 1, "_id": 0})])

    with st.form("disc_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            subj = st.selectbox("Subject ID (SUBJ)*", options=subjs) if subjs else st.number_input("Subject ID*", min_value=1, step=1)
            discrea = st.selectbox("Discontinuation Reason (DISCREA)*", options=list(DISCREA_VALUES.keys()), format_func=lambda x: DISCREA_VALUES[x])
        with col2:
            disc_date = st.date_input("Discontinuation Date")
            ipldyltr = st.number_input("Days from last dose (IPLDYLTR)", value=0, step=1)

        submitted = st.form_submit_button("Save Discontinuation", type="primary")
        if submitted:
            existing = db["discontinuation"].find_one({"SUBJ": subj}, {"_id": 0})
            record = {
                "SUBJ": subj, "DISCREA": discrea, "DISCDAT": str(disc_date),
                "IPLDYLTR": ipldyltr,
                "_entered_by": user.get("username"),
                "_entered_at": datetime.datetime.utcnow().isoformat(),
            }
            db["discontinuation"].update_one({"SUBJ": subj}, {"$set": record}, upsert=True)
            write_audit(db, user, "discontinuation", subj, "upsert", existing or {}, record)
            st.success(f"✅ Discontinuation recorded for Subject {subj} — Reason: {DISCREA_VALUES[discrea]}")


def render_audit_log(db):
    st.subheader("Audit Trail")
    st.caption("All data entry and modifications are logged here.")
    logs = list(db[AUDIT_COLLECTION].find({}, {"_id": 0}).sort("timestamp", -1).limit(100))
    if not logs:
        st.info("No audit entries yet.")
        return
    import pandas as pd
    df = pd.DataFrame(logs)[["timestamp", "user_name", "role", "collection", "subject", "action"]]
    st.dataframe(df, use_container_width=True, hide_index=True)
    with st.expander("View full audit detail (last 10 entries)"):
        for log in logs[:10]:
            st.json(log)
