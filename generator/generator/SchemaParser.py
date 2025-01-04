from NamespaceParser import NamespaceManager


SCHEMA_BASE_URL = 'https://schemas.opengis.net/citygml/'

class SchemaParser:
	def __init__(self, version):
		manager = NamespaceManager()
		manager.loadRoot(SCHEMA_BASE_URL + f'profiles/base/{version}/CityGML.xsd', 'http://www.opengis.net/citygml/profiles/base/3.0')
		self.debugWriteTypes(manager)

	def debugWriteTypes(self, manager: NamespaceManager):
		types = manager.getTypes()
		print(len(types))
		typeNames = [type.name for type in types]
		with open("./types.txt", 'w') as file:
			file.write(str(typeNames))
