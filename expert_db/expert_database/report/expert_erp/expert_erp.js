// Copyright (c) 2025, apm and contributors
// For license information, please see license.txt

frappe.query_reports["expert erp"] = {
	"filters": [
		{
			"fieldname": "course",
			"label": __("Course"),
			"fieldtype": "Select",
			"options": ["All", "IE (M.Eng)", "IM (M.Eng)", "IE (Ph.D.)", "LE (M.Eng)"],
			"default": "All",
		},
	]
};
