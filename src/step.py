# My files
from args import *
from error import *
from page import *

def print_trees():
    step = arg('-tree')
    tree_taxon = arg('-tree_taxon')
    if tree_taxon:
        print(f'### selected taxon(s) after step {step} ###')
        for taxon in tree_taxon:
            page = find_page1(taxon)
            if page:
                page.print_tree()
            else:
                error(f'-tree taxon "{taxon}" not found.')
    else:
        print(f'### Known taxons after step {step} ###')
        exclude_set = set()
        for page in full_page_array:
            if not page.parent and not page.linn_parent:
                page.print_tree(exclude_set=exclude_set)
    sys.stdout.flush()

# a class that supports code like this:
#   with Step(keyword, msg):
#     do stuff
#
# Perform one "step" of the script.
# If specified by an arg, print the steps as they occur.
# If an error occurs, print the step where it happened.
# If specified by an arg, print the page hierarchy at the end of the step.
class Step(Progress):
    def __init__(self, keyword, msg):
        self.__keyword = keyword
        self.__msg = msg
        super().__init__(msg)

    def __enter__(self):
        if arg('-steps'):
            info(f'Step {self.__keyword}: {self.__msg}')
        super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_val and arg('-tree') == self.__keyword:
            print_trees()
        super().__exit__(exc_type, exc_val, exc_tb)
