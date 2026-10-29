"""
PayFlow Tax Engine
==================
Automated Income Tax Calculation Engine for India's Tax Regimes:
- New Tax Regime (Section 115BAC) - Default
- Old Tax Regime (With itemized Chapter VI-A deductions & exemptions)

Applicable for Financial Year 2024-25 / 2025-26 (Assessment Year 2025-26 / 2026-27).
All calculations are strictly implemented in pure Python with no external dependencies.
"""

from typing import Dict, Any, List, Tuple


# --- TAX SLAB CONFIGURATIONS ---

NEW_REGIME_STANDARD_DEDUCTION = 75000.0  # Increased to ₹75,000 for salaried employees
OLD_REGIME_STANDARD_DEDUCTION = 50000.0  # Standard ₹50,000 for salaried employees
HEALTH_AND_EDUCATION_CESS_RATE = 0.04    # 4% Cess on tax after rebate

# New Tax Regime Slabs (FY 2024-25 / FY 2025-26 default)
NEW_REGIME_SLABS: List[Tuple[float, float, float]] = [
    (0.0, 300000.0, 0.00),         # Up to 3 Lakh: Nil
    (300000.0, 700000.0, 0.05),    # 3 Lakh to 7 Lakh: 5%
    (700000.0, 1000000.0, 0.10),   # 7 Lakh to 10 Lakh: 10%
    (1000000.0, 1200000.0, 0.15),  # 10 Lakh to 12 Lakh: 15%
    (1200000.0, 1500000.0, 0.20),  # 12 Lakh to 15 Lakh: 20%
    (1500000.0, float('inf'), 0.30) # Above 15 Lakh: 30%
]

# Old Tax Regime Slabs
OLD_REGIME_SLABS: List[Tuple[float, float, float]] = [
    (0.0, 250000.0, 0.00),         # Up to 2.5 Lakh: Nil
    (250000.0, 500000.0, 0.05),    # 2.5 Lakh to 5 Lakh: 5%
    (500000.0, 1000000.0, 0.20),   # 5 Lakh to 10 Lakh: 20%
    (1000000.0, float('inf'), 0.30) # Above 10 Lakh: 30%
]

# Section 87A Rebate Thresholds
NEW_REGIME_87A_THRESHOLD = 700000.0  # Full rebate if taxable income <= 7L
NEW_REGIME_87A_MAX_REBATE = 25000.0

OLD_REGIME_87A_THRESHOLD = 500000.0  # Full rebate if taxable income <= 5L
OLD_REGIME_87A_MAX_REBATE = 12500.0

# Deduction Caps for Old Regime
MAX_80C_DEDUCTION = 150000.0
MAX_80D_DEDUCTION = 50000.0
MAX_HOME_LOAN_INTEREST_24B = 200000.0


def calculate_slab_tax(taxable_income: float, slabs: List[Tuple[float, float, float]]) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Computes slab-wise tax breakdown for a given taxable income.
    Returns (total_slab_tax, list_of_slab_details).
    """
    if taxable_income <= 0:
        return 0.0, []

    total_tax = 0.0
    slab_breakdown = []

    for lower, upper, rate in slabs:
        if taxable_income > lower:
            taxable_in_slab = min(taxable_income, upper) - lower
            tax_in_slab = taxable_in_slab * rate
            total_tax += tax_in_slab
            slab_breakdown.append({
                "slab_label": f"₹{int(lower):,} - {'Above' if upper == float('inf') else '₹' + str(int(upper))}",
                "rate_pct": int(rate * 100),
                "taxable_amount": round(taxable_in_slab, 2),
                "tax_amount": round(tax_in_slab, 2)
            })
        else:
            slab_breakdown.append({
                "slab_label": f"₹{int(lower):,} - {'Above' if upper == float('inf') else '₹' + str(int(upper))}",
                "rate_pct": int(rate * 100),
                "taxable_amount": 0.0,
                "tax_amount": 0.0
            })

    return round(total_tax, 2), slab_breakdown


def calculate_hra_exemption(basic_annual: float, hra_annual: float, rent_paid_annual: float, is_metro: bool = True) -> float:
    """
    Calculates HRA exemption under Section 10(13A) of Income Tax Act.
    Minimum of:
    1. Actual HRA received
    2. Rent paid - 10% of Basic salary
    3. 50% of Basic salary (metro) or 40% (non-metro)
    """
    if rent_paid_annual <= 0 or hra_annual <= 0:
        return 0.0

    ten_pct_basic = 0.10 * basic_annual
    rent_minus_ten_pct = max(0.0, rent_paid_annual - ten_pct_basic)
    metro_factor = 0.50 if is_metro else 0.40
    pct_basic = metro_factor * basic_annual

    exemption = min(hra_annual, rent_minus_ten_pct, pct_basic)
    return round(max(0.0, exemption), 2)


def compute_tax_new_regime(gross_annual_income: float) -> Dict[str, Any]:
    """
    Calculates Income Tax under India's New Tax Regime (Section 115BAC).
    Allows standard deduction of ₹75,000.
    Section 87A rebate applies if net taxable income <= ₹7,00,000.
    """
    gross_income = max(0.0, float(gross_annual_income))
    standard_deduction = min(gross_income, NEW_REGIME_STANDARD_DEDUCTION)
    net_taxable_income = max(0.0, gross_income - standard_deduction)

    slab_tax, slab_breakdown = calculate_slab_tax(net_taxable_income, NEW_REGIME_SLABS)

    # Section 87A Rebate: if taxable income <= 7,00,000, tax liability is 0
    rebate_87a = 0.0
    if net_taxable_income <= NEW_REGIME_87A_THRESHOLD:
        rebate_87a = min(slab_tax, NEW_REGIME_87A_MAX_REBATE)
    
    # Marginal relief check for New Regime:
    # If income exceeds 7L slightly, tax payable cannot exceed income - 7,00,000
    tax_after_rebate = max(0.0, slab_tax - rebate_87a)
    if net_taxable_income > NEW_REGIME_87A_THRESHOLD:
        excess_income = net_taxable_income - NEW_REGIME_87A_THRESHOLD
        if tax_after_rebate > excess_income:
            # Marginal relief applied
            marginal_relief = tax_after_rebate - excess_income
            tax_after_rebate = excess_income
        else:
            marginal_relief = 0.0
    else:
        marginal_relief = 0.0

    # 4% Health & Education Cess
    cess = round(tax_after_rebate * HEALTH_AND_EDUCATION_CESS_RATE, 2)
    total_tax_payable = round(tax_after_rebate + cess, 2)
    monthly_withholding = round(total_tax_payable / 12.0, 2)
    effective_rate = round((total_tax_payable / gross_income * 100), 2) if gross_income > 0 else 0.0

    return {
        "regime": "New Tax Regime (Sec 115BAC)",
        "regime_key": "new",
        "gross_annual_income": round(gross_income, 2),
        "standard_deduction": round(standard_deduction, 2),
        "other_deductions": 0.0,
        "total_deductions": round(standard_deduction, 2),
        "net_taxable_income": round(net_taxable_income, 2),
        "slab_tax": round(slab_tax, 2),
        "rebate_87a": round(rebate_87a, 2),
        "marginal_relief": round(marginal_relief, 2),
        "tax_after_rebate": round(tax_after_rebate, 2),
        "cess_4_pct": cess,
        "total_tax_payable": total_tax_payable,
        "monthly_tax_withholding": monthly_withholding,
        "effective_tax_rate": effective_rate,
        "slab_breakdown": slab_breakdown,
        "applicable_fy": "FY 2024-25 / FY 2025-26",
        "rebate_note": "Rebate under Section 87A covers net income up to ₹7,00,000 (tax becomes ₹0)."
    }


def compute_tax_old_regime(
    gross_annual_income: float,
    deduction_80c: float = 0.0,
    deduction_80d: float = 0.0,
    hra_exemption: float = 0.0,
    home_loan_interest_24b: float = 0.0,
    other_deductions: float = 0.0
) -> Dict[str, Any]:
    """
    Calculates Income Tax under India's Old Tax Regime.
    Allows standard deduction of ₹50,000 plus Chapter VI-A deductions (80C, 80D, HRA, etc.).
    Section 87A rebate applies if net taxable income <= ₹5,00,000.
    """
    gross_income = max(0.0, float(gross_annual_income))
    standard_deduction = min(gross_income, OLD_REGIME_STANDARD_DEDUCTION)

    # Apply caps
    capped_80c = min(max(0.0, float(deduction_80c)), MAX_80C_DEDUCTION)
    capped_80d = min(max(0.0, float(deduction_80d)), MAX_80D_DEDUCTION)
    capped_hra = max(0.0, float(hra_exemption))
    capped_home_loan = min(max(0.0, float(home_loan_interest_24b)), MAX_HOME_LOAN_INTEREST_24B)
    other_ded = max(0.0, float(other_deductions))

    total_exemptions_deductions = (
        standard_deduction + capped_80c + capped_80d + capped_hra + capped_home_loan + other_ded
    )
    total_deductions = min(gross_income, total_exemptions_deductions)
    net_taxable_income = max(0.0, gross_income - total_deductions)

    slab_tax, slab_breakdown = calculate_slab_tax(net_taxable_income, OLD_REGIME_SLABS)

    # Section 87A Rebate: if taxable income <= 5,00,000, tax liability is 0 (up to 12,500)
    rebate_87a = 0.0
    if net_taxable_income <= OLD_REGIME_87A_THRESHOLD:
        rebate_87a = min(slab_tax, OLD_REGIME_87A_MAX_REBATE)

    tax_after_rebate = max(0.0, slab_tax - rebate_87a)
    cess = round(tax_after_rebate * HEALTH_AND_EDUCATION_CESS_RATE, 2)
    total_tax_payable = round(tax_after_rebate + cess, 2)
    monthly_withholding = round(total_tax_payable / 12.0, 2)
    effective_rate = round((total_tax_payable / gross_income * 100), 2) if gross_income > 0 else 0.0

    return {
        "regime": "Old Tax Regime (With Chapter VI-A)",
        "regime_key": "old",
        "gross_annual_income": round(gross_income, 2),
        "standard_deduction": round(standard_deduction, 2),
        "deduction_80c": round(capped_80c, 2),
        "deduction_80d": round(capped_80d, 2),
        "hra_exemption": round(capped_hra, 2),
        "home_loan_interest_24b": round(capped_home_loan, 2),
        "other_deductions": round(other_ded, 2),
        "total_deductions": round(total_deductions, 2),
        "net_taxable_income": round(net_taxable_income, 2),
        "slab_tax": round(slab_tax, 2),
        "rebate_87a": round(rebate_87a, 2),
        "marginal_relief": 0.0,
        "tax_after_rebate": round(tax_after_rebate, 2),
        "cess_4_pct": cess,
        "total_tax_payable": total_tax_payable,
        "monthly_tax_withholding": monthly_withholding,
        "effective_tax_rate": effective_rate,
        "slab_breakdown": slab_breakdown,
        "applicable_fy": "FY 2024-25 / FY 2025-26",
        "rebate_note": "Rebate under Section 87A covers net income up to ₹5,00,000 (tax becomes ₹0)."
    }


def compare_tax_regimes(
    gross_annual_income: float,
    deduction_80c: float = 0.0,
    deduction_80d: float = 0.0,
    hra_exemption: float = 0.0,
    home_loan_interest_24b: float = 0.0,
    other_deductions: float = 0.0
) -> Dict[str, Any]:
    """
    Compares New vs Old Tax Regime and provides a clear recommendation
    highlighting the tax savings.
    """
    new_res = compute_tax_new_regime(gross_annual_income)
    old_res = compute_tax_old_regime(
        gross_annual_income,
        deduction_80c=deduction_80c,
        deduction_80d=deduction_80d,
        hra_exemption=hra_exemption,
        home_loan_interest_24b=home_loan_interest_24b,
        other_deductions=other_deductions
    )

    diff = old_res["total_tax_payable"] - new_res["total_tax_payable"]

    if diff > 0:
        recommended = "new"
        recommendation_text = (
            f"The New Tax Regime is beneficial! You save ₹{diff:,.2f} annually "
            f"(₹{diff/12:,.2f} per month)."
        )
        savings = round(diff, 2)
    elif diff < 0:
        recommended = "old"
        savings = round(abs(diff), 2)
        recommendation_text = (
            f"The Old Tax Regime is beneficial! You save ₹{savings:,.2f} annually "
            f"(₹{savings/12:,.2f} per month) through deductions."
        )
    else:
        recommended = "equal"
        savings = 0.0
        recommendation_text = (
            "Both regimes result in the exact same tax liability. "
            "New Regime is typically simpler with zero paperwork."
        )

    return {
        "new_regime": new_res,
        "old_regime": old_res,
        "recommended": recommended,
        "tax_savings": savings,
        "recommendation_text": recommendation_text
    }


def estimate_monthly_tds(
    monthly_gross: float,
    regime: str = "new",
    annual_80c: float = 0.0,
    annual_80d: float = 0.0,
    annual_hra_exemption: float = 0.0
) -> float:
    """
    Quick helper for monthly payroll to calculate Tax Deducted at Source (TDS).
    Multiplies monthly gross by 12 to project annual salary, runs the engine,
    and returns 1/12th of the estimated annual tax liability.
    """
    projected_annual = max(0.0, monthly_gross * 12.0)
    if regime.lower() == "old":
        res = compute_tax_old_regime(
            projected_annual,
            deduction_80c=annual_80c,
            deduction_80d=annual_80d,
            hra_exemption=annual_hra_exemption
        )
    else:
        res = compute_tax_new_regime(projected_annual)

    return res["monthly_tax_withholding"]
