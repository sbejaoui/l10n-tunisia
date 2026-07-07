# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command, models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('tn')
    def _get_tn_template_data(self):
        return {
            'code_digits': 6,
            'property_account_receivable_id': 'tn_pcg_recv',
            'property_account_payable_id': 'tn_pcg_pay',
            'property_account_expense_categ_id': 'tn_pcg_expense',
            'property_account_income_categ_id': 'tn_pcg_sale',
            'property_account_downpayment_categ_id': 'pcg_4191',
        }

    @template('tn', 'res.company')
    def _get_tn_res_company(self):
        return {
            self.env.company.id: {
                'account_fiscal_country_id': 'base.tn',
                'bank_account_code_prefix': '532',
                'cash_account_code_prefix': '541',
                'transfer_account_code_prefix': '58',
                'account_default_pos_receivable_account_id': 'tn_pcg_recv',
                'income_currency_exchange_account_id': 'pcg_756',
                'expense_currency_exchange_account_id': 'pcg_655',
                'account_journal_suspense_account_id': 'pcg_461',
                'account_journal_early_pay_discount_loss_account_id': 'pcg_654',
                'account_journal_early_pay_discount_gain_account_id': 'pcg_755',
                'deferred_expense_account_id': 'pcg_471',
                'deferred_revenue_account_id': 'pcg_472',
                'account_sale_tax_id': 'tax_tva_sale',
                'account_purchase_tax_id': 'tax_tva_purchase',
            },
        }

    @template('tn', 'account.journal')
    def _get_tn_account_journal(self):
        return {
            'sale': {'refund_sequence': True},
            'purchase': {'refund_sequence': True},
        }

    @template('tn', 'account.reconcile.model')
    def _get_tn_reconcile_model(self):
        return {
            'bank_charges_reconcile_model': {
                'name': 'Bank fees',
                'line_ids': [
                    Command.create({
                        'account_id': 'pcg_6278',
                        'amount_type': 'percentage',
                        'amount_string': '100',
                    }),
                ],
            },
        }
