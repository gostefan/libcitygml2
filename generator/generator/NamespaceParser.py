from io import BytesIO
import urllib.parse
import xml.etree.ElementTree as ET

import requests


class SimpleType:
	def __init__(self, name: str):
		self.name = name

class NamespaceManager:
	def __init__(self):
		self.namespaces: dict[str, 'NamespaceParser'] = {}

	def loadRoot(self, url: str, name: str):
		self.load(url, name)
		print("Loaded files - parsing now")
		for namespace in self.namespaces.values():
			namespace.compile()
	
	def load(self, url: str, name: str):
		if name in self.namespaces:
			return self.namespaces[name]
		else:
			from NamespaceParser import NamespaceParser
			namespace = NamespaceParser(url, name, self)
			self.namespaces[name] = namespace
			namespace.readXml()
			return namespace

	def getTypes(self) -> list['Type']:
		types = []
		for name, namespace in self.namespaces.items():
			print(f'Namespace {name} has {len(namespace.types)} types')
			types = types + namespace.types
		return types

	# TODO: The return value is not correct - it also returns the unrelated SimpleType. Need to find a nicer solution
	def getType(self, name: str) -> 'Type':
		if ':' in name:
			ns, name = name.split('[:]') if name.count('[:]') == 1 else name.split(':')
			if ns in self.namespaces:
				return self.namespaces[ns].getRawType(name)
			elif ns != 'http://www.w3.org/2001/XMLSchema':
				raise RuntimeError(f'Namespace {ns} not found')
			# purposeful fallthrough for XML schema types

		else:
			for namespace in self.namespaces.values():
				type = namespace.getRawType(name)
				if type is not None:
					return type

		match name:
			case 'boolean':
				return SimpleType("boolean")
			case 'double' | 'decimal' | 'float':
				return SimpleType("double")
			case 'integer' | 'negativeInteger' | 'nonNegativeInteger' | 'nonPositiveInteger' | 'positiveInteger':
				# TODO: use the correct restrictions on these - probably best by loading the xmlschema schema.
				return SimpleType("integer")
			case 'anyURI' | 'date' | 'dateTime' | 'duration' | 'gDay' | 'gMonth' | 'gMonthDay' | 'gYear' | 'gYearMonth' | 'ID' | 'Name' | 'NCName' | 'normalizedString' | 'QName' | 'string' | 'time' | 'token':
				# TODO: use the correct restrictions on these - probably best by loading the xmlschema schema.
				return SimpleType("string")
			case 'anyType':
				# TODO: Not sure what is correct to return here...
				return SimpleType("string")

		raise RuntimeError(f'Type {name} not found.')

	def getElement(self, name: str) -> 'Type':
		if ':' in name:
			ns, name = name.split('[:]') if name.count('[:]') == 1 else name.split(':')
			if ns in self.namespaces:
				return self.namespaces[ns].getRawElement(name)
			#elif ns != 'http://www.w3.org/2001/XMLSchema':
			raise RuntimeError(f'Namespace {ns} not found')
			# purposeful fallthrough for XML schema types

		else:
			for namespace in self.namespaces.values():
				ele = namespace.getRawElement(name)
				if ele is not None:
					return ele

		raise RuntimeError(f'Element {name} not found.')

class NamespaceParser:
	def __init__(self, url: str, name: str, manager: NamespaceManager):
		self.url = url
		self.name = name
		self.manager = manager

		self._aliases: dict[str, str] = {}
		self.elements: list[Element] = []
		self.groups: list[ET.Element] = []
		self.imports: list[ET.Element] = []
		self.includes: list[str] = []
		self.types: list['Type'] = []
	
	def readXml(self):
		self._readAnyXml(self.url)
	
	def _readAnyXml(self, url: str):
		response = requests.get(url)
		response.raise_for_status
		
		root = self.fromstringWithAliases(response.text)
		self.parseElements(root)

	def fromstringWithAliases(self, text):
		root = None
		parser = ET.XMLParser(target=ET.TreeBuilder())
		for event, elem in ET.iterparse(BytesIO(text.encode("UTF-8")), events=(["start-ns", "start"]), parser=parser):
			if event == 'start-ns':
				#print("ns")
				prefix, uri = elem
				self._aliases[prefix] = uri
			elif event == 'start':
				#print("start", elem)
				if root == None:
					root = elem
		if root == None:
			raise RuntimeError("No start event when parsing xml file")
		return root

	def parseElements(self, parent: ET.Element):
		for element in parent:
			if element.tag.endswith('attributeGroup') or element.tag.endswith('attribute'):
				# TODO: ignored for now - unsure if necessary
				pass
			elif element.tag.endswith('annotation'):
				# not important for code generation
				pass
			elif element.tag.endswith('complexType') or element.tag.endswith('simpleType'):
				self.types.append(Type(self, element))
			elif element.tag.endswith('element'):
				self.elements.append(Element(element, self))
			elif element.tag.endswith('group'):
				self.groups.append(element)
			elif element.tag.endswith('import'):
				url = element.attrib['schemaLocation']
				if not url.startswith('http'):
					url = urllib.parse.urljoin(self.url, url)
				self.imports.append(self.manager.load(url, element.attrib['namespace']))
			elif element.tag.endswith('include'):
				url = element.attrib['schemaLocation']
				if not url.startswith('http'):
					url = urllib.parse.urljoin(self.url, url)
				if url not in self.includes:
					self.includes.append(url)
					self._readAnyXml(url)
			else:
				print(f"Looking for children in {element.tag}")
				self.parseElements(element)

	def compile(self):
		if 'citygml' not in self.url:
			print(f"Weird ns {self.name} at {self.url}")
		for type in self.types:
			type.compileType()
		for element in self.elements:
			element.compileElement()

	def getRawType(self, name: str) -> 'Type':
		for type in self.types:
			if type.name == name:
				return type
		return None

	def getType(self, name: str) -> 'Type':
		if ':' in name:
			ns, name = name.split(':')
			fullNs = self._aliases[ns]
			return self.manager.getType(f'{fullNs}[:]{name}')
		else:
			directType = self.getRawType(name)
			if directType != None:
				return directType

		# TODO: Only check (anonymous) namespaces that are referenced in the schema.
		return self.manager.getType(name)

	def getRawElement(self, name: str) -> 'Element':
		for ele in self.elements:
			if ele.name == name:
				return ele
		return None

	def getElement(self, name: str) -> 'Element':
		if ':' in name:
			ns, name = name.split(':')
			fullNs = self._aliases[ns]
			return self.manager.getElement(f'{fullNs}[:]{name}')
		else:
			directElement = self.getRawElement(name)
			if directElement != None:
				return directElement

		# TODO: Only check (anonymous) namespaces that are referenced in the schema.
		return self.manager.getElement(name)


ANONYMOUS_TYPE: str = '__anonymous_type__'
class Type:
	def __init__(self, namespace: NamespaceParser, xmlNode: ET.Element):
		self._rootNode: ET.Element = xmlNode
		self._isCompiled: bool = False

		self.base: 'Type' = None
		self.choice: list['Type'] = []
		self.elements: list['Element'] = []
		self.innerTypes: list['Type'] = []
		self.isAbstract: bool
		self.isComplexContent: bool = False
		self.isFinal: bool
		self.isList: bool = False
		self.isMixed: bool = False
		self.isSequence: bool = False
		self.isSimpleContent: bool = False
		self.members: list["ChildMember"] = []
		self.union: list['Type'] = []

		self.namespace = namespace
		self.name = self._rootNode.attrib['name'] if 'name' in self._rootNode.attrib else ANONYMOUS_TYPE

	def compileType(self):
		if not (self._rootNode.tag.endswith('complexType') or self._rootNode.tag.endswith('simpleType')):
			self.raiseRuntime(f'Unknown type {self._rootNode.tag}')

		self.isAbstract = True if self._rootNode.attrib.get('abstract') == 'true' else False
		self.isFinal = True if self._rootNode.attrib.get('final') == 'true' else False
		self.isMixed = True if self._rootNode.attrib.get('mixed') == 'true' else False

		self.parseChildren(self._rootNode)
		self._isCompiled = True

	def parseChildren(self, node: ET.Element):
		for child in node:
			if child.tag.endswith('any') or child.tag.endswith('attributeGroup') or child.tag.endswith('group') or child.tag.endswith('anyAttribute'):
				# TODO: ignored for now - unsure if necessary
				pass
			elif child.tag.endswith('annotation'):
				# not important for code generation
				pass
			elif child.tag.endswith('attribute'):
				self.parseAttribute(child)
			elif child.tag.endswith('choice'):
				self.parseChoice(child)
			elif child.tag.endswith('complexContent'):
				self.parseComplexContent(child)
			elif child.tag.endswith('element'):
				self.parseElement(child)
			elif child.tag.endswith('list'):
				self.parseList(child)
			elif child.tag.endswith('restriction'):
				self.parseRestriction(child)
			elif child.tag.endswith('sequence'):
				self.isSequence = True
				self.parseChildren(child)
			elif child.tag.endswith('simpleContent'):
				self.parseSimpleContent(child)
			elif child.tag.endswith('union'):
				self.parseUnion(child)
			else:
				self.raiseRuntime(f'Unknown tag {child.tag}')

	def parseAttribute(self, node: ET.Element):
		self.elements.append(Element(node, self.namespace))

	def parseElement(self, node: ET.Element):
		member = ChildMember(node, self.namespace)
		self.members.append(member)
		# TODO: print(f'Found element {member.name} on type {self.name}')

	def parseChoice(self, node: ET.Element):
		types = []
		for element in node:
			if element.tag.endswith('element') or element.tag.endswith('sequence') or element.tag.endswith('choice'):
				tmpParent = ET.Element('complexType')
				tmpParent.append(element)
				type = Type(self.namespace, tmpParent)
				types.append(type)
				type.compileType()
		self.union = types

	def parseComplexContent(self, node: ET.Element):
		# Not sure if the `id` attribute is relevant - we're ignoring it currently.
		if len(node) != 1:
			self.raiseRuntime('complexContent node has too many nodes')
		self.isComplexContent = True
		child = node[0]
		if child.tag.endswith('extension'):
			self.parseExtension(child)
		elif child.tag.endswith('restriction'):
			self.parseRestriction(child)
		else:
			self.raiseRuntime(f'Unexpected type {child.tag} in {node.tag} tag')

	def parseList(self, node: ET.Element):
		if 'itemType' in node.attrib:
			self.type = self.namespace.getType(node.attrib['itemType'])
		self.isList = True

	def parseExtension(self, node: ET.Element):
		if 'base' not in node.attrib:
			self.raiseRuntime('no base given for extension')
		self.base = self.namespace.getType(node.attrib['base'])
		self.parseChildren(node)

	def parseRestriction(self, node: ET.Element):
		if 'base' in node.attrib:
			if self.base != None:
				self.raiseRuntime(f'Double inheritance in {node.tag}')
			self.base = self.namespace.getType(node.attrib['base'])
		elif len(node) >= 1 and node[0].tag.endswith('simpleType'):
			type = Type(self.namespace, node[0])
			self.base = type
			type.compileType()
		else:
			self.raiseRuntime('Unexpected number of children in restriction')
		# TODO: Parse actual restrictions

	def parseSimpleContent(self, node: ET.Element):
		# Not sure if the `id` attribute is relevant - we're ignoring it currently.
		if len(node) != 1:
			self.raiseRuntime('simpleContent node has too many nodes')
		self.isSimpleContent = True
		child = node[0]
		if child.tag.endswith('extension'):
			self.parseExtension(child)
		elif child.tag.endswith('restriction'):
			self.parseRestriction(child)
		else:
			self.raiseRuntime(f'Unexpected type {child.tag} in {node.tag} tag')

	def parseUnion(self, node: ET.Element):
		# Not sure if the `id` attribute is relevant - we're ignoring it currently.
		types = []
		if 'memberTypes' in node.attrib:
			types = list(set([self.namespace.getType(type) for type in node.attrib['memberTypes'].split(' ')]))
		for element in node:
			type = Type(self.namespace, element)
			types.append(type)
			type.compileType()
		self.union = types

	def raiseRuntime(self, str):
		raise RuntimeError(f'{str} on {self.name} in namespace {self.namespace.name}')

ANONYMOUS_ELEMENT: str = '__anonymous_element__'
class Element:

	def __init__(self, node: ET.Element, namespace: NamespaceParser):
		self.isAbstract: bool = False
		self.default: any = None
		self.fixed: str = None
		self.isReference: bool = False
		self.reference: Element = None
		self.name: str = ANONYMOUS_ELEMENT
		self.namespace: NamespaceParser = namespace
		self.substitutes = None
		self.substitutions = []
		self.type: Type = None
		self.typeName: str = None
		self.use: str = "optional"

		for attr, value in node.attrib.items():
			if attr == 'default':
				self.default = value
			elif attr == 'name':
				self.name = value
			elif attr == 'ref':
				self.isReference = True
				self.name = value
			elif attr == 'type':
				self.typeName = value
			elif attr == 'use':
				self.use = value
			elif attr == 'fixed':
				self.fixed = value
			elif attr == 'abstract':
				self.isAbstract = True if value == 'true' else False
			elif attr == 'nillable':
				pass # TODO: We probably need to know this.
			elif attr == 'substitutionGroup':
				self.substitutes = value
			elif attr == 'block':
				pass # not interesting for us - we're not validating the schema
			else:
				raise RuntimeError(f'Unknown attribute {attr} => {value} on {node.tag} in {self.namespace.name} $({self.namespace.url})')

	def addSubstitution(self, subst):
		self.substitutions.append(subst)

	def compileElement(self):
		if self.isReference:
			self.reference = self.namespace.getElement(self.name)
		elif self.typeName != None:
			self.type = self.namespace.getType(self.typeName)
		else:
			print(f'type {self.name} in {self.namespace.name} isn\'t ref and doesn\'t have a type... unsure what that means')

		if self.substitutes != None:
			target = self.namespace.getElement(self.substitutes)
			if target == None:
				raise RuntimeError(f'Unknown element {self.substitutes}')
			target.addSubstitution(self)



ANONYMOUS_MEMBER = "__anonymous_member__"
class ChildMember:
	def __init__(self, node: ET.Element, namespace: NamespaceParser):
		self._node: ET.Element = node
		self.name: str = node.attrib['name'] if 'name' in node.attrib else ANONYMOUS_MEMBER
		self.namespace: NamespaceParser = namespace
		self.type: Type = None
