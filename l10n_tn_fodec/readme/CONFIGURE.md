* Sales FODEC: 1% of the untaxed line amount, posted to the existing account
  43658 (Other turnover taxes).
* Purchase FODEC: 1%, charged to the invoice line's account as a non-recoverable
  cost, without posting it to a deductible VAT account.
* Both taxes are excluded from the price, have sequence 0 (before the standard
  VAT taxes), ignore preceding taxes, and increase the base of subsequent taxes.
  VAT must retain "Base Affected by Previous Taxes" and a higher sequence.
* The export fiscal position replaces sales FODEC with a separate 0% FODEC tax.
  A VAT exemption alone does not establish a FODEC exemption; no automatic
  mapping is added to the generic Exemption fiscal position.

Select FODEC alongside VAT only for supplies subject to FODEC. This addon does
not classify products, change company default taxes, or apply taxes automatically
to every transaction. For imports, calculate FODEC on the customs value; an
ordinary foreign supplier bill is not a customs assessment.

For 100.000 TND excluding tax, FODEC is 1.000 TND and 19% VAT on 101.000 TND
is 19.190 TND, giving 120.190 TND before stamp duty.

Existing companies receive these definitions when the addon is installed.
Future chart loads and reloads use the standard Odoo chart-template mechanism.
FODEC has its own tax group; this addon does not extend the statutory tax report
or assign VAT report tags to FODEC.

Legal references
================

* Articles 36 and 37 of law 99-101 of 31 December 1999, as amended, define
  scope, the 1% rate and the export exemption. Decree 2000-634, amended by
  decrees 2008-4111 and 2012-435, lists covered products. Applicability depends
  on the supply and the taxpayer's role, not merely the company's industry.
  See the Ministry of Finance compilation, pages 134-137:
  https://www.finances.gov.tn/sites/default/files/RECUEIL%20DES%20TEXTES%20RELATIFS%20AUX%20DROITS%20ET%20TAXES%20NON%20INCORPORES%20DANS%20LES%20CODES%20FISCAUX%202017.pdf
* The Ministry of Finance confirms that FODEC forms part of the VAT base:
  https://www.finances.gov.tn/fr/faq?page=8
