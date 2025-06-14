import sys

_arg_value = {}

sys.argv.pop(0) # We don't need the executable name

while len(sys.argv):
    arg = sys.argv.pop(0)
    if arg in ('-jepson_usage',
               '-incomplete_keys',
               '-no_error_limit',
               '-without_cache',
               '-debug_js',
               '-steps',
               '-core'):
        _arg_value[arg] = True
    elif arg in ('-dir',
                 '-tree',
                 '-api',
                 '-api_expire',
                 '-api_delay',
                 '-ca'):
        if arg == '-ca':
            # Behave as if '-core -api' were specified,
            # including support for taxons to discard from the API cache.
            _arg_value['-core'] = True
            arg = '-api'

        if arg in ('-dir',
                   '-tree',
                   '-api_expire',
                   '-api_delay'):
            _arg_value[arg] = sys.argv.pop(0)
        else:
            _arg_value[arg] = True

        if arg in ('-tree',
                   '-api'):
            taxon_list = []
            while len(sys.argv) and not sys.argv[0].startswith('-'):
                if arg == '-tree' and sys.argv[0] in ('props', 'toxic'):
                    _arg_value[f'{arg}_{sys.argv[0]}'] = True
                    sys.argv.pop(0)
                else:
                    taxon_list.append(sys.argv.pop(0))
            if taxon_list:
                _arg_value[f'{arg}_taxon'] = taxon_list
    else:
        print(f'Argument not recognized: {arg}', file=sys.stderr)
        sys.exit(-1)

def arg(name):
    if name in _arg_value:
        return _arg_value[name]
    else:
        return None
