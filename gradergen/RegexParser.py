import re
import sys
import pprint
from gradergen.structures import PrimitiveType, Location

class RegexParser:
    # Join the argument in a regex accepting an arbitrary number of spaces
    # between each piece.
    def JoinRegex(self, *args):
        res = self.maybe_spaces
        for arg in args:
            res += arg + self.maybe_spaces
        return res
        
    # Creates a group with the given name containing the regex.
    def GroupName(self, regex, name):
        return "(?P<{0}>{1})".format(name, regex)
    
    # Remove all names from groups in the regex.
    # It is used internally to avoid name collision and to make MatchTree work 
    # properly.
    def RemoveNames(self, regex):
        return re.sub("\?P<" + self.name + ">", "", regex)
    
    # Creates a regex that matches repetition of 'regex' separated by the
    # given separator. There must be at least an occurence of 'regex'.
    def RepeatedSeparatedNonEmptyNoName(self, regex, separator):
        return self.RemoveNames(self.JoinRegex("(" + self.JoinRegex(regex, separator) + ")*", regex))
    
    # Generate a standard name, used by MatchTree, for repeated groups.
    # It encodes in the name both the regex_name and the separator.
    # Given that group names have to be proper python identifiers, the separator
    # is transformed before being included in the group name.
    def GenerateRepeatedGroupName(self, regex_name, separator, group_name = None):
        encoded_separator = "_".join([str(ord(char)) for char in separator])
        return "REPEATED" + self.repeated_divider.join([regex_name, encoded_separator, group_name])
    
    # Decode and parse information (regex and separator) from a group name
    # generated by GenerateRepeatedGroupName.
    def ParseRepeatedGroupName(self, group_name):
        regex_name, encoded_separator, group_name = group_name[8:].split(self.repeated_divider)
        separator = ''.join([chr(int(code)) for code in encoded_separator.split("_")])
        return regex_name, separator, group_name
    
    # Exactly as RepeatedSeparatedNonEmptyNoName but also gives a name to
    # the resulting regex using GenerateRepeatedGroupName.
    def RepeatedSeparatedNonEmpty(self, regex_name, separator, group_name):
        regex = getattr(self, regex_name)
        return self.GroupName(
            self.RepeatedSeparatedNonEmptyNoName(regex, separator), 
            self.GenerateRepeatedGroupName(regex_name, separator, group_name)
        )
    
    # As RepeatedSeparatedNonEmpty, but matching empty repetitions also.
    def RepeatedSeparated(self, regex_name, separator, group_name):
        regex = getattr(self, regex_name)
        return self.GroupName(
            "(" + self.maybe_spaces + "|" +
            self.RepeatedSeparatedNonEmptyNoName(regex, separator)
            +")",
            self.GenerateRepeatedGroupName(regex_name, separator, group_name)
        )
    
    # Match the full string against the regex, differently from re.match that
    # matches any prefix of the string.
    def FullMatch(self, regex_name, string):
        return re.match(getattr(self, regex_name)+"$", string)
    
    # Builds the matching tree (considering only named groups).
    # If needed calls itself recursively.
    # Repeated groups builded with RepeatedSeparated and RepeatedSeparatedNonEmpty
    # are handled ad-hoc. In the tree they corresponds to arrays of subtrees.
    def MatchTree(self, regex_name, string):
        match = self.FullMatch(regex_name, string)
        if not match:
            return None
        
        match_tree = {}
        for group_name in match.groupdict():
            # If the group is not matched. 
            # E.g. "ab(?P<group_name>c)?" matched against "ab".
            if match.group(group_name) is None:
                continue
            
            if group_name.startswith("REPEATED"):
                regex_name, separator, clean_group_name = self.ParseRepeatedGroupName(group_name)
                
                rep_groups = []
                string = match.group(group_name)
                for sub_string in re.split(separator, string):
                    sub_tree = self.MatchTree(regex_name, sub_string.strip())
                    if sub_tree:
                        rep_groups.append(sub_tree)
                match_tree[clean_group_name] = rep_groups
            else:
                match_tree[group_name] = match.group(group_name).strip()
        
        if not match_tree:
            return string
        else:
            return match_tree
    
    def __init__(self):
        # String used to separate the name from the separator in the
        # method GenerateRepeatedGroupName.
        self.repeated_divider = "_GRADERGEN_IS_COOL_"
        
        # This is the list of type specifiers (int, char,...).
        self.type_specifiers = [enum_element.value for enum_element in PrimitiveType]
        
        # All regexes needed to correctly parse task.spec are here defined.
        self.maybe_spaces = " *"
        self.type_ = "(" + "|".join(self.type_specifiers) + ")"
        self.type_non_void = "(" + "|".join(self.type_specifiers[1:]) + ")"
        self.name = "([a-zA-Z_][a-zA-Z_0-9]*)"
        self.array_no_sizes = self.GroupName(self.name, "name") + self.GroupName("(\[\])+", "dim")
        
        self.call = self.JoinRegex(
            "(" + self.JoinRegex(self.GroupName(self.name, "return_var"), "=") + ")?", 
            self.GroupName(self.name, "name"), 
            "\(", self.RepeatedSeparated("name", ",", "params"), "\)"
        )
        
        self.IO_variables = self.RepeatedSeparatedNonEmpty("name", " ", "variables")
        
        self.IO_arrays = self.RepeatedSeparatedNonEmpty("array_no_sizes", " ", "arrays")
        
        self.variable = self.JoinRegex(
            self.GroupName(self.type_non_void, "type"), 
            " ", 
            self.GroupName(self.name, "name")
        )
        
        # begin working on self.expression
        sign = "(\+|\-)"
        signed_number = self.JoinRegex(sign, "[0-9]+")
        number = self.JoinRegex("(" + sign + ")?", "[0-9]+")
        
        linear_expression_formats = [
            self.JoinRegex(
                "(" + self.JoinRegex(self.GroupName(number, "coef"), "\*") + ")?",
                self.GroupName(self.name, "variable")
            )
        ]
        linear_expression = "(" + "|".join(linear_expression_formats)+ ")"
        
        expression_formats = [
            self.GroupName(number, "const1"), # Group names must be different
            self.JoinRegex(
                linear_expression, 
                self.GroupName(signed_number, "const2")+"?"
            )
        ]
        self.expression = "(" + "|".join(expression_formats)+ ")"
        # end working on self.expression
        
        self.array = self.JoinRegex(
            self.GroupName(self.type_non_void, "type"), 
            " ", 
            self.GroupName(self.name, "name"), 
            "\[",
            self.RepeatedSeparatedNonEmpty("expression", self.JoinRegex("\]", "\["), "sizes"),
            "\]"
        )
        
        self.proto_param = self.JoinRegex(
            self.GroupName(self.type_non_void, "type"), 
            self.GroupName("( | &|& )", "by_ref"), 
            self.GroupName(self.name, "name"), 
            self.GroupName("(\[\])*", "dim"),
        )
        
        self.prototype = self.JoinRegex(
            self.GroupName(self.type_, "return_type"),
            self.GroupName(self.name, "name"), 
            "\(", self.RepeatedSeparated("proto_param", ",", "params"), "\)",
            "(\{" + self.GroupName(
                "(" + Location.SOLUTION.value + "|" + Location.GRADER.value + ")", 
                "location"
            ) + "\})?"
        )
    
    # Testing for the regexes
    def test(self):
        tests = {
            "name": {
                "valid": ["foo", "_foo_231bar123"],
                "invalid": ["", "foo ", " foo", "foo 123", "1foo", "foo'foo"]
            },
            
            "type_non_void": {
                "valid": self.type_specifiers[1:],
                "invalid": ["", " ", "int ", "foo", "int1", "1"]
            },
            
            "type_": {
                "valid": self.type_specifiers,
                "invalid": [" ", "int ", "foo", "int1", "1"]
            },
            
            "proto_param": {
                "valid": ["int foo", "longint foo123[][][]", "char & int[][]", "int int", "real& foo", "real &bar[]"],
                "invalid": ["int_foo", " int_foo", "  ", "int&foo[]", "int foo bar", "int& &foo", "int []foo", "int foo()", "foo int"]
            },
            
            "variable": {
                "valid": [],
                "invalid": []
            },
            
            "expression": {
                "valid": ["bar  ", " +  150   ", "150", " foo", "2 * foo", "-5 * foo", "foo + 15", "5*f123-10"],
                "invalid": ["15*15", "-foo", "123*foo -", "", "14 14", "foo + foo", "15 + foo", "foo * 15"]
            },
            
            "array": {
                "valid": ["  int    foo[N]", "   longint bar[N_  ]", "real foo [123][  2*N + 1][A - 123]"],
                "invalid": ["foo[N]", "int [N]", "int foo", "int foo[?]", "int foo[foo[N]]", "int foo(N)", "int foo[-bar+15]"]
            },
            
            "prototype": {
                "valid": ["  f () ", " real longint123_name_123(int &a[][][], longint& b, char &    _c32132 , longint d[]) {grader}"],
                "invalid": ["()", "int f(", "int f(int, &int)", "int f() {}", "int f() {grader"]
            }
        }
        
        for regex in tests:
            for string in tests[regex]["valid"]:
                if not self.FullMatch(regex, string):
                    sys.exit("(ERROR) Should match: " + regex + " " + string)
            for string in tests[regex]["invalid"]:
                if self.FullMatch(regex, string):
                    sys.exit("(ERROR) Should not match: " + regex + " " + string)
        
        pprint.PrettyPrinter(indent=4, width=150).pprint(self.MatchTree("prototype", tests["prototype"]["valid"][1]))
        print("\n\n\n")
        pprint.PrettyPrinter(indent=4, width=150).pprint(self.MatchTree("array", tests["array"]["valid"][2]))
        
