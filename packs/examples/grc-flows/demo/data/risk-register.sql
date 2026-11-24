-- The demo's risk register. Invented data for a made-up company.
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
INSERT INTO risks VALUES
  ('R-001', 'Administrator accounts without multi-factor authentication', 'Access', 20, 12, 'Asha Menon', 'open', '2026-09-12', 'Payments core'),
  ('R-002', 'Security logs kept for less than a year', 'Monitoring', 12, 9, 'Daniel Okafor', 'open', '2026-08-30', 'Log platform'),
  ('R-003', 'Critical vendor without a current assurance report', 'Third party', 16, 16, NULL, 'open', '2026-03-02', 'CloudLedger'),
  ('R-004', 'Unpatched internet-facing web server', 'Vulnerability', 25, 15, 'Asha Menon', 'open', '2026-10-21', 'Customer portal'),
  ('R-005', 'Customer data entered into unapproved AI services', 'Data', 16, 12, NULL, 'open', '2026-06-18', 'All staff'),
  ('R-006', 'Backups not tested by restore', 'Resilience', 15, 6, 'Wei Chen', 'mitigated', '2026-10-02', 'Payments core'),
  ('R-007', 'Leaver accounts stay active', 'Access', 12, 4, 'Sofia Rossi', 'mitigated', '2026-09-25', 'Identity platform'),
  ('R-008', 'Payment fraud through social engineering', 'Fraud', 20, 10, 'Marcus Lee', 'open', '2026-10-11', 'Finance operations'),
  ('R-009', 'Single data centre for the ledger service', 'Resilience', 20, 16, 'Wei Chen', 'open', '2026-05-09', 'Ledger service'),
  ('R-010', 'Encryption keys not rotated on schedule', 'Cryptography', 12, 8, 'Daniel Okafor', 'open', '2026-07-14', 'Key management'),
  ('R-011', 'Personal data kept longer than the retention schedule', 'Data', 12, 9, 'Priya Nair', 'open', '2026-04-22', 'Data warehouse'),
  ('R-012', 'No tested plan for a ransomware attack', 'Resilience', 25, 20, NULL, 'open', '2026-02-15', 'All systems'),
  ('R-013', 'Developers have standing access to production', 'Access', 16, 12, 'Asha Menon', 'open', '2026-10-05', 'Payments core'),
  ('R-014', 'Phishing leads to stolen staff credentials', 'Access', 20, 8, 'Sofia Rossi', 'mitigated', '2026-10-19', 'All staff'),
  ('R-015', 'Sub-processor change without notice', 'Third party', 12, 12, 'Priya Nair', 'open', '2026-06-01', 'CloudLedger'),
  ('R-016', 'Regulatory change missed by compliance', 'Compliance', 15, 10, 'Priya Nair', 'open', '2026-09-03', 'Compliance'),
  ('R-017', 'Open source component with a known exploited flaw', 'Vulnerability', 20, 15, 'Asha Menon', 'open', '2026-10-23', 'Customer portal'),
  ('R-018', 'Mobile app stores tokens insecurely', 'Vulnerability', 12, 6, 'Marcus Lee', 'mitigated', '2026-08-08', 'Mobile app');
INSERT INTO controls VALUES
  ('C-01', 'MFA on administrator accounts', 'PR.AA-03', 'Asha Menon', '2026-09-10', 'failed'),
  ('C-02', 'Central log retention', 'PR.PS-04', 'Daniel Okafor', '2026-08-28', 'passed'),
  ('C-03', 'Vendor assurance report review', 'GV.SC-07', 'Priya Nair', '2025-11-30', 'not tested'),
  ('C-04', 'Monthly patching of internet-facing systems', 'ID.RA-06', 'Asha Menon', '2026-10-20', 'failed'),
  ('C-05', 'AI service allowlist', 'GV.OC-03', 'Priya Nair', NULL, 'not tested'),
  ('C-06', 'Backup restore test', 'RC.RP-03', 'Wei Chen', '2026-10-01', 'passed'),
  ('C-07', 'Leaver account removal', 'PR.AA-05', 'Sofia Rossi', '2026-09-24', 'passed'),
  ('C-08', 'Payment call-back verification', 'PR.AT-01', 'Marcus Lee', '2026-10-10', 'passed'),
  ('C-09', 'Key rotation schedule', 'PR.DS-01', 'Daniel Okafor', '2026-07-12', 'failed'),
  ('C-10', 'Quarterly access review', 'PR.AA-05', 'Asha Menon', '2026-10-04', 'passed'),
  ('C-11', 'Phishing simulation and training', 'PR.AT-01', 'Sofia Rossi', '2026-10-18', 'passed'),
  ('C-12', 'Software composition analysis in the build', 'ID.RA-01', 'Asha Menon', '2026-10-22', 'passed');
INSERT INTO risk_controls VALUES
  ('R-001', 'C-01'),
  ('R-002', 'C-02'),
  ('R-003', 'C-03'),
  ('R-004', 'C-04'),
  ('R-005', 'C-05'),
  ('R-006', 'C-06'),
  ('R-007', 'C-07'),
  ('R-008', 'C-08'),
  ('R-010', 'C-09'),
  ('R-013', 'C-10'),
  ('R-014', 'C-11'),
  ('R-017', 'C-12'),
  ('R-017', 'C-04');
INSERT INTO vendors VALUES
  ('CloudLedger Inc', 'Ledger hosting', 'critical', '2025-11-30', '2026-09-30', TRUE),
  ('Halden Cloud Hosting', 'Data centre', 'critical', '2026-06-14', '2027-03-31', TRUE),
  ('Brightmail', 'Email delivery', 'high', '2026-02-20', '2026-12-31', TRUE),
  ('Paywise Gateway', 'Card processing', 'critical', '2026-08-05', '2027-06-30', TRUE),
  ('Kestrel Analytics', 'Product analytics', 'medium', '2025-07-19', NULL, TRUE),
  ('Office Supplies Direct', 'Stationery', 'low', '2024-01-10', NULL, FALSE),
  ('Sentry Guard', 'Building security', 'medium', '2026-04-02', NULL, FALSE),
  ('TalentPath', 'Recruitment platform', 'high', '2025-09-09', '2026-08-31', TRUE);
INSERT INTO vulnerabilities VALUES
  ('CVE-2021-44228', 'Customer portal', '2026-10-19', 'critical', 'open'),
  ('CVE-2023-4863', 'Mobile app', '2026-09-28', 'high', 'fixed'),
  ('CVE-2024-3094', 'Build servers', '2026-10-02', 'critical', 'open'),
  ('CVE-2022-22965', 'Customer portal', '2026-10-19', 'critical', 'open'),
  ('CVE-2019-0708', 'Legacy file server', '2026-08-11', 'critical', 'accepted');
