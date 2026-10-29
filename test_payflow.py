"""
Automated Verification Suite for PayFlow
Tests all endpoints, calculations, duplicate constraints, and CSV export.
"""

import unittest
import io
import csv
from app import app, get_db, seed_demo_data
from tax_engine import compute_tax_new_regime, compute_tax_old_regime, compare_tax_regimes, estimate_monthly_tds

class PayFlowTestSuite(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            seed_demo_data(force=True)

    def test_01_health_check(self):
        """Test health-check endpoint for Render"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['database'], 'connected')

    def test_02_dashboard(self):
        """Test dashboard page loads with metrics"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"PayFlow", response.data)
        self.assertIn(b"Executive Payroll Dashboard", response.data)

    def test_03_tax_engine_math(self):
        """Test income tax calculations for both regimes"""
        # Test 1: New Regime <= 7 Lakhs (Tax should be ₹0 due to Section 87A rebate)
        res_7L = compute_tax_new_regime(700000.0)
        self.assertEqual(res_7L["total_tax_payable"], 0.0)
        self.assertEqual(res_7L["standard_deduction"], 75000.0)

        # Test 2: New Regime 10 Lakhs (Gross 10L - 75k SD = 9.25L Taxable)
        # Slabs: 0-3L 0, 3-7L 5% (20k), 7-9.25L 10% (22.5k) = 42,500 + 4% cess (1,700) = 44,200
        res_10L = compute_tax_new_regime(1000000.0)
        self.assertEqual(res_10L["total_tax_payable"], 44200.0)

        # Test 3: Old Regime 5 Lakhs (Tax should be ₹0 due to Section 87A rebate)
        res_old_5L = compute_tax_old_regime(500000.0)
        self.assertEqual(res_old_5L["total_tax_payable"], 0.0)

        # Test 4: Comparison
        comp = compare_tax_regimes(1200000.0, deduction_80c=150000.0, deduction_80d=25000.0)
        self.assertIn(comp["recommended"], ["new", "old", "equal"])
        self.assertTrue(comp["tax_savings"] >= 0)

    def test_04_employee_crud(self):
        """Test adding, editing, and deleting an employee"""
        # Add employee
        emp_data = {
            "emp_code": "EMP999",
            "first_name": "Test",
            "last_name": "User",
            "email": "test.user@payflow.test",
            "phone": "9999988888",
            "department": "Engineering",
            "designation": "QA Analyst",
            "date_of_joining": "2024-01-01",
            "pan_number": "ABCDE1234F",
            "tax_regime": "new",
            "basic_salary": "50000",
            "hra": "20000",
            "special_allowance": "10000",
            "pf_applicable": "1",
            "custom_pf_rate": "12.0",
            "status": "Active"
        }
        res_add = self.client.post('/employees/add', data=emp_data, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b"EMP999", res_add.data)

        # Verify in DB
        with app.app_context():
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT id FROM employees WHERE emp_code = 'EMP999';")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            emp_id = row['id']

        # Edit employee
        emp_data['first_name'] = "TestUpdated"
        res_edit = self.client.post(f'/employees/edit/{emp_id}', data=emp_data, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b"TestUpdated", res_edit.data)

        # Delete employee
        res_del = self.client.post(f'/employees/delete/{emp_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIn(b"deleted", res_del.data)

        # Confirm deleted from database
        with app.app_context():
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT id FROM employees WHERE id = ?;", (emp_id,))
            self.assertIsNone(cur.fetchone())

    def test_05_payroll_duplicate_prevention(self):
        """Test payroll calculation and duplicate prevention constraint"""
        with app.app_context():
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT id FROM employees WHERE emp_code = 'EMP101';")
            emp_id = cur.fetchone()['id']

        # Try to process payroll for EMP101 for current month (already seeded)
        import datetime
        cur_month = datetime.datetime.now().strftime("%Y-%m")
        payroll_data = {
            "employee_id": str(emp_id),
            "payroll_month": cur_month,
            "pay_date": "2026-10-28",
            "basic_salary": "95000",
            "hra": "38000",
            "special_allowance": "17000",
            "bonus_overtime": "0",
            "pf_deduction": "11400",
            "pt_deduction": "200",
            "tax_tds_deduction": "10000",
            "other_deductions": "0",
            "tax_regime_used": "new"
        }
        res = self.client.post('/payroll/process', data=payroll_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        # Duplicate error warning must appear
        self.assertIn(b"Duplicate Error", res.data)

    def test_06_payslip_and_pdf(self):
        """Test payslip rendering with Indian words and print preview"""
        with app.app_context():
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT id FROM payrolls LIMIT 1;")
            pid = cur.fetchone()['id']

        res = self.client.get(f'/payslip/{pid}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Salary Payslip", res.data)
        self.assertIn(b"Rupees", res.data)
        self.assertIn(b"Print / Save as PDF", res.data)

    def test_07_csv_export(self):
        """Test CSV export generation via Python built-in csv module"""
        import datetime
        cur_month = datetime.datetime.now().strftime("%Y-%m")
        res = self.client.get(f'/reports/export-csv?month={cur_month}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Content-Type'), 'text/csv; charset=utf-8')
        self.assertIn(b"attachment; filename=PayFlow_Payroll_Report_", res.headers.get('Content-Disposition').encode())
        
        # Verify CSV content is parseable
        csv_file = io.StringIO(res.data.decode('utf-8'))
        reader = csv.reader(csv_file)
        rows = list(reader)
        self.assertTrue(len(rows) > 1)
        self.assertIn("Employee Code", rows[0])
        self.assertIn("Net Salary (INR)", rows[0])

    def test_08_tax_calculator_post(self):
        """Test interactive tax calculator POST with Old Regime deductions"""
        calc_data = {
            "gross_annual": "1500000",
            "regime_choice": "compare",
            "deduction_80c": "150000",
            "deduction_80d": "30000",
            "hra_exemption": "120000",
            "home_loan_interest_24b": "100000",
            "other_deductions": "0"
        }
        res = self.client.post('/tax-calculator', data=calc_data)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Engine Recommendation Result", res.data)
        self.assertIn(b"New Tax Regime", res.data)
        self.assertIn(b"Old Tax Regime", res.data)

    def test_09_batch_payroll_processing(self):
        """Test batch payroll processing for a future month"""
        batch_data = {
            "target_month": "2026-11",
            "pay_date": "2026-11-28"
        }
        res = self.client.post('/payroll/batch-process', data=batch_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Batch Run Complete", res.data)

        # Verify payroll count for 2026-11 matches active employee count
        with app.app_context():
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT COUNT(*) FROM employees WHERE status = 'Active';")
            emp_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM payrolls WHERE payroll_month = '2026-11';")
            pay_count = cur.fetchone()[0]
            self.assertEqual(emp_count, pay_count)

    def test_10_reports_filtering(self):
        """Test reports page with department and month filters"""
        res = self.client.get('/reports?department=Engineering')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Comprehensive Payroll Reports", res.data)
        self.assertIn(b"Engineering", res.data)


if __name__ == '__main__':
    unittest.main()
