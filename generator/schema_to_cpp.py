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

def create_header_contents(type: xmlschema.validators.XsdType) -> str:
	header: str = ''
	header += '// This file was generated on ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '.\n'
	header += '// DO NOT EDIT MANUALLY!\n\n'
	header += '#pragma once\n\n'

	cpp_namespace: str = get_uniform_namespace(type.target_namespace).replace(':', '::')
	namespace: str = f'namespace {cpp_namespace} {{\n\n'
	footer = f'\n}} // namespace {cpp_namespace}\n'

	the_class: str = f'class {type.local_name} {{ }};\n'

	include: str = ''

	return header + include + namespace + the_class + footer

def create_body_contents(type: xmlschema.validators.XsdType) -> str:
	header: str = ''
	header += '// This file was generated on ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '.\n'
	header += '// DO NOT EDIT MANUALLY!\n\n'
	header += '#pragma once\n\n'

	cpp_namespace: str = get_uniform_namespace(type.target_namespace).replace(':', '::')
	namespace: str = f'namespace {cpp_namespace} {{\n\n'
	footer = f'\n}} // namespace {cpp_namespace}\n'

	the_class: str = ''

	include: str = ''

	return header + include + namespace + the_class + footer

def write_source(type: xmlschema.validators.XsdType, fileType: FileType, callback: Callable[[xmlschema.validators.XsdType], str]):
	content: str = callback(type)
	file_path: str = get_file_path(type, fileType)

	dir: str = '/'.join(file_path.split('/')[:-1])
	if not os.path.exists(dir):
		os.makedirs(dir)

	with open(file_path, 'w') as file:
		file.write(content)

def write_sources(schema: xmlschema.XMLSchema):
	for _, type in schema.types.items():
		write_source(type, FileType.HEADER, create_header_contents)
		write_source(type, FileType.SOURCE, create_body_contents)

if __name__ == '__main__':
	if os.path.exists(OUTPUT_FOLDER):
		shutil.rmtree(OUTPUT_FOLDER)

	root_schema: xmlschema.XMLSchema = xmlschema.XMLSchema("schemas/schemas.opengis.net/citygml/profiles/base/CityGML.xsd")
	all_schemas: set[xmlschema.XMLSchema] = get_all_schemas(root_schema)
	print('Found', sum(len(schema.elements) for schema in all_schemas), 'elements and', sum(len(schema.types) for schema in all_schemas), 'types. Converting...')

	for schema in all_schemas:
		write_sources(schema)
