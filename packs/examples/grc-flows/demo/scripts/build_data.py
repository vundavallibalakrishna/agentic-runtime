#!/usr/bin/env python
"""Write the demo's documents and the risk register's SQL.

Everything here is invented for a made-up company, Meridian Payments Ltd, and its made-up
vendor, CloudLedger Inc. The control list paraphrases NIST CSF 2.0 outcomes (a public
United States government framework). Run it again to rebuild the files in ``data/``:

    uv run --no-sync python packs/examples/grc-flows/demo/scripts/build_data.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from docx import Document
from openpyxl import Workbook

OUT = Path(__file__).parents[1] / "data"

# A policy is a list of (number, heading, paragraphs). Version 4.0 is version 3.2 with the
# changes listed in CHANGES applied, so the right answer to "what changed" is known.
POLICY_V3: list[tuple[str, str, list[str]]] = [
    (
        "1",
        "Purpose and scope",
        [
            "This policy sets the minimum information security requirements for Meridian Payments Ltd. "
            "It applies to all employees, contractors and third parties who access Meridian systems or data.",
            "The Chief Information Security Officer (CISO) owns this policy. It is reviewed every twelve months.",
        ],
    ),
    (
        "2",
        "Roles and responsibilities",
        [
            "The Board Risk Committee approves this policy and receives a security report twice a year.",
            "System owners are accountable for the controls on their systems. Every employee must report "
            "suspected security events to the Security Operations team.",
        ],
    ),
    (
        "3",
        "Access control",
        [
            "Access is granted on the principle of least privilege and must be approved by the system owner.",
            "Multi-factor authentication (MFA) is recommended for remote access and for administrator accounts.",
            "User access rights are reviewed by system owners every twelve months.",
            "Accounts of leavers are disabled within five working days of their last day.",
        ],
    ),
    (
        "4",
        "Cryptography",
        [
            "Customer data is encrypted at rest using AES-256 and in transit using TLS 1.2 or higher.",
            "Encryption keys are stored in a hardware security module and rotated every two years.",
        ],
    ),
    (
        "5",
        "Logging and monitoring",
        [
            "Security logs from production systems are collected centrally and retained for 90 days.",
            "Alerts of high severity are reviewed by the Security Operations team within four hours.",
        ],
    ),
    (
        "6",
        "Vulnerability management",
        [
            "Production systems are scanned for vulnerabilities every month.",
            "Critical vulnerabilities are remediated within 30 days and high vulnerabilities within 60 days.",
            "An independent penetration test of internet-facing systems is carried out every year.",
        ],
    ),
    (
        "7",
        "Incident management",
        [
            "Security incidents are classified by severity and handled under the Incident Response Plan.",
            "Incidents that involve personal data are reported to the Data Protection Officer within 72 hours.",
            "A post-incident review is completed for every high severity incident.",
        ],
    ),
    (
        "8",
        "Third-party risk",
        [
            "Vendors that process customer data are assessed for security before a contract is signed.",
            "Contracts with such vendors include a data processing agreement.",
        ],
    ),
    (
        "9",
        "Removable media",
        [
            "Removable media may be used for business data when the line manager approves an exception.",
        ],
    ),
    (
        "10",
        "Business continuity",
        [
            "Critical services have a recovery time objective of eight hours and a recovery point objective of four hours.",
            "Backups are tested by a restore every six months.",
        ],
    ),
    (
        "11",
        "Training and awareness",
        [
            "All staff complete security awareness training when they join and every year after that.",
        ],
    ),
    (
        "12",
        "Exceptions",
        [
            "Exceptions to this policy are approved by the CISO, recorded in the risk register and reviewed every year.",
        ],
    ),
]

CHANGES: dict[str, list[str]] = {
    "1": [
        "This policy sets the minimum information security requirements for Meridian Payments Ltd. "
        "It applies to all employees, contractors and third parties who access Meridian systems or data.",
        "The Chief Information Security Officer (CISO) owns this policy. It is reviewed every twelve months "
        "and after any major incident.",
    ],
    "3": [
        "Access is granted on the principle of least privilege and must be approved by the system owner.",
        "Multi-factor authentication (MFA) is required for all access to production systems, for remote access "
        "and for every administrator account.",
        "User access rights are reviewed by system owners every quarter.",
        "Accounts of leavers are disabled within one working day of their last day.",
    ],
    "5": [
        "Security logs from production systems are collected centrally and retained for 365 days.",
        "Alerts of high severity are reviewed by the Security Operations team within one hour.",
    ],
    "6": [
        "Production systems are scanned for vulnerabilities every week.",
        "Critical vulnerabilities are remediated within 7 days and high vulnerabilities within 30 days.",
        "An independent penetration test of internet-facing systems is carried out every year.",
    ],
    "7": [
        "Security incidents are classified by severity and handled under the Incident Response Plan.",
        "Incidents that involve personal data are reported to the Data Protection Officer within 24 hours.",
        "A post-incident review is completed for every high severity incident.",
    ],
    "8": [
        "Vendors that process customer data are assessed for security before a contract is signed.",
        "Contracts with such vendors include a data processing agreement.",
        "Critical vendors are re-assessed every year, and their independent assurance reports are reviewed "
        "when they are issued.",
    ],
}
REMOVED = {"9"}
ADDED = (
    "13",
    "Use of artificial intelligence",
    [
        "Customer data must not be entered into an AI service that Meridian has not approved.",
        "Every AI system used in a business process is recorded in the AI register with its owner, "
        "its purpose and the data it uses.",
        "Decisions that affect a customer are reviewed by a person before they take effect.",
    ],
)


def policy(version: str) -> list[tuple[str, str, list[str]]]:
    if version == "3.2":
        return POLICY_V3
    rows = [
        (number, heading, CHANGES.get(number, body))
        for number, heading, body in POLICY_V3
        if number not in REMOVED
    ]
    return [*rows, ADDED]


def write_policy(version: str, approved: str) -> None:
    doc = Document()
    doc.add_heading(f"Meridian Information Security Policy v{version}", level=0)
    doc.add_paragraph(
        f"Meridian Payments Ltd. Version {version}. Approved by the Board Risk Committee on {approved}."
    )
    doc.add_paragraph("Classification: Internal.")
    for number, heading, body in policy(version):
        doc.add_heading(f"{number}. {heading}", level=2)
        for index, text in enumerate(body, start=1):
            doc.add_paragraph(f"{number}.{index} {text}")
    doc.save(OUT / f"meridian-information-security-policy-v{version}.docx")


CONTROLS = [
    (
        "GV.PO-01",
        "Govern",
        "A security policy is established, approved by senior management and reviewed at least every year.",
    ),
    ("GV.RR-02", "Govern", "Security roles and responsibilities are assigned and communicated."),
    (
        "GV.SC-07",
        "Govern",
        "Critical suppliers are assessed before engagement and monitored at least every year.",
    ),
    (
        "PR.AA-03",
        "Protect",
        "Multi-factor authentication is required for all access to production systems.",
    ),
    (
        "PR.AA-05",
        "Protect",
        "Access rights are reviewed at least every quarter and follow least privilege.",
    ),
    ("PR.DS-01", "Protect", "Data at rest is encrypted with a strong algorithm."),
    ("PR.DS-02", "Protect", "Data in transit is encrypted."),
    ("PR.AT-01", "Protect", "All staff receive security awareness training at least every year."),
    ("PR.PS-04", "Protect", "Security logs are retained for at least one year."),
    ("ID.RA-01", "Identify", "Vulnerabilities are identified by scanning at least every month."),
    ("ID.RA-06", "Identify", "Critical vulnerabilities are remediated within 15 days."),
    (
        "DE.CM-01",
        "Detect",
        "Networks and systems are monitored and high severity alerts are reviewed within one hour.",
    ),
    (
        "RS.CO-02",
        "Respond",
        "Incidents involving personal data are reported internally within 24 hours.",
    ),
    ("RC.RP-03", "Recover", "Backups are tested by restore at least every six months."),
    (
        "GV.OC-03",
        "Govern",
        "Use of artificial intelligence is governed, and AI systems are recorded in a register.",
    ),
    (
        "PR.IR-04",
        "Protect",
        "Capacity is planned so that critical services stay available under twice the peak load.",
    ),
]

DPA_STANDARD = [
    (
        "1",
        "Subject matter",
        [
            "The Processor processes personal data only on the documented instructions of Meridian Payments Ltd (the Controller)."
        ],
    ),
    (
        "2",
        "Confidentiality",
        [
            "The Processor ensures that persons authorised to process the personal data are bound by confidentiality."
        ],
    ),
    (
        "3",
        "Security",
        [
            "The Processor encrypts personal data at rest with AES-256 and in transit with TLS 1.2 or higher, and holds a current SOC 2 Type II report."
        ],
    ),
    (
        "4",
        "Sub-processors",
        [
            "The Processor does not engage a sub-processor without the prior written consent of the Controller, given at least 30 days before the engagement."
        ],
    ),
    (
        "5",
        "Breach notification",
        [
            "The Processor notifies the Controller of a personal data breach without undue delay and no later than 48 hours after becoming aware of it."
        ],
    ),
    (
        "6",
        "Audit",
        [
            "The Controller may audit the Processor once a year on 30 days' notice, and the Processor makes available all information needed to show compliance."
        ],
    ),
    (
        "7",
        "Data location",
        [
            "Personal data is stored and processed only in the country of the Controller unless the Controller agrees otherwise in writing."
        ],
    ),
    (
        "8",
        "Return and deletion",
        [
            "On termination the Processor returns or deletes all personal data within 30 days and certifies the deletion in writing."
        ],
    ),
    (
        "9",
        "Liability",
        [
            "The Processor is liable for damage caused by processing that breaches this agreement, without a cap for breaches of confidentiality or security."
        ],
    ),
]
DPA_VENDOR = [
    (
        "1",
        "Subject matter",
        [
            "CloudLedger Inc (the Processor) processes personal data on the instructions of the Controller and as needed to improve its services."
        ],
    ),
    (
        "2",
        "Confidentiality",
        [
            "The Processor ensures that persons authorised to process the personal data are bound by confidentiality."
        ],
    ),
    (
        "3",
        "Security",
        ["The Processor applies commercially reasonable security measures to personal data."],
    ),
    (
        "4",
        "Sub-processors",
        [
            "The Processor may engage sub-processors and lists them on its website. Changes take effect when the list is updated."
        ],
    ),
    (
        "5",
        "Breach notification",
        [
            "The Processor notifies the Controller of a confirmed personal data breach within 7 days of confirming it."
        ],
    ),
    (
        "6",
        "Data location",
        [
            "Personal data may be stored and processed in any country where the Processor or its sub-processors operate."
        ],
    ),
    (
        "7",
        "Return and deletion",
        [
            "On termination the Processor deletes personal data within 180 days, except copies held in backups."
        ],
    ),
    (
        "8",
        "Liability",
        [
            "The total liability of the Processor under this agreement is limited to the fees paid in the three months before the claim."
        ],
    ),
    (
        "9",
        "Analytics",
        ["The Processor may use aggregated customer data for analytics and product development."],
    ),
]

SOC2 = [
    (
        "1",
        "Report",
        [
            "Independent service auditor's report on CloudLedger Inc's ledger hosting platform. SOC 2 Type II.",
            "Report period: 1 October 2025 to 30 September 2026. Service auditor: Northgate Assurance LLP.",
            "Trust services categories in scope: Security, Availability and Confidentiality.",
        ],
    ),
    (
        "2",
        "Opinion",
        [
            "In our opinion the controls were suitably designed and operated effectively throughout the period, "
            "except for the matters described in section 4. The opinion is qualified.",
        ],
    ),
    (
        "3",
        "Sub-service organisations",
        [
            "CloudLedger uses Halden Cloud Hosting for data centre services and carves it out of this report.",
        ],
    ),
    (
        "4",
        "Exceptions noted",
        [
            "CC6.1: for 3 of 25 sampled administrator accounts, multi-factor authentication was not enforced.",
            "CC6.3: the quarterly user access review for the third quarter was completed 41 days late.",
            "CC7.2: no exceptions noted. Security logs were retained for 400 days.",
            "A1.2: one of two sampled backup restore tests failed and was repeated successfully after 12 days.",
        ],
    ),
    (
        "5",
        "Complementary user entity controls",
        [
            "User entities are responsible for reviewing their own users' access to CloudLedger every quarter.",
            "User entities are responsible for configuring single sign-on for their users.",
        ],
    ),
]

QUESTIONS = [
    "Is multi-factor authentication required for access to production systems?",
    "How long are security logs retained?",
    "How is customer data encrypted at rest and in transit?",
    "How often are user access rights reviewed?",
    "How quickly are critical vulnerabilities remediated?",
    "How often is an independent penetration test carried out?",
    "Within what time are incidents involving personal data reported internally?",
    "What are the recovery time and recovery point objectives for critical services?",
    "How are critical vendors monitored after the contract is signed?",
    "Do you have a policy on the use of artificial intelligence?",
    "Are you certified to ISO 27001?",
    "Do you carry cyber insurance, and what is the cover limit?",
]


def write_sections(
    name: str, title: str, lead: str, sections: list[tuple[str, str, list[str]]]
) -> None:
    doc = Document()
    doc.add_heading(title, level=0)
    doc.add_paragraph(lead)
    for number, heading, body in sections:
        doc.add_heading(f"{number}. {heading}", level=2)
        for index, text in enumerate(body, start=1):
            doc.add_paragraph(f"{number}.{index} {text}")
    doc.save(OUT / name)


RISKS = [
    # id, title, category, inherent, residual, owner, status, last_review, asset
    (
        "R-001",
        "Administrator accounts without multi-factor authentication",
        "Access",
        20,
        12,
        "Asha Menon",
        "open",
        "2026-09-12",
        "Payments core",
    ),
    (
        "R-002",
        "Security logs kept for less than a year",
        "Monitoring",
        12,
        9,
        "Daniel Okafor",
        "open",
        "2026-08-30",
        "Log platform",
    ),
    (
        "R-003",
        "Critical vendor without a current assurance report",
        "Third party",
        16,
        16,
        None,
        "open",
        "2026-03-02",
        "CloudLedger",
    ),
    (
        "R-004",
        "Unpatched internet-facing web server",
        "Vulnerability",
        25,
        15,
        "Asha Menon",
        "open",
        "2026-10-21",
        "Customer portal",
    ),
    (
        "R-005",
        "Customer data entered into unapproved AI services",
        "Data",
        16,
        12,
        None,
        "open",
        "2026-06-18",
        "All staff",
    ),
    (
        "R-006",
        "Backups not tested by restore",
        "Resilience",
        15,
        6,
        "Wei Chen",
        "mitigated",
        "2026-10-02",
        "Payments core",
    ),
    (
        "R-007",
        "Leaver accounts stay active",
        "Access",
        12,
        4,
        "Sofia Rossi",
        "mitigated",
        "2026-09-25",
        "Identity platform",
    ),
    (
        "R-008",
        "Payment fraud through social engineering",
        "Fraud",
        20,
        10,
        "Marcus Lee",
        "open",
        "2026-10-11",
        "Finance operations",
    ),
    (
        "R-009",
        "Single data centre for the ledger service",
        "Resilience",
        20,
        16,
        "Wei Chen",
        "open",
        "2026-05-09",
        "Ledger service",
    ),
    (
        "R-010",
        "Encryption keys not rotated on schedule",
        "Cryptography",
        12,
        8,
        "Daniel Okafor",
        "open",
        "2026-07-14",
        "Key management",
    ),
    (
        "R-011",
        "Personal data kept longer than the retention schedule",
        "Data",
        12,
        9,
        "Priya Nair",
        "open",
        "2026-04-22",
        "Data warehouse",
    ),
    (
        "R-012",
        "No tested plan for a ransomware attack",
        "Resilience",
        25,
        20,
        None,
        "open",
        "2026-02-15",
        "All systems",
    ),
    (
        "R-013",
        "Developers have standing access to production",
        "Access",
        16,
        12,
        "Asha Menon",
        "open",
        "2026-10-05",
        "Payments core",
    ),
    (
        "R-014",
        "Phishing leads to stolen staff credentials",
        "Access",
        20,
        8,
        "Sofia Rossi",
        "mitigated",
        "2026-10-19",
        "All staff",
    ),
    (
        "R-015",
        "Sub-processor change without notice",
        "Third party",
        12,
        12,
        "Priya Nair",
        "open",
        "2026-06-01",
        "CloudLedger",
    ),
    (
        "R-016",
        "Regulatory change missed by compliance",
        "Compliance",
        15,
        10,
        "Priya Nair",
        "open",
        "2026-09-03",
        "Compliance",
    ),
    (
        "R-017",
        "Open source component with a known exploited flaw",
        "Vulnerability",
        20,
        15,
        "Asha Menon",
        "open",
        "2026-10-23",
        "Customer portal",
    ),
    (
        "R-018",
        "Mobile app stores tokens insecurely",
        "Vulnerability",
        12,
        6,
        "Marcus Lee",
        "mitigated",
        "2026-08-08",
        "Mobile app",
    ),
]
CONTROLS_DB = [
    # id, name, framework_ref, owner, last_tested, result
    ("C-01", "MFA on administrator accounts", "PR.AA-03", "Asha Menon", "2026-09-10", "failed"),
    ("C-02", "Central log retention", "PR.PS-04", "Daniel Okafor", "2026-08-28", "passed"),
    (
        "C-03",
        "Vendor assurance report review",
        "GV.SC-07",
        "Priya Nair",
        "2025-11-30",
        "not tested",
    ),
    (
        "C-04",
        "Monthly patching of internet-facing systems",
        "ID.RA-06",
        "Asha Menon",
        "2026-10-20",
        "failed",
    ),
    ("C-05", "AI service allowlist", "GV.OC-03", "Priya Nair", None, "not tested"),
    ("C-06", "Backup restore test", "RC.RP-03", "Wei Chen", "2026-10-01", "passed"),
    ("C-07", "Leaver account removal", "PR.AA-05", "Sofia Rossi", "2026-09-24", "passed"),
    ("C-08", "Payment call-back verification", "PR.AT-01", "Marcus Lee", "2026-10-10", "passed"),
    ("C-09", "Key rotation schedule", "PR.DS-01", "Daniel Okafor", "2026-07-12", "failed"),
    ("C-10", "Quarterly access review", "PR.AA-05", "Asha Menon", "2026-10-04", "passed"),
    ("C-11", "Phishing simulation and training", "PR.AT-01", "Sofia Rossi", "2026-10-18", "passed"),
    (
        "C-12",
        "Software composition analysis in the build",
        "ID.RA-01",
        "Asha Menon",
        "2026-10-22",
        "passed",
    ),
]
LINKS = [
    ("R-001", "C-01"),
    ("R-002", "C-02"),
    ("R-003", "C-03"),
    ("R-004", "C-04"),
    ("R-005", "C-05"),
    ("R-006", "C-06"),
    ("R-007", "C-07"),
    ("R-008", "C-08"),
    ("R-010", "C-09"),
    ("R-013", "C-10"),
    ("R-014", "C-11"),
    ("R-017", "C-12"),
    ("R-017", "C-04"),
]
VENDORS = [
    # name, service, tier, last_assessment, report_expiry, processes_personal_data
    ("CloudLedger Inc", "Ledger hosting", "critical", "2025-11-30", "2026-09-30", True),
    ("Halden Cloud Hosting", "Data centre", "critical", "2026-06-14", "2027-03-31", True),
    ("Brightmail", "Email delivery", "high", "2026-02-20", "2026-12-31", True),
    ("Paywise Gateway", "Card processing", "critical", "2026-08-05", "2027-06-30", True),
    ("Kestrel Analytics", "Product analytics", "medium", "2025-07-19", None, True),
    ("Office Supplies Direct", "Stationery", "low", "2024-01-10", None, False),
    ("Sentry Guard", "Building security", "medium", "2026-04-02", None, False),
    ("TalentPath", "Recruitment platform", "high", "2025-09-09", "2026-08-31", True),
]
VULNS = [
    # cve, asset, found, severity, status
    ("CVE-2021-44228", "Customer portal", "2026-10-19", "critical", "open"),
    ("CVE-2023-4863", "Mobile app", "2026-09-28", "high", "fixed"),
    ("CVE-2024-3094", "Build servers", "2026-10-02", "critical", "open"),
    ("CVE-2022-22965", "Customer portal", "2026-10-19", "critical", "open"),
    ("CVE-2019-0708", "Legacy file server", "2026-08-11", "critical", "accepted"),
]


def sql_value(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert(table: str, rows: list[tuple[object, ...]]) -> str:
    lines = ",\n".join("  (" + ", ".join(sql_value(item) for item in row) + ")" for row in rows)
    return f"INSERT INTO {table} VALUES\n{lines};\n"


def write_register() -> None:
    schema = """-- The demo's risk register. Invented data for a made-up company.
CREATE TABLE risks (
  risk_id text PRIMARY KEY, title text NOT NULL, category text NOT NULL,
  inherent_score int NOT NULL, residual_score int NOT NULL, owner text,
  status text NOT NULL, last_review date NOT NULL, asset text NOT NULL
);
CREATE TABLE controls (
  control_id text PRIMARY KEY, name text NOT NULL, framework_ref text NOT NULL,
  owner text NOT NULL, last_tested date, test_result text NOT NULL
);
CREATE TABLE risk_controls (
  risk_id text REFERENCES risks, control_id text REFERENCES controls, PRIMARY KEY (risk_id, control_id)
);
CREATE TABLE vendors (
  name text PRIMARY KEY, service text NOT NULL, tier text NOT NULL, last_assessment date NOT NULL,
  assurance_report_expiry date, processes_personal_data boolean NOT NULL
);
CREATE TABLE vulnerabilities (
  cve_id text NOT NULL, asset text NOT NULL, found_on date NOT NULL, severity text NOT NULL,
  status text NOT NULL, PRIMARY KEY (cve_id, asset)
);
COMMENT ON TABLE risks IS 'One row for each risk. Scores are likelihood times impact, 1 to 25. An empty owner means nobody owns the risk.';
COMMENT ON TABLE controls IS 'One row for each control. framework_ref is the NIST CSF 2.0 outcome the control serves.';
COMMENT ON TABLE risk_controls IS 'Which control treats which risk.';
COMMENT ON TABLE vendors IS 'Third parties. tier is critical, high, medium or low.';
COMMENT ON TABLE vulnerabilities IS 'Open and closed findings from the vulnerability scanner, by CVE and asset.';
"""
    body = (
        schema
        + insert("risks", RISKS)  # type: ignore[arg-type]
        + insert("controls", CONTROLS_DB)  # type: ignore[arg-type]
        + insert("risk_controls", LINKS)  # type: ignore[arg-type]
        + insert("vendors", VENDORS)  # type: ignore[arg-type]
        + insert("vulnerabilities", VULNS)  # type: ignore[arg-type]
    )
    (OUT / "risk-register.sql").write_text(body, encoding="utf-8")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    write_policy("3.2", "14 March 2025")
    write_policy("4.0", "9 October 2026")
    with (OUT / "nist-csf-2-control-subset.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["control_id", "function", "statement"])
        writer.writerows(CONTROLS)
    write_sections(
        "meridian-standard-data-processing-agreement.docx",
        "Meridian standard data processing agreement",
        "Meridian's standard terms for a vendor that processes personal data on its behalf.",
        DPA_STANDARD,
    )
    write_sections(
        "cloudledger-data-processing-agreement-draft.docx",
        "CloudLedger data processing agreement (vendor draft)",
        "Draft received from CloudLedger Inc on 3 November 2026 for the ledger hosting contract.",
        DPA_VENDOR,
    )
    write_sections(
        "cloudledger-soc2-type2-report-2026.docx",
        "CloudLedger SOC 2 Type II report 2026 (summary)",
        "Summary of the independent service auditor's report, as shared by CloudLedger Inc.",
        SOC2,
    )
    book = Workbook()
    sheet = book.active
    sheet.title = "Questionnaire"
    sheet.append(["No.", "Question", "Answer", "Source"])
    for index, question in enumerate(QUESTIONS, start=1):
        sheet.append([f"Q{index}", question, "", ""])
    sheet.column_dimensions["B"].width = 80
    book.save(OUT / "customer-security-questionnaire.xlsx")
    write_register()
    for path in sorted(OUT.iterdir()):
        print(path.name, path.stat().st_size)


if __name__ == "__main__":
    main()
