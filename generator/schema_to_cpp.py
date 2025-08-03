import os, shutil, xmlschema
from datetime import datetime
from enum import Enum
from typing import Callable, List, Dict

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

def get_simple_cpp_type_and_include(simple_type: xmlschema.validators.XsdSimpleType, containing_namespace: str, includes: set[str], backup_name: str) -> tuple[str, str, str]:
	if simple_type.local_name == None:
		simple_type.local_name = backup_name
		the_class: str = create_simple_type(simple_type, includes)
		return backup_name, '', the_class
	if 'XMLSchema' in simple_type.target_namespace:
		if simple_type.local_name == 'double':
			return 'double', '', ''
		else:
			return 'std::string', '<string>', ''
	cpp_namespace: str = '' if simple_type.target_namespace == containing_namespace else get_uniform_namespace(simple_type.target_namespace).replace(':', '::') + '::'
	include: str = '' if simple_type.target_namespace == containing_namespace else get_uniform_namespace(simple_type.target_namespace).replace(':', '/') + '/simpleTypes' + FileType.HEADER.value
	return f'{cpp_namespace}{simple_type.local_name}', '' if len(include) == 0 else f'"{include}"', ''

def create_simple_type(simple_type: xmlschema.validators.XsdSimpleType, includes: set[str]) -> str:
		the_class: str = ''
		if simple_type.is_union():
			member_types: list[str] = []
			for member in simple_type.member_types:
				# Handle anonymous inner simple_types like in TimeUnitType
				cpp_type, include, definition = get_simple_cpp_type_and_include(member, simple_type.target_namespace, includes, simple_type.local_name + 'Member' + str(len(member_types)))
				if len(definition) > 0:
					the_class += definition
				member_types.append(cpp_type)
				if len(include) > 0:
					includes.add(include)
			includes.add('<variant>')
			the_class += f'using {simple_type.local_name} = std::variant<{", ".join(member_types)}>;\n\n'
		elif simple_type.is_restriction():
			# Handle anonymous inner simple_types like in TimeUnitType - can probably happen for restrictions as well
			cpp_type, include, definition = get_simple_cpp_type_and_include(simple_type.base_type, simple_type.target_namespace, includes, simple_type.local_name + 'Base')
			if len(definition) > 0:
				the_class += definition
			the_class += f'using {simple_type.local_name} = {cpp_type};\n\n'
			if len(include) > 0:
				includes.add(include)
		elif simple_type.is_list():
			# Handle anonymous inner simple_types like in TimeUnitType - can probably happen for vectors as well
			cpp_type, include, definition = get_simple_cpp_type_and_include(simple_type.item_type, simple_type.target_namespace, includes, simple_type.local_name + 'Element')
			if len(definition) > 0:
				the_class += definition
			the_class += f'using {simple_type.local_name} = std::vector<{cpp_type}>;\n\n'
			includes.add('<vector>')
			if len(include) > 0:
				includes.add(include)
		else:
			print("Unknown simple type ", simple_type)
		return the_class

def create_simple_header_contents(simple_types: List[xmlschema.validators.XsdSimpleType]) -> str:
	header: str = ''
	header += '// This file was generated on ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '.\n'
	header += '// DO NOT EDIT MANUALLY!\n\n'
	header += '#pragma once\n\n'

	cpp_namespace: str = get_uniform_namespace(simple_types[0].target_namespace).replace(':', '::')
	namespace: str = f'namespace {cpp_namespace} {{\n\n'
	footer = f'}} // namespace {cpp_namespace}\n'

	includes: set[str] = set()

	the_class = ''

	for simple_type in simple_types:
		the_class += create_simple_type(simple_type, includes)

	include: str = sort_and_concat_includes(includes)

	return header + include + namespace + the_class + footer

def write_simple_sources(xsd_types: List[xmlschema.validators.XsdType], fileType: FileType, callback: Callable[[List[xmlschema.validators.XsdSimpleType]], str]):
	content: str = callback(xsd_types)
	namespace: str = get_uniform_namespace(xsd_types[0].target_namespace)
	dir: str = OUTPUT_FOLDER + '/' + namespace.replace(':', '/')
	file_path: str = dir + '/simpleTypes' +  fileType.value

	if not os.path.exists(dir):
		os.makedirs(dir)

	with open(file_path, 'w') as file:
		file.write(content)

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

def write_complex_source(xsd_type: xmlschema.validators.XsdType, fileType: FileType, callback: Callable[[xmlschema.validators.XsdType], str]):
	content: str = callback(xsd_type)
	file_path: str = get_file_path(xsd_type, fileType)

	dir: str = '/'.join(file_path.split('/')[:-1])
	if not os.path.exists(dir):
		os.makedirs(dir)

	with open(file_path, 'w') as file:
		file.write(content)

# lower values have less dependencies - dependent types have at least 1 more than base types
def typeHierarchyDepth(type: xmlschema.validators.XsdSimpleType) -> str:
	if type.base_type:
		return typeHierarchyDepth(type.base_type) + 1
	elif type.is_union():
		return sum([typeHierarchyDepth(sub_type) for sub_type in type.member_types]) + 1
	elif type.is_list():
		return typeHierarchyDepth(type.item_type) + 1
	else:
		return 0 

def write_sources(schema: xmlschema.XMLSchema):
	simple_types: List[xmlschema.validators.XsdSimpleType] = [type for _, type in schema.types.items() if type.is_simple()]
	if len(simple_types) == 0:
		return

	simple_types.sort(key=typeHierarchyDepth) # Simplest types first, more complex later to satisfy internal dependencies
	write_simple_sources(simple_types, FileType.HEADER, create_simple_header_contents)

	for _, xsd_type in schema.types.items():
		if xsd_type.is_complex():
			write_complex_source(xsd_type, FileType.HEADER, create_header_contents)
			write_complex_source(xsd_type, FileType.SOURCE, create_body_contents)

if __name__ == '__main__':
	if os.path.exists(OUTPUT_FOLDER):
		shutil.rmtree(OUTPUT_FOLDER)

	root_schema: xmlschema.XMLSchema = xmlschema.XMLSchema("schemas/schemas.opengis.net/citygml/profiles/base/CityGML.xsd")
	all_schemas: set[xmlschema.XMLSchema] = get_all_schemas(root_schema)
	print('Found', sum(len(schema.elements) for schema in all_schemas), 'elements and', sum(len(schema.types) for schema in all_schemas), 'types. Converting...')

	for schema in all_schemas:
		write_sources(schema)
