import sys

_former_prefix = None
_error_cnt = 0
_in_section = False
_delayed_cnt = 0 # is always 0 when _in_section is False

def warning(msg):
    print(msg, file=sys.stderr, flush=True)

# By default, errors are emitted as soon as detected, and duplicates are
# not removed.
#
# However, after error_begin_section() is called, errors with different
# prefixes are collated together.  Whatever error occurs first is allowed
# to emit immediately as it occurs, along with any other errors with the
# same prefix.  Errors with different prefixes are delayed and emitted
# after error_end_section() is called.
#
# Additionally, while within an error section, all duplicate errors are
# removed, whether the error was originally emitted immediately or delayed.
def error_begin_section():
    global _in_section, _stored_data, _delayed_cnt, _former_prefix

    if _in_section:
        error('error_begin_section() called when already in an error section')
        error_end_section()

    _in_section = True
    _stored_data = {} # only valid when _in_section is True
    _delayed_cnt = 0

    # The first message should always be emitted (not delayed) regardless
    # of its prefix.  We need a value different than None to indicate
    # this fresh start since None already has a meaning.
    _former_prefix = 'start'

def error_end_section():
    global _in_section, _delayed_cnt

    if not _in_section:
        error('error_end_section() called when not in an error section')
        return

    _in_section = False
    _delayed_cnt = 0

    for prefix in _stored_data.keys(): # not sorted because None causes problems
        for msg in sorted(_stored_data[prefix].keys()):
            if _stored_data[prefix][msg]: # 'delay' boolean
                _emit_error(msg, prefix)

def _emit_error(msg, prefix):
    global _former_prefix, _error_cnt

    if prefix:
        if prefix != _former_prefix:
            print(prefix, file=sys.stderr)
            _error_cnt += 1
        msg = '  ' + msg
    _former_prefix = prefix

    print(msg, file=sys.stderr, flush=True)
    _error_cnt += 1

def _check_error_cnt():
    if _error_cnt + _delayed_cnt >= 10:
        if _in_section:
            error_end_section()
        sys.exit('Too many errors')

def error(msg, prefix=None):
    global _error_cnt, _former_prefix, _delayed_cnt

    # When in a section of related errors, delay the msg as necessary
    # to avoid intermixing different prefixes.  Note that a valid
    # prefix can still be emitted when the former prefix is None, but
    # a new msg with prefix=None must be stored if there was a valid
    # former prefix.
    delay = (_in_section and
             _former_prefix != 'start' and
             prefix != _former_prefix)

    if _in_section:
        # When in a section of related errors, we *always* store the msg,
        # even if it is emitted right away.  This allows us to detect
        # duplicates.

        # If this is a duplicate message within this section, discard it.
        if prefix in _stored_data and msg in _stored_data[prefix]:
            return

        # Store the message along with the 'delay' boolean to indicate
        # whether it should be emitted later.
        if prefix not in _stored_data:
            _stored_data[prefix] = {}
            if delay and prefix:
                _delayed_cnt += 1
        _stored_data[prefix][msg] = delay
        if delay:
            _delayed_cnt += 1

    if not delay:
        _emit_error(msg, prefix)

    _check_error_cnt()

def error_end():
    if _error_cnt:
        sys.exit(_error_cnt)
