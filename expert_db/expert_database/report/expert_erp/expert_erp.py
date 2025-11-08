# Copyright (c) 2025, apm and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = build_column()

	# Build DB filters from UI filters (support: name_expert partial, course dropdown)
	filters_for_db = []
	if filters:
		# course dropdown -> map to boolean fields
		course = filters.get("course")
		if course and course != "All":
			if course == "IE (M.Eng)":
				filters_for_db.append(
					["m_ie", "=", 1]
				)
			elif course == "IM (M.Eng)":
				filters_for_db.append(
					["m_im", "=", 1]
				)
			elif course == "IE (Ph.D.)":
				filters_for_db.append(
					["p_ie", "=", 1]
				)
			elif course == "LE (M.Eng)":
				filters_for_db.append(
					["m_le", "=", 1]
				)

	# Fetch Candidate Profile data using mapped filters
	profiles = frappe.get_all(
		"Candidate Profile",
		fields=[
			"name",
			"name_expert",
			"affiliation",
			"p_ie",
			"m_im",
			"m_ie",
			"m_le",
			"expert_examiner",
			"expert_advisor",
			"announcement_no",
			"announcement_date",
		],
		filters=filters_for_db or None,
	)

	# Fetch expert_specialization for each profile and determine courses
	data = []
	for profile in profiles:
		# Determine courses based on field values
		courses = []
		if profile.get("p_ie") == 1:
			courses.append("IE (Ph.D.)")
		if profile.get("m_im") == 1:
			courses.append("IM (M.Eng)")
		if profile.get("m_ie") == 1:
			courses.append("IE (M.Eng)")
		if profile.get("m_le") == 1:
			courses.append("LE (M.Eng)")
		profile["courses"] = ", ".join(courses)

		# Determine permissions based on expert_examiner and expert_advisor
		profile["can_exam"] = (
			1
			if profile.get("expert_examiner") == 1
			else 0
		)
		profile["can_advise"] = (
			1
			if profile.get("expert_advisor") == 1
			else 0
		)

		# Fetch expert_specialization
		specializations = frappe.get_all(
			"Expert Specialization",
			filters={"parent": profile["name"]},
			fields=["experts_specialization"],
		)
		profile["expert_specialization"] = (
			", ".join(
				[
					spec["experts_specialization"]
					for spec in specializations
				]
			)
		)
		data.append(profile)

	# print(data)
	return columns, data


def build_column():
	column = [
		{
			"fieldname": "name_expert",
			"label": "ชื่อ-สกุล",
			"fieldtype": "Data",
			"width": 350,
		},
		{
			"fieldname": "affiliation",
			"label": "สังกัด",
			"fieldtype": "Data",
			"width": 300,
		},
		{
			"fieldname": "announcement_no",
			"label": "เลขที่คำสั่ง",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"fieldname": "courses",
			"label": "หลักสูตรที่สามารถสอบได้",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "can_exam",
			"label": "สิทธิ์สอบ",
			"fieldtype": "Check",
			"width": 150,
		},
		{
			"fieldname": "can_advise",
			"label": "สิทธิ์เป็นที่ปรึกษา",
			"fieldtype": "Check",
			"width": 150,
		},
		{
			"fieldname": "expert_specialization",
			"label": "ความเชี่ยวชาญ",
			"fieldtype": "Data",
			"width": 250,
		},
		{
			"fieldname": "announcement_date",
			"label": "แต่งตั้งตามข้อบังคับ",
			"fieldtype": "Data",
			"width": 350,
		},
	]
	return column
