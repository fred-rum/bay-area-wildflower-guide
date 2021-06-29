import sys

_arg_value = {}

sys.argv.pop(0) # We don't need the executable name

while len(sys.argv):
    if (sys.argv[0] in ('-jepson_usage',
                        '-incomplete_keys',
                        '-no_error_limit',
                        '-not_top_usage',
                        '-without_cache',
                        '-debug_js',
                        '-steps') or
        sys.argv[0].startswith('-tree')):
        _arg_value[sys.argv.pop(0)] = True
    elif sys.argv[0] == '-dir':
        _arg_value[sys.argv.pop(0)] = sys.argv.pop(1)
    else:
        print(f'Argument not recognized: {sys.argv[0]}', file=sys.stderr)
        sys.exit(-1)

def arg(name):
    if name in _arg_value:
        return _arg_value[name]
    else:
        return None
