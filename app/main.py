"""
AgenticPharma MVP - Streamlit App
Run: streamlit run app/main.py
"""
import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
from dotenv import load_dotenv

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB", "agenticpharma")

st.set_page_config(
    page_title="AgenticPharma - Zibotentan Trial",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Login gate ───────────────────────────────────────────────────────────────
from app.auth import authenticate

if "current_user" not in st.session_state:
    st.session_state.current_user = None

if st.session_state.current_user is None:
    st.markdown('<p class="main-header" style="font-size:1.6rem">AgenticPharma — Zibotentan Phase 3 Trial</p>', unsafe_allow_html=True)
    st.markdown("#### Sign In")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", type="primary")
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.current_user = user
                st.rerun()
            else:
                st.error("Invalid username or password.")
    st.markdown("---")
    st.caption("Demo credentials: `investigator` / `pi2024` · `sponsor` / `sponsor2024` · `admin` / `admin2024`")
    st.stop()

# CSS styling
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #1a365d; }
    .metric-card { background: #f7fafc; border-radius: 8px; padding: 1rem; border-left: 4px solid #3182ce; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 20px; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db():
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]


@st.cache_data(ttl=300)
def load_collection(collection_name: str, query: dict = None, limit: int = 10000) -> pd.DataFrame:
    db = get_db()
    cursor = db[collection_name].find(query or {}, {"_id": 0}).limit(limit)
    return pd.DataFrame(list(cursor))


def check_mongo_connection() -> bool:
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return True
    except Exception:
        return False


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://via.placeholder.com/200x60/1a365d/ffffff?text=AgenticPharma", use_column_width=True)
    st.markdown("---")
    st.markdown("**Trial:** NCT00617669  \n**Drug:** Zibotentan  \n**Sponsor:** AstraZeneca")
    st.markdown("---")
    # User info + logout
    user = st.session_state.current_user
    role_color = {"admin": "🔴", "investigator": "🟢", "sponsor": "🔵"}.get(user["role"], "⚪")
    st.markdown(f"{role_color} **{user['name']}**  \nRole: `{user['role']}`")
    if user.get("site"):
        st.caption(f"Site: {user['site']}")
    if st.button("Sign Out"):
        st.session_state.current_user = None
        st.rerun()
    st.markdown("---")

    mongo_ok = check_mongo_connection()
    if mongo_ok:
        st.success("MongoDB Connected")
    else:
        st.error("MongoDB Offline")
        st.info("Run: `docker run -d -p 27017:27017 mongo:latest`\nThen: `python ingestion/load_csvs.py`")

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        st.success("Gemini API Ready")
    else:
        st.warning("Gemini API Key Missing")
        st.info("Add GEMINI_API_KEY to .env file")

    st.markdown("---")
    st.caption("AgenticPharma MVP v1.0 | Phase 1 Prototype")


# ─── Main content ─────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">AgenticPharma — Zibotentan Phase 3 Trial</p>', unsafe_allow_html=True)
st.caption("NCT00617669 | AstraZeneca | Prostate Cancer | De-identified data")

if not mongo_ok:
    st.error("MongoDB is not running. Start MongoDB and load CSVs first.")
    st.code("docker run -d -p 27017:27017 mongo:latest\ncd agenticpharma_mvp\npython ingestion/load_csvs.py")
    st.stop()

# ─── Tabs ─────────────────────────────────────────────────────────────────────
current_user = st.session_state.current_user
can_write_data = current_user["permissions"]["can_write"]

tabs = ["Overview", "Safety (AEs)", "Efficacy (PSA/Survival)", "Laboratory", "AI Chat", "🔍 Data Checks"]
if can_write_data:
    tabs += ["✏️ Data Entry", "📋 Audit Trail"]

tab_list = st.tabs(tabs)
tab_overview = tab_list[0]
tab_safety   = tab_list[1]
tab_efficacy = tab_list[2]
tab_labs     = tab_list[3]
tab_chat     = tab_list[4]
tab_checks   = tab_list[5]
tab_entry    = tab_list[6] if can_write_data else None
tab_audit    = tab_list[7] if can_write_data else None


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_overview:
    st.subheader("Enrollment Overview")

    try:
        dem = load_collection("demographics")

        col1, col2, col3, col4 = st.columns(4)
        total = len(dem)
        arm_col = "TRTSHORT" if "TRTSHORT" in dem.columns else "TRTCODE"
        sites = dem["CENT"].nunique() if "CENT" in dem.columns else 0
        studies = dem["STUDY"].nunique() if "STUDY" in dem.columns else 0
        arms = dem[arm_col].value_counts() if arm_col in dem.columns else {}

        col1.metric("Total Patients", f"{total:,}")
        col2.metric("Treatment Arms", f"{len(arms):,}")
        col3.metric("Clinical Sites", f"{sites:,}")
        col4.metric("Studies", f"{studies:,}")

        # Show per-arm breakdown as sub-metrics
        if len(arms) > 0:
            arm_cols = st.columns(len(arms))
            for i, (arm_name, arm_count) in enumerate(arms.items()):
                arm_cols[i].metric(f"Arm: {arm_name}", f"{arm_count:,} patients")

        col_left, col_right = st.columns(2)

        with col_left:
            if arm_col in dem.columns:
                arm_counts = dem[arm_col].value_counts().reset_index()
                arm_counts.columns = ["Arm", "Count"]
                fig = px.pie(arm_counts, values="Count", names="Arm",
                             title="Treatment Arm Split",
                             color_discrete_sequence=["#3182ce", "#e53e3e"])
                st.plotly_chart(fig, use_container_width=True)

        with col_right:
            # Use AGEGRP if AGE not present
            age_col = "AGE" if "AGE" in dem.columns else "AGEGRP"
            if age_col in dem.columns:
                if age_col == "AGEGRP":
                    age_counts = dem[age_col].value_counts().sort_index().reset_index()
                    age_counts.columns = ["Age Group", "Count"]
                    fig = px.bar(age_counts, x="Age Group", y="Count",
                                 title="Age Group Distribution",
                                 color_discrete_sequence=["#3182ce"])
                else:
                    dem[age_col] = pd.to_numeric(dem[age_col], errors="coerce")
                    fig = px.histogram(dem.dropna(subset=[age_col]), x=age_col, color=arm_col,
                                       nbins=30, title="Age Distribution by Treatment Arm",
                                       labels={arm_col: "Arm", age_col: "Age"})
                st.plotly_chart(fig, use_container_width=True)

        if "SEX" in dem.columns and arm_col in dem.columns:
            dem["Sex"] = dem["SEX"].map({1: "Male", 2: "Female"}).fillna(dem["SEX"].astype(str))
            sex_counts = dem.groupby([arm_col, "Sex"]).size().reset_index(name="Count")
            fig = px.bar(sex_counts, x=arm_col, y="Count", color="Sex",
                         barmode="group", title="Sex Distribution by Treatment Arm",
                         color_discrete_map={"Male": "#3182ce", "Female": "#e53e3e"})
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading demographics: {e}")
        st.info("Run ingestion/load_csvs.py first.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: SAFETY (Adverse Events)
# ══════════════════════════════════════════════════════════════════════════════
with tab_safety:
    st.subheader("Adverse Events (AE) Summary")

    try:
        ae = load_collection("adverse_events")

        if ae.empty:
            st.warning("No adverse event data found.")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total AE Records", f"{len(ae):,}")

            if "SUBJ" in ae.columns:
                col2.metric("Unique Patients with AEs", f"{ae['SUBJ'].nunique():,}")

            grade_col = "CTCGMAX" if "CTCGMAX" in ae.columns else next((c for c in ae.columns if "GRADE" in c.upper() or "CTCG" in c.upper()), None)
            if grade_col:
                ae[grade_col] = pd.to_numeric(ae[grade_col], errors="coerce")
                severe = ae[ae[grade_col] >= 3]
                col3.metric("Grade ≥3 AEs", f"{len(severe):,}")

            col_left, col_right = st.columns(2)
            ae_arm_col = "TRTSHORT" if "TRTSHORT" in ae.columns else "TRTCODE"

            with col_left:
                if ae_arm_col in ae.columns:
                    ae_by_arm = ae[ae_arm_col].value_counts().reset_index()
                    ae_by_arm.columns = ["Arm", "Count"]
                    fig = px.bar(ae_by_arm, x="Arm", y="Count",
                                 title="AE Count by Treatment Arm",
                                 color="Arm",
                                 color_discrete_sequence=["#3182ce", "#e53e3e"])
                    st.plotly_chart(fig, use_container_width=True)

            with col_right:
                if grade_col:
                    ae[grade_col] = pd.to_numeric(ae[grade_col], errors="coerce")
                    grade_counts = ae[grade_col].value_counts().sort_index().reset_index()
                    grade_counts.columns = ["Grade", "Count"]
                    grade_counts = grade_counts.dropna()
                    fig = px.bar(grade_counts, x="Grade", y="Count",
                                 title="AE Severity (Max CTC Grade)",
                                 color_discrete_sequence=["#3182ce"])
                    st.plotly_chart(fig, use_container_width=True)

            # Top body systems — SOC_NAME is the MedDRA body system column
            body_sys_col = "SOC_NAME" if "SOC_NAME" in ae.columns else next((c for c in ae.columns if "SOC" in c.upper()), None)
            if body_sys_col:
                top_soc = ae[body_sys_col].value_counts().head(15).reset_index()
                top_soc.columns = ["Body System", "Count"]
                fig = px.bar(top_soc, x="Count", y="Body System", orientation="h",
                             title="Top 15 AEs by Body System (MedDRA SOC)",
                             color_discrete_sequence=["#3182ce"])
                fig.update_layout(yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)

            # Top preferred terms
            pt_col = "PT_NAME" if "PT_NAME" in ae.columns else None
            if pt_col:
                top_pt = ae[pt_col].value_counts().head(15).reset_index()
                top_pt.columns = ["Preferred Term", "Count"]
                fig = px.bar(top_pt, x="Count", y="Preferred Term", orientation="h",
                             title="Top 15 AEs by Preferred Term (MedDRA PT)",
                             color_discrete_sequence=["#e53e3e"])
                fig.update_layout(yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)

            # Raw data table
            with st.expander("View Raw AE Data"):
                st.dataframe(ae.head(200), use_container_width=True)

    except Exception as e:
        st.error(f"Error loading AE data: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: EFFICACY
# ══════════════════════════════════════════════════════════════════════════════
with tab_efficacy:
    st.subheader("Efficacy — PSA Biomarker & Survival")

    col_psa, col_surv = st.columns(2)

    with col_psa:
        st.markdown("**PSA Biomarker Over Time**")
        try:
            psa = load_collection("psa_biomarker")
            if not psa.empty:
                psa_col = next((c for c in psa.columns if "PSA" in c.upper() and "VALUE" in c.upper()), None) or \
                          next((c for c in psa.columns if "PSA" in c.upper()), None)
                visit_col = next((c for c in psa.columns if "VISIT" in c.upper() or "WEEK" in c.upper()), None)

                if psa_col and visit_col and "TRTCODE" in psa.columns:
                    psa[psa_col] = pd.to_numeric(psa[psa_col], errors="coerce")
                    psa[visit_col] = pd.to_numeric(psa[visit_col], errors="coerce")
                    psa_mean = psa.groupby([visit_col, "TRTCODE"])[psa_col].mean().reset_index()
                    psa_mean["TRTCODE"] = psa_mean["TRTCODE"].map({"A": "Zibotentan", "B": "Placebo"})
                    fig = px.line(psa_mean, x=visit_col, y=psa_col, color="TRTCODE",
                                  title="Mean PSA by Visit and Arm",
                                  labels={"TRTCODE": "Arm"},
                                  color_discrete_map={"Zibotentan": "#3182ce", "Placebo": "#e53e3e"})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.dataframe(psa.head(100))
            else:
                st.info("No PSA data loaded.")
        except Exception as e:
            st.error(f"PSA error: {e}")

    with col_surv:
        st.markdown("**Survival Data**")
        try:
            surv = load_collection("survival")
            if not surv.empty:
                # Simple survival summary
                col1, col2 = st.columns(2)
                death_col = next((c for c in surv.columns if "DEATH" in c.upper() or "DIED" in c.upper()), None)
                if death_col:
                    death_counts = surv[death_col].value_counts().reset_index()
                    death_counts.columns = ["Status", "Count"]
                    fig = px.pie(death_counts, values="Count", names="Status",
                                 title="Survival Status",
                                 color_discrete_sequence=["#48bb78", "#e53e3e"])
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.dataframe(surv.head(100))
            else:
                st.info("No survival data loaded.")
        except Exception as e:
            st.error(f"Survival error: {e}")

    # Vital signs over time
    st.markdown("---")
    st.markdown("**Vital Signs Over Time**")
    try:
        vit = load_collection("vital_signs", limit=5000)
        if not vit.empty and "VISIT" in vit.columns:
            bp_col = next((c for c in vit.columns if "SYSBP" in c.upper() or "SBP" in c.upper() or "SYSTOL" in c.upper()), None)
            vit_arm = "TRTSHORT" if "TRTSHORT" in vit.columns else "TRTCODE"
            if bp_col and vit_arm in vit.columns:
                vit[bp_col] = pd.to_numeric(vit[bp_col], errors="coerce")
                vit["VISIT"] = pd.to_numeric(vit["VISIT"], errors="coerce")
                vit_mean = vit.groupby(["VISIT", vit_arm])[bp_col].mean().reset_index()
                fig = px.line(vit_mean, x="VISIT", y=bp_col, color=vit_arm,
                              title="Mean Systolic BP by Visit",
                              labels={vit_arm: "Arm"})
                st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Vital signs: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: LABORATORY
# ══════════════════════════════════════════════════════════════════════════════
with tab_labs:
    st.subheader("Laboratory Results")

    try:
        lab = load_collection("laboratory", limit=10000)
        if lab.empty:
            st.warning("No lab data found.")
        else:
            st.metric("Total Lab Records", f"{len(lab):,}")

            # Lab test selector
            test_col = next((c for c in lab.columns if "TEST" in c.upper() or "PARAM" in c.upper() or "LBTEST" in c.upper()), None)
            value_col = next((c for c in lab.columns if "VALUE" in c.upper() or "RESULT" in c.upper() or "LBSTRESN" in c.upper()), None)

            if test_col and value_col:
                tests = sorted(lab[test_col].dropna().unique().tolist())
                selected_test = st.selectbox("Select Lab Test", tests[:50])

                lab_filtered = lab[lab[test_col] == selected_test].copy()
                lab_filtered[value_col] = pd.to_numeric(lab_filtered[value_col], errors="coerce")

                if "TRTCODE" in lab.columns and "VISIT" in lab.columns:
                    lab_filtered["VISIT"] = pd.to_numeric(lab_filtered["VISIT"], errors="coerce")
                    lab_mean = lab_filtered.groupby(["VISIT", "TRTCODE"])[value_col].mean().reset_index()
                    lab_mean["TRTCODE"] = lab_mean["TRTCODE"].map({"A": "Zibotentan", "B": "Placebo"})
                    fig = px.line(lab_mean, x="VISIT", y=value_col, color="TRTCODE",
                                  title=f"{selected_test} Over Time by Treatment Arm",
                                  color_discrete_map={"Zibotentan": "#3182ce", "Placebo": "#e53e3e"})
                    st.plotly_chart(fig, use_container_width=True)

                    # Box plot
                    fig2 = px.box(lab_filtered.dropna(subset=[value_col]),
                                  x="TRTCODE", y=value_col,
                                  title=f"{selected_test} Distribution by Arm",
                                  labels={"TRTCODE": "Treatment Arm"})
                    st.plotly_chart(fig2, use_container_width=True)

            with st.expander("Raw Lab Data (first 200 rows)"):
                st.dataframe(lab.head(200), use_container_width=True)

    except Exception as e:
        st.error(f"Lab error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: AI CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.subheader("AI Clinical Data Chat")
    st.caption("Ask questions about the Zibotentan trial data in plain English.")

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        st.error("GEMINI_API_KEY not set in .env file")
        st.code("GEMINI_API_KEY=your_key_here  # in agenticpharma_mvp/.env")
        st.stop()

    # Initialize chat agent
    if "agent" not in st.session_state:
        from chat.agent import ClinicalAgent
        st.session_state.agent = ClinicalAgent()
        st.session_state.messages = []

    # Suggested questions
    st.markdown("**Suggested questions:**")
    suggestions = [
        "How many patients are in each treatment arm?",
        "What are the most common adverse events?",
        "Compare PSA response rates between Zibotentan and Placebo arms",
        "How many Grade 3+ adverse events occurred in the Zibotentan arm?",
        "What is the average age of patients in each arm?",
        "Show me survival outcomes by treatment arm",
    ]
    cols = st.columns(3)
    for i, suggestion in enumerate(suggestions):
        if cols[i % 3].button(suggestion, key=f"sugg_{i}", use_container_width=True):
            st.session_state.pending_question = suggestion

    st.markdown("---")

    # Chat history display
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Handle suggested question click
    if "pending_question" in st.session_state:
        question = st.session_state.pop("pending_question")
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Querying trial database..."):
                try:
                    response = st.session_state.agent.chat(question)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    err_msg = f"Error: {e}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
        st.rerun()

    # Chat input
    if prompt := st.chat_input("Ask about the trial data..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Querying trial database..."):
                try:
                    response = st.session_state.agent.chat(prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    err_msg = f"Error: {e}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})

    # Clear chat
    if st.session_state.messages:
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.session_state.agent.reset()
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6: DATA CHECKS
# ══════════════════════════════════════════════════════════════════════════════
with tab_checks:
    st.subheader("Data Quality Checks")
    st.caption("Cross-dataset validation rules — flags data integrity issues across clinical trial domains.")

    SEVERITY_COLOR = {"CRITICAL": "#e53e3e", "MAJOR": "#dd6b20", "MINOR": "#d69e2e", "INFO": "#3182ce"}
    STATUS_EMOJI = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}

    if st.button("Run All Data Checks", type="primary"):
        with st.spinner("Running validation checks across all collections..."):
            try:
                from app.checks import run_all_checks
                results = run_all_checks()
                st.session_state["check_results"] = results
            except Exception as e:
                st.error(f"Error running checks: {e}")

    results = st.session_state.get("check_results", None)

    if results is None:
        st.info("Click **Run All Data Checks** to validate data integrity across all clinical trial domains.")
    else:
        # ── Summary row ──
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        warned = sum(1 for r in results if r["status"] == "WARN")
        total_fails = sum(r["failures"] for r in results)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Checks Run", total)
        c2.metric("Passed", passed, delta=None)
        c3.metric("Failed", failed, delta=None)
        c4.metric("Warnings", warned, delta=None)
        c5.metric("Total Failing Records", f"{total_fails:,}")

        st.markdown("---")

        # ── Per-check cards ──
        for r in results:
            sev_color = SEVERITY_COLOR.get(r["severity"], "#718096")
            status_icon = STATUS_EMOJI.get(r["status"], "?")
            border = "2px solid " + ("#48bb78" if r["status"] == "PASS" else sev_color)

            with st.expander(
                f"{status_icon} [{r['check_id']}] {r['check_name']} — {r['domain']}  |  "
                f"Failures: {r['failures']} / {r['total_checked']}  |  Pass Rate: {r['pass_rate']}%",
                expanded=(r["status"] != "PASS"),
            ):
                col_meta, col_stat = st.columns([3, 1])
                with col_meta:
                    st.markdown(f"**Description:** {r['description']}")
                    st.markdown(
                        f"**Severity:** <span style='color:{sev_color};font-weight:bold'>{r['severity']}</span>  "
                        f"&nbsp;&nbsp; **Domain:** `{r['domain']}`",
                        unsafe_allow_html=True,
                    )
                with col_stat:
                    st.metric("Pass Rate", f"{r['pass_rate']}%")
                    st.metric("Failures", r["failures"])

                if r["failing_records"]:
                    st.markdown(f"**Failing Records** (showing up to 50 of {r['failures']}):")
                    fail_df = pd.DataFrame(r["failing_records"])
                    st.dataframe(fail_df, use_container_width=True)

                    # Download CSV
                    csv_data = fail_df.to_csv(index=False)
                    st.download_button(
                        label=f"⬇ Download {r['check_id']} failures as CSV",
                        data=csv_data,
                        file_name=f"{r['check_id']}_failures.csv",
                        mime="text/csv",
                        key=f"dl_{r['check_id']}",
                    )

        # ── Full summary table ──
        st.markdown("---")
        st.markdown("**All Checks Summary**")
        summary_df = pd.DataFrame([{
            "Check ID": r["check_id"],
            "Name": r["check_name"],
            "Domain": r["domain"],
            "Severity": r["severity"],
            "Status": r["status"],
            "Checked": r["total_checked"],
            "Failures": r["failures"],
            "Pass Rate %": r["pass_rate"],
        } for r in results])
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        full_csv = summary_df.to_csv(index=False)
        st.download_button(
            "⬇ Download Full Check Summary CSV",
            data=full_csv,
            file_name="data_checks_summary.csv",
            mime="text/csv",
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7: DATA ENTRY (write-access roles only)
# ══════════════════════════════════════════════════════════════════════════════
if tab_entry is not None:
    with tab_entry:
        st.subheader("Patient Data Entry")
        st.caption(
            f"Logged in as **{current_user['name']}** (`{current_user['role']}`). "
            "All changes are audit-logged."
        )
        from app.entry import render_demographics_form, render_ae_form, render_discontinuation_form

        entry_section = st.radio(
            "Select Form",
            ["Demographics (R_DEM)", "Adverse Event (R_AEVBB)", "Discontinuation (R_DISC)"],
            horizontal=True,
        )
        st.markdown("---")

        db = get_db()
        if entry_section == "Demographics (R_DEM)":
            render_demographics_form(db, current_user)
        elif entry_section == "Adverse Event (R_AEVBB)":
            render_ae_form(db, current_user)
        elif entry_section == "Discontinuation (R_DISC)":
            render_discontinuation_form(db, current_user)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 8: AUDIT TRAIL (write-access roles only)
# ══════════════════════════════════════════════════════════════════════════════
if tab_audit is not None:
    with tab_audit:
        from app.entry import render_audit_log
        render_audit_log(get_db())
