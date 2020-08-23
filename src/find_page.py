# My files
from error import *

name_page = {} # original page name -> page [final file name may vary]
com_page = {} # common name -> page (or 'multiple' if there are name conflicts)
sci_page = {} # scientific name -> page
isci_page = {} # iNaturalist scientific name -> page (only where it differs)

def is_sci(name):
    # If there isn't an uppercase letter anywhere, it's a common name.
    # If there is an uppercase letter somewhere, it's a scientific name.
    # E.g. "Taraxacum officinale" or "family Asteraceae".
    return not name.islower()

def strip_sci(sci):
    sci_words = sci.split(' ')
    if (len(sci_words) >= 2 and
        sci_words[0][0].isupper() and
        sci_words[1][0] == 'X'):
        sci_words[1] = sci_words[1][1:]
        sci = ' '.join(sci_words)
    if len(sci_words) == 4:
        # Four words in the scientific name implies a subset of a species
        # with an elaborated subtype specifier.  The specifier is stripped
        # from the 'sci' name.
        return ' '.join((sci_words[0], sci_words[1], sci_words[3]))
    elif len(sci_words) == 2:
        if sci_words[1] == 'spp.':
            # It is a genus name in elaborated format.  The 'spp.' suffix is
            # stripped from the 'sci' name.
            return sci_words[0]
        elif sci[0].islower():
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
def find_page2(com, sci):
    if sci:
        sci = strip_sci(sci)
        if sci in sci_page:
            return sci_page[sci]

    if com:
        page = None
        if com in name_page:
            page = name_page[com]
        elif com in com_page and com_page[com] != 'multiple':
            page = com_page[com]

        if page:
            if sci and page.sci and page.sci != sci:
                # If the common name matches a page with a different
                # scientific name, it's treated as not a match.
                return None
            else:
                return page

    return None

def find_page1(name):
    if is_sci(name):
        return find_page2(None, name)
    else:
        return find_page2(name, None)
