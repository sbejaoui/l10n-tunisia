from odoo import Command
from odoo.tests import Form
from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from .common import setup_tunisian_parties, setup_withholding_accounts


@tagged("post_install", "-at_install")
class TestAccountMove(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_tunisian_parties(cls)
        setup_withholding_accounts(cls)
        cls.test_journal1 = cls.env["account.journal"].create(
            {
                "name": "RS 1.5%",
                "type": "bank",
                "code": "RS15",
                "is_withholding_tax_journal": True,
                "withholding_direction": "outbound",
                "withholding_tax_rate": 0.015,
            }
        )
        cls.test_journal2 = cls.env["account.journal"].create(
            {
                "name": "RS 5%",
                "type": "bank",
                "code": "RS5",
                "is_withholding_tax_journal": True,
                "withholding_direction": "outbound",
                "withholding_tax_rate": 0.05,
            }
        )
        cls.inbound_journal = cls.test_journal1.copy(
            {
                "name": "Incoming RS 1.5%",
                "code": "IRS15",
                "withholding_direction": "inbound",
            }
        )
        for journal in cls.test_journal1 | cls.test_journal2:
            journal.outbound_payment_method_line_ids.payment_account_id = (
                cls.tax_payable
            )
        cls.inbound_journal.inbound_payment_method_line_ids.payment_account_id = (
            cls.tax_receivable
        )
        cls.test_withholding_rule = cls.env["l10n.tn.withholding.rule"].create(
            {
                "product_id": [Command.set(cls.product_a.ids)],
                "description": "Test Withholding Rule",
                "amount": 0,
                "move_type": "in_invoice",
                "withholding_journal_id": cls.test_journal1.id,
            }
        )
        cls.test_withholding_rule2 = cls.env["l10n.tn.withholding.rule"].create(
            {
                "product_id": [Command.set(cls.product_b.ids)],
                "description": "Test Withholding Rule 2",
                "amount": 1000,
                "move_type": "in_invoice",
                "withholding_journal_id": cls.test_journal2.id,
            }
        )
        cls.test_withholding_rule.copy(
            {
                "move_type": "out_invoice",
                "withholding_journal_id": cls.inbound_journal.id,
            }
        )

    def _create_bill(self, move_type="in_invoice"):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "invoice_date": "2024-01-01",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_a.id,
                            "quantity": 1,
                            "price_unit": 2000,
                        }
                    )
                ],
            }
        )

    def test_calculate_withholding_tax_amount(self):
        bill = self._create_bill()
        bill.action_post()
        applicable_rules = self.test_withholding_rule._get_applicable_rules(bill)
        self.assertIn(self.test_withholding_rule, applicable_rules)
        withholding_amount = self.test_withholding_rule._get_withholding_amount(bill)
        expected_amount = bill.amount_total * self.test_journal1.withholding_tax_rate
        self.assertEqual(withholding_amount, expected_amount)

    def test_invoice_report_lists_withholding_before_other_payments(self):
        bill = self._create_bill(move_type="out_invoice")
        bill.action_post()
        self.assertEqual(bill._get_withholding_invoice_report_payments(), [])
        bank = self.company_data["default_journal_bank"]
        registered_payments = self.env["account.payment"]
        for journal, amount in ((bank, 500), (bank, 250), (self.inbound_journal, 30)):
            wizard = (
                self.env["account.payment.register"]
                .with_context(active_model="account.move", active_ids=bill.ids)
                .create({})
            )
            with Form(wizard) as form:
                form.journal_id = journal
                form.amount = amount
            registered_payments |= wizard._create_payments()

        original_payments = [
            dict(payment) for payment in bill.invoice_payments_widget["content"]
        ]
        report_payments = bill._get_withholding_invoice_report_payments()
        withholding = registered_payments.filtered("is_withholding_tax_payment")
        self.assertEqual(report_payments[0]["account_payment_id"], withholding.id)
        self.assertEqual(report_payments[0]["amount"], 30)
        self.assertEqual(report_payments[0]["journal_name"], self.inbound_journal.name)
        self.assertTrue(report_payments[0]["is_withholding_tax_payment"])
        self.assertEqual(
            [item["account_payment_id"] for item in report_payments[1:]],
            [
                item["account_payment_id"]
                for item in original_payments
                if item["account_payment_id"] != withholding.id
            ],
        )
        self.assertTrue(
            all(not item["is_withholding_tax_payment"] for item in report_payments[1:])
        )
        self.assertEqual(bill.invoice_payments_widget["content"], original_payments)

    def test_calculate_withholding_tax_amount2(self):
        bill = self._create_bill()
        tax = self.env["account.tax"].create(
            {
                "name": "Test purchase VAT 15%",
                "amount_type": "percent",
                "amount": 15,
                "type_tax_use": "purchase",
                "company_id": bill.company_id.id,
            }
        )
        bill.invoice_line_ids.tax_ids = [Command.set(tax.ids)]
        bill.action_post()
        self.assertEqual(bill.amount_total, 2300)
        applicable_rules = self.test_withholding_rule._get_applicable_rules(bill)
        self.assertIn(self.test_withholding_rule, applicable_rules)
        withholding_amount = self.test_withholding_rule._get_withholding_amount(bill)
        expected_amount = 34.5
        self.assertEqual(withholding_amount, expected_amount)

    def test_withholding_tax_alert(self):
        bill = self._create_bill()
        bill.action_post()

        wizard = (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move",
                active_ids=[bill.id],
            )
            .create({})
        )

        self.assertTrue(wizard.withholding_tax_alert)
        self.assertIn(self.product_a.display_name, wizard.withholding_tax_alert)
        self.assertIn(self.test_journal1.name, wizard.withholding_tax_alert)
        self.assertNotIn(self.test_journal2.name, wizard.withholding_tax_alert)

    def test_switch_from_withholding_to_bank_journal(self):
        bank = self.company_data["default_journal_bank"]
        for move_type in ("in_invoice", "out_invoice"):
            with self.subTest(move_type=move_type):
                journal = (
                    self.test_journal1
                    if move_type == "in_invoice"
                    else self.inbound_journal
                )
                bill = self._create_bill(move_type)
                bill.action_post()
                wizard = (
                    self.env["account.payment.register"]
                    .with_context(active_model="account.move", active_ids=bill.ids)
                    .create({})
                )

                with Form(wizard) as form:
                    form.journal_id = journal
                    self.assertAlmostEqual(form.amount, bill.amount_total * 0.015)
                    form.amount = 10
                    form.journal_id = bank
                    self.assertAlmostEqual(form.amount, bill.amount_residual)

    def test_switch_to_bank_uses_remaining_balance(self):
        bill = self._create_bill()
        bill.action_post()
        bank = self.company_data["default_journal_bank"]
        wizard_model = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=bill.ids
        )
        partial_wizard = wizard_model.create({})
        with Form(partial_wizard) as form:
            form.journal_id = bank
            form.amount = 500
        partial_wizard._create_payments()
        self.assertAlmostEqual(bill.amount_residual, bill.amount_total - 500)

        wizard = wizard_model.create({})
        with Form(wizard) as form:
            form.journal_id = self.test_journal1
            form.journal_id = bank
            self.assertAlmostEqual(form.amount, bill.amount_residual)

    def test_switch_between_bank_journals_keeps_custom_amount(self):
        bill = self._create_bill()
        bill.action_post()
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({})
        )
        another_bank = self.env["account.journal"].create(
            {"name": "Other Bank", "type": "bank", "code": "BNK2"}
        )

        with Form(wizard) as form:
            form.journal_id = self.company_data["default_journal_bank"]
            form.amount = 500
            form.journal_id = another_bank
            self.assertEqual(form.amount, 500)

    # def test_already_paid_withholding_tax(self):
    #     bill = self._create_bill()
    #     bill.action_post()

    #     wizard = (
    #         self.env["account.payment.register"]
    #         .with_context(
    #             active_model="account.move",
    #             active_ids=[bill.id],
    #         )
    #         .create({"journal_id": self.test_journal1.id})
    #     )

    #     wizard2 = (
    #         self.env["account.payment.register"]
    #         .with_context(
    #             active_model="account.move",
    #             active_ids=[bill.id],
    #         )
    #         .create({"journal_id": self.test_journal1.id})
    #     )
