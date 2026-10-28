import streamlit as st
import pandas as pd
from workflow import (
    init_db, load_policies, process_vendors, get_vendors, get_events,
    get_quarantine, get_metrics, review_vendor
)

st.set_page_config(page_title="Vendor Onboarding & Compliance", page_icon="📋", layout="wide")
init_db()

st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
div[data-testid="stMetric"] {background-color:#1e293b;border:1px solid #334155;padding:16px;border-radius:12px;}
div[data-testid="stMetricLabel"] {color:#cbd5e1 !important;}
div[data-testid="stMetricValue"] {color:#f8fafc !important;}
</style>
""", unsafe_allow_html=True)

st.title("📋 Vendor Onboarding & Compliance Governance")
st.caption("Enterprise workflow automation · Compliance validation · Risk-based routing · Auditability")

with st.sidebar:
    st.header("Workspace")
    role = st.selectbox("Demo role", ["Vendor Submitter", "Procurement Approver", "Compliance Approver", "Administrator", "Auditor"])
    actor_id = st.text_input("Demo user ID", value={
        "Vendor Submitter": "VENDOR-DEMO-01",
        "Procurement Approver": "PROC-APPROVER-01",
        "Compliance Approver": "COMP-APPROVER-01",
        "Administrator": "ADMIN-01",
        "Auditor": "AUDITOR-01"
    }[role])
    st.divider()
    page = st.radio("Navigate", [
        "Overview", "Submit Vendor", "Vendor Register",
        "Governance & Compliance", "Approval Queue", "Audit & Metrics"
    ])
    st.divider()
    st.caption("Use synthetic data only. Role selection demonstrates permissions; it is not production authentication.")

policies = load_policies()

if page == "Overview":
    st.subheader("Enterprise onboarding overview")
    st.write("Validate vendor records, apply configurable compliance rules, route cases by risk, and record human decisions.")
    m = get_metrics()
    cols = st.columns(5)
    cols[0].metric("Total vendors", m["total"])
    cols[1].metric("Pending review", m["pending"])
    cols[2].metric("Compliance review", m["compliance_review"])
    cols[3].metric("Approved", m["approved"])
    cols[4].metric("Quarantined", m["quarantined"])
    st.markdown("### Workflow stages")
    for title, desc in [
        ("Vendor intake", "Capture company, contact, service category, tax identifier status and risk declaration."),
        ("Data quality checks", "Validate required fields, email format, allowed categories and duplicate vendor IDs."),
        ("Governance and compliance", "Check document completeness, data classification, risk flags and policy requirements."),
        ("Risk-based routing", "Route low-risk vendors to procurement and higher-risk or incomplete cases to compliance review."),
        ("Human decision", "Authorized reviewers approve, reject, hold or request further information."),
        ("Audit and monitoring", "Record policy version, status changes, review notes, timestamps and workflow metrics.")
    ]:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.write(desc)
    st.info("This is an educational prototype. Do not enter real tax identifiers, bank details, contracts, or sensitive vendor data.")

elif page == "Submit Vendor":
    st.subheader("Submit a vendor for onboarding")
    with st.form("vendor_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            vendor_id = st.text_input("Vendor ID", placeholder="VEN-2001")
            company_name = st.text_input("Company name", placeholder="Northstar Digital Services")
            contact_email = st.text_input("Business contact email", placeholder="contact@example.com")
            service_category = st.selectbox("Service category", ["Software", "Consulting", "Hardware", "Facilities", "Data Processing", "Other"])
        with c2:
            tax_status = st.selectbox("Tax documentation status", ["Verified", "Pending", "Missing"])
            security_review = st.selectbox("Security / privacy impact", ["Low", "Medium", "High"])
            handles_data = st.selectbox("Will vendor process company/customer data?", ["No", "Yes"])
            documents_complete = st.selectbox("Required onboarding documents", ["Complete", "Incomplete"])
        justification = st.text_area("Business purpose", placeholder="Describe why the vendor is needed.")
        submitted = st.form_submit_button("Validate and submit vendor", type="primary", use_container_width=True)
    if submitted:
        record = {
            "vendor_id": vendor_id, "company_name": company_name, "contact_email": contact_email,
            "service_category": service_category, "tax_status": tax_status,
            "security_impact": security_review, "handles_data": handles_data,
            "documents_complete": documents_complete, "business_purpose": justification
        }
        try:
            result = process_vendors(pd.DataFrame([record]), source="streamlit-form", actor=actor_id)
            if result["accepted_count"]:
                st.success(f"Vendor submitted. Proposed route: {result['last_route']}.")
            else:
                st.error(f"Vendor not accepted: {result['last_reason']}")
        except Exception as e:
            st.error(f"Submission failed: {e}")

elif page == "Vendor Register":
    st.subheader("Vendor register")
    df = get_vendors()
    if df.empty:
        st.info("No vendors yet. Load synthetic demo data below.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download vendor register (CSV)", df.to_csv(index=False).encode(), "vendor_register.csv", "text/csv")
    with st.expander("Load synthetic demo vendors"):
        st.write("Loads fictional examples, including a missing-document case and a duplicate/invalid test case.")
        if st.button("Load sample vendors", type="primary"):
            try:
                sample = pd.read_csv("sample_vendors.csv")
                result = process_vendors(sample, source="sample:sample_vendors.csv", actor=actor_id)
                st.success(f"Accepted: {result['accepted_count']} · Quarantined: {result['quarantined_count']}")
                if result["accepted_count"] == 0:
                    st.info("No new records added. They may already exist; check the register and quarantine report.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not load sample data: {e}")

elif page == "Governance & Compliance":
    st.subheader("Governance and compliance controls")
    st.write(f"Active policy version: **{policies['policy_version']}**")
    st.markdown("### Active policy configuration")
    st.json(policies)
    for title, desc in [
        ("Purpose limitation", "Collect only vendor information required for procurement and compliance assessment."),
        ("Data minimization", "The prototype does not collect bank account details, identity scans or real tax identifiers."),
        ("Document completeness", "Missing or incomplete onboarding documents trigger compliance review or quarantine as configured."),
        ("Risk-based review", "High security/privacy impact or data-processing vendors require compliance approval."),
        ("Separation of duties", "Compliance and procurement routes require the appropriate reviewer role."),
        ("Duplicate handling", "Duplicate vendor IDs are quarantined and logged rather than silently overwritten."),
        ("Auditability", "Record ingestion, routing, approval actions and errors with timestamps and policy version."),
        ("Retention", "A production system should implement an approved retention and deletion schedule.")
    ]:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.write(desc)
    st.markdown("### Quarantined records")
    rejected = get_quarantine()
    if rejected.empty:
        st.info("No quarantined records.")
    else:
        st.dataframe(rejected, use_container_width=True, hide_index=True)
        st.download_button("Download quarantine report", rejected.to_csv(index=False).encode(), "vendor_quarantine.csv", "text/csv")
    st.warning("This prototype demonstrates compliance workflow concepts; it does not certify legal or regulatory compliance.")

elif page == "Approval Queue":
    st.subheader("Human approval queue")
    df = get_vendors(pending_only=True)
    if df.empty:
        st.info("No pending vendor reviews.")
    else:
        st.dataframe(df[["vendor_id", "company_name", "service_category", "tax_status", "security_impact", "handles_data", "proposed_route", "status"]], use_container_width=True, hide_index=True)
        vendor_id = st.selectbox("Select vendor", df["vendor_id"].astype(str).tolist())
        row = df[df["vendor_id"].astype(str) == vendor_id].iloc[0].to_dict()
        with st.container(border=True):
            st.markdown(f"### {row['vendor_id']} · {row['company_name']}")
            st.write(f"**Service:** {row['service_category']} · **Tax status:** {row['tax_status']}")
            st.write(f"**Security impact:** {row['security_impact']} · **Processes data:** {row['handles_data']}")
            st.write(f"**Proposed route:** {row['proposed_route']}")
            st.write(f"**Business purpose:** {row['business_purpose']}")
        action = st.selectbox("Decision", ["APPROVE", "REJECT", "HOLD", "REQUEST_INFO"])
        notes = st.text_area("Review notes (required for reject, hold or request-info)")
        if st.button("Record decision", type="primary"):
            try:
                review_vendor(vendor_id, action, actor_id, role, notes)
                st.success("Decision recorded in the audit trail.")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    st.caption("Approval is simulated; no real vendor account or payment setup is performed.")

elif page == "Audit & Metrics":
    st.subheader("Audit trail and workflow metrics")
    m = get_metrics()
    cols = st.columns(4)
    cols[0].metric("Validation acceptance", f"{m['acceptance_rate']:.1f}%")
    cols[1].metric("Review completion", f"{m['review_completion_rate']:.1f}%")
    cols[2].metric("Approval rate", f"{m['approval_rate']:.1f}%")
    cols[3].metric("Audit events", m["event_count"])
    events = get_events()
    st.markdown("### Audit events")
    if events.empty:
        st.info("No audit events yet.")
    else:
        st.dataframe(events, use_container_width=True, hide_index=True)
        st.download_button("Export audit log (CSV)", events.to_csv(index=False).encode(), "vendor_audit_log.csv", "text/csv")
    st.markdown("### Metrics detail")
    st.json(m)
