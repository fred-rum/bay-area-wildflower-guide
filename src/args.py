import sys

_arg_value = {}

sys.argv.pop(0) # We don't need the executable name

while len(sys.argv):
    if sys.argv[0] in ('-jepson_usage',
                       '-incomplete_keys',
                       '-no_error_limit',
                       '-not_top_usage'):
        _arg_value[sys.argv[0]] = True
    
    sys.argv.pop(0)

def arg(name):
    if name in _arg_value:
        return _arg_value[name]
    else:
        return None
