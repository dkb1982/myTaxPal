"""Executable coverage contract for source-checked calculation profiles.

This registry is deliberately independent of rule-file discovery: a file on disk
does not make a jurisdiction available to callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path


class CoverageStatus(StrEnum):
    ENABLED = "enabled"
    PENDING = "pending"
    BLOCKED = "blocked"


class UnsupportedCoverageError(ValueError):
    """A requested jurisdiction, period or profile has no verified policy."""


@dataclass(frozen=True)
class CoverageEntry:
    jurisdiction_id: str
    tax_year: int
    profile_id: str
    status: CoverageStatus
    native_period_id: str
    period_label: str
    period_start: date
    period_end: date
    earnings_start: date
    earnings_end: date
    parent_id: str | None
    dependencies: tuple[str, ...]
    rule_paths: tuple[str, ...]
    policy_id: str
    rules_version: str
    currency: str
    rounding: str
    income_categories: frozenset[str]
    loss_treatment: str
    locality_status: str
    payroll_scope: str
    evidence_ids: tuple[str, ...]
    verified_on: date | None
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.period_end < self.period_start or self.earnings_end < self.earnings_start:
            raise ValueError("Coverage periods must have inclusive start/end dates")
        if self.status == CoverageStatus.ENABLED:
            if not self.rule_paths or not self.evidence_ids or self.verified_on is None:
                raise ValueError("Enabled coverage requires rules, evidence and verification")
            if self.unavailable_reason:
                raise ValueError("Enabled coverage cannot have an unavailable reason")
        elif not self.unavailable_reason:
            raise ValueError("Unavailable coverage requires a public-safe reason")


US_VANILLA_PROFILE = "us_single_40_resident_employee_standard_direct_securities_v1"
US_VANILLA_INCOME = frozenset({
    "employment_wages", "dividends_ordinary", "dividends_qualified",
    "capital_gains_short_term", "capital_gains_long_term",
})

_RULES_ROOT = Path(__file__).resolve().parents[3] / "rules"

SOURCE_LEDGER: dict[str, str] = {
    "IRS-REV-PROC-2025-32": "https://www.irs.gov/irb/2025-45_IRB",
    "SSA-2026-WAGE-BASE": "https://www.ssa.gov/oact/COLA/cbb.html",
    "TX-CONST-ART-8-24A": "https://tcss.legis.texas.gov/resources/CN/htm/CN.8.htm",
    "AK-NO-PERSONAL-IT": "https://labor.alaska.gov/lss/forms/Pam400.pdf",
    "FL-NO-PERSONAL-IT": "https://floridarevenue.com/faq/Pages/FAQDetails.aspx?FAQID=1466",
    "NV-NO-PERSONAL-IT": "https://tax.nv.gov/about-nevada-department-of-taxation/income-tax-in-nevada/",
    "NH-INTEREST-DIVIDEND-REPEAL": "https://www.revenue.nh.gov/news-and-media/repeal-nh-interest-and-dividends-tax-now-effect",
    "SD-NO-PERSONAL-IT": "https://dor.sd.gov/individuals/taxes/",
    "TN-HALL-TAX-REPEAL": "https://www.tn.gov/revenue/taxes/hall-income-tax.html",
    "WY-NO-PERSONAL-IT": "https://wyomingbusiness.org/why-wyoming/business-resources/",
    "NC-2026-SRC-1": "https://www.ncdor.gov/income-tax-withholding-tables-and-instructions-employers/open",
    "NC-2026-SRC-2": "https://www.ncdor.gov/important-notice-impact-recently-enacted-laws-north-carolina-individual-and-corporate-income-tax",
    "NC-2026-SRC-3": "https://taxnews.ey.com/news/2026-1630-north-carolina-law-progressively-lowers-personal-income-tax-rate-over-several-years",
    "ND-2026-SRC-1": "https://www.tax.nd.gov/sites/www/files/documents/forms/individual/2025-iit/28709-form-nd-1es-2026.pdf",
    "ND-2026-SRC-2": "https://ndlegis.gov/cencode/t57c38.pdf",
    "ND-2026-SRC-3": "https://www.tax.nd.gov/sites/www/files/documents/forms/individual/2026-iit/2026-income-tax-withholding-rates-booklet.pdf",
    "OH-2026-SRC-1": "https://codes.ohio.gov/ohio-revised-code/section-5747.02",
    "OH-2026-SRC-2": "https://codes.ohio.gov/ohio-revised-code/section-5747.025",
    "OH-2026-SRC-3": "https://codes.ohio.gov/ohio-revised-code/section-5747.022",
    "OH-2026-SRC-4": "https://www.lsc.ohio.gov/assets/legislation/136/hb96/en0/files/hb96-tax-bill-analysis-as-enacted-136th-general-assembly.pdf",
    "OH-2026-SRC-5": "https://dam.assets.ohio.gov/image/upload/tax.ohio.gov/forms/ohio_individual/individual/2025/it1040-booklet.pdf",
    "OK-2026-SRC-1": "https://www.oklegislature.gov/cf_pdf/2025-26%20ENR/hB/HB2764%20ENR.PDF",
    "OK-2026-SRC-2": "https://otcportal.tax.ok.gov/billimpact/Home/GetPDF/2025HB2764",
    "OK-2026-SRC-3": "https://oklahoma.gov/content/dam/ok/en/tax/documents/forms/individuals/current/511-Pkt.pdf",
    "OR-2026-SRC-1": "https://www.oregon.gov/dor/forms/FormsPubs/publication-or-estimate_101-026_2026.pdf",
    "OR-2026-SRC-2": "https://www.oregon.gov/dor/forms/FormsPubs/withholding-tax-formulas_206-436_2026.pdf",
    "OR-2026-SRC-3": "https://www.oregonlegislature.gov/bills_laws/ors/ors316.html",
    "OR-2026-SRC-4": "https://data.bls.gov/timeseries/CUUR0000SA0",
    "PA-2026-SRC-1": "https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/personal-income-tax",
    "PA-2026-SRC-2": "https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/personal-income-tax/tax-forgiveness",
    "PA-2026-SRC-3": "https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/personal-income-tax/working-pennsylvanians-tax-credit",
    "RI-2026-SRC-1": "https://tax.ri.gov/sites/g/files/xkgbur541/files/2025-11/ADV_2025_22_Inflation_Adjustments.pdf",
    "RI-2026-SRC-2": "https://rilegislature.gov/housefiscalreport/2020/FY%202027%20Budget%20as%20Enacted%20-%20Budget%20at%20a%20Glance.pdf",
    "NYC-2026-SRC-1": "https://www.tax.ny.gov/pdf/current_forms/it/it2105i.pdf",
    "NYC-2026-SRC-2": "https://www.tax.ny.gov/pdf/current_forms/it/it201i.pdf",
    "NYC-2026-SRC-3": "https://www.tax.ny.gov/pdf/current_forms/it/it270i.pdf",
    "NYC-2026-SRC-4": "https://www.hodgsonruss.com/newsroom/alerts/tax-provisions-of-interest-in-the-enacted-2026-27-new-york-budget-bill",
    "YNK-2026-SRC-1": "https://www.tax.ny.gov/pdf/current_forms/it/it2105i.pdf",
    "YNK-2026-SRC-2": "https://www.tax.ny.gov/pdf/current_forms/it/it201i.pdf",
    "DET-2026-SRC-1": "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/City-Withholding/TY2026/5469_ty2026.pdf",
    "DET-2026-SRC-2": "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/City-IIT/TY2025/5313_City-Book.pdf",
    "BAL-2026-SRC-1": "https://www.marylandcomptroller.gov/content/dam/mdcomp/md/state-payroll/memos/2026/2026-maryland-state-and-local-withholding-information.pdf",
    "BAL-2026-SRC-2": "https://dls.maryland.gov/pubs/prod/NoPblTabPDF/2026CountyLocalTaxRates.pdf",
    "BAL-2026-SRC-3": "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gtg&section=10-704&enactments=false",
    "BAL-2026-SRC-4": "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gtg&section=10-709&enactments=false",
    "BAL-2026-SRC-5": "https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines",
    "IND-2026-SRC-1": "https://www.in.gov/dor/files/dn01.pdf",
    "IND-2026-SRC-2": "https://www.in.gov/dor/i-am-a/individual/first-time-filer/your-indiana-tax-return-line-by-line/",
    "BHM-2026-SRC-1": "https://s3.us-east-2.amazonaws.com/assets.birminghamal.gov/s3fs-public/2026-09/FY26%20Offical%20Budget%20Book%20Merged%20with%20Tabs.pdf%20(v2).pdf",
    "BHM-2026-SRC-2": "https://library.municode.com/al/birmingham/codes/code_of_ordinances?nodeId=PT1THCOGEOR_TIT3ARETA_CH2OCTA",
    "LOU-2026-SRC-1": "https://louisvilleky.gov/sites/default/files/2026-01/Louisville%20Metro%20Revenue%20Commission%20Regulations%20(2026).1.pdf",
    "LOU-2026-SRC-2": "https://louisvilleky.gov/sites/default/files/2024-12/ol-3d_instructions_2025.pdf",
    "CLE-2026-SRC-1": "https://www.ccaohio.gov/tax-rates/",
    "CLE-2026-SRC-2": "https://codes.ohio.gov/ohio-revised-code/section-718.01",
    "CIN-2026-SRC-1": "https://www.cincinnati-oh.gov/finance/income-taxes/",
    "CIN-2026-SRC-2": "https://codes.ohio.gov/ohio-revised-code/section-718.01",
    "CMH-2026-SRC-1": "https://www.columbus.gov/Government/City-Auditor/Income-Tax-Division/General-Income-Tax-Information",
    "CMH-2026-SRC-2": "https://www.columbus.gov/files/sharedassets/city/v/2/city-auditor/news/2026-official-revenue-estimate-of-the-city-auditor.pdf",
    "CMH-2026-SRC-3": "https://codes.ohio.gov/ohio-revised-code/section-718.01",
    "PHL-2026-SRC-1": "https://www.phila.gov/documents/tax-rate-schedule/",
    "PHL-2026-SRC-2": "https://www.phila.gov/services/payments-assistance-taxes/business-taxes/wage-tax-employers/",
    "PHL-2026-SRC-3": "https://www.phila.gov/media/20260128151226/2025-School-Income-Tax-SIT-instructions.pdf",
    "SC-2026-SRC-1": "https://dor.sc.gov/sites/dor/files/policies/IL26-20.pdf",
    "SC-2026-SRC-2": "https://www.scstatehouse.gov/sess126_2025-2026/bills/4216.htm",
    "UT-2026-SRC-1": "https://le.utah.gov/xcode/Title59/Chapter10/C59-10-S104_2026050620260506.html",
    "UT-2026-SRC-2": "https://le.utah.gov/xcode/Title59/Chapter10/C59-10-S1018_2026050620260506.html",
    "UT-2026-SRC-3": "https://le.utah.gov/xcode/Title59/Chapter10/C59-10-S1044_2023050320230503.html",
    "UT-2026-SRC-4": "https://data.bls.gov/timeseries/CUUR0000SA0",
    "VT-2026-SRC-1": "https://legislature.vermont.gov/statutes/section/32/151/05822",
    "VT-2026-SRC-2": "https://legislature.vermont.gov/statutes/section/32/151/05811",
    "VT-2026-SRC-3": "https://legislature.vermont.gov/statutes/section/32/151/05828b",
    "VT-2026-SRC-4": "https://tax.vermont.gov/sites/tax/files/documents/GB-1210-2026.pdf",
    "VT-2026-SRC-5": "https://tax.vermont.gov/sites/tax/files/documents/IN-111-Instr-2025.pdf",
    "VT-2026-SRC-6": "https://data.bls.gov/timeseries/CUUR0000SA0",
    "VA-2026-SRC-1": "https://law.lis.virginia.gov/vacode/title58.1/chapter3/section58.1-320/",
    "VA-2026-SRC-2": "https://law.lis.virginia.gov/vacode/title58.1/chapter3/section58.1-322.03/",
    "VA-2026-SRC-3": "https://law.lis.virginia.gov/vacode/title58.1/chapter3/section58.1-321/",
    "VA-2026-SRC-4": "https://law.lis.virginia.gov/vacode/title58.1/chapter3/section58.1-339.8/",
    "VA-2026-SRC-5": "https://www.tax.virginia.gov/sites/default/files/inline-files/2026-legislative-summary.pdf",
    "VA-2026-SRC-6": "https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines",
    "WA-2026-SRC-1": "https://app.leg.wa.gov/RCW/default.aspx?cite=82.87.040",
    "WA-2026-SRC-2": "https://app.leg.wa.gov/RCW/default.aspx?cite=82.87.150",
    "WA-2026-SRC-3": "https://app.leg.wa.gov/RCW/default.aspx?cite=82.87.020",
    "WA-2026-SRC-4": "https://dor.wa.gov/taxes-rates/other-taxes/capital-gains-tax/do-you-owe-capital-gains-tax",
    "WA-2026-SRC-5": "https://data.bls.gov/timeseries/CUURS49DSA0",
    "WV-2026-SRC-1": "https://code.wvlegislature.gov/signed_bills/2026/2026-RS-SB392-SUB1%20ENR_signed.pdf",
    "WV-2026-SRC-2": "https://code.wvlegislature.gov/11-21-16/",
    "WV-2026-SRC-3": "https://code.wvlegislature.gov/11-21-22a/",
    "WV-2026-SRC-4": "https://code.wvlegislature.gov/11-21-22b/",
    "WV-2026-SRC-5": "https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines",
    "AR-2026-SRC-1": "https://www.arkleg.state.ar.us/Home/FTPDocument?path=%2FACTS%2F2026S1%2FPublic%2FACT2.pdf",
    "AR-2026-SRC-2": "https://www.arkleg.state.ar.us/Home/FTPDocument?path=%2FAssembly%2F2025%2F2026S1%2FFiscal+Impacts%2FHB1001-DFA1.pdf",
    "AR-2026-SRC-3": "https://www.dfa.arkansas.gov/wp-content/uploads/Withholding-Tax-Formula.pdf",
    "AR-2026-SRC-4": "https://www.dfa.arkansas.gov/wp-content/uploads/2026_Final_AR1000ES.pdf",
    "AR-2026-SRC-5": "https://www.dfa.arkansas.gov/wp-content/uploads/2025_TaxTables.pdf",
    "AR-2026-SRC-6": "https://www.dfa.arkansas.gov/wp-content/uploads/2025_AR1000D_CapitalGains.pdf",
    "CO-2026-SRC-1": "https://codes.findlaw.com/co/title-39-taxation/co-rev-st-sect-39-22-104/",
    "CO-2026-SRC-2": "https://tax.colorado.gov/individual-income-tax-guide",
    "CO-2026-SRC-3": "https://content.leg.colorado.gov/sites/default/files/2026-09/sept2026-forecast-with-cover-for-remediation-and-posting-accessible.pdf",
    "CO-2026-SRC-4": "https://content.leg.colorado.gov/sites/default/files/2026-te5-report-federal-tax-law-provisions-and-changes-impact-colorado-accessible.pdf",
    "WI-2026-SRC-1": "https://web.archive.org/web/20260307092226/https://docs.legis.wisconsin.gov/statutes/statutes/71.pdf",
    "WI-2026-SRC-2": "https://www.revenue.wi.gov/TaxForms2025/2025-Form1-Inst.pdf",
    "WI-2026-SRC-3": "https://www.revenue.wi.gov/WisconsinTaxBulletin/234-07-31-WTB.pdf",
    "WI-2026-SRC-4": "https://www.revenue.wi.gov/WisconsinTaxBulletin/233-04-30-WTB.pdf",
    "WI-2026-SRC-5": "https://data.bls.gov/timeseries/CUUR0000SA0",
    "MS-2026-SRC-1": "https://billstatus.ls.state.ms.us/documents/2025/pdf/HB/0001-0099/HB0001SG.pdf",
    "MS-2026-SRC-2": "https://www.dor.ms.gov/individual/tax-rates",
    "MO-2026-SRC-1": "https://dor.mo.gov/forms/Withholding%20Formula_2026.pdf",
    "MO-2026-SRC-2": "https://dor.mo.gov/forms/Withholding%20Formula_2025.pdf",
    "MO-2026-SRC-3": "https://dor.mo.gov/taxation/individual/tax-types/income/year-changes/",
    "MO-2026-SRC-4": "https://revisor.mo.gov/main/OneSection.aspx?section=143.171",
    "MO-2026-SRC-5": "https://showmeinstitute.org/article/state-and-local-government/2026-end-of-the-legislative-session-report/",
    "MT-2026-SRC-1": "https://revenue.mt.gov/news/recent-news/HB-337",
    "MT-2026-SRC-2": "https://mca.legmt.gov/bills/mca/title_0150/chapter_0300/part_0210/section_0030/0150-0300-0210-0030.html",
    "MT-2026-SRC-3": "https://archive.legmt.gov/content/Publications/fiscal/2027-Biennium/Committees/LFC/Interim/HR1-Provisions-and-Impacts.pdf",
    "MT-2026-SRC-4": "https://news.mt.gov/Governors-Office/Governor_Gianforte_Celebrates_Largest_Income_Tax_Cut_in_State-_History",
    "NE-2026-SRC-1": "https://revenue.nebraska.gov/sites/default/files/doc/tax-forms/2026/2026_tax_calculation_schedule.pdf",
    "NE-2026-SRC-2": "https://revenue.nebraska.gov/sites/default/files/doc/tax-forms/2026/f_1040n.pdf",
    "NE-2026-SRC-3": "https://revenue.nebraska.gov/tax-professionals/2026-final-income-tax-forms",
    "NJ-2026-SRC-1": "https://www.nj.gov/treasury/taxation/pdf/current/njtaxratesch.pdf",
    "NJ-2026-SRC-2": "https://www.nj.gov/treasury/taxation/taxtables.shtml",
    "NJ-2026-SRC-3": "https://www.nj.gov/governor/news/2026/20260630d.shtml",
    "NJ-2026-SRC-4": "https://www.nj.gov/treasury/taxation/pdf/current/1040i.pdf",
    "NM-2026-SRC-1": "https://taxsim.nber.org/historical_state_tax_forms/NM/2025/PIT%20rates_2005_2025.pdf",
    "NM-2026-SRC-2": "https://realfile.tax.newmexico.gov/2025pit-1-ins.pdf",
    "NM-2026-SRC-3": "https://realfile.tax.newmexico.gov/2025trt.pdf",
    "NM-2026-SRC-4": "https://www.nmsenate.com/senate-tax-committee-passes-comprehensive-tax-package-bill/",
    "NY-2026-SRC-1": "https://www.nysenate.gov/legislation/laws/TAX/601",
    "NY-2026-SRC-2": "https://www.nysenate.gov/legislation/laws/TAX/606",
    "NY-2026-SRC-3": "https://www.nysenate.gov/legislation/laws/TAX/614",
    "NY-2026-SRC-4": "https://www.hodgsonruss.com/newsroom/alerts/tax-provisions-of-interest-in-the-enacted-2026-27-new-york-budget-bill",
    "AL-2026-SRC-1": "https://www.revenue.alabama.gov/wp-content/uploads/2026/01/26f40esblk.pdf",
    "AL-2026-SRC-2": "https://www.revenue.alabama.gov/wp-content/uploads/2026/01/whbooklet_0126.pdf",
    "AL-2026-SRC-3": "https://www.revenue.alabama.gov/wp-content/uploads/2026/01/25f40bk.pdf",
    "AL-2026-SRC-4": "https://www.revenue.alabama.gov/individual-corporate/overtime-premium-deduction-act-2026-604/",
    "AZ-2026-SRC-1": "https://www.azleg.gov/ars/43/01041.htm",
    "AZ-2026-SRC-2": "https://www.azleg.gov/ars/43/00105.htm",
    "AZ-2026-SRC-3": "https://www.azleg.gov/legtext/57leg/2R/bills/HB4168H.pdf",
    "AZ-2026-SRC-4": "https://www.azleg.gov/ars/43/01022.htm",
    "AZ-2026-SRC-5": "https://azdor.gov/sites/default/files/document/FORMS_INDIVIDUAL_2026_140ESBooklet.pdf",
    "AZ-2026-SRC-6": "https://www.irs.gov/irb/2025-45_IRB",
    "CA-2026-SRC-1": "https://www.ftb.ca.gov/about-ftb/newsroom/tax-news/index.html",
    "CA-2026-SRC-2": "https://www.dir.ca.gov/OPRL/CPI/PresentCCPIchange.PDF",
    "CA-2026-SRC-3": "https://www.ftb.ca.gov/forms/2025/2025-540-booklet.html",
    "CA-2026-SRC-4": "https://www.ftb.ca.gov/forms/2025/2025-540-tax-rate-schedules.pdf",
    "CT-2026-SRC-1": "https://portal.ct.gov/-/media/drs/forms/2025/income/ct1040es-flat0126.pdf",
    "CT-2026-SRC-2": "https://portal.ct.gov/-/media/drs/forms/2025/income/2025-ct-1040-instructions_1225.pdf",
    "DE-2026-SRC-1": "https://revenuefiles.delaware.gov/2025/PITForms_Instructions/Instructions/PIT-EST_Instructions_2026-01.pdf",
    "DE-2026-SRC-2": "https://revenuefiles.delaware.gov/2024/PIT_2024_Forms/TY24_taxtable.pdf",
    "DE-2026-SRC-3": "https://legis.delaware.gov/AllLegislation",
    "DC-2026-SRC-1": "https://lims.dccouncil.gov/downloads/LIMS/61627/Meeting3/Amendment/B26-0661-Amendment1.pdf?Id=242559",
    "DC-2026-SRC-2": "https://tax.thomsonreuters.com/news/district-of-columbia-2027-budget-support-legislation-becomes-law/",
    "DC-2026-SRC-3": "https://code.dccouncil.gov/us/dc/council/code/sections/47-1801.04",
    "DC-2026-SRC-4": "https://otr.cfo.dc.gov/sites/default/files/dc/sites/otr/publication/attachments/2025_D40_Book_082026_v1.pdf",
    "GA-2026-SRC-1": "https://gov.georgia.gov/document/2026-signed-legislation/hb-463/download",
    "GA-2026-SRC-2": "https://dor.georgia.gov/taxes/important-tax-updates",
    "GA-2026-SRC-3": "https://gov.georgia.gov/press-releases/2026-05-11/gov-kemp-signs-legislation-lowering-taxes-and-supporting-economic-growth",
    "HI-2026-SRC-1": "https://files.hawaii.gov/tax/news/announce/ann24-03.pdf",
    "HI-2026-SRC-2": "https://files.hawaii.gov/tax/news/announce/ann25-07.pdf",
    "HI-2026-SRC-3": "https://files.hawaii.gov/tax/news/announce/ann26-06.pdf",
    "HI-2026-SRC-4": "https://files.hawaii.gov/tax/forms/current/n11ins.pdf",
    "ID-2026-SRC-1": "https://legislature.idaho.gov/statutesrules/idstat/title63/t63ch30/sect63-3024/",
    "ID-2026-SRC-2": "https://legislature.idaho.gov/statutesrules/idstat/title63/t63ch30/sect63-3024a/",
    "ID-2026-SRC-3": "https://tax.idaho.gov/wp-content/uploads/forms/EIN00046/EIN00046_03-02-2026.pdf",
    "ID-2026-SRC-4": "https://tax.idaho.gov/wp-content/uploads/pubs/EPB00744/EPB00744_07-23-2026.pdf",
    "ID-2026-SRC-5": "https://data.bls.gov/timeseries/CUUR0000SA0",
    "IL-2026-SRC-1": "https://tax.illinois.gov/content/dam/soi/en/web/tax/forms/withholding/documents/currentyear/il-700-t.pdf",
    "IL-2026-SRC-2": "https://tax.illinois.gov/research/publications/pubs/illinois-earned-income-tax-credit-information.html",
    "IL-2026-SRC-3": "https://tax.illinois.gov/content/dam/soi/en/web/tax/forms/incometax/documents/currentyear/individual/il-1040-instr.pdf",
    "IN-2026-SRC-1": "https://www.in.gov/dor/resources/tax-rates-and-reports/rates-fees-and-penalties/",
    "IN-2026-SRC-2": "https://www.in.gov/dor/files/dn01.pdf",
    "IN-2026-SRC-3": "https://www.in.gov/dor/files/ib92.pdf",
    "IA-2026-SRC-1": "https://www.legis.iowa.gov/docs/code/422.5.pdf",
    "IA-2026-SRC-2": "https://www.legis.iowa.gov/docs/code/422.12.pdf",
    "IA-2026-SRC-3": "https://www.legis.iowa.gov/docs/code/422.12B.pdf",
    "IA-2026-SRC-4": "https://revenue.iowa.gov/press-release/2025-10-21/idr-announces-2026-individual-income-tax-and-interest-rates",
    "IA-2026-SRC-5": "https://www.legis.iowa.gov/docs/publications/FR/1611991.pdf",
    "KS-2026-SRC-1": "https://ksrevenue.gov/taxnotices/notice25-06.pdf",
    "KS-2026-SRC-2": "https://ksrevenue.gov/taxnotices/notice26-11.pdf",
    "KS-2026-SRC-3": "https://www.ksrevisor.gov/statutes/chapters/ch79/079_032_0110.html",
    "KS-2026-SRC-4": "https://www.ksrevisor.gov/statutes/chapters/ch79/079_032_0119.html",
    "KS-2026-SRC-5": "https://www.ksrevisor.gov/statutes/chapters/ch79/079_032_0121.html",
    "KS-2026-SRC-6": "https://www.ksrevenue.gov/pdf/ip25.pdf",
    "KY-2026-SRC-1": "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=56339",
    "KY-2026-SRC-2": "https://revenue.ky.gov/Forms/2026%20Withholding%20Formula.pdf",
    "KY-2026-SRC-3": "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=29067",
    "KY-2026-SRC-4": "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=49188",
    "KY-2026-SRC-5": "https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines",
    "LA-2026-SRC-1": "https://www.legis.la.gov/legis/Law.aspx?d=101946",
    "LA-2026-SRC-2": "https://dam.ldr.la.gov/lawspolicies/RIB%2026-019.pdf",
    "LA-2026-SRC-3": "https://www.legis.la.gov/legis/Law.aspx?d=453085",
    "ME-2026-SRC-1": "https://www.maine.gov/revenue/sites/maine.gov.revenue/files/2026-05/ind_tax_rate_sched_2026_rev.pdf",
    "ME-2026-SRC-2": "https://legislature.maine.gov/statutes/36/title36sec5124-C.html",
    "ME-2026-SRC-3": "https://legislature.maine.gov/statutes/36/title36sec5126-A.html",
    "ME-2026-SRC-4": "https://legislature.maine.gov/statutes/36/title36sec5403.html",
    "ME-2026-SRC-5": "https://legislature.maine.gov/statutes/36/title36sec5111.html",
    "ME-2026-SRC-6": "https://legislature.maine.gov/statutes/36/title36sec5219-S.html",
    "MD-2026-SRC-1": "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gtg&section=10-105&enactments=false",
    "MD-2026-SRC-2": "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gtg&section=10-217&enactments=false",
    "MD-2026-SRC-3": "https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/instructions/withholding/2026/withholding-guide.pdf",
    "MD-2026-SRC-4": "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gtg&section=10-211&enactments=false",
    "MD-2026-SRC-5": "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gtg&section=10-704&enactments=false",
    "MD-2026-SRC-6": "https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=gtg&section=10-709&enactments=false",
    "MD-2026-SRC-7": "https://api.bls.gov/publicAPI/v2/timeseries/data/SUUR0000SA0",
    "MA-2026-SRC-1": "https://www.mass.gov/doc/fy26-surtax-certification-period-4/download",
    "MA-2026-SRC-2": "https://www.mass.gov/doc/2026-form-1-es-estimated-tax-payment-vouchers-instructions-and-worksheets/download",
    "MA-2026-SRC-3": "https://www.mass.gov/info-details/massachusetts-personal-income-tax-exemptions",
    "MA-2026-SRC-4": "https://www.mass.gov/doc/2025-form-1-instructions/download",
    "MI-2026-SRC-1": "https://www.michigan.gov/treasury/reference/taxpayer-notices/2026/04/15/425-income-tax-rate-for-individuals-and-fiduciaries-in-2026-tax-year",
    "MI-2026-SRC-2": "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/SUW/TY2026/446_Withholding-Guide_2026.pdf",
    "MI-2026-SRC-3": "https://www.michigan.gov/taxes/business-taxes/withholding/calendar-year-tax-information",
    "MI-2026-SRC-4": "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT/TY2025/MI-1040-Book.pdf",
    "MN-2026-SRC-1": "https://www.revenue.state.mn.us/sites/default/files/2025-12/inflation-adjusted-amounts-2026.pdf",
    "MN-2026-SRC-2": "https://www.revenue.state.mn.us/press-release/2025-12-16/minnesota-income-tax-brackets-standard-deduction-and-dependent-exemption",
    "MN-2026-SRC-3": "https://www.revisor.mn.gov/statutes/cite/290.0123",
    "MN-2026-SRC-4": "https://www.revisor.mn.gov/laws/2026/0/128/",
    "MN-2026-SRC-5": "https://www.revisor.mn.gov/statutes/cite/290.0671",
}

_COVERAGE: dict[tuple[str, int, str], CoverageEntry] = {
    ("US-TX", 2026, US_VANILLA_PROFILE): CoverageEntry(
        jurisdiction_id="US-TX",
        tax_year=2026,
        profile_id=US_VANILLA_PROFILE,
        status=CoverageStatus.ENABLED,
        native_period_id="US-TY2026",
        period_label="US tax year 2026",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        earnings_start=date(2026, 1, 1),
        earnings_end=date(2026, 12, 31),
        parent_id="US",
        dependencies=("US", "US-TX"),
        rule_paths=("federal/2026.yaml", "states/2026/tx.yaml"),
        policy_id="us_federal_2026_plus_no_individual_income_tax_v1",
        rules_version="2026.1.0",
        currency="USD",
        rounding="federal Form 1040 whole dollars; state zero",
        income_categories=US_VANILLA_INCOME,
        loss_treatment="federal Schedule D; no Texas individual tax",
        locality_status="none",
        payroll_scope="federal employee FICA only",
        evidence_ids=(
            "IRS-REV-PROC-2025-32", "SSA-2026-WAGE-BASE", "TX-CONST-ART-8-24A",
        ),
        verified_on=date(2026, 9, 30),
    ),
}


_ZERO_TAX_STATE_EVIDENCE = {
    "AK": "AK-NO-PERSONAL-IT",
    "FL": "FL-NO-PERSONAL-IT",
    "NV": "NV-NO-PERSONAL-IT",
    "NH": "NH-INTEREST-DIVIDEND-REPEAL",
    "SD": "SD-NO-PERSONAL-IT",
    "TN": "TN-HALL-TAX-REPEAL",
    "WY": "WY-NO-PERSONAL-IT",
}

for _state_code, _state_evidence in _ZERO_TAX_STATE_EVIDENCE.items():
    _entry = CoverageEntry(
        jurisdiction_id=f"US-{_state_code}",
        tax_year=2026,
        profile_id=US_VANILLA_PROFILE,
        status=CoverageStatus.ENABLED,
        native_period_id="US-TY2026",
        period_label="US tax year 2026",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        earnings_start=date(2026, 1, 1),
        earnings_end=date(2026, 12, 31),
        parent_id="US",
        dependencies=("US", f"US-{_state_code}"),
        rule_paths=("federal/2026.yaml", f"states/2026/{_state_code.lower()}.yaml"),
        policy_id="us_federal_2026_plus_no_individual_income_tax_v1",
        rules_version="2026.1.0",
        currency="USD",
        rounding="federal Form 1040 whole dollars; state zero",
        income_categories=US_VANILLA_INCOME,
        loss_treatment="federal Schedule D; no individual state income tax",
        locality_status="none",
        payroll_scope="federal employee FICA only",
        evidence_ids=("IRS-REV-PROC-2025-32", "SSA-2026-WAGE-BASE", _state_evidence),
        verified_on=date(2026, 10, 1),
    )
    _COVERAGE[(_entry.jurisdiction_id, _entry.tax_year, _entry.profile_id)] = _entry


# Taxed states enabled for 2026 after source review: state code ->
# (evidence ids in SOURCE_LEDGER, verified date). A policy in
# states/policies_2026_g*.py stays private until it is listed here.
_TAXED_STATE_EVIDENCE_2026: dict[str, tuple[tuple[str, ...], date]] = {
    "KY": (("KY-2026-SRC-1", "KY-2026-SRC-2", "KY-2026-SRC-3", "KY-2026-SRC-4", "KY-2026-SRC-5"), date(2026, 10, 23)),
    "LA": (("LA-2026-SRC-1", "LA-2026-SRC-2", "LA-2026-SRC-3"), date(2026, 10, 23)),
    "ME": (("ME-2026-SRC-1", "ME-2026-SRC-2", "ME-2026-SRC-3", "ME-2026-SRC-4", "ME-2026-SRC-5", "ME-2026-SRC-6"), date(2026, 10, 23)),
    "MD": (("MD-2026-SRC-1", "MD-2026-SRC-2", "MD-2026-SRC-3", "MD-2026-SRC-4", "MD-2026-SRC-5", "MD-2026-SRC-6", "MD-2026-SRC-7"), date(2026, 10, 23)),
    "MA": (("MA-2026-SRC-1", "MA-2026-SRC-2", "MA-2026-SRC-3", "MA-2026-SRC-4"), date(2026, 10, 23)),
    "MI": (("MI-2026-SRC-1", "MI-2026-SRC-2", "MI-2026-SRC-3", "MI-2026-SRC-4"), date(2026, 10, 23)),
    "MN": (("MN-2026-SRC-1", "MN-2026-SRC-2", "MN-2026-SRC-3", "MN-2026-SRC-4", "MN-2026-SRC-5"), date(2026, 10, 23)),
    "DC": (("DC-2026-SRC-1", "DC-2026-SRC-2", "DC-2026-SRC-3", "DC-2026-SRC-4"), date(2026, 10, 23)),
    "GA": (("GA-2026-SRC-1", "GA-2026-SRC-2", "GA-2026-SRC-3"), date(2026, 10, 23)),
    "HI": (("HI-2026-SRC-1", "HI-2026-SRC-2", "HI-2026-SRC-3", "HI-2026-SRC-4"), date(2026, 10, 23)),
    "ID": (("ID-2026-SRC-1", "ID-2026-SRC-2", "ID-2026-SRC-3", "ID-2026-SRC-4", "ID-2026-SRC-5"), date(2026, 10, 23)),
    "IL": (("IL-2026-SRC-1", "IL-2026-SRC-2", "IL-2026-SRC-3"), date(2026, 10, 23)),
    "IN": (("IN-2026-SRC-1", "IN-2026-SRC-2", "IN-2026-SRC-3"), date(2026, 10, 23)),
    "IA": (("IA-2026-SRC-1", "IA-2026-SRC-2", "IA-2026-SRC-3", "IA-2026-SRC-4", "IA-2026-SRC-5"), date(2026, 10, 23)),
    "KS": (("KS-2026-SRC-1", "KS-2026-SRC-2", "KS-2026-SRC-3", "KS-2026-SRC-4", "KS-2026-SRC-5", "KS-2026-SRC-6"), date(2026, 10, 23)),
    "AR": (("AR-2026-SRC-1", "AR-2026-SRC-2", "AR-2026-SRC-3", "AR-2026-SRC-4", "AR-2026-SRC-5", "AR-2026-SRC-6"), date(2026, 10, 29)),
    "CO": (("CO-2026-SRC-1", "CO-2026-SRC-2", "CO-2026-SRC-3", "CO-2026-SRC-4"), date(2026, 10, 29)),
    "AL": (("AL-2026-SRC-1", "AL-2026-SRC-2", "AL-2026-SRC-3", "AL-2026-SRC-4"), date(2026, 10, 23)),
    "AZ": (("AZ-2026-SRC-1", "AZ-2026-SRC-2", "AZ-2026-SRC-3", "AZ-2026-SRC-4", "AZ-2026-SRC-5", "AZ-2026-SRC-6"), date(2026, 10, 23)),
    "CA": (("CA-2026-SRC-1", "CA-2026-SRC-2", "CA-2026-SRC-3", "CA-2026-SRC-4"), date(2026, 10, 23)),
    "CT": (("CT-2026-SRC-1", "CT-2026-SRC-2"), date(2026, 10, 23)),
    "DE": (("DE-2026-SRC-1", "DE-2026-SRC-2", "DE-2026-SRC-3"), date(2026, 10, 23)),
    "MS": (("MS-2026-SRC-1", "MS-2026-SRC-2"), date(2026, 10, 23)),
    "MO": (("MO-2026-SRC-1", "MO-2026-SRC-2", "MO-2026-SRC-3", "MO-2026-SRC-4", "MO-2026-SRC-5"), date(2026, 10, 23)),
    "MT": (("MT-2026-SRC-1", "MT-2026-SRC-2", "MT-2026-SRC-3", "MT-2026-SRC-4"), date(2026, 10, 23)),
    "NE": (("NE-2026-SRC-1", "NE-2026-SRC-2", "NE-2026-SRC-3"), date(2026, 10, 23)),
    "NJ": (("NJ-2026-SRC-1", "NJ-2026-SRC-2", "NJ-2026-SRC-3", "NJ-2026-SRC-4"), date(2026, 10, 23)),
    "NM": (("NM-2026-SRC-1", "NM-2026-SRC-2", "NM-2026-SRC-3", "NM-2026-SRC-4"), date(2026, 10, 23)),
    "NY": (("NY-2026-SRC-1", "NY-2026-SRC-2", "NY-2026-SRC-3", "NY-2026-SRC-4"), date(2026, 10, 23)),
    "SC": (("SC-2026-SRC-1", "SC-2026-SRC-2"), date(2026, 10, 23)),
    "UT": (("UT-2026-SRC-1", "UT-2026-SRC-2", "UT-2026-SRC-3", "UT-2026-SRC-4"), date(2026, 10, 23)),
    "VT": (("VT-2026-SRC-1", "VT-2026-SRC-2", "VT-2026-SRC-3", "VT-2026-SRC-4", "VT-2026-SRC-5", "VT-2026-SRC-6"), date(2026, 10, 23)),
    "VA": (("VA-2026-SRC-1", "VA-2026-SRC-2", "VA-2026-SRC-3", "VA-2026-SRC-4", "VA-2026-SRC-5", "VA-2026-SRC-6"), date(2026, 10, 23)),
    "WA": (("WA-2026-SRC-1", "WA-2026-SRC-2", "WA-2026-SRC-3", "WA-2026-SRC-4", "WA-2026-SRC-5"), date(2026, 10, 23)),
    "WV": (("WV-2026-SRC-1", "WV-2026-SRC-2", "WV-2026-SRC-3", "WV-2026-SRC-4", "WV-2026-SRC-5"), date(2026, 10, 23)),
    "WI": (("WI-2026-SRC-1", "WI-2026-SRC-2", "WI-2026-SRC-3", "WI-2026-SRC-4", "WI-2026-SRC-5"), date(2026, 10, 23)),
    "NC": (("NC-2026-SRC-1", "NC-2026-SRC-2", "NC-2026-SRC-3"), date(2026, 10, 23)),
    "ND": (("ND-2026-SRC-1", "ND-2026-SRC-2", "ND-2026-SRC-3"), date(2026, 10, 23)),
    "OH": (("OH-2026-SRC-1", "OH-2026-SRC-2", "OH-2026-SRC-3", "OH-2026-SRC-4", "OH-2026-SRC-5"), date(2026, 10, 23)),
    "OK": (("OK-2026-SRC-1", "OK-2026-SRC-2", "OK-2026-SRC-3"), date(2026, 10, 23)),
    "OR": (("OR-2026-SRC-1", "OR-2026-SRC-2", "OR-2026-SRC-3", "OR-2026-SRC-4"), date(2026, 10, 23)),
    "PA": (("PA-2026-SRC-1", "PA-2026-SRC-2", "PA-2026-SRC-3"), date(2026, 10, 23)),
    "RI": (("RI-2026-SRC-1", "RI-2026-SRC-2"), date(2026, 10, 23)),
}

# States registered for discovery but not yet enabled: code -> public reason.
_PENDING_STATES_2026: dict[str, str] = {}

for _state_code, (_state_evidence_ids, _verified_on) in _TAXED_STATE_EVIDENCE_2026.items():
    _entry = CoverageEntry(
        jurisdiction_id=f"US-{_state_code}",
        tax_year=2026,
        profile_id=US_VANILLA_PROFILE,
        status=CoverageStatus.ENABLED,
        native_period_id="US-TY2026",
        period_label="US tax year 2026",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        earnings_start=date(2026, 1, 1),
        earnings_end=date(2026, 12, 31),
        parent_id="US",
        dependencies=("US", f"US-{_state_code}"),
        rule_paths=("federal/2026.yaml", f"states/2026/{_state_code.lower()}.yaml"),
        policy_id=f"us_federal_2026_plus_{_state_code.lower()}_resident_2026_v1",
        rules_version="2026.1.0",
        currency="USD",
        rounding="federal Form 1040 whole dollars; state per reviewed policy",
        income_categories=US_VANILLA_INCOME,
        loss_treatment="federal Schedule D; state per reviewed policy",
        locality_status="state only",
        payroll_scope="federal employee FICA only",
        evidence_ids=("IRS-REV-PROC-2025-32", "SSA-2026-WAGE-BASE", *_state_evidence_ids),
        verified_on=_verified_on,
    )
    _COVERAGE[(_entry.jurisdiction_id, _entry.tax_year, _entry.profile_id)] = _entry

for _state_code, _reason in _PENDING_STATES_2026.items():
    _entry = CoverageEntry(
        jurisdiction_id=f"US-{_state_code}",
        tax_year=2026,
        profile_id=US_VANILLA_PROFILE,
        status=CoverageStatus.PENDING,
        native_period_id="US-TY2026",
        period_label="US tax year 2026",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        earnings_start=date(2026, 1, 1),
        earnings_end=date(2026, 12, 31),
        parent_id="US",
        dependencies=("US", f"US-{_state_code}"),
        rule_paths=(),
        policy_id="pending",
        rules_version="2026.1.0",
        currency="USD",
        rounding="not applicable",
        income_categories=US_VANILLA_INCOME,
        loss_treatment="not applicable",
        locality_status="state only",
        payroll_scope="federal employee FICA only",
        evidence_ids=(),
        verified_on=None,
        unavailable_reason=_reason,
    )
    _COVERAGE[(_entry.jurisdiction_id, _entry.tax_year, _entry.profile_id)] = _entry


# Cities enabled for 2026 after source review: region id -> (rules file stem,
# evidence ids in SOURCE_LEDGER, verified date). A city also needs its parent
# state enabled; see enabled_us_cities().
_CITY_EVIDENCE_2026: dict[str, tuple[str, tuple[str, ...], date]] = {
    "US-NY-NYC": ("ny_nyc", ("NYC-2026-SRC-1", "NYC-2026-SRC-2", "NYC-2026-SRC-3", "NYC-2026-SRC-4"), date(2026, 10, 23)),
    "US-NY-YNK": ("ny_yonkers", ("YNK-2026-SRC-1", "YNK-2026-SRC-2"), date(2026, 10, 23)),
    "US-MI-DET": ("mi_detroit", ("DET-2026-SRC-1", "DET-2026-SRC-2"), date(2026, 10, 23)),
    "US-MD-BAL": ("md_baltimore", ("BAL-2026-SRC-1", "BAL-2026-SRC-2", "BAL-2026-SRC-3", "BAL-2026-SRC-4", "BAL-2026-SRC-5"), date(2026, 10, 23)),
    "US-IN-IND": ("in_marion_county", ("IND-2026-SRC-1", "IND-2026-SRC-2"), date(2026, 10, 23)),
    "US-AL-BHM": ("al_birmingham", ("BHM-2026-SRC-1", "BHM-2026-SRC-2"), date(2026, 10, 23)),
    "US-KY-LOU": ("ky_louisville", ("LOU-2026-SRC-1", "LOU-2026-SRC-2"), date(2026, 10, 23)),
    "US-OH-CLE": ("oh_cleveland", ("CLE-2026-SRC-1", "CLE-2026-SRC-2"), date(2026, 10, 23)),
    "US-OH-CIN": ("oh_cincinnati", ("CIN-2026-SRC-1", "CIN-2026-SRC-2"), date(2026, 10, 23)),
    "US-OH-CMH": ("oh_columbus", ("CMH-2026-SRC-1", "CMH-2026-SRC-2", "CMH-2026-SRC-3"), date(2026, 10, 23)),
    "US-PA-PHL": ("pa_philadelphia", ("PHL-2026-SRC-1", "PHL-2026-SRC-2", "PHL-2026-SRC-3"), date(2026, 10, 23)),
}

for _city_id, (_stem, _city_evidence_ids, _verified_on) in _CITY_EVIDENCE_2026.items():
    _parent = _city_id.rsplit("-", 1)[0]
    _entry = CoverageEntry(
        jurisdiction_id=_city_id,
        tax_year=2026,
        profile_id=US_VANILLA_PROFILE,
        status=CoverageStatus.ENABLED,
        native_period_id="US-TY2026",
        period_label="US tax year 2026",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        earnings_start=date(2026, 1, 1),
        earnings_end=date(2026, 12, 31),
        parent_id=_parent,
        dependencies=("US", _parent, _city_id),
        rule_paths=(
            "federal/2026.yaml",
            f"states/2026/{_parent.removeprefix('US-').lower()}.yaml",
            f"locals/2026/{_stem}.yaml",
        ),
        policy_id=f"us_federal_2026_plus_{_stem}_resident_2026_v1",
        rules_version="2026.1.0",
        currency="USD",
        rounding="federal Form 1040 whole dollars; state and local per reviewed policy",
        income_categories=US_VANILLA_INCOME,
        loss_treatment="federal Schedule D; state and local per reviewed policy",
        locality_status="resident city",
        payroll_scope="federal employee FICA only",
        evidence_ids=("IRS-REV-PROC-2025-32", "SSA-2026-WAGE-BASE", *_city_evidence_ids),
        verified_on=_verified_on,
    )
    _COVERAGE[(_entry.jurisdiction_id, _entry.tax_year, _entry.profile_id)] = _entry


def coverage_entry(
    jurisdiction_id: str, tax_year: int, profile_id: str = US_VANILLA_PROFILE
) -> CoverageEntry | None:
    """Return registered coverage, including pending entries for public discovery."""
    return _COVERAGE.get((jurisdiction_id.upper(), tax_year, profile_id))


def enabled_coverage(tax_year: int, profile_id: str = US_VANILLA_PROFILE) -> tuple[CoverageEntry, ...]:
    """Return enabled entries; never infer availability from files on disk."""
    return tuple(
        entry for entry in _COVERAGE.values()
        if entry.tax_year == tax_year
        and entry.profile_id == profile_id
        and entry.status == CoverageStatus.ENABLED
    )


def require_coverage(
    jurisdiction_id: str,
    tax_year: int,
    profile_id: str = US_VANILLA_PROFILE,
    *,
    rules_root: Path | None = None,
    income_categories: frozenset[str] | None = None,
) -> CoverageEntry:
    """Enforce registry, income capabilities and all required rule dependencies."""
    entry = coverage_entry(jurisdiction_id, tax_year, profile_id)
    if entry is None:
        raise UnsupportedCoverageError(
            f"{jurisdiction_id} has no supported {tax_year} {profile_id} coverage"
        )
    if entry.status != CoverageStatus.ENABLED:
        raise UnsupportedCoverageError(entry.unavailable_reason or "Coverage is unavailable")
    if income_categories and not income_categories <= entry.income_categories:
        unsupported = ", ".join(sorted(income_categories - entry.income_categories))
        raise UnsupportedCoverageError(f"Unsupported income categories: {unsupported}")
    root = rules_root or _RULES_ROOT
    missing = [path for path in entry.rule_paths if not (root / path).is_file()]
    if missing:
        raise UnsupportedCoverageError(
            f"{jurisdiction_id} {tax_year} coverage is unavailable: required rules are missing"
        )
    return entry


def require_aligned_earnings_period(entries: tuple[CoverageEntry, ...]) -> None:
    """Prevent a ranking between different income-earning windows."""
    periods = {(entry.earnings_start, entry.earnings_end) for entry in entries}
    if len(periods) > 1:
        raise UnsupportedCoverageError(
            "2026 comparison cannot rank different earnings periods"
        )


def enabled_us_states(tax_year: int, *, rules_root: Path | None = None) -> frozenset[str]:
    """State codes enabled for the US vanilla profile in a given year."""
    states = set()
    for entry in enabled_coverage(tax_year):
        if entry.parent_id != "US" or entry.jurisdiction_id.count("-") != 1:
            continue
        try:
            require_coverage(
                entry.jurisdiction_id, tax_year, rules_root=rules_root
            )
        except UnsupportedCoverageError:
            continue
        states.add(entry.jurisdiction_id.removeprefix("US-"))
    return frozenset(states)


def enabled_us_cities(tax_year: int, *, rules_root: Path | None = None) -> frozenset[str]:
    """City region ids (e.g. US-NY-NYC) enabled with their parent state.

    Empty for 2025, whose cities are governed by the advertised 2025 policies.
    """
    states = enabled_us_states(tax_year, rules_root=rules_root)
    cities = set()
    for entry in enabled_coverage(tax_year):
        if entry.jurisdiction_id.count("-") != 2:
            continue
        if entry.parent_id is None or entry.parent_id.removeprefix("US-") not in states:
            continue
        try:
            require_coverage(entry.jurisdiction_id, tax_year, rules_root=rules_root)
        except UnsupportedCoverageError:
            continue
        cities.add(entry.jurisdiction_id)
    return frozenset(cities)
