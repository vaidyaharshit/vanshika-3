"""
PayFlow — Automated Payroll Management & Income Tax Calculation Engine
======================================================================
College Project - Full Stack Python Application
Flask + Jinja2 + Pure HTML/CSS + SQLite3 + Gunicorn
Ready for Render Deployment
"""

import os
import sqlite3
import csv
import io
from datetime import datetime
from typing import Optional, List, Dict, Any
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    Response,
    g
)

from tax_engine import (
    compute_tax_new_regime,
    compute_tax_old_regime,
    compare_tax_regimes,
    estimate_monthly_tds
)

# Initialize Flask App
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "payflow-secure-college-project-key-2026")

# Database Path Configuration
# Supports Render Persistent Disk via DATABASE_PATH environment variable (e.g. /var/data/payflow.db)
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "payflow.db"))


# --- DATABASE CONNECTION & HELPERS ---

def get_db() -> sqlite3.Connection:
    """Provides a thread-safe SQLite connection per request."""
    if "db" not in g:
        # Ensure directory exists for persistent disks
        db_dir = os.path.dirname(DATABASE_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


@app.teardown_appcontext
def close_db(exception: Optional[BaseException] = None) -> None:
    """Closes database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """Initializes tables and indexes automatically on application startup."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Employees table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_code TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                department TEXT NOT NULL,
                designation TEXT NOT NULL,
                date_of_joining TEXT NOT NULL,
                pan_number TEXT,
                tax_regime TEXT DEFAULT 'new',
                basic_salary REAL NOT NULL DEFAULT 0.0,
                hra REAL NOT NULL DEFAULT 0.0,
                special_allowance REAL NOT NULL DEFAULT 0.0,
                pf_applicable INTEGER DEFAULT 1,
                custom_pf_rate REAL DEFAULT 12.0,
                annual_80c REAL DEFAULT 0.0,
                annual_80d REAL DEFAULT 0.0,
                annual_hra_exemption REAL DEFAULT 0.0,
                bank_account TEXT,
                bank_ifsc TEXT,
                status TEXT DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Payrolls table with UNIQUE constraint on (employee_id, payroll_month)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payrolls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                payroll_month TEXT NOT NULL,
                pay_date TEXT NOT NULL,
                basic_salary REAL NOT NULL,
                hra REAL NOT NULL,
                special_allowance REAL NOT NULL,
                bonus_overtime REAL DEFAULT 0.0,
                gross_salary REAL NOT NULL,
                pf_deduction REAL DEFAULT 0.0,
                pt_deduction REAL DEFAULT 200.0,
                tax_tds_deduction REAL DEFAULT 0.0,
                other_deductions REAL DEFAULT 0.0,
                total_deductions REAL NOT NULL,
                net_salary REAL NOT NULL,
                tax_regime_used TEXT DEFAULT 'new',
                status TEXT DEFAULT 'Processed',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                UNIQUE(employee_id, payroll_month)
            );
        """)

        # Indexes for fast querying
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payrolls_month ON payrolls(payroll_month);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_employees_dept ON employees(department);")
        db.commit()


# --- NUMBER TO WORDS (INDIAN NUMBERING FORMAT) ---

def number_to_inr_words(num: float) -> str:
    """
    Converts a numeric amount to Indian English words.
    E.g., 64800 -> 'Rupees Sixty-Four Thousand Eight Hundred Only'
    """
    try:
        n = int(round(num))
    except (ValueError, TypeError):
        return "Rupees Zero Only"

    if n == 0:
        return "Rupees Zero Only"

    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def convert_hundred(val: int) -> str:
        res = ""
        if val >= 100:
            res += ones[val // 100] + " Hundred "
            val %= 100
        if val >= 20:
            res += tens[val // 10] + " "
            val %= 10
        if val > 0:
            res += ones[val] + " "
        return res.strip()

    crore = n // 10000000
    n %= 10000000
    lakh = n // 100000
    n %= 100000
    thousand = n // 1000
    n %= 1000
    remainder = n

    parts = []
    if crore > 0:
        parts.append(f"{convert_hundred(crore)} Crore")
    if lakh > 0:
        parts.append(f"{convert_hundred(lakh)} Lakh")
    if thousand > 0:
        parts.append(f"{convert_hundred(thousand)} Thousand")
    if remainder > 0:
        parts.append(convert_hundred(remainder))

    return "Rupees " + " ".join(parts).strip() + " Only"


# Register template filters
@app.template_filter("inr")
def inr_format(val) -> str:
    """Formats a number as Indian Currency string: e.g. ₹75,000.00"""
    try:
        val = float(val)
        return f"₹{val:,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"

@app.template_filter("inr_clean")
def inr_clean_format(val) -> str:
    """Formats without decimal if clean: e.g. ₹75,000"""
    try:
        val = float(val)
        if val.is_integer():
            return f"₹{int(val):,}"
        return f"₹{val:,.2f}"
    except (ValueError, TypeError):
        return "₹0"


# --- SEED DEMO DATA HELPER ---

def seed_demo_data(force: bool = False) -> int:
    """Seeds realistic corporate employees and payroll records for college demonstration."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM employees;")
        if cursor.fetchone()["count"] > 0 and not force:
            return 0

        if force:
            cursor.execute("DELETE FROM payrolls;")
            cursor.execute("DELETE FROM employees;")

        sample_employees = [
            ("EMP101", "Aarav", "Sharma", "aarav.sharma@payflow.internal", "+91 98765 43210", "Engineering", "Senior Software Architect", "2023-03-15", "ABCPS1234A", "new", 95000.0, 38000.0, 17000.0, 1, 12.0, 150000.0, 25000.0, 0.0, "918273645019", "HDFC0001234", "Active"),
            ("EMP102", "Priya", "Nair", "priya.nair@payflow.internal", "+91 98765 43211", "Human Resources", "HR Operations Lead", "2023-06-01", "BCDPS2345B", "new", 48000.0, 19200.0, 8800.0, 1, 12.0, 50000.0, 15000.0, 0.0, "827163549102", "ICIC0005678", "Active"),
            ("EMP103", "Rohan", "Verma", "rohan.verma@payflow.internal", "+91 98765 43212", "Finance", "Senior Financial Analyst", "2022-11-10", "CDEPS3456C", "old", 70000.0, 28000.0, 12000.0, 1, 12.0, 150000.0, 35000.0, 96000.0, "736251498203", "SBIN0004321", "Active"),
            ("EMP104", "Ananya", "Deshmukh", "ananya.d@payflow.internal", "+91 98765 43213", "Marketing", "Brand Marketing Specialist", "2024-01-15", "DEPES4567D", "new", 42000.0, 16800.0, 7200.0, 1, 12.0, 0.0, 0.0, 0.0, "645372819034", "KKBK0008765", "Active"),
            ("EMP105", "Vikram", "Malhotra", "vikram.m@payflow.internal", "+91 98765 43214", "Engineering", "Principal DevOps Engineer", "2022-04-20", "EFGPS5678E", "new", 115000.0, 46000.0, 21000.0, 1, 12.0, 150000.0, 25000.0, 0.0, "536271829045", "UTIB0009876", "Active"),
            ("EMP106", "Sneha", "Kulkarni", "sneha.k@payflow.internal", "+91 98765 43215", "Sales", "Corporate Account Director", "2023-08-01", "FGIPS6789F", "old", 85000.0, 34000.0, 15000.0, 1, 12.0, 150000.0, 40000.0, 120000.0, "425364758697", "HDFC0004567", "Active"),
            ("EMP107", "Karan", "Patel", "karan.p@payflow.internal", "+91 98765 43216", "Operations", "Supply Chain Coordinator", "2024-02-10", "GHIJS7890G", "new", 35000.0, 14000.0, 6000.0, 1, 12.0, 0.0, 0.0, 0.0, "314253647586", "PUNB0006543", "Active"),
            ("EMP108", "Meera", "Iyer", "meera.iyer@payflow.internal", "+91 98765 43217", "Engineering", "Frontend UI/UX Engineer", "2024-05-02", "HIJKS8901H", "new", 55000.0, 22000.0, 9500.0, 1, 12.0, 60000.0, 15000.0, 0.0, "203142536475", "ICIC0007890", "Active")
        ]

        cursor.executemany("""
            INSERT INTO employees (
                emp_code, first_name, last_name, email, phone, department, designation,
                date_of_joining, pan_number, tax_regime, basic_salary, hra, special_allowance,
                pf_applicable, custom_pf_rate, annual_80c, annual_80d, annual_hra_exemption,
                bank_account, bank_ifsc, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, sample_employees)
        db.commit()

        # Pre-process current month payroll for the employees
        current_month = datetime.now().strftime("%Y-%m")
        pay_date = datetime.now().strftime("%Y-%m-28")

        cursor.execute("SELECT * FROM employees WHERE status = 'Active';")
        active_emps = cursor.fetchall()

        for emp in active_emps:
            basic = emp["basic_salary"]
            hra = emp["hra"]
            special = emp["special_allowance"]
            gross = basic + hra + special
            pf = round(basic * (emp["custom_pf_rate"] / 100.0), 2) if emp["pf_applicable"] else 0.0
            pt = 200.0
            tds = estimate_monthly_tds(
                monthly_gross=gross,
                regime=emp["tax_regime"],
                annual_80c=emp["annual_80c"],
                annual_80d=emp["annual_80d"],
                annual_hra_exemption=emp["annual_hra_exemption"]
            )
            total_ded = round(pf + pt + tds, 2)
            net = round(gross - total_ded, 2)

            cursor.execute("""
                INSERT OR IGNORE INTO payrolls (
                    employee_id, payroll_month, pay_date, basic_salary, hra, special_allowance,
                    bonus_overtime, gross_salary, pf_deduction, pt_deduction, tax_tds_deduction,
                    other_deductions, total_deductions, net_salary, tax_regime_used, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                emp["id"], current_month, pay_date, basic, hra, special,
                0.0, gross, pf, pt, tds, 0.0, total_ded, net,
                emp["tax_regime"], "Processed", "Regular monthly payroll run"
            ))

        db.commit()
        return len(sample_employees)


# --- ROUTES: 1. DASHBOARD ---

@app.route("/")
def dashboard():
    """
    Main Executive Dashboard.
    Provides real-time payroll metrics, tax withholdings, and employee summary.
    """
    db = get_db()
    cursor = db.cursor()

    # Default to current month or latest available month
    cursor.execute("SELECT DISTINCT payroll_month FROM payrolls ORDER BY payroll_month DESC LIMIT 1;")
    latest_month_row = cursor.fetchone()
    current_month = latest_month_row["payroll_month"] if latest_month_row else datetime.now().strftime("%Y-%m")

    # Metrics
    cursor.execute("SELECT COUNT(*) AS total_employees FROM employees WHERE status = 'Active';")
    total_employees = cursor.fetchone()["total_employees"]

    cursor.execute("""
        SELECT 
            COUNT(id) AS payroll_count,
            COALESCE(SUM(gross_salary), 0) AS total_gross,
            COALESCE(SUM(net_salary), 0) AS total_net,
            COALESCE(SUM(tax_tds_deduction), 0) AS total_tax,
            COALESCE(SUM(pf_deduction), 0) AS total_pf,
            COALESCE(SUM(total_deductions), 0) AS total_deductions
        FROM payrolls
        WHERE payroll_month = ?;
    """, (current_month,))
    stats = cursor.fetchone()

    # Department breakdown
    cursor.execute("""
        SELECT 
            e.department,
            COUNT(p.id) AS emp_count,
            COALESCE(SUM(p.net_salary), 0) AS dept_net_total,
            COALESCE(SUM(p.gross_salary), 0) AS dept_gross_total
        FROM payrolls p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.payroll_month = ?
        GROUP BY e.department
        ORDER BY dept_net_total DESC;
    """, (current_month,))
    dept_breakdown = cursor.fetchall()

    # Recent payroll records
    cursor.execute("""
        SELECT 
            p.*,
            e.emp_code,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            e.designation
        FROM payrolls p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.payroll_month = ?
        ORDER BY p.net_salary DESC
        LIMIT 8;
    """, (current_month,))
    recent_payrolls = cursor.fetchall()

    # Available months for selector
    cursor.execute("SELECT DISTINCT payroll_month FROM payrolls ORDER BY payroll_month DESC;")
    available_months = [row["payroll_month"] for row in cursor.fetchall()]
    if current_month not in available_months:
        available_months.insert(0, current_month)

    return render_template(
        "dashboard.html",
        current_month=current_month,
        available_months=available_months,
        total_employees=total_employees,
        stats=stats,
        dept_breakdown=dept_breakdown,
        recent_payrolls=recent_payrolls
    )


# --- ROUTES: 2. EMPLOYEE MANAGEMENT ---

@app.route("/employees")
def employees_list():
    """View all employees with optional search and department filter."""
    db = get_db()
    cursor = db.cursor()

    search_query = request.args.get("search", "").strip()
    dept_filter = request.args.get("department", "").strip()

    sql = "SELECT * FROM employees WHERE 1=1"
    params = []

    if search_query:
        sql += " AND (first_name LIKE ? OR last_name LIKE ? OR emp_code LIKE ? OR email LIKE ?)"
        wildcard = f"%{search_query}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    if dept_filter:
        sql += " AND department = ?"
        params.append(dept_filter)

    sql += " ORDER BY emp_code ASC;"
    cursor.execute(sql, params)
    employees = cursor.fetchall()

    # Distinct departments for filter
    cursor.execute("SELECT DISTINCT department FROM employees ORDER BY department ASC;")
    departments = [r["department"] for r in cursor.fetchall()]

    return render_template(
        "employees.html",
        employees=employees,
        departments=departments,
        search_query=search_query,
        selected_dept=dept_filter
    )


@app.route("/employees/add", methods=["GET", "POST"])
def employee_add():
    """Add a new employee."""
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()

        emp_code = request.form.get("emp_code", "").strip().upper()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        department = request.form.get("department", "").strip()
        designation = request.form.get("designation", "").strip()
        date_of_joining = request.form.get("date_of_joining", "").strip()
        pan_number = request.form.get("pan_number", "").strip().upper()
        tax_regime = request.form.get("tax_regime", "new").strip().lower()
        
        try:
            basic_salary = max(0.0, float(request.form.get("basic_salary", 0)))
            hra = max(0.0, float(request.form.get("hra", 0)))
            special_allowance = max(0.0, float(request.form.get("special_allowance", 0)))
            pf_applicable = 1 if request.form.get("pf_applicable") == "1" else 0
            custom_pf_rate = float(request.form.get("custom_pf_rate", 12.0))
            annual_80c = max(0.0, float(request.form.get("annual_80c", 0)))
            annual_80d = max(0.0, float(request.form.get("annual_80d", 0)))
            annual_hra_exemption = max(0.0, float(request.form.get("annual_hra_exemption", 0)))
        except ValueError:
            flash("Invalid numeric value provided in salary or tax inputs.", "danger")
            return render_template("employee_form.html", action="add", employee=request.form)

        bank_account = request.form.get("bank_account", "").strip()
        bank_ifsc = request.form.get("bank_ifsc", "").strip().upper()
        status = request.form.get("status", "Active")

        # Basic validations
        if not emp_code or not first_name or not last_name or not email or not department:
            flash("Please fill in all required fields.", "danger")
            return render_template("employee_form.html", action="add", employee=request.form)

        # Check unique code and email
        cursor.execute("SELECT id FROM employees WHERE emp_code = ? OR email = ?;", (emp_code, email))
        if cursor.fetchone():
            flash("An employee with this Employee Code or Email already exists.", "danger")
            return render_template("employee_form.html", action="add", employee=request.form)

        cursor.execute("""
            INSERT INTO employees (
                emp_code, first_name, last_name, email, phone, department, designation,
                date_of_joining, pan_number, tax_regime, basic_salary, hra, special_allowance,
                pf_applicable, custom_pf_rate, annual_80c, annual_80d, annual_hra_exemption,
                bank_account, bank_ifsc, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            emp_code, first_name, last_name, email, phone, department, designation,
            date_of_joining, pan_number, tax_regime, basic_salary, hra, special_allowance,
            pf_applicable, custom_pf_rate, annual_80c, annual_80d, annual_hra_exemption,
            bank_account, bank_ifsc, status
        ))
        db.commit()
        flash(f"Employee {first_name} {last_name} ({emp_code}) added successfully!", "success")
        return redirect(url_for("employees_list"))

    # Auto-generate next code suggestion
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM employees ORDER BY id DESC LIMIT 1;")
    last_row = cursor.fetchone()
    next_id = (last_row["id"] + 1) if last_row else 101
    suggested_code = f"EMP{next_id}"

    empty_emp = {
        "emp_code": suggested_code,
        "date_of_joining": datetime.now().strftime("%Y-%m-%d"),
        "tax_regime": "new",
        "pf_applicable": 1,
        "custom_pf_rate": 12.0,
        "status": "Active"
    }
    return render_template("employee_form.html", action="add", employee=empty_emp)


@app.route("/employees/edit/<int:emp_id>", methods=["GET", "POST"])
def employee_edit(emp_id: int):
    """Edit existing employee details."""
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM employees WHERE id = ?;", (emp_id,))
    emp = cursor.fetchone()
    if not emp:
        flash("Employee not found.", "danger")
        return redirect(url_for("employees_list"))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        department = request.form.get("department", "").strip()
        designation = request.form.get("designation", "").strip()
        date_of_joining = request.form.get("date_of_joining", "").strip()
        pan_number = request.form.get("pan_number", "").strip().upper()
        tax_regime = request.form.get("tax_regime", "new").strip().lower()

        try:
            basic_salary = max(0.0, float(request.form.get("basic_salary", 0)))
            hra = max(0.0, float(request.form.get("hra", 0)))
            special_allowance = max(0.0, float(request.form.get("special_allowance", 0)))
            pf_applicable = 1 if request.form.get("pf_applicable") == "1" else 0
            custom_pf_rate = float(request.form.get("custom_pf_rate", 12.0))
            annual_80c = max(0.0, float(request.form.get("annual_80c", 0)))
            annual_80d = max(0.0, float(request.form.get("annual_80d", 0)))
            annual_hra_exemption = max(0.0, float(request.form.get("annual_hra_exemption", 0)))
        except ValueError:
            flash("Invalid numeric value provided in salary or tax inputs.", "danger")
            return render_template("employee_form.html", action="edit", employee=request.form, emp_id=emp_id)

        bank_account = request.form.get("bank_account", "").strip()
        bank_ifsc = request.form.get("bank_ifsc", "").strip().upper()
        status = request.form.get("status", "Active")

        # Check email conflict with other employees
        cursor.execute("SELECT id FROM employees WHERE email = ? AND id != ?;", (email, emp_id))
        if cursor.fetchone():
            flash("Another employee is already registered with this email.", "danger")
            return render_template("employee_form.html", action="edit", employee=request.form, emp_id=emp_id)

        cursor.execute("""
            UPDATE employees SET
                first_name = ?, last_name = ?, email = ?, phone = ?, department = ?,
                designation = ?, date_of_joining = ?, pan_number = ?, tax_regime = ?,
                basic_salary = ?, hra = ?, special_allowance = ?, pf_applicable = ?,
                custom_pf_rate = ?, annual_80c = ?, annual_80d = ?, annual_hra_exemption = ?,
                bank_account = ?, bank_ifsc = ?, status = ?
            WHERE id = ?;
        """, (
            first_name, last_name, email, phone, department,
            designation, date_of_joining, pan_number, tax_regime,
            basic_salary, hra, special_allowance, pf_applicable,
            custom_pf_rate, annual_80c, annual_80d, annual_hra_exemption,
            bank_account, bank_ifsc, status, emp_id
        ))
        db.commit()
        flash(f"Profile for {first_name} {last_name} updated successfully!", "success")
        return redirect(url_for("employees_list"))

    return render_template("employee_form.html", action="edit", employee=emp, emp_id=emp_id)


@app.route("/employees/delete/<int:emp_id>", methods=["POST"])
def employee_delete(emp_id: int):
    """Delete an employee and their corresponding payroll records."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT emp_code, first_name, last_name FROM employees WHERE id = ?;", (emp_id,))
    emp = cursor.fetchone()
    if emp:
        cursor.execute("DELETE FROM employees WHERE id = ?;", (emp_id,))
        db.commit()
        flash(f"Employee {emp['first_name']} {emp['last_name']} ({emp['emp_code']}) deleted.", "info")
    else:
        flash("Employee not found.", "danger")
    return redirect(url_for("employees_list"))


# --- ROUTES: 3. PAYROLL MANAGEMENT ---

@app.route("/payroll")
def payroll_list():
    """View all processed payrolls with month filtering."""
    db = get_db()
    cursor = db.cursor()

    selected_month = request.args.get("month", "").strip()
    if not selected_month:
        cursor.execute("SELECT DISTINCT payroll_month FROM payrolls ORDER BY payroll_month DESC LIMIT 1;")
        row = cursor.fetchone()
        selected_month = row["payroll_month"] if row else datetime.now().strftime("%Y-%m")

    cursor.execute("""
        SELECT 
            p.*,
            e.emp_code,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            e.designation,
            e.pan_number
        FROM payrolls p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.payroll_month = ?
        ORDER BY e.emp_code ASC;
    """, (selected_month,))
    payrolls = cursor.fetchall()

    # Month aggregate statistics
    cursor.execute("""
        SELECT 
            COUNT(id) AS count,
            COALESCE(SUM(gross_salary), 0) AS total_gross,
            COALESCE(SUM(total_deductions), 0) AS total_deductions,
            COALESCE(SUM(net_salary), 0) AS total_net,
            COALESCE(SUM(tax_tds_deduction), 0) AS total_tax,
            COALESCE(SUM(pf_deduction), 0) AS total_pf
        FROM payrolls
        WHERE payroll_month = ?;
    """, (selected_month,))
    month_stats = cursor.fetchone()

    # Available months list
    cursor.execute("SELECT DISTINCT payroll_month FROM payrolls ORDER BY payroll_month DESC;")
    available_months = [r["payroll_month"] for r in cursor.fetchall()]
    if selected_month not in available_months:
        available_months.insert(0, selected_month)

    return render_template(
        "payroll.html",
        payrolls=payrolls,
        selected_month=selected_month,
        available_months=available_months,
        stats=month_stats
    )


@app.route("/payroll/process", methods=["GET", "POST"])
def payroll_process():
    """
    Process monthly payroll for a selected employee.
    Enforces duplicate prevention for the same employee and month.
    """
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        try:
            employee_id = int(request.form.get("employee_id", 0))
            payroll_month = request.form.get("payroll_month", "").strip()
            pay_date = request.form.get("pay_date", datetime.now().strftime("%Y-%m-%d")).strip()
            
            basic_salary = max(0.0, float(request.form.get("basic_salary", 0)))
            hra = max(0.0, float(request.form.get("hra", 0)))
            special_allowance = max(0.0, float(request.form.get("special_allowance", 0)))
            bonus_overtime = max(0.0, float(request.form.get("bonus_overtime", 0)))
            
            gross_salary = basic_salary + hra + special_allowance + bonus_overtime

            pf_deduction = max(0.0, float(request.form.get("pf_deduction", 0)))
            pt_deduction = max(0.0, float(request.form.get("pt_deduction", 0)))
            tax_tds_deduction = max(0.0, float(request.form.get("tax_tds_deduction", 0)))
            other_deductions = max(0.0, float(request.form.get("other_deductions", 0)))
            
            total_deductions = round(pf_deduction + pt_deduction + tax_tds_deduction + other_deductions, 2)
            net_salary = round(gross_salary - total_deductions, 2)
            tax_regime_used = request.form.get("tax_regime_used", "new")
            notes = request.form.get("notes", "").strip()
        except ValueError:
            flash("Invalid numeric value provided in payroll amounts.", "danger")
            return redirect(url_for("payroll_process"))

        # DUPLICATE PAYROLL CHECK: Prevent duplicate payroll records for same employee & month
        cursor.execute("""
            SELECT id FROM payrolls 
            WHERE employee_id = ? AND payroll_month = ?;
        """, (employee_id, payroll_month))
        existing_payroll = cursor.fetchone()

        if existing_payroll:
            flash(f"Duplicate Error: Payroll for this employee for month {payroll_month} has already been processed! (Payroll #{existing_payroll['id']})", "warning")
            return redirect(url_for("payroll_process", emp_id=employee_id, month=payroll_month))

        cursor.execute("""
            INSERT INTO payrolls (
                employee_id, payroll_month, pay_date, basic_salary, hra, special_allowance,
                bonus_overtime, gross_salary, pf_deduction, pt_deduction, tax_tds_deduction,
                other_deductions, total_deductions, net_salary, tax_regime_used, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            employee_id, payroll_month, pay_date, basic_salary, hra, special_allowance,
            bonus_overtime, gross_salary, pf_deduction, pt_deduction, tax_tds_deduction,
            other_deductions, total_deductions, net_salary, tax_regime_used, "Processed", notes
        ))
        db.commit()
        new_id = cursor.lastrowid
        flash(f"Payroll processed successfully for {payroll_month}! Net Pay: ₹{net_salary:,.2f}", "success")
        return redirect(url_for("payslip_view", payroll_id=new_id))

    # GET Request: Preload employee details if selected
    selected_emp_id = request.args.get("emp_id", type=int)
    default_month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    
    cursor.execute("SELECT id, emp_code, first_name, last_name, department, designation FROM employees WHERE status = 'Active' ORDER BY emp_code ASC;")
    active_employees = cursor.fetchall()

    selected_emp = None
    tax_estimation = None
    if selected_emp_id:
        cursor.execute("SELECT * FROM employees WHERE id = ?;", (selected_emp_id,))
        selected_emp = cursor.fetchone()
        if selected_emp:
            monthly_gross = selected_emp["basic_salary"] + selected_emp["hra"] + selected_emp["special_allowance"]
            est_tds = estimate_monthly_tds(
                monthly_gross=monthly_gross,
                regime=selected_emp["tax_regime"],
                annual_80c=selected_emp["annual_80c"],
                annual_80d=selected_emp["annual_80d"],
                annual_hra_exemption=selected_emp["annual_hra_exemption"]
            )
            est_pf = round(selected_emp["basic_salary"] * (selected_emp["custom_pf_rate"] / 100.0), 2) if selected_emp["pf_applicable"] else 0.0
            tax_estimation = {
                "monthly_gross": monthly_gross,
                "monthly_pf": est_pf,
                "monthly_pt": 200.0,
                "monthly_tds": est_tds,
                "estimated_net": round(monthly_gross - (est_pf + 200.0 + est_tds), 2)
            }

    return render_template(
        "payroll_process.html",
        active_employees=active_employees,
        selected_emp=selected_emp,
        selected_emp_id=selected_emp_id,
        default_month=default_month,
        today_date=datetime.now().strftime("%Y-%m-%d"),
        tax_estimation=tax_estimation
    )


@app.route("/payroll/batch-process", methods=["POST"])
def payroll_batch_process():
    """
    1-Click batch processing for all active employees for a given month.
    Skips any employee who already has a payroll record for this month.
    """
    db = get_db()
    cursor = db.cursor()

    target_month = request.form.get("target_month", datetime.now().strftime("%Y-%m")).strip()
    pay_date = request.form.get("pay_date", datetime.now().strftime("%Y-%m-%d")).strip()

    cursor.execute("SELECT * FROM employees WHERE status = 'Active';")
    active_emps = cursor.fetchall()

    processed_count = 0
    skipped_count = 0

    for emp in active_emps:
        # Check duplicate
        cursor.execute("SELECT id FROM payrolls WHERE employee_id = ? AND payroll_month = ?;", (emp["id"], target_month))
        if cursor.fetchone():
            skipped_count += 1
            continue

        basic = emp["basic_salary"]
        hra = emp["hra"]
        special = emp["special_allowance"]
        gross = basic + hra + special
        pf = round(basic * (emp["custom_pf_rate"] / 100.0), 2) if emp["pf_applicable"] else 0.0
        pt = 200.0
        tds = estimate_monthly_tds(
            monthly_gross=gross,
            regime=emp["tax_regime"],
            annual_80c=emp["annual_80c"],
            annual_80d=emp["annual_80d"],
            annual_hra_exemption=emp["annual_hra_exemption"]
        )
        total_ded = round(pf + pt + tds, 2)
        net = round(gross - total_ded, 2)

        cursor.execute("""
            INSERT INTO payrolls (
                employee_id, payroll_month, pay_date, basic_salary, hra, special_allowance,
                bonus_overtime, gross_salary, pf_deduction, pt_deduction, tax_tds_deduction,
                other_deductions, total_deductions, net_salary, tax_regime_used, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            emp["id"], target_month, pay_date, basic, hra, special,
            0.0, gross, pf, pt, tds, 0.0, total_ded, net,
            emp["tax_regime"], "Processed", "Batch Automated Run"
        ))
        processed_count += 1

    db.commit()
    flash(f"Batch Run Complete for {target_month}: {processed_count} payrolls processed, {skipped_count} skipped (already present).", "info")
    return redirect(url_for("payroll_list", month=target_month))


@app.route("/payroll/delete/<int:payroll_id>", methods=["POST"])
def payroll_delete(payroll_id: int):
    """Delete a payroll record."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM payrolls WHERE id = ?;", (payroll_id,))
    db.commit()
    flash("Payroll record deleted.", "info")
    return redirect(url_for("payroll_list"))


# --- ROUTES: 4. INCOME TAX CALCULATOR ---

@app.route("/tax-calculator", methods=["GET", "POST"])
def tax_calculator():
    """
    Dedicated Income Tax Calculation Engine page.
    Supports India's Old vs New Tax Regimes (FY 2024-25 / FY 2025-26).
    Provides side-by-side comparison, deduction breakdown, and monthly TDS forecast.
    """
    calculation_result = None
    form_data = {
        "gross_annual": 1200000.0,
        "regime_choice": "compare",
        "deduction_80c": 150000.0,
        "deduction_80d": 25000.0,
        "hra_exemption": 0.0,
        "home_loan_interest_24b": 0.0,
        "other_deductions": 0.0
    }

    # Optional preload from employee
    emp_id = request.args.get("emp_id", type=int)
    if emp_id and request.method == "GET":
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM employees WHERE id = ?;", (emp_id,))
        emp = cursor.fetchone()
        if emp:
            annual_gross = (emp["basic_salary"] + emp["hra"] + emp["special_allowance"]) * 12.0
            form_data = {
                "gross_annual": round(annual_gross, 2),
                "regime_choice": emp["tax_regime"],
                "deduction_80c": emp["annual_80c"],
                "deduction_80d": emp["annual_80d"],
                "hra_exemption": emp["annual_hra_exemption"],
                "home_loan_interest_24b": 0.0,
                "other_deductions": 0.0
            }

    if request.method == "POST":
        try:
            gross_annual = max(0.0, float(request.form.get("gross_annual", 0)))
            regime_choice = request.form.get("regime_choice", "compare")
            deduction_80c = max(0.0, float(request.form.get("deduction_80c", 0)))
            deduction_80d = max(0.0, float(request.form.get("deduction_80d", 0)))
            hra_exemption = max(0.0, float(request.form.get("hra_exemption", 0)))
            home_loan_24b = max(0.0, float(request.form.get("home_loan_interest_24b", 0)))
            other_ded = max(0.0, float(request.form.get("other_deductions", 0)))

            form_data = {
                "gross_annual": gross_annual,
                "regime_choice": regime_choice,
                "deduction_80c": deduction_80c,
                "deduction_80d": deduction_80d,
                "hra_exemption": hra_exemption,
                "home_loan_interest_24b": home_loan_24b,
                "other_deductions": other_ded
            }

            if regime_choice == "new":
                calculation_result = {
                    "mode": "single",
                    "data": compute_tax_new_regime(gross_annual)
                }
            elif regime_choice == "old":
                calculation_result = {
                    "mode": "single",
                    "data": compute_tax_old_regime(
                        gross_annual,
                        deduction_80c=deduction_80c,
                        deduction_80d=deduction_80d,
                        hra_exemption=hra_exemption,
                        home_loan_interest_24b=home_loan_24b,
                        other_deductions=other_ded
                    )
                }
            else:
                # Compare both
                comparison = compare_tax_regimes(
                    gross_annual,
                    deduction_80c=deduction_80c,
                    deduction_80d=deduction_80d,
                    hra_exemption=hra_exemption,
                    home_loan_interest_24b=home_loan_24b,
                    other_deductions=other_ded
                )
                calculation_result = {
                    "mode": "compare",
                    "data": comparison
                }
        except ValueError:
            flash("Invalid input numbers in tax calculator.", "danger")

    # If first load without post, produce initial default calculation for 12 Lakhs
    if calculation_result is None:
        calculation_result = {
            "mode": "compare",
            "data": compare_tax_regimes(
                form_data["gross_annual"],
                deduction_80c=form_data["deduction_80c"],
                deduction_80d=form_data["deduction_80d"],
                hra_exemption=form_data["hra_exemption"],
                home_loan_interest_24b=form_data["home_loan_interest_24b"],
                other_deductions=form_data["other_deductions"]
            )
        }

    return render_template(
        "tax_calculator.html",
        form_data=form_data,
        result=calculation_result
    )


# --- ROUTES: 5. PAYSLIP ---

@app.route("/payslip/<int:payroll_id>")
def payslip_view(payroll_id: int):
    """
    Renders corporate payslip for browser viewing and printing.
    Optimized for printing / saving as PDF via window.print().
    """
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT 
            p.*,
            e.emp_code,
            e.first_name,
            e.last_name,
            e.email,
            e.phone,
            e.department,
            e.designation,
            e.date_of_joining,
            e.pan_number,
            e.bank_account,
            e.bank_ifsc
        FROM payrolls p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.id = ?;
    """, (payroll_id,))
    record = cursor.fetchone()

    if not record:
        flash("Payslip not found.", "danger")
        return redirect(url_for("payroll_list"))

    # Convert Net Salary to Indian Currency Words
    net_in_words = number_to_inr_words(record["net_salary"])

    # Parse Month for display (e.g. 2026-10 -> October 2026)
    try:
        month_obj = datetime.strptime(record["payroll_month"], "%Y-%m")
        formatted_period = month_obj.strftime("%B %Y")
    except ValueError:
        formatted_period = record["payroll_month"]

    return render_template(
        "payslip.html",
        record=record,
        net_in_words=net_in_words,
        formatted_period=formatted_period
    )


# --- ROUTES: 6. REPORTS & CSV EXPORT ---

@app.route("/reports")
def reports_view():
    """
    Comprehensive Monthly Payroll Reports & Department Analytics.
    """
    db = get_db()
    cursor = db.cursor()

    selected_month = request.args.get("month", "").strip()
    selected_dept = request.args.get("department", "").strip()

    if not selected_month:
        cursor.execute("SELECT DISTINCT payroll_month FROM payrolls ORDER BY payroll_month DESC LIMIT 1;")
        r = cursor.fetchone()
        selected_month = r["payroll_month"] if r else datetime.now().strftime("%Y-%m")

    # Filtered Query
    sql = """
        SELECT 
            p.*,
            e.emp_code,
            e.first_name || ' ' || e.last_name AS employee_name,
            e.department,
            e.designation,
            e.pan_number
        FROM payrolls p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.payroll_month = ?
    """
    params = [selected_month]

    if selected_dept:
        sql += " AND e.department = ?"
        params.append(selected_dept)

    sql += " ORDER BY e.emp_code ASC;"
    cursor.execute(sql, params)
    records = cursor.fetchall()

    # Aggregates for selection
    agg_sql = """
        SELECT 
            COUNT(p.id) AS total_count,
            COALESCE(SUM(p.basic_salary), 0) AS total_basic,
            COALESCE(SUM(p.hra), 0) AS total_hra,
            COALESCE(SUM(p.special_allowance), 0) AS total_special,
            COALESCE(SUM(p.bonus_overtime), 0) AS total_bonus,
            COALESCE(SUM(p.gross_salary), 0) AS total_gross,
            COALESCE(SUM(p.pf_deduction), 0) AS total_pf,
            COALESCE(SUM(p.pt_deduction), 0) AS total_pt,
            COALESCE(SUM(p.tax_tds_deduction), 0) AS total_tax,
            COALESCE(SUM(p.total_deductions), 0) AS total_deductions,
            COALESCE(SUM(p.net_salary), 0) AS total_net
        FROM payrolls p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.payroll_month = ?
    """
    agg_params = [selected_month]
    if selected_dept:
        agg_sql += " AND e.department = ?"
        agg_params.append(selected_dept)

    cursor.execute(agg_sql, agg_params)
    totals = cursor.fetchone()

    # Department distribution
    cursor.execute("""
        SELECT 
            e.department,
            COUNT(p.id) as emp_count,
            COALESCE(SUM(p.gross_salary), 0) as gross_sum,
            COALESCE(SUM(p.net_salary), 0) as net_sum,
            COALESCE(SUM(p.tax_tds_deduction), 0) as tax_sum
        FROM payrolls p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.payroll_month = ?
        GROUP BY e.department
        ORDER BY gross_sum DESC;
    """, (selected_month,))
    dept_stats = cursor.fetchall()

    # Available months and departments
    cursor.execute("SELECT DISTINCT payroll_month FROM payrolls ORDER BY payroll_month DESC;")
    available_months = [row["payroll_month"] for row in cursor.fetchall()]
    if selected_month not in available_months:
        available_months.insert(0, selected_month)

    cursor.execute("SELECT DISTINCT department FROM employees ORDER BY department ASC;")
    departments = [row["department"] for row in cursor.fetchall()]

    return render_template(
        "reports.html",
        records=records,
        totals=totals,
        dept_stats=dept_stats,
        selected_month=selected_month,
        selected_dept=selected_dept,
        available_months=available_months,
        departments=departments
    )


@app.route("/reports/export-csv")
def reports_export_csv():
    """
    Exports payroll report as a downloadable CSV using Python's built-in csv module.
    """
    db = get_db()
    cursor = db.cursor()

    selected_month = request.args.get("month", datetime.now().strftime("%Y-%m")).strip()
    selected_dept = request.args.get("department", "").strip()

    sql = """
        SELECT 
            e.emp_code AS "Employee Code",
            e.first_name || ' ' || e.last_name AS "Full Name",
            e.department AS "Department",
            e.designation AS "Designation",
            e.pan_number AS "PAN",
            p.payroll_month AS "Payroll Month",
            p.pay_date AS "Payment Date",
            p.basic_salary AS "Basic Salary (INR)",
            p.hra AS "HRA (INR)",
            p.special_allowance AS "Special Allowance (INR)",
            p.bonus_overtime AS "Bonus / Overtime (INR)",
            p.gross_salary AS "Gross Salary (INR)",
            p.pf_deduction AS "PF Deduction (INR)",
            p.pt_deduction AS "PT Deduction (INR)",
            p.tax_tds_deduction AS "Income Tax TDS (INR)",
            p.other_deductions AS "Other Deductions (INR)",
            p.total_deductions AS "Total Deductions (INR)",
            p.net_salary AS "Net Salary (INR)",
            p.tax_regime_used AS "Tax Regime",
            p.status AS "Status"
        FROM payrolls p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.payroll_month = ?
    """
    params = [selected_month]
    if selected_dept:
        sql += " AND e.department = ?"
        params.append(selected_dept)

    sql += " ORDER BY e.emp_code ASC;"
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    if rows:
        headers = [d[0] for d in cursor.description]
        writer.writerow(headers)
        for r in rows:
            writer.writerow([r[k] for k in headers])
    else:
        writer.writerow(["No payroll records found for this selection."])

    csv_data = output.getvalue()
    filename = f"PayFlow_Payroll_Report_{selected_month}.csv" if not selected_dept else f"PayFlow_{selected_dept}_{selected_month}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# --- ROUTES: 7. SYSTEM & SEEDING ---

@app.route("/seed-demo", methods=["POST", "GET"])
def seed_demo_route():
    """Interactive demo seeder endpoint."""
    count = seed_demo_data(force=True)
    flash(f"Demo database populated with {count} sample corporate employees and processed payrolls!", "success")
    return redirect(url_for("dashboard"))


@app.route("/health")
def health_check():
    """Health check endpoint for Render monitoring and uptime checks."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT 1;")
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "service": "PayFlow — Automated Payroll & Tax Engine",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


# Automatically initialize DB on import/startup
init_db()
# Automatically populate demo data if DB is empty on first boot
seed_demo_data(force=False)


# --- PRODUCTION ENTRY POINT ---

if __name__ == "__main__":
    # In local development: read PORT or default to 5000, listen on 0.0.0.0
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
