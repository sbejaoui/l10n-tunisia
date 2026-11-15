# Copyright 2026 Sobware
# License AGPL-3.0 or later (https://www.gnu.org/licenses/AGPL-3.0).


def post_init_hook(env):
    companies = env["res.company"].search(
        [("chart_template", "=", "tn"), ("parent_id", "=", False)]
    )
    for company in companies:
        chart_template = env["account.chart.template"].with_company(company)
        for xmlid, values in chart_template._get_tn_stamp_tax_account_tax().items():
            tax = chart_template.ref(xmlid, raise_if_not_found=False)
            if not tax:
                continue
            configured_tax = env["account.tax"].search(
                [
                    ("company_id", "=", company.id),
                    ("type_tax_use", "=", tax.type_tax_use),
                    ("l10n_tn_is_stamp_tax", "=", True),
                ],
                limit=1,
            )
            if not configured_tax:
                tax.write(values)
