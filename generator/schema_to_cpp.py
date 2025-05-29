import os, shutil, xmlschema
from datetime import datetime
from enum import Enum
from typing import Callable

SCHEMA_FOLDER = 'schemas'
OUTPUT_FOLDER = 'generated'
NUMBER_PREFIX = 'v'

def get_all_schemas(schema: xmlschema.XMLSchema) -> set[xmlschema.XMLSchema]:
	all_namespaces: set[xmlschema.XMLSchema] = set()
	collected_namespaces: set[xmlschema.XMLSchema] = set()
	remaining_namespaces: set[xmlschema.XMLSchema] = set()
	all_namespaces.add(schema)
	remaining_namespaces.add(schema)
	while remaining_namespaces:
		iter_schema: xmlschema.XMLSchema = remaining_namespaces.pop()
		collected_namespaces.add(iter_schema)

		imported = [iter_schema.get_schema(namespace) for namespace in iter_schema.imported_namespaces]
		all_namespaces.update(imported)
		remaining_namespaces.update(imported)
		remaining_namespaces = remaining_namespaces - collected_namespaces
	return all_namespaces

def get_uniform_namespace(namespace: str) -> str:
	# Currently only supports http(s) and urn schemas
	# Removes the 'urn:' resp. everything including the host name from the namespace
	clean_namespace: str = namespace[4:] if namespace.startswith('urn:') else ':'.join(namespace.split('/')[3:])
	namespace_parts: list[str] = clean_namespace.split(':')

	converters = [
		lambda part: NUMBER_PREFIX + part if part[0].isdigit() else part,
		lambda part: ''.join(char for char in part if char.isalnum())
	]
	for converter in converters:
		namespace_parts = [converter(part) for part in namespace_parts]
	return ':'.join(namespace_parts)

FileType = Enum('FileType', [('HEADER', '.hpp'), ('SOURCE', '.cpp')])
def get_file_path(xsd_type: xmlschema.validators.XsdType, type: FileType):
	namespace: str = get_uniform_namespace(xsd_type.target_namespace)
	dir: str = namespace.replace(':', '/')
	file: str = xsd_type.local_name
	return '/'.join([OUTPUT_FOLDER, dir, file + type.value])

def sort_and_concat_includes(includes: set[str]) -> str:
	system_includes: list[str] = sorted([f'#include {incl}' for incl in includes if incl.startswith('<')])
	lib_includes: list[str] = sorted([f'#include {incl}' for incl in includes if incl.startswith('"')])
	return '\n'.join(system_includes) + ('\n\n' if len(system_includes) > 0 and len(lib_includes) > 0 else '') + '\n'.join(lib_includes) + ('\n\n' if len(includes) > 0 else '')

def create_header_contents(complex_type: xmlschema.validators.XsdComplexType) -> str:
	header: str = ''
	header += '// This file was generated on ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '.\n'
	header += '// DO NOT EDIT MANUALLY!\n\n'
	header += '#pragma once\n\n'

	cpp_namespace: str = get_uniform_namespace(complex_type.target_namespace).replace(':', '::')
	namespace: str = f'namespace {cpp_namespace} {{\n\n'
	footer = f'\n}} // namespace {cpp_namespace}\n'

	includes: set[str] = set(['<memory>'])

	the_class: str = f'class {complex_type.local_name} '
	if complex_type.base_type:
		base_namespace: str = get_uniform_namespace(complex_type.base_type.target_namespace).replace(':', '::')
		the_class += f': public {base_namespace}::{complex_type.base_type.local_name} '
		base_include_path: str = get_file_path(complex_type.base_type, FileType.HEADER)
		includes.add(f'"{base_include_path}"')
	the_class += '{\n'
	the_class += 'public:\n'
	the_class += f'\tusing UPtr = std::unique_ptr<{complex_type.local_name}>;\n'
	the_class += f'\tusing SPtr = std::shared_ptr<{complex_type.local_name}>;\n\n'

	if complex_type.abstract:
		the_class += 'protected:\n'
	else:
		the_class += 'public:\n'
	the_class += f'\t{complex_type.local_name}() = default;\n\n'

	the_class += '};\n'

	include: str = sort_and_concat_includes(includes)

	return header + include + namespace + the_class + footer

def create_body_contents(complex_type: xmlschema.validators.XsdComplexType) -> str:
	header: str = ''
	header += '// This file was generated on ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '.\n'
	header += '// DO NOT EDIT MANUALLY!\n\n'
	header += '#pragma once\n\n'

	cpp_namespace: str = get_uniform_namespace(complex_type.target_namespace).replace(':', '::')
	namespace: str = f'namespace {cpp_namespace} {{\n\n'
	footer = f'\n}} // namespace {cpp_namespace}\n'

	the_class: str = ''

	include: str = ''

	return header + include + namespace + the_class + footer

def write_source(xsd_type: xmlschema.validators.XsdType, fileType: FileType, callback: Callable[[xmlschema.validators.XsdType], str]):
	content: str = callback(xsd_type)
	file_path: str = get_file_path(xsd_type, fileType)

	dir: str = '/'.join(file_path.split('/')[:-1])
	if not os.path.exists(dir):
		os.makedirs(dir)

	with open(file_path, 'w') as file:
		file.write(content)

def write_sources(schema: xmlschema.XMLSchema):
	for _, xsd_type in schema.types.items():
		if xsd_type.is_complex():
			write_source(xsd_type, FileType.HEADER, create_header_contents)
			write_source(xsd_type, FileType.SOURCE, create_body_contents)
		else:
			#TODO: Currently we don't handle simple types. Not sure how to approach these yet. Probably these will not be "proper" types in the end.
			pass

if __name__ == '__main__':
	if os.path.exists(OUTPUT_FOLDER):
		shutil.rmtree(OUTPUT_FOLDER)

	root_schema: xmlschema.XMLSchema = xmlschema.XMLSchema("schemas/schemas.opengis.net/citygml/profiles/base/CityGML.xsd")
	all_schemas: set[xmlschema.XMLSchema] = get_all_schemas(root_schema)
	print('Found', sum(len(schema.elements) for schema in all_schemas), 'elements and', sum(len(schema.types) for schema in all_schemas), 'types. Converting...')

	for schema in all_schemas:
		write_sources(schema)
