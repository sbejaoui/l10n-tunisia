# Copyright 2026 Sobware
# License AGPL-3.0 or later (https://www.gnu.org/licenses/AGPL-3.0).


def post_init_hook(env):
    companies = env["res.company"].search(
        [("chart_template", "=", "tn"), ("parent_id", "=", False)]
    )
    for company in companies:
        chart_template = env["account.chart.template"].with_company(company)
        data = {
            model: chart_template._parse_csv("tn", model, module="l10n_tn_fodec")
            for model in ("account.tax.group", "account.tax")
        }
        chart_template._pre_reload_data(company, {}, data)
        chart_template._load_data(data)
