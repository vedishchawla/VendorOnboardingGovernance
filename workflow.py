import json
import sqlite3
from datetime import datetime, timezone
import pandas as pd

DB_PATH = "vendor_onboarding.db"
POLICY_PATH = "policies.json"
REQUIRED = ["vendor_id", "company_name", "contact_email", "service_category", "tax_status",
            "security_impact", "handles_data", "documents_complete", "business_purpose"]
CATEGORIES = {"Software", "Consulting", "Hardware", "Facilities", "Data Processing", "Other"}
TAX_STATUSES = {"Verified", "Pending", "Missing"}
IMPACTS = {"Low", "Medium", "High"}
YES_NO = {"Yes", "No"}
DOC_STATUSES = {"Complete", "Incomplete"}

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def connect():
    return sqlite3.connect(DB_PATH, timeout=10)

def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS vendors(
            vendor_id TEXT PRIMARY KEY, company_name TEXT, contact_email TEXT, service_category TEXT,
            tax_status TEXT, security_impact TEXT, handles_data TEXT, documents_complete TEXT,
            business_purpose TEXT, proposed_route TEXT, status TEXT, policy_version TEXT,
            source TEXT, created_at TEXT, updated_at TEXT, reviewer_id TEXT, reviewer_role TEXT, review_notes TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS quarantine(
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, source TEXT, vendor_id TEXT, reason TEXT, record_json TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS audit_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, event_type TEXT, vendor_id TEXT,
            actor TEXT, actor_role TEXT, policy_version TEXT, details TEXT
        )""")

def load_policies():
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def log_event(event_type, vendor_id="", actor="SYSTEM", role="System", details="", version=""):
    with connect() as con:
        con.execute("""INSERT INTO audit_events(timestamp,event_type,vendor_id,actor,actor_role,policy_version,details)
                       VALUES(?,?,?,?,?,?,?)""",
                    (now_iso(), event_type, str(vendor_id or ""), actor, role, version, str(details)))

def validate_vendor(row):
    record = {str(k).strip(): ("" if pd.isna(v) else str(v).strip()) for k, v in row.items()}
    for field in REQUIRED:
        if not record.get(field, ""):
            return record, False, f"Missing required field: {field}"
    email = record["contact_email"]
    if "@" not in email or "." not in email.split("@")[-1]:
        return record, False, "Invalid business contact email"
    checks = [
        ("service_category", CATEGORIES), ("tax_status", TAX_STATUSES),
        ("security_impact", IMPACTS), ("handles_data", YES_NO),
        ("documents_complete", DOC_STATUSES)
    ]
    for field, allowed in checks:
        if record[field] not in allowed:
            return record, False, f"Invalid value for {field}"
    if len(record["business_purpose"]) < 10:
        return record, False, "Business purpose must contain at least 10 characters"
    return record, True, "Valid vendor record"

def route_vendor(record, policies):
    rules = policies["routing"]
    if (record["security_impact"] == "High" or record["handles_data"] == "Yes"
            or record["service_category"] == "Data Processing"
            or record["tax_status"] == "Missing" or record["documents_complete"] == "Incomplete"):
        return "COMPLIANCE_REVIEW"
    if record["tax_status"] == "Pending" or record["security_impact"] == "Medium":
        return "PROCUREMENT_MANAGER_REVIEW"
    return "STANDARD_PROCUREMENT_REVIEW"

def process_vendors(df, source="upload", actor="SYSTEM"):
    init_db()
    missing = sorted(set(REQUIRED) - {str(c).strip() for c in df.columns})
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    policies = load_policies()
    result = {"total": len(df), "accepted_count": 0, "quarantined_count": 0, "last_route": "", "last_reason": ""}
    seen = set()
    for raw in df.to_dict(orient="records"):
        record, valid, reason = validate_vendor(raw)
        vid = record.get("vendor_id", "")
        log_event("VENDOR_INGESTED", vid, actor, "System", f"source={source}", policies["policy_version"])
        if not valid:
            quarantine(record, source, reason, policies["policy_version"])
            result["quarantined_count"] += 1
            result["last_reason"] = reason
            continue
        if vid in seen or vendor_exists(vid):
            quarantine(record, source, "Duplicate vendor_id; record quarantined", policies["policy_version"])
            log_event("DUPLICATE_DETECTED", vid, actor, "System", f"source={source}", policies["policy_version"])
            result["quarantined_count"] += 1
            result["last_reason"] = "Duplicate vendor_id; record quarantined"
            continue
        seen.add(vid)
        route = route_vendor(record, policies)
        with connect() as con:
            con.execute("""INSERT INTO vendors(
                vendor_id,company_name,contact_email,service_category,tax_status,security_impact,handles_data,
                documents_complete,business_purpose,proposed_route,status,policy_version,source,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vid, record["company_name"], record["contact_email"], record["service_category"], record["tax_status"],
             record["security_impact"], record["handles_data"], record["documents_complete"], record["business_purpose"],
             route, "PENDING_REVIEW", policies["policy_version"], source, now_iso(), now_iso()))
        log_event("VENDOR_VALIDATED_ROUTED", vid, actor, "System", f"route={route}", policies["policy_version"])
        result["accepted_count"] += 1
        result["last_route"] = route
    log_event("BATCH_COMPLETED", "", actor, "System", json.dumps(result), policies["policy_version"])
    return result

def vendor_exists(vid):
    with connect() as con:
        return con.execute("SELECT 1 FROM vendors WHERE vendor_id=?", (str(vid),)).fetchone() is not None

def quarantine(record, source, reason, version):
    with connect() as con:
        con.execute("INSERT INTO quarantine(timestamp,source,vendor_id,reason,record_json) VALUES(?,?,?,?,?)",
                    (now_iso(), source, str(record.get("vendor_id", "")), reason, json.dumps(record, ensure_ascii=False)))
    log_event("VENDOR_QUARANTINED", record.get("vendor_id", ""), "SYSTEM", "System", reason, version)

def review_vendor(vendor_id, action, actor, role, notes):
    policies = load_policies()
    allowed = {
        "COMPLIANCE_REVIEW": {"Compliance Approver", "Administrator"},
        "PROCUREMENT_MANAGER_REVIEW": {"Procurement Approver", "Administrator"},
        "STANDARD_PROCUREMENT_REVIEW": {"Procurement Approver", "Administrator"}
    }
    with connect() as con:
        row = con.execute("SELECT proposed_route,status FROM vendors WHERE vendor_id=?", (str(vendor_id),)).fetchone()
    if not row:
        raise ValueError("Vendor not found.")
    route, status = row
    if status != "PENDING_REVIEW":
        raise ValueError("Vendor is not pending review.")
    if role not in allowed.get(route, set()):
        log_event("UNAUTHORIZED_ACTION", vendor_id, actor, role, f"action={action}; route={route}", policies["policy_version"])
        raise PermissionError(f"Role '{role}' is not authorized for route '{route}'.")
    if action not in {"APPROVE", "REJECT", "HOLD", "REQUEST_INFO"}:
        raise ValueError("Unsupported review action.")
    if action in {"REJECT", "HOLD", "REQUEST_INFO"} and not notes.strip():
        raise ValueError("Review notes are required for reject, hold, and request-information actions.")
    new_status = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "HOLD": "ON_HOLD", "REQUEST_INFO": "AWAITING_INFORMATION"}[action]
    with connect() as con:
        con.execute("""UPDATE vendors SET status=?,updated_at=?,reviewer_id=?,reviewer_role=?,review_notes=?
                       WHERE vendor_id=?""", (new_status, now_iso(), actor, role, notes.strip(), str(vendor_id)))
    log_event("HUMAN_DECISION_RECORDED", vendor_id, actor, role,
              f"action={action}; status={new_status}; notes={notes.strip()}", policies["policy_version"])

def get_vendors(pending_only=False):
    init_db()
    with connect() as con:
        q = "SELECT * FROM vendors ORDER BY created_at DESC"
        if pending_only:
            q = "SELECT * FROM vendors WHERE status='PENDING_REVIEW' ORDER BY created_at"
        return pd.read_sql_query(q, con)

def get_events():
    init_db()
    with connect() as con:
        return pd.read_sql_query("SELECT * FROM audit_events ORDER BY id DESC", con)

def get_quarantine():
    init_db()
    with connect() as con:
        return pd.read_sql_query("SELECT timestamp,source,vendor_id,reason,record_json FROM quarantine ORDER BY id DESC", con)

def get_metrics():
    init_db()
    with connect() as con:
        total = con.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM vendors WHERE status='PENDING_REVIEW'").fetchone()[0]
        compliance = con.execute("SELECT COUNT(*) FROM vendors WHERE proposed_route='COMPLIANCE_REVIEW' AND status='PENDING_REVIEW'").fetchone()[0]
        approved = con.execute("SELECT COUNT(*) FROM vendors WHERE status='APPROVED'").fetchone()[0]
        quarantined = con.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
        reviewed = con.execute("SELECT COUNT(*) FROM vendors WHERE status!='PENDING_REVIEW'").fetchone()[0]
        events = con.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    denom = total + quarantined
    return {
        "total": total, "pending": pending, "compliance_review": compliance, "approved": approved,
        "quarantined": quarantined, "event_count": events,
        "acceptance_rate": total / denom * 100 if denom else 0.0,
        "review_completion_rate": reviewed / total * 100 if total else 0.0,
        "approval_rate": approved / total * 100 if total else 0.0
    }
