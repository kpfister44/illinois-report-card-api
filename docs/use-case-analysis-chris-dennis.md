# API Use Case Analysis — Chris Dennis (CTU / IRRPP)

**Date:** 2026-04-09  
**Contact:** Chris Dennis, researcher at Chicago Teachers Union / Institute for Research on Race and Public Policy (IRRPP)

---

## Project 1: CTU — District Finance + Demographics (2017-18 through 2023-24)

**Goal:** Build a dataset merging property levy, EAV, and demographics with Evidence-Based Funding adequacy targets to compare levy changes over time to school funding need.

| Need | Available | Notes |
|------|-----------|-------|
| District-level data | ✅ 2018–2024 | 865 districts per year |
| Racial demographics | ✅ | % White, Black, Hispanic, Asian, 2+ races, low income, IEP |
| Finance data | ✅ 2018–2024 | Property taxes, total revenue, tax rate per $100, expenditures per pupil |
| 2017-18 data | ❌ | District table does not exist for 2017 — schools only |

**Verdict:** Good fit for 2018–2024 (7 years). He'll be missing the 2017-18 year he asked for.

**Important caveat:** Finance columns in the 2018 table are labeled `2016_17` — ISBE publishes prior-year actuals in the current report card. The finance data lags the report card year by one year. Chris should account for this when merging by year.

---

## Project 2: IRRPP — Harmonized Property Tax Inequality Dataset (2000–2025)

**Goal:** Update a previously harmonized 2000–2020 dataset to 2025 for a report on property tax inequality across the Chicagoland area. Originally written in R, wants to use the API in Python instead.

| Need | Available | Notes |
|------|-----------|-------|
| 2010–2024 data | ✅ | Full coverage |
| Pre-2010 data (2000–2009) | ❌ | Not in the API — ISBE source files not imported |

**Verdict:** Partial fit. The API covers 2010–2024, so it can extend his dataset forward. He'll still need his original R-cleaned data for years 2000–2009.

---

## Overall Recommendation

Give him access. Both projects are legitimate research use cases and the API covers the bulk of what he needs. Be upfront about:

1. No district table for 2017 (Project 1 will cover 2018–2024, not 2017–2024)
2. Finance data lags by one year in the report card
3. No pre-2010 data (Project 2 still needs his original source for 2000–2009)

He's offered to cite the API/GitHub in both reports, and the IRRPP report has potential UIC student exposure — good visibility.
