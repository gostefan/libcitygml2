import codecs, os, re, requests, shutil, xml.etree.ElementTree as ET

GML_URL = 'https://schemas.opengis.net/gml/3.2.1/gml.xsd'
CITY_GML_URL = 'https://schemas.opengis.net/citygml/profiles/base/3.0/CityGML.xsd'
SCHEMA_FOLDER = 'schemas'

def splitPath(url: str) -> list[str]:
	return url.split('/')

def joinPath(parts: list[str]) -> str:
	return '/'.join(parts)

def url_to_folder(url: str) -> str:
	urlParts: list[str] = splitPath(url)
	return joinPath([part for part in urlParts[:-1] if len(part) > 0 and not re.match(r'.*[0-9:].*', part)] + [urlParts[-1]])

def gather_referenced_schemas(content: str, srcSchema: str) -> set:
	pattern = r'schemaLocation="([^"]+)"'
	schemas: list[str] = re.findall(pattern, content)
	return [schema if schema.startswith('http') else joinPath(splitPath(srcSchema)[:-1] + [schema]) for schema in schemas ]

def adapt_paths(content: str, folder_depth: int) -> str:
	def replace_url_with_folder(match):
		url = match.group(1)
		prefix: str = '../' * folder_depth if url.startswith('http') else ''
		return f'schemaLocation="{prefix + url_to_folder(url)}"'

	pattern = r'schemaLocation="(http[^"]+|[^"]*xAL[^"]*)"'
	return re.sub(pattern, replace_url_with_folder, content)

def download_schema(url: str):
	response: requests.Response = requests.get(url=url)
	if not response.ok:
		raise "Request wasn't ok"
	return response.content.decode('utf-8')

if __name__ == '__main__':
	if os.path.exists(SCHEMA_FOLDER):
		shutil.rmtree(SCHEMA_FOLDER)

	schemas_to_gather = set()
	gathered_schemas = set()
	schemas_to_gather.add(CITY_GML_URL)

	while schemas_to_gather:
		schema = schemas_to_gather.pop()
		gathered_schemas.add(schema)

		path: str = joinPath([SCHEMA_FOLDER] + splitPath(url_to_folder(schema)))
		print(schema, '-->', path)

		schema_content: str = download_schema(schema)
		referenced_schemas: list = gather_referenced_schemas(schema_content, schema)
		new_schemas: set = set(referenced_schemas) - gathered_schemas
		schemas_to_gather.update(new_schemas)

		dir = joinPath(splitPath(path)[:-1])
		updated_content: str = adapt_paths(schema_content, dir.count('/'))

		if not os.path.exists(dir):
			os.makedirs(dir)
		with codecs.open(path, 'w', 'utf-8') as out:
			out.write(updated_content)
