import sys

_arg_value = {}

sys.argv.pop(0) # We don't need the executable name

while len(sys.argv):
    if sys.argv[0] in ('-jepson_usage',
                       '-incomplete_keys',
                       '-no_error_limit',
                       '-without_cache',
                       '-debug_js',
                       '-steps'):
        _arg_value[sys.argv.pop(0)] = True
    elif sys.argv[0] in ('-dir',
                         '-tree'):
        _arg_value[sys.argv.pop(0)] = sys.argv.pop(1)
        tree_taxon_list = []
        while len(sys.argv) and not sys.argv[0].startswith('-'):
            if sys.argv[0] == 'props':
                sys.argv.pop(0)
                _arg_value['-tree_props'] = True
            else:
                tree_taxon_list.append(sys.argv.pop(0))
        if tree_taxon_list:
            _arg_value['-tree_taxon'] = ' '.join(tree_taxon_list)
    else:
        print(f'Argument not recognized: {sys.argv[0]}', file=sys.stderr)
        sys.exit(-1)

def arg(name):
    if name in _arg_value:
        return _arg_value[name]
    else:
        return None
