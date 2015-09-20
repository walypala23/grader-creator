class Variable:
	def __init__(self, n, t):
		self.name = n
		self.type = t
		self.read = False

class Array:
	def __init__(self, n, t, s):
		self.name = n
		self.type = t
		self.dim = len(s)
		self.sizes = s
		self.allocated = False

class Function:
	def __init__(self, n = None, p = None, b = None, r = None):
		self.name = n
		self.parameters = p
		self.by_ref = b
		if r != None:
			self.type = r.type
			self.return_var = r
		else:
			self.type = ""
			self.return_var = None

class IOline:
	def __init__(self, t = None, l = None, s = None):
		self.type = t
		self.list = l
		if self.type == "Array":
			self.sizes = s

variables = {}
arrays = {}
# print(type(functions))
functions = {}
