* Register a payment using Traite from one or more posted invoices for a single
  customer, receivable account, company and TND currency. Selecting Traite groups
  compatible invoices into one payment automatically, allowing a partial amount.
  Supply the bill reference, maturity and signed acceptance.
* Alternatively, prepare a draft bill under Accounting / Traites clients /
  Portefeuille et suivi. Select the invoices, attach the signed title and confirm
  receipt when acceptance is evidenced. Printing a draft does not record payment.
* The invoice's residual decreases through native reconciliation. A partially
  covered invoice remains Partially Paid; a fully covered bill still awaiting
  collection stays In Payment, including in the Community accounting workflow.
* Record collections from the bill. A new native payment credits the bills
  account directly. Payments using the bank/cash account directly settle immediately.
  An outstanding payment reserves principal until the user confirms receipt from
  the collection, with or without bank matching. This confirms the native payment
  and settles the bill without requiring a bank statement. The outstanding account
  remains open until bank matching if that workflow is used. An existing payment
  or bank-transaction credit can also be used,
  provided its remaining credit exactly matches the selected principal.
* Declare an unpaid principal with a reason and an optional supporting document.
  The original invoices reopen for the returned amount while collected fractions
  remain paid. The corresponding incident remains available for explicit recovery
  allocation.
* Use Recouvrer on the incident for later collections. Ordinary invoice payments
  may cover unrelated open balances, but cannot silently consume principal
  reserved for incident follow-up.
* A replacement bill can cover the exact outstanding, unreserved incidents of
  a rejected bill. Link the previous bill and the original invoices. Transfers
  to the replacement are shown separately from cash recoveries; canceling the
  replacement restores the old incident balance.
* Collection reversal and bill cancellation use reversing entries. Posted bill
  details and the original invoice links are protected against ordinary edits.

## Dashboard and follow-up

The dashboard is a live native spreadsheet with five sheets:

* Synthèse: current principal, portfolio, bill exposure, overdue titles, pending
  receipts, unpaid balances and actionable dossiers.
* Échéancier: expected principal by month and exclusive delay buckets.
* Portefeuille: customer/custody and responsible analyses.
* Impayés et recouvrement: current incident balances, period incident flows
  and linked dossiers.
* Encaissements et recouvrements: confirmed period collections and recoveries.

Filter by company, customer, responsible, maturity and flow period. The flow
period does not filter current-stock cards. Amounts awaiting confirmation are
already included in active principal; never add them a second time. Pivot
totals cover all records; detailed spreadsheet lists show the first 50 dossiers.
Use the native list for the full work queue and pivot source drill-down.

The native work queue exposes next action, due date, last contact, promise,
responsible and financial balances. Promises never change accounting totals.
Daily activities cover approaching maturity, overdue confirmation, incidents,
pending collections and expired promises, with escalation and no duplicate
automated activity for the same bill.

The load timestamp is refreshed when the dashboard is loaded. Refresh/reload
the spreadsheet after operations. Source queries use the viewer's accounting
rights and allowed companies; no sample business values are embedded in the
spreadsheet. Public snapshot sharing is disabled for this dashboard because
a public cached snapshot cannot preserve each viewer's accounting permissions.

## Implementation

Receipt checks use the native journal-entry generation hook; reconciliation
and sharing rules use ORM constraints. The two remaining write guards protect
confirmed payment details and posted financial lines.

Settlements and incidents have read-only ACLs. Authorized workflow actions
perform financial operations with the caller's accounting permissions, then
use narrowly scoped elevated access to append or update history and its proof.
Direct creation and editing of history remain unavailable to accounting users.
Each history model has its own security XML file with company rules.

Concurrency protection uses Odoo 19's native lock_for_update API. The module
contains no handwritten SQL queries. A field restricted to technical users
records whether a transient operation has already been applied.

## Limits and acceptance

The initial scope is customer bills in TND with fixed maturity, including partial
collections. Supplier bills, discounting, endorsements, guarantees, partial legal
acceptance, grouped remittance files, foreign currencies and legal deadline
automation are outside this version.

The PDF is a proposed document layout to validate against the client's actual
title. A generated PDF or an Odoo confirmation is not a legal signature.
No bill stamp tax is generated automatically.

Stamp-duty rules and compatibility with invoice-stamp addons belong to those
addons. This module does not depend on or override their tax logic.

Bank remittance actions and fee management are outside the supported workflow.

No arbitrary historical portfolio reconstruction or write-off automation is
included. Incident closure is driven by explicit collections or replacement;
it is never a manual financial-status change.

The source includes business tests for coverage, partial settlement, pending
confirmation, rejection, recovery, reversal, replacement, chart setup, workflow
guards and dashboard access. Odoo installation and test execution require an
explicitly authorized test database; static validation alone does not establish
accounting acceptance.
