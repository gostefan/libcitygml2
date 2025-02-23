import os, sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from SchemaParser import SchemaParser


if __name__ == '__main__':
	selfPath = Path(__file__)
	outputPath = selfPath.parent.parent / "genOutput"
	outputPath.mkdir(parents = True, exist_ok = True)
	v3Parser = SchemaParser('3.0', outputPath)
