import unittest
from workflow import validate_vendor, route_vendor, load_policies

class VendorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "vendor_id": "T-1", "company_name": "Example Vendor", "contact_email": "vendor@example.com",
            "service_category": "Software", "tax_status": "Verified", "security_impact": "Low",
            "handles_data": "No", "documents_complete": "Complete",
            "business_purpose": "Provide approved software licenses for the team."
        }

    def test_valid_vendor(self):
        _, valid, _ = validate_vendor(self.record)
        self.assertTrue(valid)

    def test_missing_purpose_invalid(self):
        row = dict(self.record, business_purpose="")
        _, valid, reason = validate_vendor(row)
        self.assertFalse(valid)
        self.assertIn("Missing required field", reason)

    def test_high_risk_routes_compliance(self):
        policies = load_policies()
        row = dict(self.record, security_impact="High")
        self.assertEqual(route_vendor(row, policies), "COMPLIANCE_REVIEW")

    def test_data_processing_routes_compliance(self):
        policies = load_policies()
        row = dict(self.record, service_category="Data Processing", handles_data="Yes")
        self.assertEqual(route_vendor(row, policies), "COMPLIANCE_REVIEW")

    def test_low_risk_routes_standard_procurement(self):
        policies = load_policies()
        self.assertEqual(route_vendor(self.record, policies), "STANDARD_PROCUREMENT_REVIEW")

if __name__ == "__main__":
    unittest.main()
