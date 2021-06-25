import re

# My files
from error import *

name_page = {} # original page name -> page [final file name may vary]
com_page = {} # common name -> page (or 'multiple' if there are name conflicts)
sci_page = {} # scientific name *or* elaborated name -> page
isci_page = {} # iNaturalist scientific name -> page (only where it differs)
taxon_id_page = {} # iNaturalist taxon ID -> page

glossary_name_dict = {} # glossary name -> glossary instance

def is_sci(name):
    # If there isn't an uppercase letter anywhere, it's a common name.
    # If there is an uppercase letter somewhere, it's a scientific name.
    # E.g. "Taraxacum officinale" or "family Asteraceae".
    return not name.islower()

def is_elab(name):
    return is_sci(name) and ' ' in name

# Strip elaborations off the scientific name.
# If keep is specified, keep certain elaborations:
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
        return 'genus ' + sci
    elif len(sci_words) == 3:
        # Three words in the scientific name implies a subset of a species.
        # We probably got this name from an iNaturalist observation, and it
        # doesn't have an explicit override, so we can only assume "ssp."
        return ' '.join((sci_words[0], sci_words[1], 'ssp.', sci_words[2]))
    # The name is already in a fine elaborated format.
    return sci

# I allow input of formatted as either "genus <Genus>" or "<Genus> spp.",
# but the former is the preferred internal and output format.
def fix_elab(elab):
    if elab and elab.endswith(' spp.'):
        elab = 'genus ' + elab[:-5]
    return elab

# Find a page using by common name and/or scientific name and/or taxon_id.
#
# taxon_id isn't used very often, but it has priority when used.
#
# If com and elab are both valid, the search finds a page with either name
# (with priority on the scientific name).
#
# Once a page is found, its names are updated with any new names supplied
# to find_page2.  E.g. if the scientific name matches, a common name can
# be added to the page, or if the page already has a common name, an
# alternative name can be recorded.
#
# If only one of taxon_id/com/elab is valid, then we search for the
# corresponding name without any extra frills.
def find_page2(com, elab, from_inat=False, taxon_id=None):
    page = None

    elab = fix_elab(elab)

    # taxon_id has first priority.
    if taxon_id in taxon_id_page:
        page = taxon_id_page[taxon_id]

    # sci has second priority.
    if not page and elab:
        sci = strip_sci(elab)
        if from_inat and elab in isci_page:
            page = isci_page[elab]
        elif from_inat and sci in isci_page:
            page = isci_page[sci]
        elif elab in sci_page:
            # If the scientific name matches, we consider it a match
            # regardless of the common name.
            page = sci_page[elab]
        elif sci in sci_page:
            page = sci_page[sci]
            if elab != sci:
                if page == 'conflict':
                    # We're looking for a page using a fully elaborated name,
                    # but instead we found multiple pages that match the
                    # stripped name at ranks that don't match what we're
                    # looking for.  So that's not a match.
                    page = None
                elif page.elab_src == 'elab' and elab != page.elab:
                    # We're looking for a page using a fully elaborated name,
                    # and we've found a page that has a fully elaborated name,
                    # but the elaborated names aren't the same.
                    if sci != page.sci:
                        # The stripped names are different, which means the
                        # sci_page lookup must have gone through an alternative
                        # scientific name, which counts as a valid match.
                        pass
                    else:
                        # The scientific name matches, but the ranks are
                        # different.  That doesn't count as a match.
                        page = None
                else:
                    # We're looking for a page using a fully elaborated name,
                    # and we found a page that doesn't know its elaborated
                    # name, but its stripped name matches.  That's good enough,
                    # and we count it as a match.
                    pass
        else:
            # Otherwise, search for a page that only has the common name
            # and doesn't (yet) have a scientific name.
            pass

        if page == 'conflict':
            if com:
                fatal(f'{com}:{elab} matches multiple pages with the same scientific name at different ranks')
            else:
                fatal(f'{elab} matches multiple pages with the same scientific name at different ranks')

    # com has last priority.
    if not page and com in com_page:
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

            if elab and page.sci:
                # If the common name matches a page with a different
                # scientific name, it's treated as not a match.
                page = None

    # Update (if appropriate) any names that are new or different.
    if page:
        if taxon_id:
            page.set_taxon_id(taxon_id)
        if elab:
            page.set_sci(elab, from_inat=from_inat)
        if com:
            page.set_com(com, from_inat=from_inat)

    return page

def find_page1(name, from_inat=False):
    if is_sci(name):
        return find_page2(None, name, from_inat)
    else:
        return find_page2(name, None, from_inat)
