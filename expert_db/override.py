import io
import json
from typing import Literal

import frappe
import pdfkit
from frappe import _
from frappe.utils import scrub_urls
from frappe.utils.pdf import (
	PDF_CONTENT_ERRORS,
	cleanup,
	get_file_data_from_writer,
	prepare_options,
)
from frappe.utils.response import json_handler
from pypdf import PdfReader, PdfWriter


def override_as_json():
	"""Replace frappe.as_json globally with custom version"""
	print("[Copa ERP] Overriding frappe.as_json with indent=4, ensure_ascii=False")

	def custom_as_json(
		obj: dict | list,
		indent=4,
		separators=None,
		ensure_ascii=False,
	) -> str:
		if separators is None:
			separators = (",", ": ")

		try:
			return json.dumps(
				obj,
				indent=indent,
				sort_keys=True,
				default=json_handler,
				separators=separators,
				ensure_ascii=ensure_ascii,
			)
		except TypeError:
			# กรณี key ไม่ใช่ string ทั้งหมด
			sorted_obj = dict(sorted(obj.items(), key=lambda kv: str(kv[0])))  # pyright: ignore[reportAttributeAccessIssue]
			return json.dumps(
				sorted_obj,
				indent=indent,
				default=json_handler,
				separators=separators,
				ensure_ascii=ensure_ascii,
			)

	frappe.as_json = custom_as_json


def override_type_exporter():
	"""Replace frappe.model.utils.type_generator.TypeExporter with custom class"""
	print("[Copa ERP] Overriding frappe.model.utils.type_generator.TypeExporter")

	import frappe.types.exporter
	from frappe.types.exporter import (
		end_block,
		field_template,
		start_block,
	)

	# --- นี่คือคลาสใหม่ที่คุณแก้ไว้ ---
	"""Creates/Updates types in python controller when schema is updated.

    Design goal:
        - Developer should be able to see schema in same file.
        - Type checkers should assist with field names and basic validation in same file.
        - `get_doc` outside of same file without explicit annotation is out of scope.
        - Customizations like change of fieldtype and addition of fields are out of scope.
    """

	import ast
	import inspect
	import json
	import re
	import textwrap
	import tokenize
	from keyword import iskeyword
	from pathlib import Path

	import frappe

	type_code_block_template = """{start_block}
{indent}# This code is auto-generated. Do not modify anything in this block.

{indent}from typing import TYPE_CHECKING, Literal

{indent}if TYPE_CHECKING:
{imports}
{fields}
{indent}{end_block}"""

	non_nullable_types = {
		"Check",
		"Currency",
		"Float",
		"Int",
		"Percent",
		"Rating",
		"Select",
		"Table",
		"Table MultiSelect",
	}

	class TypeExporter:
		def __init__(self, doc):
			from frappe.model.base_document import (
				get_controller,
			)

			self.doc = doc
			self.doctype = doc.name
			self.field_types = {}

			self.imports = set()
			self.indent = "\t"
			self.controller_path = Path(inspect.getfile(get_controller(self.doctype)))

		def export_types(self):
			self._guess_indentation()
			new_code = self._generate_code()
			self._replace_or_add_code(new_code)

		def _replace_or_add_code(self, new_code: str):
			despaced_name = self.doctype.replace(" ", "")

			class_definition = f"class {despaced_name}("  # )
			code = self.controller_path.read_text()

			first_line, *_, last_line = new_code.splitlines()
			if first_line in code and last_line in code:  # Replace
				existing_block_start = code.find(first_line)
				existing_block_end = code.find(last_line) + len(last_line)

				code = code[:existing_block_start] + new_code + code[existing_block_end:]
			elif class_definition in code:  # Add just after class definition
				# Regex by default will only match till line ends, span end is when we need to stop
				if class_def := re.search(rf"class {despaced_name}\(.*", code):  # )
					class_definition_end = class_def.span()[1] + 1
					code = code[:class_definition_end] + new_code + "\n" + code[class_definition_end:]

			if self._validate_code(code):
				self.controller_path.write_text(code)

		def _generate_code(self):
			for field in self.doc.fields:
				if iskeyword(field.fieldname):
					continue
				if field.is_virtual and not field.options:
					continue
				if python_type := self._map_fieldtype(field):
					self.field_types[field.fieldname] = python_type

			if self.doc.istable:
				for parent_field in ("parent", "parentfield", "parenttype"):
					self.field_types[parent_field] = "str"

			if self.doc.autoname == "autoincrement":
				self.field_types["name"] = "int | None"

			fields_code_block = self._create_fields_code_block()
			imports = self._create_imports_block()

			# ใช้ indent 2 ระดับสำหรับ imports และ fields (ภายใน if TYPE_CHECKING:)
			double_indent = self.indent * 2

			# ไม่ต้อง indent ทั้งหมดอีกครั้ง เพราะ template มี {indent} อยู่แล้ว
			generated_code = type_code_block_template.format(
				start_block=start_block,
				end_block=end_block,
				indent=self.indent,
				fields=textwrap.indent(fields_code_block, double_indent),
				imports=textwrap.indent(imports, double_indent),
			)

			return generated_code

		def _create_fields_code_block(self):
			return "\n".join(
				sorted(
					[
						field_template.format(field=field, type=typehint)
						for field, typehint in self.field_types.items()
					]
				)
			)

		def _create_imports_block(self) -> str:
			return "\n".join(sorted(self.imports))

		def _get_doctype_imports(self, doctype):
			from frappe.model.base_document import (
				get_controller,
			)

			doctype_module = get_controller(doctype)

			filepath = doctype_module.__module__
			class_name = doctype_module.__name__

			return f"from {filepath} import {class_name}", class_name

		def _map_fieldtype(self, field) -> str | None:
			fieldtype = field.fieldtype.replace(" ", "")
			field_definition = ""

			if fieldtype == "Select":
				field_definition += "Literal"
			else:
				# Map to basic Python types
				type_mapping = {
					"Data": "str",
					"Text": "str",
					"SmallText": "str",
					"LongText": "str",
					"Code": "str",
					"TextEditor": "str",
					"HTMLEditor": "str",
					"MarkdownEditor": "str",
					"Password": "str",
					"Color": "str",
					"Barcode": "str",
					"Link": "str",
					"DynamicLink": "str",
					"Autocomplete": "str",
					"ReadOnly": "str",
					"Attach": "str",
					"AttachImage": "str",
					"Check": "int",
					"Int": "int",
					"Currency": "float",
					"Float": "float",
					"Percent": "float",
					"Rating": "float",
					"Date": "str",
					"Datetime": "str",
					"Time": "str",
					"Duration": "int",
					"JSON": "str",
					"Phone": "str",
					"Table": "list",
					"TableMultiSelect": "list",
				}

				if fieldtype in type_mapping:
					field_definition += type_mapping[fieldtype]
				else:
					return

			if parameter_definition := self._generic_parameters(field):
				field_definition += parameter_definition

			if self._is_nullable(field):
				field_definition += " | None"

			return field_definition

		def _is_nullable(self, field) -> bool:
			"""If value can be `None`"""

			if field.fieldtype in non_nullable_types:
				return False

			return not bool(field.reqd)

		def _generic_parameters(self, field) -> str | None:
			"""If field is container type then return element type."""
			if field.fieldtype in ("Table", "Table MultiSelect"):
				doctype = field.options
				if not doctype:
					return

				import_statment, cls_name = self._get_doctype_imports(doctype)
				self.imports.add(import_statment)
				return f"[{cls_name}]"

			elif field.fieldtype == "Select":
				if not field.options:
					# Could be dynamic
					return "[None]"
				options = [o.strip() for o in field.options.split("\n")]
				return json.dumps(options, ensure_ascii=False)

		@staticmethod
		def _validate_code(code) -> bool:
			"""Make sure whatever code Frappe adds dynamically is valid python."""
			try:
				ast.parse(code)
				return True
			except Exception:
				frappe.msgprint(frappe._("Failed to export python type hints"), alert=True)
				return False

		def _guess_indentation(
			self,
		) -> None:
			from token import INDENT

			with self.controller_path.open() as f:
				for token in tokenize.generate_tokens(f.readline):
					if token.type == INDENT:
						if "\t" in token.string:
							self.indent = "\t"
						else:
							# TODO: any other custom indent not supported
							# Ideally this should be longest common substring but I don't l33tc0de.
							# If someone really needs it, add support via hooks.
							self.indent = " " * 4
						break

	# --- แทนที่ของเดิมใน frappe namespace ---
	frappe.types.exporter.TypeExporter = TypeExporter


def override_unicode_writer():
	"""Replace frappe.utils.csvutils.UnicodeWriter with utf-8-sig version"""
	print("[Copa ERP] Overriding frappe.utils.csvutils.UnicodeWriter")

	import csv
	from io import StringIO

	import frappe.utils.csvutils

	class UnicodeWriter:
		# change encoding to utf-8-sig from utf-8
		def __init__(self, encoding="utf-8-sig", quoting: Literal[2] = csv.QUOTE_NONNUMERIC):
			self.encoding = encoding
			self.queue = StringIO()
			self.writer = csv.writer(self.queue, quoting=quoting)

		def writerow(self, row):
			self.writer.writerow(row)

		def getvalue(self):
			return self.queue.getvalue()

	# ✅ แทนของเดิมใน frappe namespace
	frappe.utils.csvutils.UnicodeWriter = UnicodeWriter


def override_get_pdf():
	"""Replace frappe.utils.pdf.get_pdf with custom version"""
	print("[Copa ERP] Overriding frappe.utils.pdf.get_pdf")

	import frappe.utils.pdf

	def get_pdf(html, options=None, output: PdfWriter | None = None):
		# --- [NEW CODE BLOCK: START] ---
		# Inject Thai Font CSS into the HTML <head>
		try:
			# 1. Get the full URL of the running Frappe site (e.g., http://localhost:8000)
			base_url = frappe.utils.get_url()  # pyright: ignore[reportAttributeAccessIssue]

			# 2. Define your app name and font path
			app_name = "copa_erp"  # <-- ชื่อ App ของคุณ
			font_path = "fonts/THSarabunNew.ttf"
			font_url = f"{base_url}/assets/{app_name}/{font_path}"

			# 3. Define the CSS style block
			# We use !important to force override any existing styles in the HTML
			font_style = f"""
            <style>
                @font-face {{
                    font-family: 'SarabunFrappe';
                    src: url('{font_url}') format('truetype');
                    font-weight: normal;
                    font-style: normal;
                }}

                /* * บังคับใช้ Font นี้กับทุก element ที่เป็นไปได้
                * นี่คือส่วนสำคัญเพื่อให้ชนะ CSS เดิมของ Print Format
                */
                body, div, p, span, td, th, h1, h2, h3, h4, h5, h6, li, a {{
                    font-family: 'SarabunFrappe', sans-serif !important;
                }}
            </style>
            """

			# 4. Inject the style block just before the closing </head> tag
			# (ใช้ count=1 เพื่อแทนที่เฉพาะจุดแรกที่เจอ)
			if "</head>" in html:
				html = html.replace("</head>", f"{font_style}</head>", 1)
			else:
				# Fallback กรณี HTML ไม่มี <head> (ไม่น่าเกิด แต่กันไว้)
				html = f"<html><head>{font_style}</head><body>{html}</body></html>"

		except Exception as e:
			# หากล้มเหลว (เช่น รันจาก background script ที่ไม่มี site context)
			# ให้ log error ไว้ แต่ยังคงพยายามสร้าง PDF ต่อไป (อาจจะอ่านไม่ออก)
			frappe.log_error(title="PDF Thai Font Injection Failed", message=str(e))  # pyright: ignore[reportAttributeAccessIssue]
		# --- [NEW CODE BLOCK: END] ---

		# --- [Original get_pdf code] ---
		html = scrub_urls(html)
		html, options = prepare_options(html, options)

		# บรรทัดนี้ถูกต้องแล้วครับ
		# 'disable-local-file-access' บล็อก 'file://' แต่ *อนุญาต* 'http://'
		options.update({"disable-smart-shrinking": ""})

		filedata: bytes
		reader: PdfReader
		password: str | None = None

		try:
			# Set filename property to false, so no file is actually created
			result = pdfkit.from_string(html, options=options or {}, verbose=True)

			# Ensure filedata is bytes before creating PdfReader
			if not isinstance(result, bytes):
				frappe.throw(_("PDF generation failed - no data returned"))

			# Type narrowing: result is now guaranteed to be bytes
			filedata = result  # pyright: ignore[reportAssignmentType]

			# create in-memory binary streams from filedata and create a PdfReader object
			reader = PdfReader(io.BytesIO(filedata))

		except OSError as e:
			if any([error in str(e) for error in PDF_CONTENT_ERRORS]):
				# filedata and reader might not be defined if exception occurred early
				if "filedata" not in locals() or not isinstance(filedata, bytes):  # pyright: ignore[reportPossiblyUnboundVariable]
					print(html, options)
					frappe.throw(_("PDF generation failed because of broken image links"))

				# allow pdfs with missing images if file got created
				if output and "reader" in locals():
					output.append_pages_from_reader(reader=reader)  # pyright: ignore[reportUnboundVariable]
			else:
				raise
		finally:
			cleanup(options)

		# At this point, if we didn't throw an error, reader must be defined
		# Add assertion to help type checker
		if "reader" not in locals():
			frappe.throw(_("PDF generation failed - reader not created"))

		# Extract password before using it
		if "password" in options:
			password = options["password"]

		if output:
			output.append_pages_from_reader(reader=reader)  # pyright: ignore[reportPossiblyUnboundVariable]
			return output

		writer = PdfWriter()
		writer.append_pages_from_reader(reader)  # pyright: ignore[reportPossiblyUnboundVariable]

		if password:
			writer.encrypt(password)

		filedata = get_file_data_from_writer(writer)

		return filedata

	frappe.utils.pdf.get_pdf = get_pdf


def override():
	"""Apply all custom overrides to frappe functions and classes.

	This function overrides:
	- frappe.as_json to use custom formatting with indent=4 and ensure_ascii=False
	- frappe.model.utils.type_generator.TypeExporter for improved type generation
	- frappe.utils.csvutils.UnicodeWriter to use utf-8-sig encoding
	- frappe.utils.pdf.get_pdf to inject Thai font into generated PDFs
	"""
	override_as_json()
	override_type_exporter()
	override_unicode_writer()
	override_get_pdf()
	pass
