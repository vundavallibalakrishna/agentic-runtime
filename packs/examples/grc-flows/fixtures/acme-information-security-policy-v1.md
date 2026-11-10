# ACME Corp Information Security Policy

Version 1.0. Owner: Chief Information Security Officer. Approved: 15 January 2026. Applies to all ACME employees, contractors and systems.

## 1. Purpose and scope

This policy sets the minimum security controls for ACME information and systems. It applies to production, corporate and customer data environments.

## 2. Access control

2.1 Access to systems is granted on a least-privilege basis and approved by the system owner.
2.2 Every user has a unique account. Shared accounts are prohibited.
2.3 Passwords must be at least 12 characters long.
2.4 Multi-factor authentication is recommended for remote access to production systems.
2.5 Access rights are reviewed by system owners every twelve months.
2.6 Access is revoked within five business days of a person leaving ACME.

## 3. Encryption

3.1 Customer data is encrypted at rest using AES-256.
3.2 Data in transit over public networks is encrypted using TLS 1.2 or higher.
3.3 Encryption keys are stored in a managed key service and rotated every year.

## 4. Logging and monitoring

4.1 Production systems send security logs to the central log platform.
4.2 Security logs are retained for 90 days.
4.3 The security team reviews alerts from the log platform on business days.

## 5. Vendor risk

5.1 Vendors that process customer data complete a security questionnaire before contract signature.
5.2 Vendor contracts include confidentiality obligations.

## 6. Incident response

6.1 ACME maintains an incident response plan, tested once a year.
6.2 Suspected security incidents are reported to the security team within 24 hours.
6.3 Customers affected by a confirmed personal data breach are notified within 72 hours of confirmation.

## 7. Business continuity

7.1 Production databases are backed up daily and backups are kept for 30 days.

## 8. Exceptions

Exceptions to this policy require written approval from the CISO and expire after six months.
