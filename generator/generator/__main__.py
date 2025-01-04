import os, sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from SchemaParser import SchemaParser


if __name__ == '__main__':
	v3Parser = SchemaParser('3.0')
