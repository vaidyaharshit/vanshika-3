/**
 * PayFlow — Automated Payroll Management & Income Tax Engine
 * Minimal Vanilla JavaScript for Interactive UI & Real-Time Helpers
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Mobile Sidebar Toggle
    const mobileToggle = document.getElementById("mobileToggle");
    const sidebar = document.getElementById("sidebar");

    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener("click", () => {
            sidebar.classList.toggle("open");
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener("click", (e) => {
            if (sidebar.classList.contains("open") && !sidebar.contains(e.target) && !mobileToggle.contains(e.target)) {
                sidebar.classList.remove("open");
            }
        });
    }

    // 2. Dismissible Alerts
    const alertCloses = document.querySelectorAll(".alert-close");
    alertCloses.forEach(btn => {
        btn.addEventListener("click", () => {
            const alert = btn.closest(".alert");
            if (alert) {
                alert.style.opacity = "0";
                setTimeout(() => alert.remove(), 250);
            }
        });
    });

    // Auto-dismiss success flash alerts after 6 seconds
    const successAlerts = document.querySelectorAll(".alert-success");
    successAlerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = "opacity 0.4s ease";
            alert.style.opacity = "0";
            setTimeout(() => alert.remove(), 400);
        }, 6000);
    });

    // 3. Employee Form Real-time Gross Salary Preview
    const basicInput = document.getElementById("basicSalaryInput");
    const hraInput = document.getElementById("hraInput");
    const specialInput = document.getElementById("specialInput");
    const grossDisplay = document.getElementById("grossSalaryDisplay");
    const pfToggle = document.getElementById("pfApplicableInput");
    const pfRateInput = document.getElementById("pfRateInput");
    const pfEstimateDisplay = document.getElementById("pfEstimateDisplay");

    function updateEmployeeCompensationPreview() {
        const basic = parseFloat(basicInput?.value) || 0;
        const hra = parseFloat(hraInput?.value) || 0;
        const special = parseFloat(specialInput?.value) || 0;
        const gross = basic + hra + special;

        if (grossDisplay) {
            grossDisplay.textContent = "₹" + gross.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        if (pfEstimateDisplay) {
            const isPf = pfToggle ? pfToggle.checked : true;
            const rate = parseFloat(pfRateInput?.value) || 12.0;
            const pfEst = isPf ? (basic * (rate / 100.0)) : 0;
            pfEstimateDisplay.textContent = "₹" + pfEst.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
    }

    if (basicInput) {
        [basicInput, hraInput, specialInput, pfRateInput].forEach(inp => {
            if (inp) inp.addEventListener("input", updateEmployeeCompensationPreview);
        });
        if (pfToggle) {
            pfToggle.addEventListener("change", updateEmployeeCompensationPreview);
        }
        updateEmployeeCompensationPreview();
    }

    // 4. Payroll Process Live Net Salary Calculator
    const payBasic = document.getElementById("payBasic");
    const payHra = document.getElementById("payHra");
    const paySpecial = document.getElementById("paySpecial");
    const payOvertime = document.getElementById("payOvertime");

    const payPf = document.getElementById("payPf");
    const payPt = document.getElementById("payPt");
    const payTds = document.getElementById("payTds");
    const payOther = document.getElementById("payOther");

    const previewGross = document.getElementById("previewGross");
    const previewDeductions = document.getElementById("previewDeductions");
    const previewNet = document.getElementById("previewNet");

    function updatePayrollCalculations() {
        const basic = parseFloat(payBasic?.value) || 0;
        const hra = parseFloat(payHra?.value) || 0;
        const special = parseFloat(paySpecial?.value) || 0;
        const overtime = parseFloat(payOvertime?.value) || 0;

        const gross = basic + hra + special + overtime;

        const pf = parseFloat(payPf?.value) || 0;
        const pt = parseFloat(payPt?.value) || 0;
        const tds = parseFloat(payTds?.value) || 0;
        const other = parseFloat(payOther?.value) || 0;

        const totalDeductions = pf + pt + tds + other;
        const net = Math.max(0, gross - totalDeductions);

        if (previewGross) previewGross.textContent = "₹" + gross.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        if (previewDeductions) previewDeductions.textContent = "₹" + totalDeductions.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        if (previewNet) previewNet.textContent = "₹" + net.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    if (payBasic) {
        [payBasic, payHra, paySpecial, payOvertime, payPf, payPt, payTds, payOther].forEach(el => {
            if (el) el.addEventListener("input", updatePayrollCalculations);
        });
        updatePayrollCalculations();
    }

    // 5. Delete Confirmations
    const deleteForms = document.querySelectorAll(".delete-confirm-form");
    deleteForms.forEach(form => {
        form.addEventListener("submit", (e) => {
            const confirmed = confirm("Are you sure you want to permanently delete this record? This action cannot be undone.");
            if (!confirmed) {
                e.preventDefault();
            }
        });
    });

    // 6. Print Payslip Functionality
    const printPayslipBtn = document.getElementById("printPayslipBtn");
    if (printPayslipBtn) {
        printPayslipBtn.addEventListener("click", () => {
            window.print();
        });
    }
});
