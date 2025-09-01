import frappe
from frappe.model.document import Document
from frappe import utils
from num2words import num2words


class SalesOrderDup(Document):
	def before_save(self):
		# Customer Check
		if self.customer:
			customer = frappe.db.get_value("Customer",self.customer,"customer_name")
			if not customer:
				customer = frappe.new_doc("Customer")
				customer.customer_name = self.customer
				customer.customer_type = "Company"
				customer.insert(ignore_permissions=True)
				customer.save()
				frappe.msgprint(f"Customer {customer.customer_name} is created")
		else:
			frappe.throw("Enter a Customer Name")

		# Default Values
		self.title = self.customer
		self.customer_name = self.customer
		self.company = "Kanish Vijay Tech"
		self.currency = "INR"
		self.price_list = "Standard Selling"

		if not self.date:
			self.date = utils.nowdate()

		# Delivery Date Checks
		if not self.delivery_date:
			frappe.throw("Delivery Date is mandatory")

		if self.delivery_date < self.date:
			frappe.throw("Delivery Date cannot be before Order Date")

		# Items Checks
		if not self.items:
			frappe.throw("At least one item is required in the Sales Order")
		
		total_qty = 0
		total_amount = 0
		for item in self.items:
			if item.item_code:
				itm = frappe.db.get_value("Item", item.item_code, "item_name")
				if not itm:
					new_itm = frappe.new_doc("Item")
					new_itm.item_code = item.item_code
					new_itm.item_name = item.item_code
					new_itm.item_group = "Products"
					new_itm.stock_uom = "Nos"
					new_itm.is_stock_item = 1
					new_itm.save()
					frappe.msgprint(f"{itm.item_code} item is created")
			else:
				frappe.throw("Item Code is mandatory for each item")

			item.delivery_date = self.delivery_date
			if not item.quantity:
				item.quantity = '1'

			# Item Price
			if not item.rate:
				itm = frappe.db.sql('''select item_code, price_list_rate from `tabItem Price` where item_code = %s''',item.item_code, as_dict=True)
				if itm :
					item.rate = itm[0].price_list_rate
				else :
					frappe.throw("This is a new item for sales order so please enter the rate of the item")
			else :
				itm = frappe.db.sql('''select item_code, price_list_rate from `tabItem Price` where item_code = %s''',item.item_code, as_dict=True)
				if itm :
					item.rate = itm[0].price_list_rate
					frappe.msgprint("Entered rate is replaced by enrty rate")
				else :
					item_price = frappe.new_doc("Item Price")
					item_price.item_code = item.item_code
					item_price.item_name = item.item_name
					item_price.description = item.item_name
					item_price.uom = "Nos"
					item_price.packing_unit = 0
					item_price.price_list = "Standard Selling"
					item_price.selling = 1
					item_price.currency = "INR"
					item_price.price_list_rate = item.rate
					item_price.valid_from = utils.getdate(utils.nowdate()).strftime("%d-%m-%Y")
					item_price.lead_time_days = 0
					item_price.save()
					frappe.msgprint("The item rate is added to Item Price")

			item.amount = int(item.quantity) * int(item.rate)
			total_qty += int(item.quantity)
			total_amount += int(item.amount)

		self.total_quantity = total_qty
		self.total = total_amount

		# Taxes
		if self.sales_taxes_and_charges :
			total_tax = 0
			for tax in self.sales_taxes_and_charges:
				if not tax.type:
					frappe.throw("Tax Type is mandatory for each tax entry")

				if not tax.account_head :
					frappe.throw("Account head is mandatory")
				exist = frappe.db.get_value("Account", tax.account_head, "account_name")
				if not exist:
					frappe.throw(f"Account {tax.account_head} does not exist")

				if not tax.tax_rate or tax.tax_rate <= '0':
					frappe.throw(f"Tax Rate for {tax.account_head} must be greater than zero")

				tax.description = tax.account_head
				tax.amount = float(tax.tax_rate) * float(self.total) / 100.00
				tax.total = tax.amount + float(self.total)
				total_tax += tax.amount

			self.total_taxes_and_charges = total_tax
			self.grand_total = self.total + self.total_taxes_and_charges
			self.in_words = "INR " + num2words(self.grand_total, lang='en_IN').title() + " Only."

			self.taxes_and_charges_calculation = f"On Net Total {self.total} with {len(self.sales_taxes_and_charges)} taxes"
			for tax in self.sales_taxes_and_charges:
				self.taxes_and_charges_calculation += f"<br>{tax.account_head} - {tax.tax_rate}% = {tax.amount}"
			self.taxes_and_charges_calculation += f"<br>Total Tax = {self.total_taxes_and_charges}<br>Grand Total = {self.grand_total}<br>In Words = {self.in_words}"

		# Sales Team
		if self.sales_team:
			percent = 0
			for team_member in self.sales_team:
				sales_person = frappe.db.get_value("Sales Person", team_member.sales_person, "sales_person_name")
				if not sales_person:
					frappe.throw(f"Sales Person {team_member.sales_person} does not exist")

				if not team_member.contribution:
					frappe.throw(f"Contribution for {team_member.sales_person} must be specified")

				percent += int(team_member.contribution)

			if percent != 100:
				frappe.throw("Total contribution percentage of Sales Team must be 100%")

			for person in self.sales_team:
				person.contribution_to_net_total = int(self.total) * int(person.contribution) / 100

		if self.rounding_adjustment is None:
			self.rounding_adjustment = 0

		if self.rounded_total is None:
			self.rounded_total = 0

		if not self.payment_schedule : 
			self.append("payment_schedule",{
				"due_date" : self.delivery_date,
				"invoice_portion" : 100,
				"payment_amount" : self.grand_total
			})

		self.apply_additional_discount_on = "Grand Total"
		self.additional_discount_percentage = 0
		self.additional_discount_amount = 0
		self._delivered = 0
		self._amount_billed = 0
		self._picked = 0
		self.amount_eligible_for_commission = self.total
		self.commission_rate = 0
		self.total_commission = 0
		self.loyalty_points = 0
		self.loyalty_amount = 0
		self.print_language = "en"
		self.status = "Draft"
	
	def on_submit(self) :
		frappe.db.set_value("Sales Order Dup", self.name, "status", "To Bill")
		frappe.db.commit()