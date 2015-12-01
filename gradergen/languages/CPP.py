import pkg_resources
import sys
from gradergen import structures
from gradergen.structures import Variable, Array, Function, IOline, Expression
from gradergen.languages.C import LanguageC


class LanguageCPP(LanguageC):
	extension = "cpp"

	headers = """\
#include <cstdio>
#include <cassert>
#include <cstdlib>

static FILE *fr, *fw;
"""

	byref_symbol = " &"
	byref_call = ""
	byref_access = ""
