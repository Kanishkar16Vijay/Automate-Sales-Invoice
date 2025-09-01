import frappe
from frappe.model.document import Document
from frappe import utils

def create_sales_invoice() :
    # Get the Sales Order deltails
    sales_orders = frappe.get_all(
        "Sales Order Dup",
        filters={
            "status": "To Bill"
        },
        fields=["name", "status", "customer"]
    )

    if sales_orders :
        sales_order = {}
        for so in sales_orders :
            if so.customer in sales_order :
                sales_order[so.customer].append(so)
            else :
                sales_order[so.customer] = [so]

        for nme in sales_order:
            pdf = []
            for so in sales_order[nme] :
                sales_doc = frappe.get_doc("Sales Order Dup", so.name)

                sales_invoice = frappe.new_doc("Sales Invoice")
                sales_invoice.title = sales_doc.title
                sales_invoice.customer = sales_doc.customer
                sales_invoice.customer_name = sales_doc.customer_name
                sales_invoice.company = sales_doc.company
                sales_invoice.posting_date = utils.getdate(utils.nowdate())
                sales_invoice.posting_time = utils.now_datetime().strftime("%H-%M-%S")
                # sales_invoice.due_date = sales_invoice.posting_date

                sales_invoice.currency = "INR"
                sales_invoice.selling_price_list = "Standard Selling"

                for itm in sales_doc.items :
                    sales_invoice.append("items",{
                        "item_code" : itm.item_code,
                        "qty" : itm.quantity,
                        "rate" : itm.rate,
                        "amount" : itm.amount
                    })
                sales_invoice.total_qty = sales_doc.total_quantity
                sales_invoice.total = sales_doc.total

                if sales_doc.sales_taxes_and_charges :
                    for tx in sales_doc.sales_taxes_and_charges :
                        sales_invoice.append("taxes", {
                            "charge_type" : tx.type,
                            "account_head" : tx.account_head,
                            "rate" : tx.tax_rate,
                            "description" : tx.account_head,
                            "tax_amount" : tx.amount,
                            "total" : tx.total
                        })
                    sales_invoice.total_taxes_and_charges = sales_doc.total_taxes_and_charges

                sales_invoice.grand_total = sales_doc.grand_total
                sales_invoice.rounding_adjustment = sales_doc.rounding_adjustment
                sales_invoice.rounded_total = sales_doc.rounded_total
                sales_invoice.in_words = sales_doc.in_words
                sales_invoice.total_avance = 0
                sales_invoice.outstanding_amount = 0

                sales_invoice.apply_discount_on = "Grand Total"
                sales_invoice.additional_discount_percentage = 0
                sales_invoice.discount_amount = 0

                for ps in sales_doc.payment_schedule :
                    sales_invoice.append("payment_schedule", {
                        "due_date" : ps.due_date,
                        "invoice_portion" : ps.invoice_portion,
                        "payment_amount" : ps.payment_amount
                    })

                sales_invoice.debit_to = "Debtors - KVT"
                sales_invoice.is_opening = "No"

                sales_invoice.amount_eligible_for_commission = sales_doc.amount_eligible_for_commission
                sales_invoice.commission_rate = sales_doc.commission_rate
                sales_invoice.total_commission = sales_doc.total_commission

                for team in sales_doc.sales_team :
                    sales_invoice.append("sales_team", {
                        "sales_person" : team.sales_person,
                        "allocated_percentage" : team.contribution,
                        "allocated_amount" : team.contribution_to_net_total,
                        "commission_rate" : team.commission_rate,
                        "incentives" : team.incentives
                    })

                sales_invoice.loyalty_points = sales_doc.loyalty_points
                sales_invoice.loyalty_amount = sales_doc.loyalty_amount

                sales_invoice.language = 'en'
                sales_invoice.status = "Paid"
                sales_invoice.remarks = "No Remarks"

                sales_invoice.insert(ignore_permissions=True)
                sales_invoice.submit()

                frappe.db.set_value("Sales Order Dup", so.name, "status", "Completed")
                frappe.db.commit()

                si_pdf = frappe.attach_print(
                    doctype = "Sales Invoice",
                    name = sales_invoice.name,
                    print_format = "Sales Invoice Print",
                    doc = sales_invoice
                )
                pdf.append(si_pdf)

            customer = frappe.get_doc("Customer", nme)
            frappe.sendmail(
                recipients = [customer.email_id],
                subject = "Sales Invoice",
                message = f"<p>Dear {sales_invoice.customer_name},</p><p>Please find attached the following Sales Invoices:</p>",
                attachments = pdf,
                now = True
            )