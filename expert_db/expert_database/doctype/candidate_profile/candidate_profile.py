# Copyright (c) 2025, apm and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document


class CandidateProfile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from expert_db.expert_database.doctype.expert_specialization.expert_specialization import (
			ExpertSpecialization,
		)

		affiliation: DF.Data | None
		announcement_attachment: DF.Attach | None
		announcement_date: DF.Date | None
		announcement_no: DF.Data | None
		expert_advisor: DF.Check
		expert_degree: DF.Attach | None
		expert_examiner: DF.Check
		expert_specialization: DF.Table[ExpertSpecialization]
		m_ie: DF.Check
		m_im: DF.Check
		m_le: DF.Check
		name_expert: DF.Data | None
		p_ie: DF.Check
	# end: auto-generated types
	pass

	# def autoname(self):
	# 	if self.name_expert:
	# 		self.name = self.name_expert
	# 	else:
	# 		frappe.throw("กรุณาระบุ ชื่อ-สกุล")
