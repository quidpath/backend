"""
Comprehensive dictionary of accounting label aliases for financial statement extraction.

This module contains canonical field mappings with 20-40+ synonyms per field,
covering Income Statements, P&L Statements, Management Accounts, Audited Financials,
SME reports, IFRS, GAAP, and regional variations.
"""

from __future__ import annotations

from typing import Dict, List

# COMPREHENSIVE ACCOUNTING ALIAS DICTIONARY
# Each canonical field maps to a list of 20-40+ synonyms covering all variations

ACCOUNTING_ALIASES: Dict[str, List[str]] = {
    "total_revenue": [
        # Standard terms
        "total revenue",
        "revenue",
        "revenues",
        "total revenues",
        "sales",
        "total sales",
        "net sales",
        "gross sales",
        "turnover",
        "total turnover",
        "net turnover",
        # REMOVED "operating income" (ambiguous - could be revenue OR profit)
        # REMOVED "income" alone (too generic)
        "total income",
        "sales revenue",
        "revenue from sales",
        "sales income",
        "revenue from operations",
        "operating revenue",
        "net revenue",
        "gross revenue",
        # With colons/punctuation
        "revenue:",
        "total revenue:",
        "sales:",
        "turnover:",
        "revenue (net)",
        "sales (net)",
        "turnover (net)",
        # Abbreviations
        "rev",
        "rev.",
        "sales rev",
        "sales rev.",
        "tr",
        "tr.",
        # Long forms
        "total revenue generated during the period",
        "income from primary business operations",
        "revenue from continuing operations",
        "total operating revenue",
        # Regional/format variations
        "trading income",
        "business income",
        "operating income",
        "revenue from goods sold",
        "revenue from services",
        "net sales revenue",
        "gross sales revenue",
        "sales of goods",
        "service revenue",
        # IFRS/GAAP variations
        "revenue from contracts with customers",
        "revenue from ordinary activities",
        "operating revenue (net)",
        # OCR/noisy variations
        "revenuc",
        "revenu",
        "revanue",
        "revenuee",
        "totai revenue",
        "tota1 revenue",
        "revenue tota1",
    ],
    "cogs": [
        # Standard terms
        "cogs",
        "cost of goods sold",
        "cost of sales",
        "cost of revenue",
        "cost of revenues",
        "cost goods sold",
        "costs of goods sold",
        "costs of sales",
        "cost of products sold",
        # Long forms
        "total cost of goods sold",
        "total cost of sales",
        "cost of goods sold (cogs)",
        "cost of sales (cos)",
        # Abbreviations
        "cogs",
        "cos",
        "cgs",
        "cost of gs",
        # With colons
        "cogs:",
        "cost of goods sold:",
        "cost of sales:",
        # Direct costs
        "direct costs",
        "direct cost",
        "total direct costs",
        "direct materials",
        "direct labor",
        "direct expenses",
        # Purchases/Materials
        "purchases",
        "total purchases",
        "purchases of goods",
        "materials",
        "raw materials",
        "inventory costs",
        "cost of inventory sold",
        "cost of merchandise sold",
        # Labor/Materials combinations
        "direct labor costs",
        "labor costs",
        "casual labor",
        "parts and materials",
        "parts & materials",
        "purchases - parts & materials",
        "purchases parts materials",
        #  FIX: Add hire/rental of tools and equipment
        "hire of small tools",
        "hire small tools equipment",
        "hire of tools",
        "hire tools",
        "tool hire",
        "hire of equipment",
        "equipment hire",
        "machinery hire",
        # Manufacturing
        "manufacturing costs",
        "production costs",
        "cost of production",
        "factory costs",
        # Regional variations
        "cost of trading stock",
        "cost of inventory",
        "goods purchased for resale",
        "merchandise costs",
        # OCR/noisy
        "cost of go0ds sold",
        "c0gs",
        "cost of g00ds",
        "purchases parts materiais",
        "materiais costs",
    ],
    "gross_profit": [
        # Standard terms
        "gross profit",
        "gross income",
        "gross margin",
        "gross earnings",
        "gross profit margin",
        # Long forms
        "total gross profit",
        "gross profit (loss)",
        "gross profit before expenses",
        "gross operating profit",
        # With colons
        "gross profit:",
        "gross income:",
        "gross margin:",
        # Abbreviations
        "gp",
        "g.p.",
        "gross p",
        "gross prof",
        # Calculations
        "revenue less cost of sales",
        "sales less cost of sales",
        "turnover less cost of sales",
        # Regional
        "trading profit",
        "gross trading profit",
        "profit before operating expenses",
        # OCR/noisy
        "gross pr0fit",
        "gross prof1t",
        "gross in come",
    ],
    "operating_expenses": [
        # Standard terms
        "operating expenses",
        "operating expense",
        "total operating expenses",
        "operating costs",
        "operating cost",
        "total operating costs",
        "operating expenditure",
        "operating expenditures",
        # Abbreviations
        "opex",
        "opex.",
        "op ex",
        "operating exp",
        "oper exp",
        # Long forms
        "total operating expenses",
        "total operating costs",
        "operating expenses (total)",
        "operating costs (total)",
        # With colons
        "operating expenses:",
        "operating costs:",
        "opex:",
        # Expense categories (totals)
        "total expenses",
        "total expense",
        "expenses (total)",
        "overhead",
        "total overhead",
        "operating overhead",
        # Common components (when looking for totals)
        "salaries and wages",
        "total salaries",
        "total wages",
        "rent expense",
        "total rent",
        "rent and utilities",
        "utilities",
        "total utilities",
        "electricity and water",
        "office expenses",
        "total office expenses",
        "marketing expenses",
        "total marketing",
        "administrative expenses",
        "admin expenses",
        "total admin",
        #  FIX: Add commonly missed expense categories
        "travel expenses",
        "travel",
        "travelling expenses",
        "travel and accommodation",
        "travelling accommodation allowance",
        "accommodation expenses",
        "accommodation allowance",
        "clearing and forwarding",
        "clearing & forwarding",
        "clearing forwarding",
        "forwarding charges",
        "freight expenses",
        "freight and forwarding",
        "logistics expenses",
        "logistics costs",
        # Regional
        "operating charges",
        "operating outgoings",
        "business expenses",
        "total business expenses",
        # IFRS/GAAP
        "selling, general and administrative expenses",
        "sga",
        "sg&a",
        "sg and a",
        "selling and administrative",
        # OCR/noisy
        "operating expenscs",
        "opexx",
        "operating expens",
        "totai operating expenses",
        "operating expenscs",
    ],
    "operating_income": [
        # Standard terms
        "operating income",
        "operating profit",
        "operating earnings",
        "operating result",
        "operating profit (loss)",
        # Long forms
        "total operating income",
        "net operating income",
        "operating income before interest",
        "operating profit before tax",
        # With colons
        "operating income:",
        "operating profit:",
        "operating result:",
        # Abbreviations
        "oi",
        "o.i.",
        "oper inc",
        "oper prof",
        # EBIT (Earnings Before Interest and Tax)
        "ebit",
        "e.b.i.t.",
        "earnings before interest and tax",
        "earnings before interest and taxes",
        "ebitda (before da)",
        # Calculations
        "gross profit less operating expenses",
        "revenue less operating expenses",
        # Regional
        "trading profit",
        "operating profit before interest",
        "profit from operations",
        "income from operations",
        # OCR/noisy
        "operating in come",
        "operating pr0fit",
        "ebit (no da)",
    ],
    "interest_expense": [
        # Standard terms
        "interest expense",
        "interest paid",
        "interest charges",
        "interest cost",
        "total interest expense",
        # Long forms
        "interest expense (total)",
        "interest on borrowings",
        "interest on loans",
        "interest on debt",
        # With colons
        "interest expense:",
        "interest paid:",
        "interest:",
        # Abbreviations
        "int exp",
        "int expense",
        "interest exp",
        # Finance costs
        "finance costs",
        "financial expenses",
        "finance charges",
        "borrowing costs",
        "cost of borrowing",
        # Interest types
        "bank interest",
        "loan interest",
        "interest on overdraft",
        "interest on credit facilities",
        # Regional
        "interest payable",
        "interest incurred",
        # OCR/noisy
        "interest expensc",
        "intcrcst",
        "interest expens",
    ],
    "taxes": [
        # Standard terms - HIGH PRIORITY
        "taxes",
        "tax",
        "income tax",
        "income taxes",
        "tax expense",
        "taxation",
        "tax provision",
        # With percentages/rates (very common)
        "tax expense (30%)",
        "tax expense (25%)",
        "tax expense (35%)",
        "tax expense (20%)",
        "tax (30%)",
        "tax (25%)",
        "tax (35%)",
        "tax (20%)",
        "tax (15%)",
        "income tax (30%)",
        "income tax (25%)",
        "income tax (35%)",
        # Long forms
        "total taxes",
        "total tax expense",
        "income tax expense",
        "income tax provision",
        "tax on income",
        # With colons
        "taxes:",
        "tax:",
        "income tax:",
        "taxation:",
        "tax expense:",
        "income tax expense:",
        # Abbreviations
        "tax exp",
        "tax expen",
        "it",
        "i.t.",
        # Tax types
        "corporate tax",
        "company tax",
        "corporation tax",
        "federal tax",
        "state tax",
        "local tax",
        # Provision/accrual
        "tax provision",
        "tax accrual",
        "deferred tax",
        "current tax",
        "tax payable",
        # Regional
        "taxation expense",
        "tax charge",
        "tax on profit",
        "tax on earnings",
        "earnings tax",
        # OCR/noisy
        "taxcs",
        "tax expensc",
        "incomc tax",
    ],
    "net_income": [
        # Standard terms - HIGHEST PRIORITY (exact match)
        "net income",
        "net profit",
        "net earnings",
        "net profit after tax",
        "profit after tax",
        # With slash variations (very common in accounting software)
        "net profit/loss",
        "net profit / loss",  # ← FIX: Add this!
        "profit/loss",
        "profit / loss",
        "net income/loss",
        "net income / loss",
        # Long forms
        "total net income",
        "net income after tax",
        "net profit for the period",
        "profit for the year",
        "profit for the period",  #  ADD: Common in statements
        # With colons
        "net income:",
        "net profit:",
        "profit after tax:",
        # Abbreviations
        "ni",
        "n.i.",
        "net inc",
        "net prof",
        # Bottom line
        "bottom line",
        "net result",
        "final profit",
        "profit (loss)",
        "net profit (loss)",
        # Calculations
        "profit after interest and tax",
        "earnings after tax",
        # Regional
        "net profit attributable",
        "profit for the year",
        "retained earnings (current period)",
        # OCR/noisy
        "net in come",
        "net pr0fit",
        "profit aftcr tax",
        #  DO NOT ADD "profit before tax" - it belongs to EBIT/pre-tax profit
    ],
    "depreciation": [
        # Standard terms
        "depreciation",
        "depreciation expense",
        "total depreciation",
        "depreciation charge",
        "depreciation and amortization",
        # Long forms
        "depreciation expense",
        "depreciation of fixed assets",
        "depreciation of property, plant and equipment",
        # With colons
        "depreciation:",
        "depreciation expense:",
        # Abbreviations
        "dep",
        "dep.",
        "depn",
        "depn.",
        # Types
        "straight line depreciation",
        "accelerated depreciation",
        "accumulated depreciation",
        "depreciation provision",
        # OCR/noisy
        "depreciatlon",
        "depreciatlon expense",
    ],
    "amortization": [
        # Standard terms
        "amortization",
        "amortisation",
        "amortization expense",
        "total amortization",
        "amortization charge",
        # Long forms
        "amortization of intangible assets",
        "amortization of goodwill",
        # With colons
        "amortization:",
        "amortisation:",
        # Abbreviations
        "amort",
        "amort.",
        "amort exp",
        # OCR/noisy
        "amortizatlon",
        "amortisatlon",
    ],
    "ebit": [
        # Standard terms
        "ebit",
        "e.b.i.t.",
        "earnings before interest and tax",
        "earnings before interest and taxes",
        # Long forms
        "earnings before interest and taxation",
        "operating profit before interest and tax",
        "profit before tax",  #  ADD: Common pre-tax profit label
        "profit before income tax",
        "pbt",
        "p.b.t.",
        "earnings before tax",
        "income before tax",
        # With colons
        "ebit:",
        "earnings before interest and tax:",
        "profit before tax:",
        # Alternative names
        "operating profit",
        "operating income",
        # OCR/noisy
        "eblt",
        "earnlngs before lnterest",
        "profit b4 tax",
    ],
    "ebitda": [
        # Standard terms
        "ebitda",
        "e.b.i.t.d.a.",
        "earnings before interest, tax, depreciation and amortization",
        "earnings before interest, taxes, depreciation and amortization",
        # Long forms
        "ebitda (earnings before interest, tax, depreciation and amortization)",
        # With colons
        "ebitda:",
        "ebitda (adjusted):",
        # OCR/noisy
        "ebltda",
        "earnlngs before lnterest tax",
    ],
    "operating_profit": [
        # Standard terms
        "operating profit",
        "operating income",
        "operating earnings",
        "profit from operations",
        "income from operations",
        # Long forms
        "operating profit before interest",
        "operating profit (loss)",
        # With colons
        "operating profit:",
        "profit from operations:",
        # Regional
        "trading profit",
        "operating result",
        # OCR/noisy
        "operating pr0fit",
        "profit from operatlons",
    ],
    "sales_expenses": [
        # Standard terms
        "sales expenses",
        "selling expenses",
        "sales costs",
        "total sales expenses",
        "total selling expenses",
        # Long forms
        "expenses related to sales",
        "costs of selling",
        # With colons
        "sales expenses:",
        "selling expenses:",
        # Components
        "sales commissions",
        "sales salaries",
        "advertising",
        "marketing expenses",
        "promotion costs",
        # OCR/noisy
        "sales expenscs",
        "selling expenscs",
    ],
    "admin_expenses": [
        # Standard terms
        "administrative expenses",
        "admin expenses",
        "administration expenses",
        "total administrative expenses",
        "total admin expenses",
        # Long forms
        "general and administrative expenses",
        "g&a expenses",
        # With colons
        "administrative expenses:",
        "admin expenses:",
        # Abbreviations
        "g&a",
        "g and a",
        "admin exp",
        "admin costs",
        # Components
        "office expenses",
        "management salaries",
        "legal fees",
        "accounting fees",
        "insurance",
        # OCR/noisy
        "administratlve expenses",
        "admin expenscs",
    ],
    "finance_costs": [
        # Standard terms
        "finance costs",
        "financial costs",
        "finance charges",
        "total finance costs",
        "financial expenses",
        # Long forms
        "costs of financing",
        "financing costs",
        # With colons
        "finance costs:",
        "financial costs:",
        # Components
        "interest expense",
        "bank charges",
        "loan fees",
        "credit facility costs",
        # OCR/noisy
        "finance c0sts",
        "flnancial costs",
    ],
    "total_expenses": [
        # Standard terms
        "total expenses",
        "total expense",
        "expenses (total)",
        "all expenses",
        "total costs",
        "total cost",
        # Long forms
        "total operating and non-operating expenses",
        # With colons
        "total expenses:",
        "total costs:",
        # Abbreviations
        "tot exp",
        "total exp",
        "tot costs",
        # OCR/noisy
        "totai expenses",
        "total expenscs",
    ],
    "other_income": [
        # Standard terms
        "other income",
        "other revenues",
        "miscellaneous income",
        "total other income",
        "other operating income",
        # Long forms
        "income from other sources",
        "other income (net)",
        # With colons
        "other income:",
        "miscellaneous income:",
        # Types
        "interest income",
        "dividend income",
        "rental income",
        "gain on sale of assets",
        # OCR/noisy
        "other in come",
        "miscellaneous lncome",
    ],
    "other_expenses": [
        # Standard terms
        "other expenses",
        "other costs",
        "miscellaneous expenses",
        "total other expenses",
        "other operating expenses",
        # Long forms
        "expenses from other activities",
        "other expenses (net)",
        # With colons
        "other expenses:",
        "miscellaneous expenses:",
        # Types
        "loss on sale of assets",
        "impairment charges",
        "restructuring costs",
        # OCR/noisy
        "other expenscs",
        "miscellaneous expenscs",
    ],
}


def _normalize_for_matching(text: str) -> str:
    """
    Normalize text for matching: lowercase, remove punctuation, normalize spaces.
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove punctuation (keep spaces and hyphens for now)
    import re

    text = re.sub(r"[^\w\s\-]", "", text)

    # Normalize whitespace
    text = " ".join(text.split())

    # Remove hyphens (treat as spaces)
    text = text.replace("-", " ").replace("_", " ")

    # Final whitespace normalization
    text = " ".join(text.split())

    return text.strip()


#  FIELD PRIORITY (for tie-breaking)
# Fields that should take precedence when multiple matches occur
FIELD_PRIORITY = {
    "total_revenue": 10,
    "cogs": 9,
    "gross_profit": 8,
    "operating_expenses": 7,
    "operating_income": 6,
    "taxes": 6,  #  FIX: Boost taxes priority to match interest_expense (prevent "Tax Expense" matching to interest)
    "net_income": 6,  #  FIX: Boost net_income to match taxes (prevent "Net Profit/Loss" matching to taxes)
    "interest_expense": 5,
    "ebit": 6,  # Same as operating_income
    "ebitda": 5,
    "operating_profit": 6,  # Same as operating_income
    "depreciation": 4,
    "amortization": 4,
    "sales_expenses": 3,
    "admin_expenses": 3,
    "finance_costs": 3,
    "total_expenses": 2,
    "other_income": 2,
    "other_expenses": 2,
}
