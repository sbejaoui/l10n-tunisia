The Tunisian chart supplies fixed stamp taxes of **1 TND** for sales and
purchases, in its existing stamp-duty tax group. Sales stamp duty posts to
account **437** and purchase stamp duty to **6654**, including refunds.
The addon enables **Is Stamp Tax** on both chart taxes automatically.

Existing companies using the Tunisian chart are configured when this addon
is installed. If a company already has a flagged stamp tax for sales or
purchases, that selection is preserved for that direction. Existing tax
amounts, names and posting accounts are preserved.

To review or customize the configuration, go to *Accounting > Configuration
> Taxes*. Keep only one active tax flagged as **Is Stamp Tax** per company
and direction. The selected tax must be a fixed-amount tax with the
appropriate Sales or Purchases type.

Future chart installations receive the flags through the standard Odoo
chart-template mechanism. If the addon was already installed before this
feature was added, flag the chart taxes manually in **Advanced Options**.
