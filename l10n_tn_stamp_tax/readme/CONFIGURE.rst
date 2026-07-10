This module does not create any tax. You flag an existing tax as the stamp
tax:

#. Go to *Accounting > Configuration > Taxes*.
#. Create (or open) the tax you want to use as the stamp tax. It should be a
   **fixed** amount tax, with the **Tax Type** set to *Sales* or *Purchases*
   depending on where it applies.
#. Open the **Advanced Options** tab and tick **Is Stamp Tax**.
#. Repeat for the purchase stamp tax if you need one on vendor bills: a
   separate fixed tax with **Tax Type** *Purchases* and **Is Stamp Tax**
   ticked.

Only one stamp tax per direction (sales / purchases) and per company should be
flagged. If no flagged stamp tax matches the document being posted, posting
raises an error asking you to configure one.

Once a stamp tax is flagged, it is added automatically at posting time; no
further configuration is required on documents.
