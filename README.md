# PayFlow — Automated Payroll Management & Income Tax Calculation Engine

> **A Complete, Lightweight College Project & Production-Ready Web Application**  
> Built with **Python**, **Flask**, **Jinja2**, **Pure HTML/CSS**, and built-in **SQLite3**.  
> Ready for 1-click deployment on **Render** with **Gunicorn**.

---

## 📌 1. Project Overview

**PayFlow** is an end-to-end Automated Payroll Management and Income Tax Calculation Engine designed to streamline human resource payroll workflows, calculate statutory deductions, compute income tax liability under India's Direct Tax laws (**New Tax Regime under Section 115BAC** vs. **Old Tax Regime with Chapter VI-A deductions**), generate corporate payslips with print/PDF support, and export reports in CSV format.

### Key Highlights
* **100% Python-Powered**: Routing, database queries, salary math, and tax algorithms are written strictly in pure Python with zero third-party UI frameworks.
* **No Frontend Framework Overhead**: Clean custom CSS with white and dark navy interface, blue/violet accents, animated cards, and responsive layout without React, Node.js, Bootstrap, or Tailwind.
* **India Income Tax Compliance**: Covers FY 2024-25 / FY 2025-26 rules:
  - New Regime: Standard Deduction ₹75,000, Section 87A rebate (tax = ₹0 up to ₹7,00,000 income), 4% Cess.
  - Old Regime: Standard Deduction ₹50,000, Section 80C (up to ₹1.5L), Section 80D (up to ₹50k), HRA Exemption (Sec 10(13A)), Home loan interest (Sec 24b), Section 87A rebate (up to ₹5,00,000).
* **Duplicate Prevention**: SQLite unique constraints (`employee_id`, `payroll_month`) + Python application validation guarantee that no duplicate payroll is processed for the same employee in the same month.
* **Production Deployment Ready**: Configured for Render using Gunicorn, dynamic `$PORT` binding, health checks (`/health`), and configurable SQLite persistent disk storage.

---

## 🛠️ 2. Technology Stack

| Layer | Technology | Details |
| :--- | :--- | :--- |
| **Backend Language** | Python 3.10+ | All core business logic, tax engine, and math |
| **Web Framework** | Flask 3.x | Lightweight WSGI web framework and routing |
| **Templating Engine** | Jinja2 | Server-side rendering, filters (`inr`, `inr_clean`) |
| **Database** | SQLite3 | Python's built-in module with foreign keys and parameterized queries |
| **Styling** | Pure CSS3 | Custom CSS variables, animations, dark navy & white theme |
| **Interactivity** | Vanilla JavaScript | Real-time salary calculation, print payslip, mobile drawer |
| **Production Server** | Gunicorn | UNIX WSGI HTTP Server for Render production deployment |

---

## 📁 3. Project Structure

```text
payflow/
├── app.py                  # Main Flask application, routes & DB controllers
├── tax_engine.py           # Indian Income Tax calculation algorithms & comparison
├── requirements.txt        # Minimal production dependencies (Flask, Gunicorn)
├── Procfile                # Gunicorn deployment command for Render / Heroku
├── render.yaml             # Render Blueprint infrastructure specification
├── README.md               # Complete documentation and setup guide
├── .gitignore              # Ignores __pycache__, local DB, and venv
├── templates/              # Jinja2 HTML Templates
│   ├── base.html           # Master layout with sidebar & top navigation
│   ├── dashboard.html      # Main executive dashboard with KPI metrics
│   ├── employees.html      # Employee management directory
│   ├── employee_form.html  # Add & Edit employee profiles
│   ├── payroll.html        # Monthly payroll register & batch processing
│   ├── payroll_process.html# Single employee payroll processing & live preview
│   ├── tax_calculator.html # Interactive Old vs. New tax regime comparison
│   ├── payslip.html        # Corporate printable salary payslip (print/PDF)
│   └── reports.html        # Monthly salary summary, filters & CSV export
└── static/
    ├── css/
    │   └── style.css       # Custom modern navy/white responsive design
    └── js/
        └── script.js       # Minimal vanilla JS (sidebar, print, live math)
```

---

## 🚀 4. How to Run Locally

### Step 1: Clone or Open the Project
Open a terminal in the project directory:
```bash
cd payflow
```

### Step 2: Create and Activate a Virtual Environment (Recommended)
On Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

On macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Run the Application Locally
```bash
python app.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```
> **Note**: On the first startup, PayFlow automatically creates `payflow.db` and loads 8 sample corporate employees across Engineering, HR, Finance, Marketing, Sales, and Operations, together with pre-processed payrolls for the current month.

### Step 5: Run with Gunicorn (Production Test on Linux / Mac / WSL)
```bash
gunicorn app:app --bind 0.0.0.0:5000
```

---

## 🧮 5. Income Tax Calculation Engine Explained

The tax calculations in `tax_engine.py` strictly mirror Indian Direct Tax laws for **FY 2024-25 / FY 2025-26**:

### 1. New Tax Regime (Section 115BAC — Default)
* **Standard Deduction**: ₹75,000 for salaried employees.
* **Tax Slabs**:
  * Up to ₹3,00,000: **Nil (0%)**
  * ₹3,00,001 to ₹7,00,000: **5%**
  * ₹7,00,001 to ₹10,00,000: **10%**
  * ₹10,00,001 to ₹12,00,000: **15%**
  * ₹12,00,001 to ₹15,00,000: **20%**
  * Above ₹15,00,000: **30%**
* **Section 87A Rebate**: Full tax rebate up to ₹25,000 if net taxable income is ≤ ₹7,00,000 (tax liability becomes ₹0).
* **Cess**: 4% Health & Education Cess on net tax.

### 2. Old Tax Regime (With Chapter VI-A Deductions)
* **Standard Deduction**: ₹50,000 for salaried employees.
* **Eligible Deductions**:
  * **Section 80C**: Up to ₹1,50,000 (PF, ELSS, PPF, Life Insurance).
  * **Section 80D**: Up to ₹50,000 for Health Insurance.
  * **Section 10(13A)**: HRA Exemption.
  * **Section 24(b)**: Home loan interest deduction up to ₹2,00,000.
* **Tax Slabs**:
  * Up to ₹2,50,000: **Nil (0%)**
  * ₹2,50,001 to ₹5,00,000: **5%**
  * ₹5,00,001 to ₹10,00,000: **20%**
  * Above ₹10,00,000: **30%**
* **Section 87A Rebate**: Full tax rebate up to ₹12,500 if net taxable income is ≤ ₹5,00,000 (tax liability becomes ₹0).
* **Cess**: 4% Health & Education Cess on net tax.

### 3. Monthly Tax Withholding (TDS)
For monthly payroll processing:
$$\text{Projected Annual Gross} = \text{Monthly Gross} \times 12$$
$$\text{Monthly TDS} = \frac{\text{Computed Annual Tax Liability}}{12}$$

---

## 🖨️ 6. Payslip & PDF Generation

* When viewing any payslip at `/payslip/<payroll_id>`, click **"Print / Save as PDF"**.
* This triggers native browser printing (`window.print()`).
* The stylesheet includes dedicated `@media print` rules:
  * Automatically strips the navigation sidebar, topbars, buttons, and footers.
  * Formats the corporate payslip into a standard, clean document layout suitable for saving as a PDF or printing directly to physical paper.

---

## 📊 7. Reports & CSV Export

* Navigate to `/reports` to filter by **Month** (e.g., `2026-10`) and **Department**.
* Click **"Export Report to CSV"** (`/reports/export-csv`).
* Uses Python's built-in `csv` module to generate RFC-4180 compliant CSV files with full salary and statutory deduction columns on the fly without writing temporary files to disk.

---

## 🌐 8. Render Deployment Instructions (Mandatory)

### Option A: Deploy via GitHub (Recommended)

1. **Initialize Git & Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: PayFlow Payroll & Tax Engine"
   git branch -M main
   git remote add origin https://github.com/<your-username>/payflow.git
   git push -u origin main
   ```

2. **Create New Web Service on Render**:
   * Log into [dashboard.render.com](https://dashboard.render.com).
   * Click **New +** -> **Web Service**.
   * Connect your GitHub repository.
   * Configure the settings:
     * **Name**: `payflow-payroll-engine`
     * **Runtime**: `Python 3`
     * **Build Command**: `pip install -r requirements.txt`
     * **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
     * **Health Check Path**: `/health`
     * **Plan**: `Free` (or Starter for Persistent Disk)

3. **Render Environment Variables**:
   Add the following environment variables under **Environment**:
   * `PYTHON_VERSION`: `3.11.9`
   * `SECRET_KEY`: `<any-random-secret-string>`
   * `FLASK_ENV`: `production`

4. **Persistent SQLite Disk Storage on Render**:
   * *Note on Render's Free tier*: Web services have ephemeral filesystems. Any file written to the local disk is reset on new deployments or service sleep.
   * *To persist SQLite across deployments on Render*:
     1. Attach a **Persistent Disk** (available on Render's Starter plan or above) mounted at `/var/data`.
     2. Add the environment variable:
        ```text
        DATABASE_PATH = /var/data/payflow.db
        ```
     3. PayFlow automatically creates the directory if it doesn't exist and stores SQLite data inside `/var/data/payflow.db`.

5. **Deploy**:
   * Click **Deploy Web Service**.
   * Render will build dependencies, run Gunicorn, verify the `/health` endpoint, and provide a live URL (e.g., `https://payflow-payroll-engine.onrender.com`).

---

## 🧪 9. Verification & Testing Checklist

- [x] Application boots locally on `0.0.0.0:5000` via `python app.py`.
- [x] Database tables and indexes created automatically on startup.
- [x] Default demo dataset loaded with 8 employees and active payrolls.
- [x] Add, View, Edit, and Delete employee records with input validation.
- [x] Payroll calculations verify: $\text{Gross} - \text{Total Deductions} = \text{Net Salary}$.
- [x] Section 87A rebate and 4% cess computed accurately for both regimes.
- [x] Duplicate payroll processing blocked for same employee + month.
- [x] 1-Click Batch Payroll processing handles all active employees.
- [x] Official payslips render properly and print/save to PDF cleanly.
- [x] CSV export generated via Python's built-in `csv` module.
- [x] Health check endpoint `/health` returns HTTP 200 JSON status.
- [x] Gunicorn starts successfully with `app:app --bind 0.0.0.0:$PORT`.

---

## 🎓 10. College Viva / Presentation Talking Points

1. **Why Flask over Django?**  
   Flask is lightweight, unopinionated, and transparent. For a specialized payroll engine, Flask allows full control over SQL queries, data flow, and tax algorithms without the overhead of heavy ORM migrations.
2. **How is Data Integrity Maintained?**  
   Using SQLite's `UNIQUE(employee_id, payroll_month)` constraint combined with pre-insert Python validation ensures that duplicate pay runs are impossible, preventing double payments.
3. **How Does the Tax Engine Determine the Best Regime?**  
   The engine computes taxable income and total liability under both Section 115BAC (New) and Chapter VI-A (Old), compares the net payable amounts, and highlights the exact rupee savings and monthly TDS adjustment.
4. **Why Pure CSS Instead of Frameworks?**  
   Building custom CSS without external CDNs or npm dependencies guarantees faster page loads, 100% offline development, zero version drift, and a tailored corporate look.

---

**Developed for College Project Examination**  
*Academic Project • Open for Educational Demonstration & Deployment*

