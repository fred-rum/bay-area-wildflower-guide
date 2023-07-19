# Handle errors, warnings, and similar messages.
#
# The script keeps this code up to date with what it is doing so that
# if something bad happens, an message can be printed that will help
# the user diagnose the problem.  "Something bad" could be a deliberate
# call to the error handler, or it could be an uncaught exception.
#
# The messages about script progress can be nested, e.g.
#  While reading observations.csv
#   processing line 327: silver bush lupine (Lupinus albifrons)
#    adding Lupinus albifrons as a Linnaean descendent of subfamily Epidendroideae
#     error: bad rank order:
#      Linnaean parent: subfamily Epidendroideae [taxonomy from observations.csv]
#      Linnaean child:  orchid family (genus Orchidaceae) [child of flowering plants.txt] (rank genus)
#
# If there are multiple messages (i.e. for warnings or non-fatal errors),
# don't repeat any parts of the progress that were already printed.
# Also, suppress duplicate messages regardless of script progress.
#
# There is a maximum count of non-fatal errors, after which the script will
# fail.  The script will also fail at the end of a section if there were any
# non-fatal errors in that section.  That way, multiple similar errors can be
# printed, but the script won't continue and then potentially run into more
# problems that might not make sense in light of the previous errors.

import sys
import traceback

# My files
from args import *

progress_msg_list = [] # stack of strings describing what is being processed
progress_printed_cnt = 0 # depth of stack already printed
progress_printed_msgs = set() # record of previous message for duplicate detection
error_cnt = 0 # count of non-fatal errors in the current section

def indent():
    return ' ' * progress_printed_cnt

# info() and warn() don't write the current progress (for now)
# because the existing messages seem sufficient.  Perhaps I'll add a
# variation of these functions later if progress is sometimes needed.
#
# Even though these functions don't write the current progress, they
# still indent appropriately if the progress was already printed
def info(msg):
    print(indent() + msg, flush=True)

def warn(msg):
    sys.stdout.flush()
    print(indent() + msg, file=sys.stderr, flush=True)

def warn_progress():
    global progress_printed_cnt

    if len(progress_msg_list) > progress_printed_cnt:
        # Skip any progress messages that were already printed
        progress_list_to_print = progress_msg_list[progress_printed_cnt:]
        warn('\n'.join(progress_list_to_print))
        progress_printed_cnt = len(progress_msg_list)

def fail_on_errors(max):
    if error_cnt >= max:
        warn_progress()
        warn(msg)
        sys.exit(error_cnt)

def error(msg):
    warn_progress()
    warn(indent() + msg)
    error_cnt += 1
    if not arg('-no_error_limit'):
        fail_on_errors(10)

def fatal(msg):
    error(msg)
    sys.exit(-1)

# a class that supports code like this:
#   with Progress(msg):
#     do stuff
#
# This does stuff with the progress message in context
# so that it can be printed in the case of an error or exception.
class Progress:
    def __init__(self, msg):
        fail_on_errors(1)

        indented_msg = indent() + msg
        progress_msg_list.append(indented_msg)

    def __enter__(self):
        pass

    # __exit__ gets called with values in the last three arguments
    # if there was an Exception, or None if the 'with' context ended cleanly.
    # Be careful here!  An exception in this handler currently disappears
    # entirely, and I haven't bothered to figure out why.
    def __exit__(self, exc_type, exc_val, exc_tb):
        global progress_printed_cnt

        if isinstance(exc_val, SystemExit):
            # Allow a SystemExit exception caued by sys.exit()
            # to fall cleanly through the exception handlers
            # until the program exits.
            return False
        elif exc_val:
            # An exception has occurred
            warn_progress()

            trace_str = indent() + indent().join(traceback.format_exception(exc_type, exc_val, exc_tb))
            warn(trace_str)

            sys.exit(-1)
        else:
            # The "with" context ended without an exception.
            fail_on_errors(1)

            progress_msg_list.pop()
            if progress_printed_cnt > len(progress_msg_list):
                progress_printed_cnt = len(progress_msg_list)

            return True

# with Progress('msg 1'):
#     try:
#         with Progress('msg 2'):
#             1/0
#     except:
#         print('here be clean up')
#         sys.exit(1)
