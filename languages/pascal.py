import structures

class Language:
	def __init__(self, fast_io):
		self.out = ""
		if fast_io == 1:
			self.fast_io = True
		else:
			self.fast_io = False
	
	types = {'': 'void', 'int':'Integer', 'longint':'Int64', 'char':'Char', 'real':'Double'}
	
	headers = """\
uses NomeSorgenteContestant;

var	fr, fw : text;
"""
	
	main_function = """\
	
begin
{$ifdef EVAL}
    assign(fr, 'input.txt');
    assign(fw, 'output.txt');
{$else}
    fr := input;
    fw := output;
{$endif}
    reset(fr);
    rewrite(fw);
"""
	
	footers = """\
	
	close(fr);
    close(fw);
end.
"""
	
	comments = {
		"dec_var": "Declaring variables", 
		"dec_fun": "", 
		"input": "Reading input", 
		"call_fun": "Calling functions", 
		"output": "Writing output", 
	}
	
	# array type
	def at(self, type, dim):
		return "array of "*dim + self.types[type]
	
	# write line
	def wl(self, line, tabulation = 0):
		self.out += "\t"*tabulation + line + "\n"
	
	# write comment
	def wc(self, short_description, tabulation = 0):
		if len(self.comments[short_description]) > 0:
			self.out += "\n" + ("\t"*tabulation) + "{ " + self.comments[short_description] +" }\n"
	
	def DeclareVariable(self, var):
		self.wl("{0} : {1};".format(var.name, self.types[var.type]), 1)
		
	def DeclareArray(self, arr):
		self.wl("{0} : {1};".format(arr.name, self.at(arr.type, arr.dim)), 1)
	
	def DeclareFunction(self, fun): #forse non serve dichiarare le funzioni
		doing_nothing = True
	
	def AllocateArray(self, arr):
		self.wl("Setlength({0}, {1});".format(arr.name, ", ".join(arr.sizes)), 1)
	
	def ReadArrays(self, all_arrs):
		all_dim = all_arrs[0].dim
		all_sizes = all_arrs[0].sizes
		for i in range(0, all_dim):
			self.wl("for {0} := 0 to {1} do".format("i" + str(i), all_sizes[i]), i+1)
			self.wl("begin", i+1)
			
		indexes = "".join("[i" + str(x) + "]" for x in range(0, all_dim))
		pointers = ", ".join(arr.name + indexes for arr in all_arrs)
		self.wl("read(fr, {0});".format(pointers), all_dim+1)
			
		for i in range(0, all_dim):
			self.wl("end;", all_dim - i)
	
	def ReadVariables(self, all_vars):
		pointers = ", ".join(var.name for var in all_vars)
		self.wl("readln(fr, {0});".format(pointers), 1)
	
	def CallFunction(self, fun):
		parameters = ', '.join([param.name for param in fun.parameters])
		if fun.type == "":
			self.wl("{0}({1});".format(fun.name, parameters), 1)
		else:
			self.wl("{2} := {0}({1});".format(fun.name, parameters, fun.return_var.name), 1)
	
	def WriteArrays(self, all_arrs):
		all_dim = all_arrs[0].dim
		all_sizes = all_arrs[0].sizes
		
		for i in range(0, all_dim):
			self.wl("for {0} := 0 to {1} do".format("i" + str(i), all_sizes[i]), i+1)
			self.wl("begin", i+1)
		indexes = "".join("[i" + str(x) + "]" for x in range(0, all_dim))
		antipointers = ", ".join(arr.name + indexes for arr in all_arrs)
		if len(all_arrs) > 1:
			self.wl("writeln(fw, {0});".format(antipointers), all_dim+1)
		else:
			self.wl("write(fw, {0});".format(antipointers), all_dim+1)
		
		for i in range(0, all_dim):
			self.wl("end;", all_dim - i)
			if i == all_dim-1 and len(all_arrs) > 1:
				self.wl("writeln(fw);", all_dim - i)

	def WriteVariables(self, all_vars):
		antipointers = ", ".join(var.name for var in all_vars)
		self.wl("writeln(fw, {0});".format(antipointers), 1)
	
	def insert_headers(self):
		print("warning: Nella prima riga del grader pascal deve essere inserito il nome del file scritto dal contestant")
		self.out += self.headers
		
	def insert_main(self):
		self.wl("\n{ iterators used in for loops }")
		if len(structures.arrays) > 0:
			max_dim = max(structures.arrays[name].dim for name in structures.arrays)
			self.wl(", ".join("i" + str(x) for x in range(0, max_dim)) + ": Integer;", 1)
		
		if self.fast_io:
			fast_io_file = open("languages/fast_io.pas", "r")
			self.out += "\n" + fast_io_file.read()
			fast_io_file.close()
			
		self.out += self.main_function
	
	def insert_footers(self):
		self.out += self.footers