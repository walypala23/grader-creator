import enum
import sys

# Here the lines matched by regex (defined as property of RegexParser) are 
# transformed in objects. 
# Lots of compilation-like checks are done before creating the objects as: an 
# array must be allocated before being written, the size of an array must be
# an integer, etc...
# Moreover, the constructors does not receive as parameters only the match_tree
# generated by RegexParser.MatchTree, but can receive also the data_manager that is
# the class containing all the data already parsed and exposing utility methods. 
# The data_manager instance passed by parameter is not modified here and can 
# be considered as if it had a const identifier.

class PrimitiveType(enum.Enum):
    VOID = ""
    INT = "int"
    LONGINT = "longint"
    CHAR = "char"
    REAL = "real"

class Location(enum.Enum):
    SOLUTION = "solution"
    GRADER = "grader"

class Variable:
    def __init__(self, match_tree):
        self.name = match_tree["name"]
        self.type = PrimitiveType(match_tree["type"])
        self.known = False # This is not used in any single language class, but only in the main parser.

class Array:
    def __init__(self, match_tree, data_manager):
        self.name = match_tree["name"]
        self.type = PrimitiveType(match_tree["type"])
        self.dim = len(match_tree["sizes"])
        self.sizes = [Expression(size, data_manager) for size in match_tree["sizes"]]
        self.allocated = False # Handled only by single language classes. It is used to know when to allocate an array.
        self.known = False # This is not used in any single language class, but only in the main parser.
    
    def is_allocable(self):
        return all(size.is_known() for size in self.sizes)
        
class Parameter:
    def __init__(self, match_tree):
        self.name = match_tree["name"]
        self.type = PrimitiveType(match_tree["type"])
        # This is the dimension, 0 means it is a simple variable.
        # match_tree["param_dim"] is a string like "[][][]", the number of "[]" is the dimension.
        self.dim = len(match_tree["dim"]) // 2
        # match_tree["by_ref"] can be ' ', ' &', '& '.
        self.by_ref = "&" in match_tree["by_ref"]
        
class Prototype:
    def __init__(self, match_tree, using_include_grader):
        self.name = match_tree["name"]
        self.type = PrimitiveType(match_tree["return_type"]) # One of the primitive types (array not supported)
        self.parameters = [Parameter(param) for param in match_tree["params"]]
        # Where this prototype should be defined. 
        # Can be SOLUTION, if this prototype has to be defined by the contestant
        # in his solution, or GRADER if this prototype should be defined in
        # include_grader.
        # If the value is GRADER, then this prototype is not included in templates.
        self.location = Location(match_tree["location"]) if "location" in match_tree else Location.SOLUTION
        
        if not using_include_grader and self.location == Location.GRADER:
            raise ValueError("The location of a prototype cannot be 'grader' "
                             "if you are not providing the include_grader file")

class Call:
    def __init__(self, match_tree, data_manager):
        self.name = match_tree["name"]
        self.return_var = data_manager.get_variable(match_tree["return_var"]) if "return_var" in match_tree else None
        
        # Cannot be an Array, must be a simple Variable.
        if self.return_var is not None and type(self.return_var) == Array:
            raise ValueError("The variable assigned to the return value of a "
                             "call cannot be an array.")
        
        # Finding the prototype with the same name as this call.
        self.prototype = data_manager.get_prototype(self.name)
        
        # Checking whether the return type is the same
        if self.prototype.type != PrimitiveType.VOID:
            if self.return_var is None:
                self.prototype_not_matched()
            if self.prototype.type != self.return_var.type:
                self.prototype_not_matched()
        elif self.return_var is not None:
            return False
        
        # List of pairs (Variable/Array, by_ref). 
        # by_ref is not parsed but deduced from the matched prototype.
        self.parameters = []
        
        # Checking the matching of all parameters.
        # If everything matched the parameters are inserted in self.parameters.
        if len(self.prototype.parameters) != len(match_tree["params"]):
            self.prototype_not_matched()
        
        for i in range(len(match_tree["params"])):
            proto_param = self.prototype.parameters[i]
            call_param = data_manager.get_variable(match_tree["params"][i])
            
            if call_param.type != proto_param.type:
                self.prototype_not_matched()
                
            if type(call_param) == Array:
                if proto_param.dim != call_param.dim:
                    self.prototype_not_matched()
            elif proto_param.dim != 0:
                self.prototype_not_matched()
            
            if type(call_param) == Array and not call_param.is_allocable():
                raise ValueError("The sizes of the array passed by parameter "
                                 "must be known.")
            if not proto_param.by_ref and not call_param.known:
                raise ValueError("The parameters not passed by reference must "
                                 "be known.")
                
            self.parameters.append((call_param, proto_param.by_ref))
        
    def prototype_not_matched():
        raise NameError("One of the calls does not match any prototype.")

class IOVariables:
    def __init__(self, match_tree, data_manager, is_input_or_output):
        self.variables = [data_manager.get_variable(var) for var in match_tree['variables']]
        if not all(type(var) == Variable for var in self.variables):
            raise SyntaxError("It is not possible to have both arrays and "
                              "variables on the same IO line. Furthermore, "
                              "arrays have to be denoted using the square "
                              "bracket notation.")
        
        if is_input_or_output == "output" and not all(var.known for var in self.variables):
            raise ValueError("Before writing a variable to output it must "
                             "have been assigned a value.")

class IOArrays:
    def __init__(self, match_tree, data_manager, is_input_or_output):
        self.arrays = [data_manager.get_variable(arr["name"]) for arr in match_tree['arrays']]
        if not all(type(arr) == Array for arr in self.arrays):
            raise SyntaxError("It is not possible to have both arrays and "
                              "variables on the same IO line. Furthermore, "
                              "arrays have to be denoted using the square "
                              "bracket notation.")
        
        self.sizes = self.arrays[0].sizes
            
        if not all(arr.sizes == self.sizes for arr in self.arrays):
            raise ValueError("Arrays read on the same line must have the same "
                             "type.")
            
        if not all(expr.is_known() for expr in self.sizes):
            raise ValueError("Before reading/writing an arrays, theirs sizes "
                             "must be known.")
            
        if is_input_or_output == "output" and not all(arr.known for arr in self.arrays):
            raise ValueError("Before writing an array to output it must have "
                             "been filled with values.")


# coef * var + const
class Expression:
    def __init__(self, match_tree, data_manager):
        if "const1" in match_tree: # Constant expression, just a number
            self.coef = 0
            self.var = None
            self.const = int(match_tree["const1"].replace(" ", "")) # Remove spaces
        else:
            self.coef = int(match_tree["coef"] if "coef" in match_tree else 1) 
            self.var = data_manager.get_variable(match_tree["variable"])
            if self.var.type not in [PrimitiveType.INT, PrimitiveType.LONGINT]:
                raise ValueError("Variables in expressions must be int or "
                                 "longint.") 
            self.const = int(match_tree["const2"].replace(" ", "") if "const2" in match_tree else 0)

    def to_string(self):
        res = ""
        if self.var==None:
            res += str(self.const)
            return res

        if self.coef == -1:
            res += "-"
        elif self.coef != -1 and self.coef != 1:
            res += str(self.coef) + "*"

        res += self.var.name

        if self.const != 0:
            if self.const>0:
                res+="+" + str(self.const)
            else:
                res+=str(self.const)
        return res
    
    def is_known(self):
        return self.var is None or self.var.known
    
    def __eq__(self, expr2):
        return (self.coef == expr2.coef and self.const == expr2.const and self.var == expr2.var)

    def __ne__(self, expr2):
        return not self.__eq__(expr2)
