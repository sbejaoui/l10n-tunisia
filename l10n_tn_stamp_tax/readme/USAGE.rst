Once a stamp tax has been flagged (see *Configuration*), it is handled
automatically:

#. Create a customer invoice or a vendor bill as usual.
#. Confirm (post) the document.
#. When posting, if no stamp tax line is present yet, a stamp tax line is
   added automatically. The correct sale or purchase stamp tax is chosen based
   on the document type and the company.

The stamp tax applies only when both the company and the partner are located
in Tunisia. The stamp tax amount is included in the document totals and in the
tax report. On the printed PDF invoice, the stamp tax line is hidden from the
invoice line table but still appears in the tax summary.
