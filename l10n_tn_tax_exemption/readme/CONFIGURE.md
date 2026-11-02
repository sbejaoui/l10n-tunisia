This module creates a 0% sales tax named **Tax exonerated**. It does not
create or automatically change fiscal positions. Configure the fiscal
position and the customer's attestation before creating an invoice:

1.  Go to *Accounting \> Configuration \> Fiscal Positions*. Open the
    Tunisian **Exemption** fiscal position, or create one for the company.
    In **Tax Mapping**, set **Tax exonerated** as the tax to apply for
    each sales tax covered by the exemption. A fiscal position needs at
    least one tax mapping to appear in the attestation's **Fiscal Position**
    field.
2.  If you also use the **Export** fiscal position and want it to apply
    **Tax exonerated**, update its sales tax mappings in the same way.
3.  Go to *Contacts* and open the customer's commercial partner. If
    invoices use a child contact, configure its parent company.
4.  On the **Invoicing** tab, under **Tax Exemptions**, add the
    **Attestation** number, **Start Date**, **End Date**, and **Fiscal
    Position**, and attach the **Tax Exemption File**. Both dates are
    included in the validity period.

Avoid overlapping validity periods for the same partner: when more than
one attestation matches, the module selects only one of them.

If exemption must require a valid attestation, check that **Detect
Automatically** is disabled on the exemption fiscal position. Otherwise,
Odoo can apply that fiscal position even without an attestation.
