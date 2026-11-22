# Copyright 2026 Sobware
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import tagged

from .common import WithholdingTaxTestCommon


@tagged("post_install", "-at_install")
class TestWithholdingJournalConfiguration(WithholdingTaxTestCommon):
    def test_standard_payment_tabs_remain_available(self):
        view = self.withholding_journal.get_view(
            view_id=self.env.ref("account.view_account_journal_form").id,
            view_type="form",
        )
        arch = etree.fromstring(view["arch"])
        for name in ("page_incoming_payments", "page_outgoing_payments"):
            page = arch.xpath(f"//page[@name='{name}']")[0]
            self.assertNotIn("is_withholding_tax_journal", page.get("invisible", ""))
            self.assertTrue(page.xpath(".//field[@name='payment_account_id']"))

    def test_new_withholding_journal_uses_standard_method_accounts(self):
        with Form(self.env["account.journal"]) as form:
            form.name = "Shared withholding setup"
            form.type = "bank"
            form.code = "RSNEW"
            form.is_withholding_tax_journal = True
            form.withholding_tax_rate = 0.015
        journal = form.record
        journal.inbound_payment_method_line_ids.payment_account_id = self.tax_receivable
        journal.outbound_payment_method_line_ids.payment_account_id = self.tax_payable
        for direction, account in (
            ("inbound", self.tax_receivable),
            ("outbound", self.tax_payable),
        ):
            payment = self._create_payment(journal=journal, payment_type=direction)
            payment.action_post()
            self.assertEqual(payment.outstanding_account_id, account)
            fiscal_line = payment.move_id.line_ids.filtered(
                lambda line, fiscal_account=account: line.account_id == fiscal_account
            )
            self.assertEqual(fiscal_line.balance, 30 if direction == "inbound" else -30)

    def _create_payment(self, journal=None, **values):
        journal = journal or self.inbound_withholding_journal
        inbound = values.get("payment_type", "inbound") == "inbound"
        method = (
            journal.inbound_payment_method_line_ids
            if inbound
            else journal.outbound_payment_method_line_ids
        )[:1]
        return self.env["account.payment"].create(
            {
                "journal_id": journal.id,
                "payment_method_line_id": method.id,
                "partner_id": self.partner_a.id,
                "payment_type": "inbound" if inbound else "outbound",
                "partner_type": "customer" if inbound else "supplier",
                "amount": 30,
                **values,
            }
        )

    def test_journal_type_and_rate_are_checked_on_create_and_write(self):
        for values, message in (
            ({"type": "cash"}, "must be a bank journal"),
            ({"withholding_tax_rate": -0.01}, "greater than 0"),
            ({"withholding_tax_rate": 0}, "greater than 0"),
            ({"withholding_tax_rate": 1.01}, "greater than 0"),
        ):
            with self.subTest(values=values):
                with (
                    self.assertRaisesRegex(ValidationError, message),
                    self.cr.savepoint(),
                ):
                    self.env["account.journal"].create(
                        {
                            "name": "Invalid withholding configuration",
                            "code": "BADRS",
                            "type": "bank",
                            "is_withholding_tax_journal": True,
                            "withholding_tax_rate": 0.015,
                            **values,
                        }
                    )
                with (
                    self.assertRaisesRegex(ValidationError, message),
                    self.cr.savepoint(),
                ):
                    self.inbound_withholding_journal.write(values)
        self.inbound_withholding_journal.withholding_tax_rate = 1
        self.assertEqual(self.inbound_withholding_journal.withholding_tax_rate, 1)

    def test_method_account_must_use_an_allowed_fiscal_type(self):
        for journal, invalid_account in (
            (
                self.inbound_withholding_journal,
                self.partner_a.property_account_receivable_id,
            ),
            (self.withholding_journal, self.company_data["default_account_expense"]),
            (
                self.inbound_withholding_journal,
                self.company_data["default_journal_bank"].default_account_id,
            ),
            (self.inbound_withholding_journal, self.env.company.transfer_account_id),
        ):
            with self.subTest(journal=journal.name, account=invalid_account.name):
                method = journal.inbound_payment_method_line_ids[:1]
                with (
                    self.assertRaisesRegex(ValidationError, "fiscal account"),
                    self.cr.savepoint(),
                ):
                    method.payment_account_id = invalid_account

    def test_method_account_cannot_belong_to_another_company(self):
        other_company = self.setup_other_company()["company"]
        account = self.env["account.account"].create(
            {
                "name": "Other company fiscal account",
                "code": "991504",
                "account_type": "asset_current",
                "reconcile": True,
                "company_ids": [Command.set(other_company.ids)],
            }
        )
        method = self.inbound_withholding_journal.inbound_payment_method_line_ids[:1]
        with self.assertRaises(ValidationError), self.cr.savepoint():
            method.payment_account_id = account

    def test_fiscal_account_cannot_be_the_journal_default_account(self):
        with (
            self.assertRaisesRegex(ValidationError, "fiscal account"),
            self.cr.savepoint(),
        ):
            self.inbound_withholding_journal.default_account_id = self.tax_receivable

    def test_fiscal_account_currency_must_match_the_payment(self):
        currency = self.env.ref("base.EUR")
        if currency == self.env.company.currency_id:
            currency = self.env.ref("base.USD")
        self.tax_receivable.currency_id = currency
        with (
            self.assertRaisesRegex(ValidationError, "currency must match"),
            self.cr.savepoint(),
        ):
            self._create_payment()

    def test_missing_account_blocks_direct_and_wizard_payments(self):
        methods = self.inbound_withholding_journal.inbound_payment_method_line_ids
        methods.payment_account_id = False
        invoice = self._create_move(self.product_a, 2000, move_type="out_invoice")
        wizard = self._create_payment_wizard(invoice)
        wizard.journal_id = self.inbound_withholding_journal
        with (
            self.assertRaisesRegex(ValidationError, "fiscal account"),
            self.cr.savepoint(),
        ):
            self._create_payment()
        with (
            self.assertRaisesRegex(ValidationError, "fiscal account"),
            self.cr.savepoint(),
        ):
            wizard._create_payments()
        self.assertFalse(invoice.matched_payment_ids)

    def test_payment_cannot_override_the_configured_account(self):
        bank_account = self.company_data["default_journal_bank"].default_account_id
        payment = self._create_payment(outstanding_account_id=bank_account.id)
        self.assertEqual(payment.outstanding_account_id, self.tax_receivable)
        with (
            self.assertRaisesRegex(ValidationError, "must use the fiscal account"),
            self.cr.savepoint(),
        ):
            payment.outstanding_account_id = bank_account

    def test_forced_move_uses_the_fiscal_account(self):
        payment = (
            self.env["account.payment"]
            .with_context(force_payment_move=True)
            .create(
                {
                    "journal_id": self.inbound_withholding_journal.id,
                    "partner_id": self.partner_a.id,
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "amount": 30,
                }
            )
        )
        self.assertEqual(payment.outstanding_account_id, self.tax_receivable)

    def test_inactive_fiscal_account_blocks_payment(self):
        self.tax_receivable.active = False
        with (
            self.assertRaisesRegex(ValidationError, "fiscal account"),
            self.cr.savepoint(),
        ):
            self._create_payment()

    def test_custom_entry_cannot_use_a_bank_account_for_withholding(self):
        receivable = self.partner_a.property_account_receivable_id
        with (
            self.assertRaisesRegex(ValidationError, "journal entry must use"),
            self.cr.savepoint(),
        ):
            self._create_payment(
                line_ids=[
                    Command.create(
                        {
                            "account_id": self.company_data[
                                "default_journal_bank"
                            ].default_account_id.id,
                            "partner_id": self.partner_a.id,
                            "debit": 30,
                        }
                    ),
                    Command.create(
                        {
                            "account_id": receivable.id,
                            "partner_id": self.partner_a.id,
                            "credit": 30,
                        }
                    ),
                ]
            )

    def test_configuration_is_checked_again_before_posting(self):
        payment = self._create_payment()
        payment.payment_method_line_id.payment_account_id = False
        with (
            self.assertRaisesRegex(ValidationError, "fiscal account"),
            self.cr.savepoint(),
        ):
            payment.action_post()
        self.assertFalse(payment.move_id)

    def test_valid_configuration_and_ordinary_journals_remain_editable(self):
        self.inbound_withholding_journal.withholding_tax_rate = 0.02
        method = self.inbound_withholding_journal.inbound_payment_method_line_ids[:1]
        replacement = self.tax_receivable.copy({"code": "991503"})
        method.payment_account_id = replacement
        payment = self._create_payment()
        payment.action_post()
        self.assertEqual(payment.outstanding_account_id, replacement)

        journal = self.company_data["default_journal_bank"]
        journal.withholding_tax_rate = 0
        journal.inbound_payment_method_line_ids.payment_account_id = (
            journal.default_account_id
        )
        ordinary_payment = self._create_payment(journal=journal)
        ordinary_payment.action_post()
        self.assertEqual(ordinary_payment.move_id.state, "posted")
        journal.withholding_tax_rate = 0.25
        ordinary_payment.payment_method_line_id.payment_account_id = False

    def test_used_journal_changes_apply_to_future_payments_only(self):
        first = self._create_payment()
        first.action_post()
        before = first.move_id.line_ids.read(
            ["account_id", "debit", "credit", "amount_currency"], load=None
        )
        first.journal_id.withholding_tax_rate = 0.02
        replacement = self.tax_receivable.copy({"code": "991505"})
        first.payment_method_line_id.payment_account_id = replacement

        second = self._create_payment(amount=40)
        second.action_post()

        self.assertEqual(
            first.move_id.line_ids.read(
                ["account_id", "debit", "credit", "amount_currency"], load=None
            ),
            before,
        )
        self.assertEqual(second.outstanding_account_id, replacement)
        fiscal_line = second.move_id.line_ids.filtered(
            lambda line: line.account_id == replacement
        )
        self.assertEqual(len(fiscal_line), 1)
        self.assertEqual(fiscal_line.debit, 40)

        # earlier entries can be reposted with the account they were created with
        first.move_id.button_draft()
        first.move_id.action_post()
        self.assertEqual(first.move_id.state, "posted")
        first.action_draft()
        first.action_post()
        self.assertEqual(first.state, "in_process")
        self.assertEqual(first.move_id.state, "posted")
        self.assertEqual(first.outstanding_account_id, self.tax_receivable)
        self.assertEqual(
            first.move_id.line_ids.read(
                ["account_id", "debit", "credit", "amount_currency"], load=None
            ),
            before,
        )
