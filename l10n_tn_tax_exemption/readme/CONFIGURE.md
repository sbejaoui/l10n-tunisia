This module creates a 0% sales tax named **Tax Exemption** for each company
using the Tunisian chart of accounts. Existing companies receive it when
the module is installed; new companies receive it when their chart is loaded.
Branches share their parent company's accounting data. The **Exemption**
fiscal position uses **Tax Exemption**, while **Export** keeps the existing
**0%** sales tax. Configure the customer's attestation before creating an
invoice:

1.  Go to *Accounting \> Configuration \> Fiscal Positions*. Open the
    Tunisian **Exemption** fiscal position, or create one for the company.
    Check that covered sales taxes map to **Tax Exemption**. A fiscal
    position needs at least one tax mapping to appear in the attestation's
    **Fiscal Position** field.
2.  If you also use the **Export** fiscal position, keep its sales tax
    mappings to the existing **0%** tax.
3.  Go to *Contacts* and open the customer's commercial partner. If
    invoices use a child contact, configure its parent company.
4.  On the **Invoicing** tab, under **Tax Exemptions**, add the
    **Certificate** number, **Start Date**, and **End Date**, and attach
    the **Tax Exemption File**. The company's Tunisian **Exemption** fiscal
    position is selected by default. The **Fiscal Position** column is
    hidden by default and can be shown through the column selector.
    Both dates are included in the validity period.

The Tunisian **Exemption** fiscal position cannot be deleted.

In *Accounting > Configuration > Settings > Taxes*, set **Tax Exemption
Reminder** for each company. The default period is 12 calendar months before
the invoice date. Set it to 0 to disable reminders for that company.

Avoid overlapping validity periods for the same partner: when more than
one attestation matches, the module selects only one of them.

If exemption must require a valid attestation, check that **Detect
Automatically** is disabled on the exemption fiscal position. Otherwise,
Odoo can apply that fiscal position even without an attestation.
