class Type:
	name: str

	def __init__(self, name: str):
		self.name = name

class ComplexType(Type):

	def __init__(self, name: str):
		super().__init__(str)