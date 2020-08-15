import sys

_error_cnt = 0
_former_prefix = None

def warning(msg):
    print(msg, file=sys.stderr, flush=True)

def error(msg, prefix=None):
    global _error_cnt, _former_prefix
    if prefix:
        if prefix != _former_prefix:
            print(prefix, file=sys.stderr)
            _error_cnt += 1
        msg = '  ' + msg
    _former_prefix = prefix

    print(msg, file=sys.stderr, flush=True)

    _error_cnt += 1
    if _error_cnt >= 10:
        sys.exit('Too many errors')

def end():
    if _error_cnt:
        sys.exit(_error_cnt)
