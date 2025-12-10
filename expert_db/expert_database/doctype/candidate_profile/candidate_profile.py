# Copyright (c) 2025, apm and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class CandidateProfile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING, Literal

	if TYPE_CHECKING:
		from expert_db.expert_database.doctype.expert_specialization.expert_specialization import (
			ExpertSpecialization,
		)
		affiliation: str | None
		announcement_attachment: str | None
		announcement_date: str | None
		announcement_no: str | None
		expert_advisor: int
		expert_degree: str | None
		expert_examiner: int
		expert_specialization: list[ExpertSpecialization]
		m_ie: int
		m_im: int
		m_le: int
		name_expert: str | None
		p_ie: int
	# end: auto-generated types

	pass

	# def autoname(self):
	# 	if self.name_expert:
	# 		self.name = self.name_expert
	# 	else:
	# 		frappe.throw("กรุณาระบุ ชื่อ-สกุล")
