#!/usr/bin/env python3

import sys
import os
import re # regexp, used to check variables and functions names
import argparse # to parse command line arguments

from gradergen.structures import Variable, Array, Function, IOline, Expression
from gradergen.languages.C import LanguageC
from gradergen.languages.CPP import LanguageCPP
from gradergen.languages.pascal import LanguagePascal

LANGUAGES_LIST = ["C", "fast_C", "CPP", "fast_CPP", "pascal", "fast_pascal"]
TYPES = ["", "int", "longint", "char", "real"]
DESCRIPTION_FILE = "grader_description.txt"

# Global variables used in parsing functions
variables = {}
arrays = {}
functions = {}
helpers = {}

# Get the correct file name
def languageize(name, language):
	name += {
		"C": ".c",
		"fast_C": ".c",
		"CPP": ".cpp",
		"fast_CPP": ".cpp",
		"pascal": ".pas",
		"fast_pascal": ".pas",
	}[language]

	if "fast" in language:
		name = "fast_" + name

	return name

def util_is_integer(s):
	try:
		n = int(s)
	except:
		return False

	return True

# Solo cose della forma a*var+-b
def parse_expression(s):
	a = 1
	var = None
	b = 0

	# Parsing a
	if "*" in s:
		splitted = re.split("\*", s)
		splitted = [x.strip() for x in splitted if x.strip()]
		if len(splitted) != 2:
			sys.exit("Un'espressione è malformata (si supportano solo quelle delle forma a*var+b)")
		if util_is_integer(splitted[0]):
			a = int(splitted[0])
		else:
			sys.exit("Le costanti nelle espressioni devono essere interi")

		s = splitted[1]

	# Parsing var
	temp_var = re.match("[a-zA-Z_][0-9a-zA-Z_]*", s)
	if temp_var:
		name = temp_var.group(0)
		if name not in variables:
			sys.exit("Le variabili nelle espressioni devono essere dichiarate")
		elif variables[name].type not in ["int", "longint"]:
			sys.exit("Le variabili nelle espressioni devono essere di tipo intero")
		else:
			var = variables[name]
		s = s[len(name):]

	# Parsing b
	if len(s) > 0:
		if util_is_integer(s):
			b = int(s)
		else:
			sys.exit("Le costanti nelle espressioni devono essere interi")

	return Expression(var, a, b)

def parse_variable(line):
	global variables, arrays, functions

	var = re.split('[ \[\]]', line) # Split line by square brackets and space
	var = [x for x in var if x] # Remove empty chunks

	if not var[0] in TYPES:
		sys.exit("Tipo non esistente")

	if not re.match("^[a-zA-Z_$][0-9a-zA-Z_$]*$", var[1]):
		sys.exit("Il nome di una variabile contiene dei caratteri non ammessi")

	if len(var) == 2:
		if var[1] in variables or var[1] in arrays:
			sys.exit("Nome della variabile già utilizzata")
		var_obj = Variable(var[1], var[0])
		return var_obj;

	else:
		dim = len(var)-2
		if var[1] in variables or var[1] in arrays:
			sys.exit("Nome dell'array già utilizzato")
		if dim == 0:
			sys.exit("Dimensioni dell'array non specificate")
		sizes = [parse_expression(expr) for expr in var[2:]]

		arr_obj = Array(var[1], var[0], sizes)
		return arr_obj

def parse_function(line):
	global variables, arrays, functions

	fun_obj = Function()

	fun = re.split("=", line)
	if len(fun) > 2:
		sys.exit("La descrizione di una funzione ha troppi caratteri '='")
	elif len(fun) == 2:
		var = fun[0].strip()
		if var not in variables:
			sys.exit("Variabile di ritorno di una funzione non definita")

		fun_obj.type = variables[var].type
		fun_obj.return_var = variables[var]
		fun = fun[1].strip()
	else:
		fun_obj.type = ""
		fun = fun[0]

	fun = re.split("[\(\)]", fun)
	if len(fun) != 3:
		sys.exit("La descrizione di una funzione ha un numero errato di parentesi")
	else:
		name = fun[0].strip()
		if name in variables or name in arrays:
			sys.exit("Il nome di una funzione è già usato")

		fun_obj.name = name

		fun_obj.parameters = []
		fun_obj.by_ref = []
		parameters = re.split(",", fun[1])
		for param in parameters:
			param = param.strip()

			if param.startswith("&"):
				param = param[1:]
				fun_obj.by_ref.append(True)
			else:
				fun_obj.by_ref.append(False)

			if param in variables:
				fun_obj.parameters.append(variables[param])
			elif param in arrays:
				fun_obj.parameters.append(arrays[param])
				if fun_obj.by_ref[-1]:
					sys.exit("Gli array non possono essere passati per reference")
			else:
				sys.exit("Parametro di funzione non definito")

	return fun_obj

def parse_input(line):
	global variables, arrays, functions

	if "[" in line: # Read arrays
		all_arrs = re.sub("[\[\]]", "", line) # Remove square brackets
		all_arrs = re.split(" ", all_arrs) # Split line by spaces
		all_arrs = [x for x in all_arrs if x] # Remove empty chuncks

		for name in all_arrs:
			if name not in arrays:
				sys.exit("Un array da leggere non esiste")

			arr = arrays[name]
			if arr.sizes != arrays[all_arrs[0]].sizes:
				sys.exit("Array da leggere insieme devono avere le stesse dimensioni")

			for expr in arr.sizes:
				if expr.var is not None and expr.var.read == False:
					sys.exit("Quando si legge un array devono essere note le dimensioni")

		input_line = IOline("Array", [arrays[name] for name in all_arrs], arrays[all_arrs[0]].sizes)
		return input_line

	else: # Read variables
		all_vars = re.split(" ", line) # Split line by spaces
		all_vars = [x for x in all_vars if x] # Remove empty chuncks
		for name in all_vars:
			if name not in variables:
				sys.exit("Una variabile da leggere non esiste")
			variables[name].read = True

		input_line = IOline("Variable", [variables[name] for name in all_vars])
		return input_line

def parse_output(line):
	global variables, arrays, functions

	if "[" in line: # Write arrays
		all_arrs = re.sub("[\[\]]", "", line) # Remove square brackets
		all_arrs = re.split(" ", all_arrs) # Split line by spaces
		all_arrs = [x for x in all_arrs if x] # Remove empty chuncks

		for name in all_arrs:
			if name not in arrays:
				sys.exit("Un array da scrivere non esiste")

			if arrays[name].sizes != arrays[all_arrs[0]].sizes:
				sys.exit("Array da scrivere insieme devono avere le stesse dimensioni")

		output_line = IOline("Array", [arrays[name] for name in all_arrs], arrays[all_arrs[0]].sizes)
		return output_line

	else: # Write variables
		all_vars = re.split(" ", line) # Split line by spaces
		all_vars = [x for x in all_vars if x] # Remove empty chuncks

		for name in all_vars:
			if name not in variables:
				sys.exit("Una variable da scrivere non esiste")

		output_line = IOline("Variable", [variables[name] for name in all_vars])
		return output_line


# Parsing grader description file
def parse_description(lines):
	sections = {"variables": False, "functions": False, "input": False, "output": False, "helpers": False}
	section_lines = {}
	act_section = None
	for line in lines:
		line = line.strip()

		if line.startswith("#") or len(line) == 0:
			continue

		is_section_title = False
		for section in sections:
			if line == "***" + section + "***":
				if sections[section]:
					sys.exit("Il file di descrizione contiene due volte la stessa sezione")
				is_section_title = True
				sections[section] = True
				act_section = section
				section_lines[section] = []
				break

		if not is_section_title:
			if not act_section:
				sys.exit("Il file di descrizione deve specificare una sezione")
			section_lines[act_section].append(line)
	return section_lines


def main():
	global languages_serializer
	global DESCRIPTION_FILE
	global variables, arrays, functions, helpers

	declarations_order = []
	input_order = []
	output_order = []
	functions_order = []
	helpers_order = []

	parser = argparse.ArgumentParser(description = "Automatically generate grader files in various languages")
	parser.add_argument(\
		"grader_description",
		metavar="grader_description",
		action="store", nargs="?",
		help="the file describing the grader"
	)
	parser.add_argument(\
		"--task-name",
		metavar="task_name",
		action="store", nargs="?",
		default="the_name_of_the_task",
		help="the name of the task"
	)
	group = parser.add_mutually_exclusive_group(required=True)

	group.add_argument(\
		"-l","--lang",
		nargs = "+",
		metavar = ("lang", "grader_filename"),
		dest = "languages",
		action = "append",
		help="programming language and grader filename"
	)

	group.add_argument(\
		"-a", "--all",
		action="store_true",
		default=False,
		help="create grader (with filename 'grader.lang') in all supported languages"
	)

	args = parser.parse_args()
	if args.grader_description is None:
		# Search for a DESCRIPTION_FILE
		directory = os.getcwd()
		while True:
			description = os.path.join(directory, DESCRIPTION_FILE)

			if os.path.isfile(description):
				args.grader_description = description
				break

			if os.path.dirname(directory) == directory:
				break
			else:
				directory = os.path.dirname(directory)

	if args.grader_description is None:
		sys.exit("The " + DESCRIPTION_FILE + " file cannot be found.")

	with open(args.grader_description, "r") as grader_description:
		lines = grader_description.read().splitlines()
		section_lines = parse_description(lines)

	if args.all:
		args.languages = [[lang] for lang in LANGUAGES_LIST]

	# Parsing variables
	for line in section_lines["variables"]:
		parsed = parse_variable(line)
		if type(parsed) == Variable:
			variables[parsed.name] = parsed
			declarations_order.append(parsed)
		elif type(parsed) == Array:
			arrays[parsed.name] = parsed
			declarations_order.append(parsed)

	# Parsing functions
	for line in section_lines["functions"]:
		parsed = parse_function(line)
		functions[parsed.name] = parsed
		functions_order.append(parsed)

	# Parsing input
	for line in section_lines["input"]:
		parsed = parse_input(line)
		input_order.append(parsed)

	use_helper = False

	if "helpers" in section_lines:
		use_helper = True

		# Parsing helpers
		for line in section_lines["helpers"]:
			parsed = parse_function(line)
			helpers[parsed.name] = parsed
			helpers_order.append(parsed)
	else:
		# Parsing output
		for line in section_lines["output"]:
			parsed = parse_output(line)
			output_order.append(parsed)

	# End of parsing

	data = {
		"task_name": args.task_name,
		"variables": variables,
		"declarations_order": declarations_order,
		"arrays": arrays,
		"functions": functions,
		"functions_order": functions_order,
		"helpers": helpers,
		"helpers_order": helpers_order,
		"input_order": input_order,
		"output_order": output_order,
	}

	# All languages are initializated (not all are written to file)
	language_classes = {
		"C": LanguageC(0, data),
		"fast_C": LanguageC(1, data),
		"CPP": LanguageCPP(0, data),
		"fast_CPP": LanguageCPP(1, data),
		"pascal": LanguagePascal(0, data),
		"fast_pascal": LanguagePascal(1, data)
	}

	chosed_languages = []
	for el in args.languages:
		if el[0] not in LANGUAGES_LIST:
			sys.exit("Uno dei linguaggi non è supportato")

		# __import__("pdb").set_trace()
		if len(el) == 1:
			el.append(languageize("grader", el[0]))
			if use_helper:
				# TODO: this name is language specific, at least for pascal...
				el.append(languageize("helper", el[0]))
		elif len(el) == 2:
			if use_helper:
				sys.exit("You specified a grader name but not a helper name")
			else:
				el.append(languageize(el[1], el[0]))
		elif len(el) == 3:
			if not use_helper:
				sys.exit("You specified a helper name even though no helper is needed")
			else:
				el.append(languageize(el[1], el[0]))
				el.append(languageize(el[2], el[0]))
		elif len(el) > 3:
			sys.exit("For each language you can specify, at most, the names of the grader/helper")

		if use_helper:
			chosed_languages.append((language_classes[el[0]], el[1], el[2]))
		else:
			chosed_languages.append((language_classes[el[0]], el[1]))

	for x in chosed_languages:
		if len(x) == 2:
			x[0].write_files(x[1])
		else:
			x[0].write_files(x[1], x[2])
