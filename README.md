# Vendor Onboarding & Compliance Governance Workflow

A Streamlit prototype demonstrating enterprise vendor intake, data validation, compliance checks, risk-based workflow routing, human approval, quarantine handling, audit logging, and workflow metrics.

## Run on macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Test
```bash
python -m unittest test_workflow.py -v
```

## Main pages
- Overview
- Submit Vendor
- Vendor Register
- Governance & Compliance
- Approval Queue
- Audit & Metrics

## Governance controls demonstrated
- Required-field and email validation
- Allowed-value validation for tax status, risk impact and document completeness
- Duplicate vendor ID detection and quarantine
- Configurable policy version and risk-based routing
- Separate procurement and compliance approver roles
- Human decision notes for rejection, hold and request-information actions
- Timestamped audit events and CSV exports
- Data minimization and synthetic-data warning

## Limitations
This is an educational prototype, not a production procurement or compliance platform. Role selection is a demo and not authentication. No real vendor onboarding, payments, contracts, or external systems are connected. Audit events are not cryptographically tamper-proof. Use synthetic data only.
