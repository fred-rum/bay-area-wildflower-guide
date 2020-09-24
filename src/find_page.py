import re

# My files
from error import *

name_page = {} # original page name -> page [final file name may vary]
com_page = {} # common name -> page (or 'multiple' if there are name conflicts)
sci_page = {} # scientific name -> page
isci_page = {} # iNaturalist scientific name -> page (only where it differs)

glossary_name_dict = {} # glossary name -> glossary instance

def is_sci(name):
    # If there isn't an uppercase letter anywhere, it's a common name.
    # If there is an uppercase letter somewhere, it's a scientific name.
    # E.g. "Taraxacum officinale" or "family Asteraceae".
    return not name.islower()

# Strip elaborations off the scientific name.
# If keep specified, keep certain elaborations:
# x - X hybrid indication
# b - var. or ssp.
# g - spp.
# r - rank
def strip_sci(sci, keep=''):
    if 'x' not in keep and sci[0].isupper():
        sci = re.sub(' X', ' ', sci)
    sci_words = sci.split(' ')
    if len(sci_words) == 4:
        # Four words in the scientific name implies a subset of a species
        # with an elaborated subtype specifier.  The specifier is stripped
        # from the 'sci' name.
        if 'b' not in keep:
            return ' '.join((sci_words[0], sci_words[1], sci_words[3]))
    elif len(sci_words) == 2:
        if sci_words[1] == 'spp.' and 'g' not in keep:
            # It is a genus name in elaborated format.  The 'spp.' suffix is
            # stripped from the 'sci' name.
            return sci_words[0]
        elif sci[0].islower() and 'r' not in keep:
            # The name is in {type} {name} format (e.g. "family Phrymaceae").
            # Strip the type from the 'sci' name.
            return sci_words[1]
    # The name is already in a fine stripped format.
    return sci

def elaborate_sci(sci):
    sci_words = sci.split(' ')
    if len(sci_words) == 1:
        # One word in the scientific name implies a genus.
        return ' '.join((sci, 'spp.'))
    elif len(sci_words) == 3:
        # Three words in the scientific name implies a subset of a species.
        # We probably got this name from an iNaturalist observation, and it
        # doesn't have an explicit override, so we can only assume "ssp."
        return ' '.join((sci_words[0], sci_words[1], 'ssp.', sci_words[2]))
    # The name is already in a fine elaborated format.
    return sci

# Find a page using by common name and/or scientific name.
#
# If com and elab are both valid, and the search finds a page with either name
# (with priority on the scientific name).  If the scientific name is found
# but the common name differs, that still counts as a match, and the existing
# common name is retained.  (Not all sources agree on common names.)
#
# If only one of com/elab is valid, then we search for the corresponding name
# without any extra frills.
def find_page2(com, sci, from_inat=False):
    page = None

    if sci:
        sci = strip_sci(sci)
        if from_inat and sci in isci_page:
            page = isci_page[sci]
        elif sci in sci_page:
            # If the scientific name matches, we consider it a match
            # regardless of the common name.
            page = sci_page[sci]
        else:
            # Otherwise, search for a page that only has the common name
            # and doesn't (yet) have a scientific name.
            pass

    if not page:
        if com in com_page:
            if isinstance(com_page[com], int):
                # We can't determine the page from the common name alone
                # due to conflicts.  However, that doesn't mean we need to
                # flag an error.  When we return 'page = None', in most
                # cases the caller will then create a new page, which could
                # succeed (e.g. if a scientific name is supplied) or flag its
                # own error if the name conflict really is terminal.
                pass
            else:
                page = com_page[com]

                if sci and page.sci:
                    # If the common name matches a page with a different
                    # scientific name, it's treated as not a match.
                    page = None

    if page:
        if sci:
            page.set_sci(sci, from_inat=from_inat)
        if com:
            page.set_com(com, from_inat=from_inat)

    return page

def find_page1(name):
    if is_sci(name):
        return find_page2(None, name)
    else:
        return find_page2(name, None)
