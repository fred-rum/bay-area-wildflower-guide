import re
import datetime

# My files
from error import *
from rank import *

name_page = {} # original page name -> page [final file name may vary]
com_page = {} # common name -> page (or 'multiple' if there are name conflicts)
sci_page = {} # scientific name *or* elaborated name -> page
isci_page = {} # iNaturalist scientific name -> page (only where it differs)
cpsci_page = {} # CalPoison scientific name -> page (only where it differs)
gsci_page = {} # gallformers code (without genus) -> page
asci_page = {} # alternative scientific name -> page
taxon_id_page = {} # iNaturalist taxon ID -> page

glossary_name_dict = {} # glossary name -> glossary instance

def is_sci(name):
    # If there isn't an uppercase letter anywhere, it's a common name.
    # If there is an uppercase letter somewhere, it's a scientific name.
    # E.g. "Taraxacum officinale" or "family Asteraceae".
    return not name.islower() or name.startswith(('ssp. ', 'var. ', 'f. '))

def is_elab(name):
    return is_sci(name) and ' ' in name

# Strip elaborations off the scientific name.
# If keep is specified, keep certain elaborations:
# x - X hybrid indication
# b - ssp., var., or f.
# g - spp.
# r - rank
def strip_sci(sci, keep=''):
    if 'x' not in keep and sci[0].isupper():
        # Remove the 'X' hybrid indicator.
        sci = re.sub(' X', ' ', sci)

    sci_words = sci.split(' ')

    if (len(sci_words) == 4 and
        sci_words[2] in ('ssp.', 'var.', 'f.') and
        'b' not in keep):
        # The name includes an 'ssp.', 'var.', 'f.' specifier.
        # The specifier is stripped from the 'sci' name.
        return ' '.join((sci_words[0], sci_words[1], sci_words[3]))
    elif len(sci_words) == 2 and sci_words[1] == 'spp.' and 'g' not in keep:
        # It is a genus name in elaborated format.  The 'spp.' suffix is
        # stripped from the 'sci' name.
        return sci_words[0]
    elif sci_words[0] in rank_set and 'r' not in keep:
        # The name is in {rank} {name} format (e.g. "family Phrymaceae").
        # Strip the rank from the 'sci' name.
        return ' '.join(sci_words[1:])

    # The name is already in a fine stripped format.
    return sci

def elaborate_sci(sci):
    if sci[0].islower():
        # If the first word is a rank, don't touch the rest of it.
        return sci

    sci_words = sci.split(' ')
    if len(sci_words) == 1:
        # If the user fails to specify a rank, we assume 'genus'.
        # (iNaturalist always specifies a rank, even if only a guess.)
        return 'genus ' + sci
    elif len(sci_words) == 3:
        # Three words in the scientific name implies a subset of a species.
        # We probably got this name from an iNaturalist observation, and it
        # doesn't have an explicit override, so we can only assume "ssp."
        return ' '.join((sci_words[0], sci_words[1], 'ssp.', sci_words[2]))
    # The name is already in a fine elaborated format.
    return sci

# I allow input formatted as either "genus <Genus>" or "<Genus> spp.",
# but the former is the preferred internal and output format.
def fix_elab(elab):
    if elab and elab.endswith(' spp.'):
        elab = 'genus ' + elab[:-5]
    return elab

# Find a page by its taxon_id (as a string, despite its numeric appearance).
# taxon_id may be None, in which case we expect to also return None.
def find_taxon_id(taxon_id):
    if taxon_id in taxon_id_page:
        return taxon_id_page[taxon_id]
    else:
        return None

# Find a page by its common name.
# com may be None, in which case we expect to also return None.
def find_com(com):
    if com in name_page and name_page[com].no_names:
        return name_page[com]
    elif com in com_page:
        page = com_page[com]

        if isinstance(com_page[com], int):
            # We can't determine the page from the common name alone
            # due to conflicts.
            # We return None to indicate that we don't have a positive match,
            # and the caller is likely to try to create a new page.
            # If the caller has a scientific name (which presumably also
            # didn't find a match), then it should be able to successfully
            # create the new page.
            # Otherwise, the page creation will fail with a useful message.
            return None
        else:
            return page
    else:
        return None

# Find a page by its scientific or elaborated name.
# elab may be None, in which case we expect to also return None.
def find_sci(elab, from_inat=False):
    if elab is None:
        return None

    elab = fix_elab(elab)
    sci_words = elab.split(' ')
    if len(sci_words) == 3 and sci_words[0] in rank_set:
        # We never allow a ranked binomial name to index a page using its
        # stripped name.
        sci = elab
    else:
        sci = strip_sci(elab)

    if from_inat and elab in isci_page:
        page = isci_page[elab]
    elif from_inat and sci in isci_page:
        page = isci_page[sci]
    elif elab in name_page and name_page[elab].no_names:
        page = name_page[elab]
    elif elab in sci_page:
        page = sci_page[elab]

        if page == 'conflict':
            # If there's a 'conflict', it's presumably because elab
            # is actually a stripped scientific name, and there are
            # multiple taxons that have the same name at different ranks.
            # We return None to indicate that we don't have a positive match.
            # The caller may have a common name which disambiguates.
            # Or the caller might try to create a new page with this
            # scientific name, which will fail with a useful message.
            return None
    elif sci in name_page and name_page[sci].no_names:
        page = name_page[sci]
    elif sci in sci_page:
        page = sci_page[sci]

        if page == 'conflict':
            # We're looking for a page using a fully elaborated name,
            # but instead we found multiple pages that match the
            # stripped name at ranks that don't match what we're
            # looking for.  So that's not a match.
            # The caller will likely create a new page with this
            # elaborated name, which will be fine.
            return None

        # Since we found sci in sci_page, but we didn't find elab in sci_page,
        # the page that we found must have a scientific name but either
        # doesn't have an elaborated name or has a *different* elaborated
        # name.  And since we didn't find elab in sci_page, elab must be
        # different than sci, which implies that elab is truly elaborated.
        if elab != page.elab and page.elab_src == 'elab':
            # We're looking for a page using a fully elaborated name,
            # and we've found a page that has a fully elaborated name,
            # but the elaborated names aren't the same.
            if sci != page.sci:
                # The stripped names are different, which means the
                # sci_page lookup must have gone through an alternative
                # scientific name, which counts as a valid match.
                pass
            else:
                if page.rank is Rank.below:
                    # If the found page's elaborated name is a subspecies,
                    # variety, or form, then the search name must be a
                    # different type.
                    error(f'Conflict between {page.elab} and {elab}')
                else:
                    # The scientific name matches, but the ranks are
                    # different.  That doesn't count as a match.
                    pass
                    page = None
        else:
            # We're looking for a page using a fully elaborated name,
            # and we found a page that doesn't know its elaborated
            # name, but its stripped name matches.  That's good enough,
            # and we count it as a match.
            pass
    else:
        page = None

    if page and not page.no_names:
        # We might have an elaboration where the page only had a scientific
        # name before.  set_sci() will improve the page information if
        # possible.
        page.set_sci(elab, from_inat=from_inat)

    return page

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
def find_page2(com, elab, from_inat=False, taxon_id=None,
               src='unknown', date=None):
    elab = fix_elab(elab)

    if com and not elab and com in name_page:
        # return the page without attempting to (re)set the com name
        return name_page[com]

    # taxon_id has first priority.
    page = find_taxon_id(taxon_id)

    if not page:
        page = find_sci(elab, from_inat)

    if not page:
        page = find_com(com)

        # If the common name matches a page with a different
        # scientific name, it's treated as not a match.
        # Note that if we're here, we already know that we didn't find
        # a match on the scientific name.  So if there are two scientific
        # names to be compared, they must mismatch.  (But if we don't have
        # a scientific name to search for or the page doesn't have an
        # associated scientific name, then that counts as a valid match.)
        if page and elab and (page.sci or (page.no_sci and elab != 'n/a')):
            page = None

    # Update (if appropriate) any names that are new or different.
    if page:
        if elab:
            page.set_sci(elab, from_inat=from_inat)
        if com:
            # Don't set the common name if the taxon_id doesn't match
            # (because the page already had a taxon id, and iNaturalist
            # observations can't always distinguish between among ranks).
            if taxon_id and taxon_id != page.taxon_id:
                pass
            else:
                page.set_com(com, from_inat=from_inat, src=src)

        # Only set the taxon_id if there was a match on the common name,
        # the scientific name, or on the alternative iNaturalist scientific
        # name.  I.e. do *not* set the taxon_id if there was a match on an
        # alternative scientific name.
        if taxon_id and strip_sci(elab) not in asci_page:
            page.set_taxon_id(taxon_id, from_obs=from_inat,
                              src=src, date=date)

    return page

def find_page1(name, from_inat=False):
    if name in name_page:
        # return the page without attempting to (re)set the com name
        return name_page[name]

    page = find_sci(name, from_inat)

    if not page:
        page = find_com(name)

    return page

# Since find_page2() needs a date which is commonly "now", we provide
# a convenience function for it.
now_at_start = datetime.datetime.now(datetime.timezone.utc)
def now():
    return now_at_start
