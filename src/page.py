import re
import yaml
import io
from operator import attrgetter
from unidecode import unidecode # ? from https://pypi.org/project/Unidecode/

# My files
from error import *
from files import *
from photo import *
from find_page import *
from rank import *
from obs import *
from easy import *
from glossary import *
from parse import *
from cache import *

###############################################################################

full_page_array = [] # array of both real and shadow pages
page_array = [] # array of real pages; only appended to; never otherwise altered
genus_page_list = {} # genus name -> list of pages in that genus
genus_family = {} # genus name -> family name

# The default_ancestor page can apply properties to any pages that otherwise
# can't find an ancestor with 'is_top' declared.
default_ancestor = None

trie = Trie([x.name for x in Rank])
ex = trie.get_pattern()
re_group = re.compile(rf'\s*({ex}):\s*(.+?)\s*$')

group_child_set = {} # rank -> group -> set of top-level pages in group
for rank in Rank:
    group_child_set[rank] = {}

traits = set()

# Each props value can be either a set of allowable property types (e.g. 'do')
# or an abbreviation (e.g. 'd').
props = {
    'create': 'd',
    'link': 'd',
    'member_link': 'd',
    'member_name': 'd',
    'no_sci': 'f',
    'no_com': 'f',
    'obs_requires_photo': 'f',
    'photo_requires_bugid': 'f',
    'one_child': 'f',
    'obs_promotion': 'df',
    'casual_obs_promotion': 'd',
    'outside_obs_promotion': 'd',
    'obs_promotion_above_peers': 'f',
    'obs_promotion_without_x': 'f',
    'casual_obs': 'd',
    'outside_obs': 'd',
    'obs_fill_com': 'df',
    'obs_fill_sci': 'df',
    'obs_fill_alt_com': 'df',
    'link_inaturalist': 'd',
    'link_calflora': 'd',
    'link_calphotos': 'd',
    'link_jepson': 'd',
    'link_birds': 'd',
    'link_bayarea_calflora': 'd',
    'link_bayarea_inaturalist': 'd',
    'default_completeness': set(('do', 'caution', 'warn', 'error')),
}

###############################################################################

# Prepare a list of properties that can be applied.
# The initial list is in props, above.
# We extend it with additional properties for each defined trait.
# Finally, we unroll the type abbreviations and generate a regular expression
# to search for properties.
def init_props():
    global prop_re

    for trait in traits:
        props[f'photo_requires_{trait}'] = 'f'
        props[f'{trait}_requires_photo'] = 'f'

    for prop in props:
        action_set = props[prop]
        if isinstance(action_set, str):
            action_str = action_set
            action_set = set()
            if 'd' in action_str:
                action_set.add('do')
            if 'f' in action_str:
                action_set.update({'warn', 'error'})
            props[prop] = action_set

    prop_re = '|'.join(props.keys())

def get_default_ancestor():
    return default_ancestor

def sort_pages(page_set, trait=None, value=None,
               with_depth=False, with_count=True):
    # helper function to sort by name
    def by_name(page):
        if page.com:
            if page.sci:
                # Since some pages may have the same common name, use the
                # scientific name as a tie breaker to ensure a consistent order.
                return page.com.lower() + '  ' + page.sci.lower()
            else:
                # If the page has no scientific name, then presumably it
                # doesn't share its common name with any other pages.
                return page.com.lower()
        else:
            return page.sci.lower()

    # helper function to sort by hierarchical depth (parents before children)
    def by_depth(page):
        if not page.parent:
            return 0

        parent_depth = 0
        for parent in page.parent:
            parent_depth = max(parent_depth, by_depth(parent))
        return parent_depth + 1

    # helper function to sort by rank.
    # Return the key as a tuple
    # so that unranked pages can be sorted relative to ranked pages.
    # The second tuple is 1 for a ranked page and 0 for an unranked page
    # so that the ranked page acts like a slightly lower-ranked page.
    def by_rank(page):
        if page.rank:
            return (page.rank, 1)
        elif page.linn_parent:
            # the Linnaean parent always has a rank
            return (page.linn_parent.rank, 0)
        else:
            return (Rank.kingdom, 2) # behaves a higher rank than 'kingdom'

        parent_depth = 0
        for parent in page.parent:
            parent_depth = max(parent_depth, by_depth(parent))
        return parent_depth + 1

    # helper function to sort by observation count, using the nonlocal
    # variables of trait and value.
    def count_flowers_helper(page):
        return page.count_flowers(trait, value)

    # Sort multiple times.  Each sort breaks ties by retaining the order
    # from the previous sort, so the sorts are performed in order from least
    # priority to most priority.

    # Start by sorting match_set sorted alphabetically.
    # The alphabetic tie breaker may or may not be useful to the user,
    # but it prevents random differences every time the script is run
    # just because the dictionary hashes differently.
    page_list = sorted(page_set, key=by_name)

    # If requested, sort by rank (higher rank first).
    # For unranked pages, use the rank of its linnaean parent to indicate
    # where the unranked page should be sorted.
    # But in case of a hierarchy of unranked pages,
    # sort by depth among themselves.
    if with_depth:
        page_list.sort(key=by_depth)
        page_list.sort(key=by_rank, reverse=True)

    # Sort by observation count, from most to least.
    if with_count:
        page_list.sort(key=count_flowers_helper, reverse=True)

    return page_list

# Split a string at commas and remove whitespace around each element.
def split_strip(txt):
    return [x.strip() for x in txt.split(',')]

# Split a string that may contain quoted or unquoted parts.
# The string is split at commas,
#   provided that the comma is not within a quoted part.
# Whitespace at the beginning and end of each comma-separated part is removed.
def split_strip_quoted(txt):
    list = []
    s = txt.strip()
    while (s):
        if s.startswith('"'):
            end = s.find('"', 1)
            if end >= 0:
                list.append(s[1:end])
                s = s[end+1:].strip()
                if s == '':
                    # no more string parts
                    pass
                elif s.startswith(','):
                    s = s[1:].strip()
                else:
                    error(f'garbled list: {txt}')
                    return list
            else:
                error(f'garbled list: {txt}')
                return list
        else:
            end = s.find(',')
            if end >= 0:
                list.append(s[:end].strip())
                s = s[end+1:].strip()
            else:
                list.append(s)
                s = ''

    return list

# Check if two names are equivalent when applying a particular plural rule.
def plural_rule_equiv(a, b, end_a, end_b):
    if a.endswith(end_a) and b.endswith(end_b):
        base_len_a = len(a) - len(end_a)
        base_len_b = len(b) - len(end_b)
        if base_len_a == base_len_b and a[:base_len_a] == b[:base_len_b]:
            return True
    return False

# Check if two common names are equivalent.
# If one is plural and the other is not, then they are considered equivalent.
# Special characters (e.g. not letters) are ignored.
def plural_equiv(a, b):
    # Remove non-word characters such as - or '
    a = re.sub(r'\W', '', a)
    b = re.sub(r'\W', '', b)

    # plural rules from https://www.grammarly.com/blog/plural-nouns/
    for end_a, end_b in (('', ''),       # no plural difference
                         ('', 's'),      # cats
                         ('s', 'ses'),   # truss
                         ('sh', 'shes'), # marsh
                         ('ch', 'ches'), # lunch
                         ('x', 'xes'),   # tax
                         ('z', 'zes'),   # blitz
                         ('s', 'sses'),  # fez
                         ('z', 'zzes'),  # gas
                         ('f', 'ves'),   # wolf
                         ('fe', 'ves'),  # wife
                         ('y', 'ies'),   # city
                         ('o', 'oes'),   # potato
                         ('us', 'i'),    # cactus
                         ('is', 'es'),   # analysis
                         ('on', 'a')):   # phenomenon
        if (plural_rule_equiv(a, b, end_a, end_b) or
            plural_rule_equiv(a, b, end_b, end_a)):
            return True
    return False

def format_elab(elab, ital=True):
        if ital:
            i0, i1 = '<i>', '</i>'
        else:
            i0, i1 = '', ''

        if not elab:
            return None
        elif elab == 'n/a':
            return elab
        elif elab[0].islower() and ' ' in elab:
            (gtype, name) = elab.split(' ', maxsplit=1)
            return f'{gtype} {i0}{name}{i1}'
        elif elab.endswith(' spp.'):
            (genus, spp) = elab.split(' ')
            return f'{i0}{genus}{i1} spp.'
        else:
            if elab[0].isupper():
                elab = re.sub(' X', ' &times; ', elab)
            elab = f'{i0}{elab}{i1}'
            elab = re.sub(r' ssp\. ', f'{i1} ssp. {i0}', elab)
            elab = re.sub(r' var\. ', f'{i1} var. {i0}', elab)
            return elab

# Compare two 'x' specifications (at the genus level or above).
def looser_complete(one, two):
    if one == None:
        return None
    elif one not in ('ba', 'ca', 'any', 'hist', 'rare', 'hist/rare'):
        # free text is treated the same as 'more'
        if two is None:
            return two # two is looser

        else:
            return one # one is looser or equally loose
    elif one == 'hist/rare':
        if two in (None, 'more'):
            return two
        else:
            return one
    elif one in ('hist', 'rare'):
        if two in (None, 'more', 'hist/rare'):
            return two
        elif two in ('hist', 'rare') and two != one:
            return 'hist/rare' # special case
        else:
            return one
    elif one == 'ba':
        if two in (None, 'more', 'hist/rare', 'hist', 'rare'):
            return two
        else:
            return one
    elif one == 'ca':
        if two in (None, 'more', 'hist/rare', 'hist', 'rare', 'ba'):
            return two
        else:
            return one
    elif one == 'any':
        if two in (None, 'more', 'hist/rare', 'hist', 'rare', 'ba', 'ca'):
            return two
        else:
            return one

def separate_name_and_suffix(name):
    # this always matches something, although the suffix may be empty
    matchobj = re.match(r'(.+?)\s*(,[-0-9][^,:]*|,)?$', name)
    name = matchobj.group(1)
    suffix = matchobj.group(2) or ''
    return name, suffix



###############################################################################

class Page:
    pass

    def __init__(self, name, elab=None, name_from_txt=False, shadow=False,
                 from_inat=False, src=None):

        # shadow=False indicates a 'real' page that will be output to HTML.
        #
        # shadow=True indicates a 'shadow' page that is not (yet) planned
        # to be output to HTML; it maintains a node in the Linnaean tree
        # that does not correspond to a real page.
        self.shadow = shadow

        # True if the page is created from observations.csv
        self.created_from_inat = from_inat

        # Record the file source that is creating this page.
        self.src = src

        full_page_array.append(self)
        if not shadow:
            page_array.append(self)

        # initial/default values
        self.com = None
        self.no_com = False # true if the page will never have a common name
        self.com_checked = False # true after no_com has checked a shadow page
        self.sci = None
        self.no_sci = False # true if the page will never have a sci name
        self.elab = None
        self.elab_src = None
        self.rank = None
        self.rank_unknown = False

        # name_from_txt=True if the name came from a txt filename.
        self.name_from_txt = name_from_txt
        if name_from_txt:
            assert name
            assert not elab
            self.name = name
            name_page[name] = self

            # If name_from_txt=True, then the name might represent a common
            # name, a scientific name, or neither (just the filename).
            # So if name_from_txt=True, defer setting any common/scientific
            # name and instead wait to see how the name is used.
            #
            # Specifically:
            # - if the page includes com: and sci:, then those names are set.
            # - if find_page2() is searched with a defined com and/or sci name,
            #   either of them is allowed to match on this page's name,
            #   and then the com/sci names are set.
            # - if find_page1() matches this page's name, the match is allowed,
            #   but we still don't know what kind of name it is.
            # - if we get to the end of the script without setting either
            #   the common or scientific name, then we'll make a guess based
            #   on capitalization.
            self.no_names = True
        else:
            # If name_from_txt=False, then set the common/scientific name
            # as appropriate.
            #
            # If both name and elab are supplied, then name must represent
            # the common name.  If only name is supplied, then it may
            # represent either the common name or the scientific name.
            # If only elab is supplied, then there is no common name (yet).
            if not elab and is_sci(name):
                elab = name
                com = None
            else:
                com = name

            # Set a temporary page name in case we need to print
            # an error message before the name is officially set.
            self.name = f'{com}:{elab}'

            self.no_names = False

            # Call set_sci() first since it should never have a name conflict.
            if elab:
                self.set_sci(elab, from_inat=from_inat)

            # Now call set_com(), which sets the common name as the page name
            # when possible.
            if com:
                self.set_com(com, from_inat=from_inat)

        # user-supplied information about ancestors.
        self.group_items = [] # each entry = (rank, name, sci)

        # properties declared on this page
        # decl_prop_rank specifies which ranks the property & action apply to.
        # decl_prop_range specifies which ranks that include a range that
        # extends below that rank (whether inclusive or exclusive).  
        self.decl_prop_rank = {} # declared property -> action -> rank set
        self.decl_prop_range = {} # declared property -> action -> rank set

        # properties assigned to this page
        self.prop_action_set = {} # property name -> set of propagated actions

        self.is_top = False

        # Alternative scientific names
        self.elab_calflora = None
        self.elab_calphotos = None
        self.elab_jepson = None
        self.elab_inaturalist = None
        self.elab_bugguide = None

        # Alternative common names
        # Must be empty if the common name isn't set.
        # All names must be different than the common name.
        self.acom = []

        # A parent's link to a child may be styled depending on whether the
        # child is itself a key (has_child_key).  Which means that a parent
        # wants to parse its children before parsing itself.  To make sure
        # that that process doesn't go hayway, we keep track of whether each
        # page has been parsed or not.
        self.parsed = False

        # has_child_key is true if at least one child gets key info.
        self.has_child_key = False

        self.ext_photo_list = [] # list of (text, calphotos_link) tuples
        self.genus_complete = None # indicates the completeness of the genus+
        self.genus_key_incomplete = False # indicates if the key is complete
        self.species_complete = None # the same for the species
        self.species_key_incomplete = False

        self.txt = ''
        self.key_txt = ''
        self.photo_dict = {} # suffix -> photo filename (including suffix)

        # rep_jpg names a jpg that will represent the page in any
        # parent listing.
        self.rep_jpg = None

        # rep_child is a page name or page object.  Its representative jpg
        # will become our representative jpg.
        self.rep_child = None

        # figure_list is a list of filenames for figures used by the page.
        self.figure_list = []

        # list_hierarchy is True if we want to write the entire descendant
        # hierarchy to the HTML rather than just the list of children.
        self.list_hierarchy = False

        # end_hierarchy is True if we want a hierarchy listing to stop at
        # this page and not traverse to its descendants.
        self.end_hierarchy = False

        # parent and child construct one or more directed acyclic graphs (DAGs)
        # of the real pages to be output to HTML.
        self.parent = set() # an unordered set of real parent pages
        self.child = [] # an ordered list of real child pages

        # linn_parent and linn_child construct a tree corresponding to
        # the Linnaean taxonomic hierarchy.  Pages in this tree may be
        # real or shadow.
        self.linn_parent = None # the Linnaean parent (if known)
        self.linn_child = set() # an unordered set of Linnaean children

        # If children are linked to the page via the Linnaean hierarchy,
        # they could end up in a non-intuitive order.  We remember which
        # children have this problem and re-order them later.
        self.non_txt_children = None

        # ancestors that this page should be listed as a 'member of',
        # ordered from lowest-ranked ancestor to highest.
        self.membership_list = []

        # traits and values (e.g. color: pink, pale purple)
        self.trait_values = {} # trait name -> set of trait values

        # Keep track of which trait values actually appear on a subset page
        # so that we can complain about any unexpected values.
        self.traits_used = {} # trait name -> set of trait values

        # A list of filtered subset pages that this page is the parent of.
        self.subset_pages = {} # trait name -> list of subset pages

        # If a page is a subset, backlink which page it is a subset of.
        # If the value is not None, then the following additional variables
        # are also assigned:
        #   subset_trait
        #   subset_value
        #   subset_list_name
        self.subset_of_page = None

        self.taxon_id = None # iNaturalist taxon ID (stored as a string)
        self.bugguide_id = None # BugGuide.net ID (stored as a string)
        self.obs_n = 0 # number of observations
        self.obs_rg = 0 # number of observations that are research grade
        self.parks = {} # a dictionary of park_name : count
        self.month = [0] * 12

        # cumulative obs_n among all descendants for a particular trait/value
        # combination.  (trait and value may be both None.)
        self.cum_obs_n = {} # trait -> value -> count

        self.glossary = None # the Glossary instance that applies to the page

        # the Glossary instances that want a warning printed if one of their
        # glossary terms is used outside the glossary
        self.glossary_warn = set()

    # Provide a hook for the sort_pages() helper function to be called
    # via a Page object without needing to import page.py.
    def sort_pages(self, page_set):
        return sort_pages(page_set)

    def infer_name(self):
        if self.no_names:
            if is_sci(self.name):
                self.set_sci(self.name)
            else:
                self.set_com(self.name)

    def set_name(self):
        if self.name_from_txt:
            # the name never changes
            return

        if self.name in name_page:
            del name_page[self.name]

        if (self.com and com_page[self.com] == self and
            (self.com not in name_page or name_page[self.com] == self)):
            name = self.com
        elif self.sci:
            if sci_page[self.sci] == 'conflict':
                name = self.elab
            else:
                name = self.sci
        else:
            fatal(f'set_name() failed for {self.full()}')

        if name in name_page:
            fatal(f'Multiple pages created with name "{name}"')

        self.name = name
        name_page[name] = self

    # In simple terms, set_com() sets the common name and then calls
    # set_name() to give priority to the common name where possible.
    #
    # However, things get complicated when there are common name conflicts.
    # Priorities are assigned as follows, from highest to lowest:
    # - common name is the same as the filename of the txt file
    # - default priority
    # - the page came from a txt file, but the filename of the txt file is
    #   different from the common name (so it disclaims priority on the name).
    #
    # Note that common names based on txt filenames are assigned first and
    # are guaranteed to be without conflicts.  Any common names assigned after
    # that will not have name_from_txt asserted.
    def set_com(self, com, from_inat=False):
        if com == 'n/a':
            if self.com:
                error(f'com:n/a used on page {self.full()}')
            else:
                self.no_com = True
            return

        if self.com:
            # This page already has a common name.
            if self.com == com:
                # The new common name is the same as the old one.
                return
            elif from_inat:
                # iNaturalist may be allowed to provide an alternative common
                # name, but only if it is sufficiently different than the
                # regular common name or any existing alternative common name.
                if plural_equiv(self.com, com):
                    return

                for acom in self.acom:
                    if plural_equiv(acom, com):
                        return

                if (self.rp_do('obs_fill_alt_com',
                               f'{self.full()} has iNaturalist common name "{com}"')):
                    # iNaturalist is allowed to add an alternative common name,
                    # and the name is sufficiently different than any existing
                    # name.
                    self.acom.append(com)

                # We either added an alternative name or not.
                # But either way the primary common name is already set,
                # so there's nothing more to do here.
                return
            else:
                fatal(f'{self.full()} is assigned a new common name: {com}')

        if (from_inat and
            not self.created_from_inat and
            not self.rp_do('obs_fill_com',
                           f'{self.full()} has iNaturalist common name "{com}"')):
            # If we got here, then
            #   - we have a new common name from iNaturalist, and
            #   - this page was created by the user, and
            #   - we don't have a property that allows us to use the new name.
            return

        if self.no_com:
            error(f'common name "{com}" assigned to page {self.full()}, but com:n/a was already used for the page')
            return

        self.com = com

        if self.shadow:
            # Give a shadow page a super-low priority.
            # If the page gets promoted to a real page, I'm fine with it
            # still having low priority.
            self.com_priority = 0
        elif self.name_from_txt:
            if com == self.name:
                # The common name is the same as the filename of the txt file
                # for this page, so it has highest priority.
                self.com_priority = 4
            else:
                # The page came from a txt file with a different filename,
                # so its common name has lower priority.
                self.com_priority = 2
        elif from_inat:
            # The common name is supplied by iNaturalist, so it has lowest
            # priority.  It can provide a common name to a real page that
            # doesn't have one, or it can create a new shadow page which a
            # property later promotes to real.
            self.com_priority = 1
        else:
            # The common name comes from the user with no special priority.
            # E.g. it is declared as the name of a child page.
            self.com_priority = 3

        if com in com_page and com_page[com] != self:
            # There is at least one other other page with the same
            # common name.
            conflict = com_page[com]

            if isinstance(conflict, int):
                if self.com_priority > conflict:
                    # Previous conflicts on this common name were at a
                    # lower priority, so we can take control of the name.
                    com_page[com] = self
                else:
                    # Previous conflicts on this common were at the same
                    # priority or higher, so the conflicts remain at the
                    # higher priority.
                    pass
            elif self.com_priority < conflict.com_priority:
                # This page has lower priority than the existing claimant,
                # so the conflict page retains control of the name.
                pass
            else:
                if self.com_priority > conflict.com_priority:
                    # This page has higher priority than the previous claimant,
                    # so we can take control of the name.
                    com_page[com] = self
                else:
                    # This page has the same priority as the previous claimant,
                    # so the common name cannot be claimed by either page.
                    # We record the priority of the conflicting pages in case
                    # there are more claimants.
                    com_page[com] = self.com_priority

                # Update the conflicting page's name to reflect the
                # fact that it lost control of the name.
                conflict.set_name()
        else:
            # No other page has claimed this common name, so it's ours.
            com_page[com] = self

        self.no_names = False
        self.set_name()

    # set_sci() can be called with a stripped or elaborated name.
    # Either way, both a stripped and an elaborated name are recorded.
    def set_sci(self, elab, from_inat=False):
        if (self.sci or self.no_sci) and from_inat:
            # This page already has a scientific name, and we don't want
            # iNaturalist to override it.  E.g. iNaturalist could have found
            # the page via isci_page[], which differs from its user-supplied
            # scientific name.
            return

        if elab == 'n/a':
            if self.sci:
                error(f'sci:n/a used on page {self.full()}')
            else:
                self.no_sci = True
            return

        if self.no_sci:
            error(f'scientific name "{elab}" assigned to page {self.full()}, but sci:n/a was already used for the page')
            return

        elab = fix_elab(elab)
        sci = strip_sci(elab)

        # Fail if
        # - the same fully elaborated name is used for another page, or
        # - a non-elaborated name is used, and another page uses the same name,
        # - or a non-elaborated name is used and already has a conflict.
        if elab in sci_page and sci_page[elab] == 'conflict':
            fatal(f'page "{self.full()}" called set_sci("{elab}"), but that non-elaborated name is being used by more than one rank')
        elif elab in sci_page and sci_page[elab] != self:
            fatal(f'page "{self.full()}" called set_sci("{elab}"), but that name is already used by page "{sci_page[elab].name}"')

        if self.sci and sci != self.sci:
            # Somehow we're trying to set a different scientific name
            # than the one already on the page.  That should only happen
            # if sci_page points both names to the same page, which is
            # only true if there are alternative scientific names via asci.
            # I don't attempt to do anything smart with that case.
            return

        if elab == self.elab:
            # We don't want to continue through the change/check logic
            # if the name isn't changing in any way.  Only upgrade
            # elab_src as appropriate.
            if sci != elab:
                self.elab_src == 'elab'
            return

        if sci == elab:
            # Nothing changed when we stripped elaborations off the original
            # elab value, so either it's a species or a name that could be
            # improved with further elaboration.

            if self.sci:
                # The page already has a scientific name.  Don't try to
                # replace a potentially elaborated name with a guess.
                return

            # Guess at a likely elaboration for the scientific name.
            elab = elaborate_sci(sci)
            elab_src = 'sci'
        elif self.elab_src == 'elab':
            # This call and a previous call to set_sci() both provided
            # a fully elaborated name, but they're not the same.
            fatal(f'{self.full()} received two different elaborated names: {self.elab} and {elab}')
        else:
            # We've received a fully elaborated name.
            # Either we had no elaborated name at all before,
            # or it was only a guess that we're happy to replace.
            elab_src = 'elab'

        elab_words = elab.split(' ')

        if (not elab[0].islower()
            and len(elab_words) > 2
            and elab_words[2] not in ('ssp.', 'var.')):
            error(f'Unexpected elaboration for {elab}')

        if (from_inat and
            not self.created_from_inat and
            not self.rp_do('obs_fill_sci',
                           f'{self.full()} can be filled by {elab}')):
            # If we got here, then
            #   - this page was created by the user, and
            #   - we have a new elaboration from iNaturalist, and
            #   - we don't have a property that allows us to use the new name.
            return

        if elab[0].islower():
            if elab_words[0] in Rank.__members__:
                self.rank = Rank[elab_words[0]]

                if elab_words[0] == 'below':
                    # A special case that only occurs when observations.csv
                    # uses an unknown rank.
                    self.rank_unknown = True
            else:
                error(f'Unrecognized rank for {elab}')
                self.rank = None
        else:
            sci_words = sci.split(' ')
            if len(sci_words) == 1:
                self.rank = Rank.genus
            elif len(sci_words) == 2:
                self.rank = Rank.species
            else:
                self.rank = Rank.below

        self.elab = elab
        self.elab_src = elab_src
        self.sci = sci
        sci_page[elab] = self
        if sci in sci_page and sci_page[sci] != self:
            conflict_page = sci_page[sci]
            sci_page[sci] = 'conflict'
            if conflict_page != 'conflict':
                # Now that we know that two pages collide on a scientific
                # name, we should regenerate the names of *both* pages to
                # avoid confusion and differences in naming based on run
                # order.
                conflict_page.set_name()
        else:
            sci_page[sci] = self

        self.no_names = False
        self.set_name()

    def format_com(self):
        if self.com:
            return easy_sub_safe(self.com)
        else:
            return None

    def format_elab(self, ital=True):
        return format_elab(self.elab, ital)

    def format_short(self):
        # When choosing a short name, the common name normally has priority.
        # However, if the scientific name matches the page name (e.g. because
        # there were multiple pages with the same common name), use the
        # scientific name instead.
        if self.com and self.sci != self.name:
            return self.format_com()
        else:
            return self.format_elab()

    def format_full(self, lines=2, ital=True, for_html=True):
        if for_html:
            com = self.format_com()
        else:
            com = self.com
        elab = self.format_elab(ital=ital)
        if com:
            if elab:
                if lines == 1:
                    return f'{com} ({elab})'
                else:
                    return f'{com}<br>{elab}'
            else:
                return com
        elif elab:
            return elab
        else:
            return '{' + self.name + '}'

    # full() is intended for Python debug output to the terminal
    # It removes all fancy formatting to emit ASCII only.
    def full(self):
        names = unidecode(self.format_full(lines=1, ital=False, for_html=False))
        return f'{names} [{self.src}]'

    def get_filename(self):
        no_spaces = re.sub(r' ', '-', self.name)
        return filename(no_spaces)

    def get_url(self):
        return url(self.get_filename())

    def add_photo(self, filename, suffix):
        if suffix in self.photo_dict:
            error(f'suffix of "{filename}" conflicts with "{self.photo_dict[suffix]}"')
        else:
            self.photo_dict[suffix] = filename

    def get_jpg(self, suffix, set_rep_jpg=True, origin=None):
        if self == origin:
            error(f'circular get_jpg() loop through {self.full()}')
            return None
        if not origin:
            origin = self

        jpg = None

        if self.rep_jpg:
            jpg = self.rep_jpg
        elif self.rep_child:
            rep = self.rep_child
            if isinstance(self.rep_child, str):
                rep = find_page1(self.rep_child)
            if rep:
                jpg = rep.get_jpg(suffix, set_rep_jpg, origin)
            else:
                error(f'unrecognized rep: {self.rep_child} in {self.full()}')
        elif suffix:
            if suffix in self.photo_dict:
                jpg = self.photo_dict[suffix]
            else:
                error(f'unrecognized suffix "{suffix}" in "{self.full()}"')
                # leave jpg = None
        elif self.photo_dict:
            first_suffix = sorted(self.photo_dict)[0]
            jpg = self.photo_dict[first_suffix]
        else:
            # Search this key page's children for a jpg to use.
            for child in self.child:
                jpg = child.get_jpg('', set_rep_jpg, origin)
                if jpg:
                    break

        if set_rep_jpg:
            self.rep_jpg = jpg

        return jpg

    def get_ext_photo(self):
        if self.ext_photo_list:
            return self.ext_photo_list[0]
        else:
            # Search this key page's children for an external photo to use.
            for child in self.child:
                ext_photo = child.get_ext_photo()
                if ext_photo:
                    return ext_photo
            return None

    def count_flowers(self, trait=None, value=None, exclude_set=None):
        top_of_count = exclude_set is None

        if top_of_count:
            # If we're counting from the top, then we can generate or
            # return a cached value.  This is important to ensure that
            # sorting is fast.
            #
            # But if count_flowers() was called with an exclude_set
            # (from recursion), then some subset of this page might
            # need to be excluded, so we re-perform the entire count
            # from scratch and *don't cache the result*.
            if trait in self.cum_obs_n and value in self.cum_obs_n[trait]:
                return self.cum_obs_n[trait][value]
            exclude_set = set()

        if self in exclude_set:
            # We've already counted this page via another path, so
            # treat it as 0 this time.
            return 0

        exclude_set.add(self)

        n = 0
        if self.page_matches_trait_value(trait, value):
            n += self.obs_n
        for child in self.child:
            child_n = child.count_flowers(trait, value, exclude_set)
            n += child_n

        if top_of_count:
            if trait not in self.cum_obs_n:
                self.cum_obs_n[trait] = {}
            self.cum_obs_n[trait][value] = n

        return n

    def remove_comments(self):
        self.txt = re.sub(r'^\s*#.*\n| +#.*', '', self.txt,
                          flags=re.MULTILINE)

    def parse_names(self):
        def repl_com(matchobj):
            com = matchobj.group(1)
            self.set_com(com)
            return ''

        def repl_sci(matchobj):
            sci = matchobj.group(1)
            self.set_sci(sci)
            return ''

        def repl_asci(matchobj):
            sci = strip_sci(matchobj.group(1))
            if sci in sci_page:
                fatal(f'{self.full()} specifies asci: {sci}, but that name already exists')
            sci_page[sci] = self
            return ''

        # Check for a scientific name first because it is guaranteed to be
        # able to assign a filename (unless the user screwed up).
        # On the other hand, the common name might collide, at which point
        # we should either fall back to using the scientific name as the
        # filename or complain that no name can be set.
        self.txt = re.sub(r'^sci:\s*(.+?)\s*?\n',
                          repl_sci, self.txt, flags=re.MULTILINE)
        self.txt = re.sub(r'^com:\s*(.+?)\s*?\n',
                          repl_com, self.txt, flags=re.MULTILINE)

        # If only a scientific name was explicitly set, then:
        # - if the filename matches the scientific name, set the scientific
        #   name again from the filename (in case the filename includes an
        #   elaboration that we otherwise don't have, although that would be
        #   weird).
        # - otherwise, set the common name from the filename.
        if not self.com and self.sci:
            elab = fix_elab(self.name)
            sci = strip_sci(elab)
            if sci == self.sci:
                self.set_sci(elab)
            else:
                self.set_com(self.name)

        # If only a common name was explicitly set and the filename looks
        # like it could be a scientific name, set it as the scientific name.
        if self.com and not self.sci and not self.name.islower():
            self.set_sci(self.name)

        matchobj = re.search(r'^subset\s+(\S*)\s*:',
                             self.txt, flags=re.MULTILINE)
        if matchobj:
            traits.add(matchobj.group(1))

    def canonical_rank(self, rank):
        if rank == 'self':
            if self.rank:
                return self.rank
            else:
                # Leave the 'self' string in place for the caller to handle
                # or fail on.
                return 'self'
        else:
            if rank not in Rank.__members__:
                fatal(f'unrecognized rank "{rank}" used in {self.full()}')
            return Rank[rank]

    def declare_property(self, action, prop, rank_str):
        if not action:
            action = 'do'

        if action not in props[prop]:
            error(f'{self.full()} - action not supported for property in "{action} {prop}')

        rank_range_list = split_strip(rank_str)

        rank_set = set()
        range_set = set()
        for rank_range in rank_range_list:
            if '-' in rank_range:
                matchobj = re.match(r'(.+?)(/?)-(/?)(.+)', rank_range)
                (rank1, rank1_excl,
                 rank2_excl, rank2) = (matchobj.group(1), matchobj.group(2),
                                       matchobj.group(3), matchobj.group(4))

                # If used in a rank range, 'self' is translated into the
                # page's actual rank if possible.  But if the current
                # page is unranked, 'self' is left as 'self'.
                rank1 = self.canonical_rank(rank1)
                rank2 = self.canonical_rank(rank2)

                # rank1 can be larger or smaller than rank2.  Reorder it
                # here so that rank2 is the larger one.
                if rank1 == 'self' or (rank2 != 'self' and rank1 > rank2):
                    (rank1, rank2) = (rank2, rank1)
                    (rank1_excl, rank2_excl) = (rank2_excl, rank1_excl)

                if rank2 == 'self':
                    range_set.add('self')

                in_range = False
                for rank in Rank: # iterate ranks from smallest to largest
                    if in_range:
                        range_set.add(rank)

                    # Calculate in_range as exclusive.
                    if rank == rank2:
                        in_range = False

                    # Include the current rank if it is within the
                    # exclusive range or if it matches a non-exclusive
                    # range boundary.
                    if (in_range or
                        (rank == rank1 and not rank1_excl) or
                        (rank == rank2 and not rank2_excl)):
                        rank_set.add(rank)

                    # Calculate in_range as exclusive.
                    if rank == rank1:
                        in_range = True

                if rank2 == 'self':
                    # if rank2 is 'self', then we never found the end of the
                    # range.  This potentially includes a lot of upper ranks
                    # that won't be applied because property application only
                    # recurses through lower ranks, but that's OK and we'll
                    # (mostly) get what we want.

                    if rank2_excl:
                        # If the page gets ranked later, its new rank will
                        # match an element of the rank_set during propagation.
                        # So we assign a pseudo-action that tells propagation
                        # to *not* assign the property, despite the match.
                        self.assign_prop(prop, 'exclude-' + action)
                    else:
                        # If the page remains unranked, it won't match any of
                        # the ranks in the rank set.  Instead, we set its
                        # property manually here.
                        self.assign_prop(prop, action)
            else:
                # Not a range, just a rank.
                # For this case, 'self' is applied directly in case the
                # current page does not have a rank.
                rank = rank_range
                if rank == 'none':
                    # 'none' is expected to be used as the only assigned
                    # rank, and it indicates that the property applies to
                    # no ranks.  E.g. a higher taxon could declare
                    # 'obs_requires_photo: genus-below', and a lower taxon
                    # could override it with 'obs_requires_photo: none'.
                    pass
                elif rank == 'self':
                    self.assign_prop(prop, action)
                else:
                    rank_set.add(self.canonical_rank(rank))

        # rank_set can be empty if the only listed ranks are 'none' or
        # 'self'.  We record the rank_set whether it is populated or empty
        # so that property propagation knows to stop at this level.
        if prop not in self.decl_prop_rank:
            self.decl_prop_rank[prop] = {}
            self.decl_prop_range[prop] = {}
        self.decl_prop_rank[prop][action] = rank_set
        self.decl_prop_range[prop][action] = range_set

        # print(f'{self.name} = {action} {prop}: {rank_set}')

    def parse_glossary(self):
        if re.search(r'^{([^-].*?)}', self.txt, flags=re.MULTILINE):
            if self.name in glossary_taxon_dict:
                glossary = glossary_taxon_dict[self.name]
            else:
                glossary = Glossary(self.name)
                glossary.taxon = self.name
                glossary.title = self.name
                glossary.page = self
                glossary.txt = None
            self.txt = glossary.parse_terms(self.txt)

    def set_sci_alt(self, sites, elab):
        elab = fix_elab(elab)

        if 'f' in sites:
            self.elab_calflora = elab
        if 'p' in sites:
            self.elab_calphotos = elab
        if 'j' in sites:
            self.elab_jepson = elab
        if 'i' in sites:
            self.elab_inaturalist = elab
            isci = strip_sci(elab)
            if isci in isci_page and isci_page[isci] != self:
                error('{isci_page[isci].full()} and {self.full()} both use sci_i {elab}')
            isci_page[isci] = self
        if 'b' in sites:
            self.elab_bugguide = elab

    def set_complete(self, matchobj):
        if matchobj.group(1) == 'x':
            if self.genus_complete is not None:
                error(f'{self.full()} has both x:{self.genus_complete} and x:{matchobj.group(3)}')
            self.genus_complete = matchobj.group(3)
            if matchobj.group(2):
                self.genus_key_incomplete = True
        else:
            if self.species_complete is not None:
                error(f'{self.full()} has both xx:{self.species_complete} and xx:{matchobj.group(3)}')
            self.species_complete = matchobj.group(3)
            if matchobj.group(2):
                self.species_key_incomplete = True
        return ''

    def set_trait_values(self, trait, value_str):
        if trait in self.trait_values:
            error(f'{trait} is defined more than once for page {self.full()}')

        self.trait_values[trait] = set(split_strip(value_str))

    def record_subset(self, trait, value, list_name, page_name):
        if list_name is None:
            list_name = value

        page = find_page2(page_name, None)
        if not page:
            page = Page(page_name, None,
                        src=f'subset {trait} in {self.name}.txt')
            page.no_sci = True

        page.subset_of_page = self
        page.subset_trait = trait
        page.subset_value = value
        page.subset_list_name = list_name

        self.link_linn_child(page)

        if trait not in self.subset_pages:
            self.subset_pages[trait] = []
        self.subset_pages[trait].append(page)

    def set_taxon_id(self, taxon_id):
        if taxon_id in taxon_id_page and taxon_id_page[taxon_id] != self:
            fatal(f'taxon_id {taxon_id} used for both {taxon_id_page[taxon_id].full()} and {self.full()}')
        if self.taxon_id and taxon_id != self.taxon_id:
            fatal(f'taxon_id {taxon_id} applied to {self.full()}, but it already has taxon_id {self.taxon_id}')

        self.taxon_id = taxon_id
        taxon_id_page[taxon_id] = self

    def record_ext_photo(self, label, link):
        if (label, link) in self.ext_photo_list:
            error(f'{link} is specified more than once for page {self.full()}')
        else:
            if label:
                label = easy_sub_safe(label)
            self.ext_photo_list.append((label, link))

    # Check if check_page is an ancestor of this page (for loop checking).
    def is_ancestor(self, check_page):
        if self == check_page:
            return True

        for parent in self.parent:
            if parent.is_ancestor(check_page):
                return True

        return False

    # Check if the page has any Linnaean descendants that are real.
    # This does not include the page itself, which may be real or shadow.
    def has_real_linnaean_descendants(self):
        for child in self.linn_child:
            if not child.shadow or child.has_real_linnaean_descendants():
                return True
        return False

    # Using recursion, find the lowest-ranked ancestor of self.
    #
    # A RecursionError is flagged if the child argument page is encountered
    # during the search.
    # 
    # This function is called during assign_child to find the best
    # ancestor to create a Linnaean link to.
    #
    # In truth, it should be unusual that an unranked page has
    # multiple ranked ancestors.  But it may occur, for example, if an
    # unranked page describes a subset species within a genus (and is
    # thus a child of the genus), and another unranked page describes
    # a larger collection with the first page as a child and with a
    # higher taxon (e.g. family) as its parent.  Presumably all
    # ancestors should be in the same taxonomic chain; if they aren't,
    # then some page's parentage is dubious.  In any case, we don't
    # bother to check for it.
    #
    # Recursion can terminate when any ranked page is found since
    # ancestors of that page must have a higher rank.  I.e. recursion
    # only traverses through unranked pages.  For performance, we also
    # terminate redundant recursion if we reach a page via multiple
    # paths.
    #
    # The code to create the Linnaean link includes a check for
    # correct rank ordering, which has a secondary benefit of
    # detecting a circular loop, but only through ranked pages.  To
    # detect and prevent a circular loop through unranked pages, we
    # raise an exception here if we try to traverse through 'child'.
    def find_lowest_ranked_ancestor(self, child, exclude_set=None):
        if self == child:
            raise RecursionError

        if self.rank:
            return self

        if exclude_set is None:
            exclude_set = set()

        list_of_parent_lists = [self.parent]
        if self.linn_parent:
            list_of_parent_lists.append([self.linn_parent])

        lra = None # lowest ranked ancestor
        for parent_list in list_of_parent_lists:
            for parent in parent_list:
                if parent not in exclude_set:
                    exclude_set.add(parent)
                    ancestor = parent.find_lowest_ranked_ancestor(child, exclude_set)
                    if (ancestor and
                        ancestor.rank and
                        (not lra or ancestor.rank < lra.rank)):
                        lra = ancestor
        return lra

    # Using recursion, create a link from the designated Linnaean parent
    # to each ranked descendent.
    #
    # linn_parent is supplied when we want to link a specific child (or its
    # descendents) from a specific parent.
    #
    # linn_parent is None when we want to link all children from this page.
    def link_linn_descendants(self, linn_parent=None, exclude_set=None):
        if linn_parent is None:
            if self.rank:
                linn_parent = self
            else:
                # Can't create Linnaean links from an unranked parent.
                return
        elif self.rank:
            linn_parent.link_linn_child(self)
            return

        if exclude_set is None:
            exclude_set = set()

        list_of_child_lists = [self.child, self.linn_child]

        for child_list in list_of_child_lists:
            for child in child_list:
                if child not in exclude_set:
                    exclude_set.add(child)
                    child.link_linn_descendants(linn_parent, exclude_set)

    # Create a Linnaean link between two existing pages.  Although we
    # use the term 'child', it could actually be a deeper descendant
    # if the 'child' page already has a lower-ranked parent.  If the
    # parent is inserted between nodes of an existing Linnaean link,
    # that link is rearranged to accomodate the parent.
    def link_linn_child(self, child):
        if child in self.linn_child:
            # Commonly we'll already know the parent-child relationship.
            # In that case, bail out as quickly as possible.
            return

        # Make sure the child rank is less than the parent rank.
        # But if the child is unranked, we don't bother to search deeper.
        # (We expect to only create a Linnaean link on an unranked child
        # after determining the lowest common child ancestor of its
        # descendants, which means their ranks are already guaranteed to
        # be compatible.
        if child.rank and self.rank <= child.rank:
            fatal(f'bad rank order when adding {child.full()} (rank {child.rank.name}) as a child of {self.full()} (rank {self.rank.name})')

        if child.linn_parent == None:
            # The child node was the top of its Linnaean tree.  Now we know
            # its Linnaean parent.
            child.linn_parent = self
            self.linn_child.add(child)
            return

        try:
            # The new link attempts to establish a different parent than the
            # child previously had.  Check whether the new parent or old
            # parent has the lower rank, and react accordingly.
            if self.rank < child.linn_parent.rank:
                # The new parent fills a gap between the child and its
                # previous parent.

                ancestor = child.linn_parent

                # Remove the previous link between the child and what
                # we now consider to be a more distant ancestor.
                # Normally when removing a link, we'd also clear
                # child.linn_parent, but we're about to overwrite that
                # below, anyway.  So all we have to do here is remove
                # the direct link from the ancestor to the child.
                ancestor.linn_child.remove(child)

                # Add the link from the child to its new parent.
                child.linn_parent = self
                self.linn_child.add(child)

                # Also add a link from the parent to the higher-ranked ancestor.
                ancestor.link_linn_child(self)
            else:
                # The child's current parent has a rank lower than the
                # new parent that we're trying to link.  That means
                # that the new parent is really an ancestor at a
                # higher level.  It's likely that the attempted new
                # parent is already linked higher in the tree, but
                # let's make sure.
                #
                # Note that we'll also fall through to this code if
                # the child's current parent has the *same* rank as
                # the new parent.  Since we already checked that the
                # parents are not the same, that's a problem, but
                # it'll get caught when we make the recursive call.
                self.link_linn_child(child.linn_parent)
        except FatalError:
            warn(f'was adding {child.full()} (rank {child.rank.name}) as a child of {self.full()} (rank {self.rank.name})')
            raise

    # Create a Linnaean link to a parent that is descibed by rank &
    # name.  Although we use the term 'parent', it could actually be a
    # higher ancestor if we already have a lower-ranked parent.  A
    # page for the ancestor is created if necessary.
    #
    # 'rank' is the rank of the ancestor page and is optional; if it
    # is None, then the rank should either be included in the 'name'
    # (below), or the name must point to an unambiguous page that
    # already has a rank.  'rank' must be None if a common name and
    # scientific name are both supplied.  If the rank is supplied with
    # a common name only, the rank is checked against the matching page.
    #
    # 'name' is the common or scientific name of the ancestor page.
    #
    # 'sci' is the scientific name of the ancestor page (in which case
    # 'name' must be its common name).
    #
    # This function is a thin wrapper around link_linn_child(), which
    # is centered on the parent page, but add_linn_parent() is
    # centered on the child page because it is the page that is
    # guaranteed to be present.
    def add_linn_parent(self, rank, name, sci=None, from_inat=False):
        if is_sci(name):
            if rank and rank >= Rank.genus:
                elab = f'{rank.name} {name}'
            else:
                # A species name is no different when elaborated.
                # A parent would never be a subspecies or variant.
                elab = name

            parent = find_page2(None, elab, from_inat)
            if not parent:
                if from_inat:
                    src = 'taxonomy from observations.csv'
                else:
                    src = 'implicit or explicit ancestor from txt'
                parent = Page(None, elab, shadow=True,
                              from_inat=from_inat, src=src)
        else: # common name
            parent = find_page2(name, sci, from_inat)
            if not parent:
                parent = Page(name, sci, shadow=True,
                              from_inat=from_inat,
                              src='explicit ancestor from txt')

            if not parent.rank:
                error(f'add_linn_parent from {self.full()} is to unranked page {name}')
                return
            elif rank and parent.rank != rank:
                error(f'add_linn_parent from {self.full()} is to {name} with rank {parent.rank.name}, but we expected rank {rank.name}')
                return
            else:
                # OK, good, the common name maps to an existing page
                # with a rank.
                pass

        # OK, we either found the parent page or created it.
        # We can finally create the Linnaean link.
        parent.link_linn_child(self)

        # Because a taxonomic chain is built from observation.csv in a
        # series from lowest to highest rank, performance is enhanced
        # by returning each linn_parent that is found or created so
        # that the next link in the chain can be added to it directly
        # without needing to find it again.  Other callers of
        # add_linn_parent() generally ignore this return value.
        return parent

    def assign_groups(self):
        page = self
        if self.rank in (Rank.below, Rank.species):
            # Derive species and genus membership from the truncated scientific
            # name.
            sci_words = self.sci.split(' ')
            if self.rank is Rank.below:
                page = self.add_linn_parent(Rank.species, ' '.join(sci_words[0:2]))
            page = page.add_linn_parent(Rank.genus, sci_words[0])

        # Assign memberships declared in the text.
        for rank, name, sci in self.group_items:
            self.add_linn_parent(rank, name, sci)

    def assign_child(self, child):
        if self in child.parent:
            error(f'{child.full()} added as child of {self.full()} twice')
            return

        # In addition to creating a real link, we also create a Linnaean link.
        # The process of adding the Linnaean link also checks for a potential
        # circular loop in the real tree, so we do that before creating the
        # real link.
        #
        # If either the parent or child is unranked, we don't want to create
        # a Linnaean link to/from it.  Instead we search for the nearest
        # Linnaean ancestor and link it to the nearest Linnaean descendants.
        #
        # Note that after the real tree has been built, we *can* make a
        # Linnaean link to an unranked child, but we still don't want to do
        # so now.  Instead, we prefer to allow the Linnaean tree to accumulate
        # as much detail as possible so that the unranked page can later
        # determine its nearest Linnaean ancestor without worrying that maybe
        # a nearer Linnaean ancestor will get created.
        try:
            linn_parent = self.find_lowest_ranked_ancestor(child)
        except RecursionError:
            fatal(f'circular loop detected through unranked pages when adding {child.full()} as child of {self.full()}')

        if linn_parent:
            child.link_linn_descendants(linn_parent)

        # OK, now we can finally create the real link.
        self.child.append(child)
        child.parent.add(self)

    def print_tree(self, level=0, link_type='', exclude_set=None):
        if exclude_set is None:
            exclude_set = set()

        name = self.full()

        if self.shadow:
            name = f'[{name}]'

        if self in exclude_set:
            # Print the repeated node, but don't descend further into it.
            name += ' {repeat}'

        print(f'{"  "*level}{link_type}{name}')

        if self in exclude_set:
            return

        exclude_set.add(self)

        if arg('-tree_props'):
            for prop in sorted(self.prop_action_set):
                action_list = sorted(self.prop_action_set[prop])
                action_str = '/'.join(action_list)
                print(f'{"  "*level}  {action_str} {prop}')

        for child in self.child:
            if child in self.linn_child:
                # link_type = '*' for a child that is both real & Linnaean
                child.print_tree(level+1, '*', exclude_set)
            else:
                # link_type = '+' for a child that is real but not Linnaean
                child.print_tree(level+1, '+', exclude_set)
        for child in self.linn_child:
            if child not in self.child:
                # link_type = '-' for a shadow child (Linnaean but not real)
                child.print_tree(level+1, '-', exclude_set)

    def propagate_is_top(self):
        ancestor = self
        while ancestor:
            ancestor.is_top = True
            ancestor = ancestor.linn_parent

    # Return a set of all ancestors.
    # If is_top is true, then also propagate that up through the ancestors.
    def get_linn_ancestor_set(self, is_top):
        # is_top propagation starts at the lowest level.
        if is_top:
            self.is_top = True

        # The ancestor_set starts populating with the first parent.
        ancestor = self.linn_parent
        ancestor_set = set()

        while ancestor:
            if is_top:
                ancestor.is_top = True
            ancestor_set.add(ancestor)
            ancestor = ancestor.linn_parent

        return ancestor_set

    # Assign the lowest common children's ancestor as linn_parent.
    # Also propagate is_top to children and their ancestors.
    def resolve_lcca(self):
        cca_set = None
        for child in self.child:
            child_ancestor_set = child.get_linn_ancestor_set(self.is_top)
            if cca_set is None:
                # create the initial value for cca_set
                cca_set = child_ancestor_set
            else:
                cca_set.intersection_update(child_ancestor_set)

        if cca_set:
            lcca = None
            for cca in cca_set:
                if not lcca or cca.rank < lcca.rank:
                    lcca = cca
            lcca.link_linn_child(self)
        else:
            # Either there are no children or no common children's ancestors.
            # Lacking any finer-grained information, link from the lowest-
            # ranked real ancestor.  This might be a higher rank than desired,
            # but there's no way to know.
            lra = self.find_lowest_ranked_ancestor(None)
            if lra:
                lra.link_linn_child(self)

    def propagate_props(self):
        for prop in self.decl_prop_rank:
            for action in self.decl_prop_rank[prop]:
                self.propagate_prop(prop, action,
                                    self.decl_prop_rank[prop][action],
                                    self.decl_prop_range[prop][action],
                                    'decl')

    # rank_set is a set of ranks for which the property applies.
    #
    # If the page is unranked, we instead check whether its closest ancestor
    # rank is in range_set.
    #
    # closest_ancestor_rank is set to 'decl' for the declaring page.
    #   This value never matches in range_set, so
    #   - if the declaring page is ranked, it checks rank_set as usual.
    #   - if the declaring page is unranked, it never assigns the property.
    #     instead, the property was assigned as appropriate during declaration
    #     if 'self' was included.
    # closest_ancestor_rank is set to 'self' for the real children of
    #   an unranked declaring page.  If those children are also unranked,
    #   then the property is assigned to them if 'self' is in range_set.
    #   These children also propagate the property with closest_ancestor_rank
    #   as 'self'.
    # closest_ancestor_rank is set to the rank of a ranked page.
    #   The property is assignd to an unranked Linnaean descendent if
    #   this rank is in range_set.
    def propagate_prop(self, prop, action, rank_set, range_set,
                       closest_ancestor_rank):
        if self.rank:
            # For the 'default_completeness' property, assist the
            # write_complete() function by recording the action at the
            # genus and species level using a hacked property name.
            if prop == 'default_completeness' and self.rank <= Rank.genus:
                if Rank.genus in rank_set:
                    self.assign_prop('default_completeness_genus', action)
                if Rank.species in rank_set and self.rank <= Rank.species:
                    self.assign_prop('default_completeness_species', action)
            elif (self.rank in rank_set and
                  not (prop in self.prop_action_set and
                       'exclude-' + action in self.prop_action_set[prop])):
                self.assign_prop(prop, action)

            # Recursively descend through Linnaean children.  Note that
            # these Linnaean children can include unranked pages.
            # These unranked pages may represent a real hierarchy, although
            # that hierarchy is lost and unimportant in this contxt.
            # Unranked pages do not themselves have Linnaean children.
            # There's no need to descend through 'real' children of this
            # page or its unranked Linnaean children because any ranked
            # real descendents should already be Linnaean descendents
            # of this page.
            #
            # Stop propagation at any child that replaces the prop assignment.
            for child in self.linn_child:
                if (prop not in child.decl_prop_rank or
                    action not in child.decl_prop_rank[prop]):
                    child.propagate_prop(prop, action, rank_set,
                                         range_set, self.rank)
        else:
            if closest_ancestor_rank in range_set:
                self.assign_prop(prop, action)

            # If a property is declared in an unranked page, then it cannot
            # have Linnaean children.  We push the properties down through
            # its real children until a ranked descendant is found, then
            # the properties are applied to each of those Linnaean trees.
            #
            # If the property propagated from a ranked page, however, then
            # do not propagate it through any unranked page.  Its ranked
            # children are already covered as Linnaean descendents of the
            # ranked ancestor.
            #
            # Stop propagation at any child that replaces the prop assignment.
            if closest_ancestor_rank in ('decl', 'self'):
                for child in self.child:
                    if (prop not in child.decl_prop_rank or
                        action not in child.decl_prop_rank[prop]):
                        child.propagate_prop(prop, action, rank_set,
                                             range_set, 'self')

    def assign_prop(self, prop, action):
        if prop not in self.prop_action_set:
            self.prop_action_set[prop] = set()
        self.prop_action_set[prop].add(action)

    # Check whether this page has 'check_ancestor' as a Linnaean ancestor.
    def has_linn_ancestor(self, check_ancestor):
        ancestor = self
        while ancestor:
            if ancestor == check_ancestor:
                return True
            ancestor = ancestor.linn_parent
        return False

    # Check Linnaean descendants of link_from to find real pages that
    # it can link to.
    def get_potential_link_set(self, potential_link_set, link_from):
        if self.shadow:
            # Keep recursing downward.
            # Since this page isn't real, we can be sure that it has no
            # real child links in self.child to worry about.
            for child in self.linn_child:
                child.get_potential_link_set(potential_link_set, link_from)
        else:
            # This page could have a real unranked parent that does or
            # does not also have link_from as a Linnaean ancestor.
            # (Note that this page cannot have a real ranked parent
            # because that would have been found first in the Linnaean
            # descent.)
            #
            # If a real (unranked) parent is also under the link_from
            # page, then that real parent will get a link, and there's no
            # no need to also make a link to this child.  (If the real
            # parent is ranked
            for parent in self.parent:
                if parent.has_linn_ancestor(link_from):
                    return

            # This is a potential link target.
            potential_link_set.add(self)

    # Promote a shadow page to be real.
    def promote_to_real(self):
        self.shadow = False
        page_array.append(self)

    def apply_prop_link(self):
        if ((self.shadow and self.rp_do('create')) or
            (not self.shadow and self.rp_do('link'))):
            # Check for Linaean descendants that can potentially be linked to
            # this parent.
            potential_link_set = set()
            for child in self.linn_child:
                # Ignore children that already have a real link
                # and subset pages.
                if child not in self.child and not child.subset_of_page:
                    child.get_potential_link_set(potential_link_set, self)

            if (self.shadow and
                potential_link_set and
                self.rp_do('create')):
                self.promote_to_real()

            self.non_txt_children = potential_link_set
            for child in potential_link_set:
                self.assign_child(child)

    def sort_children(self):
        # If children were linked to the page via the Linnaean hierarchy,
        # they may be in a non-intuitive order.  We re-order them here.
        # This includes both adjusting their order in self.child and
        # also adding links to them in the txt.
        if self.non_txt_children:
            self.child = self.child[:-len(self.non_txt_children)]
            for child in sort_pages(self.non_txt_children):
                self.child.append(child)
                self.txt += f'==\n'

        if self.subset_of_page:
            # Get the top layer of pages in the subset.
            # This also propagates membership information to those descendent
            # pages that have a matching trait value.  This must be done before
            # check_traits() so that it can tell which trait values are used
            # in each part of the hierarchy.
            primary = self.subset_of_page
            self.subset_page_list = find_matches(primary.child,
                                                 self.subset_trait,
                                                 self.subset_value)

    def check_traits(self):
        for trait in sorted(self.trait_values):
            if trait not in self.traits_used:
                error(f'no page makes use of trait: {trait} defined in {self.full()}')
            else:
                values_not_used = ', '.join(self.trait_values[trait] -
                                            self.traits_used[trait])
            if values_not_used:
                error(f'no page makes use of these {trait} values defined in {self.full()}: {values_not_used}')

        for trait in traits:
            if self.photo_dict and trait not in self.trait_values:
                self.rp_check(f'photo_requires_{trait}',
                              f'page {self.full()} has photos but no assigned {trait}')

    # Apply properties not related to link creation.
    def apply_most_props(self):
        self.apply_prop_member()
        self.apply_prop_checks()

    def propagate_membership(self, ancestor):
        for child in self.child:
            child.assign_membership(ancestor)
        for child in self.linn_child:
            # There's no harm in repeating a descendent, but we might as
            # well avoid the common case of repeating a direct child.
            if child not in self.child:
                child.assign_membership(ancestor)

    def assign_membership(self, ancestor):
        if ancestor not in self.membership_list and ancestor not in self.parent:
            self.membership_list.append(ancestor)
        self.propagate_membership(ancestor)

    def rp_check(self, prop, msg, shadow_bad=False):
        # A shadow page normally is only checked if shadow_bad is True.
        if self.shadow and not shadow_bad:
            return

        if prop in self.prop_action_set:
            if 'error' in self.prop_action_set[prop]:
                error(f'error {prop}: {msg}')
            elif 'warn' in self.prop_action_set[prop]:
                warn(f'warn {prop}: {msg}')

    def rp_action(self, prop, action):
        return (prop in self.prop_action_set and
                action in self.prop_action_set[prop])

    def rp_do(self, prop, msg=None, shadow_bad=False):
        self.rp_check(prop, msg)
        return self.rp_action(prop, 'do')

    def apply_prop_member(self):
        if ((not self.shadow and self.rp_do('member_link')) or
            (self.shadow and self.rp_do('member_name'))):
            self.propagate_membership(self)

    def apply_prop_checks(self):
        if self.shadow:
            # None of these checks apply to shadow pages.
            return

        if not (self.sci or self.no_sci):
            self.rp_check('no_sci',
                          f'{self.full()} has no scientific name')

        if not (self.com or self.no_com):
            self.rp_check('no_com',
                          f'{self.full()} has no common name')

        if self.count_flowers() and not self.get_jpg('', set_rep_jpg=False):
            self.rp_check('obs_requires_photo',
                          f'{self.full()} is observed but has no photos')

        if self.photo_dict and not self.bugguide_id:
            self.rp_check('photo_requires_bugid',
                          f'{self.full()} has photos but has no bugguide ID')

        if len(self.child) == 1:
            self.rp_check('one_child',
                          f'{self.full()} has exactly one child')

        for trait in sorted(traits):
            if trait in self.trait_values and not self.photo_dict:
                self.rp_check(f'{trait}_requires_photo',
                              f'{self.full()} has a {trait} assigned but has no photos')

    def expand_abbrev(self, sci):
        if len(sci) > 3 and sci[1:3] == '. ':
            # sci has an abbreviated genus name
            if self.no_names:
                # If this page doesn't have a name yet, then either the
                # filename is a scientific name that provides the genus,
                # or we'll get a fatal error below.  So it is either useful
                # or harmless to use the filename as the scientific name.
                self.set_sci(self.name)

            if self.rank and self.rank <= Rank.genus and self.sci[0] == sci[0]:
                sci_words = self.sci.split(' ')
                return sci_words[0] + sci[2:]
            else:
                fatal(f'Abbreviation "{sci}"  cannot be parsed in page "{self.full()}"')
        if sci.startswith(('ssp. ', 'var. ')):
            # sci has an abbreviated subspecies or variety
            if self.no_names:
                self.set_sci(self.name)

            return self.sci + ' ' + sci

        return sci

    def parse_children_and_attributes(self):
        # Replace a ==[name] link with ==[page] and record the
        # parent->child relationship.
        def repl_child(matchobj):
            # ==[*]com[,suffix][:sci] -> creates a child relationship with the
            #   page named by [com] or [sci] and creates two links to it:
            #   an image link and a text link.
            #   If a suffix is specified, the jpg with that suffix is used
            #   for the image link.
            #   If [:sci] isn't specified, a scientific name can be used
            #   in place of [com].
            #   If the child page doesn't exist, it is created.  If the
            #   child page is missing a common or scientific name that
            #   is supplied by the child link, that name is added to the child.
            #   The scientific name can be in elaborated or stripped format.
            #   The genus can also be abbreviated as '[capital letter]. '
            is_rep = matchobj.group(1)
            com = matchobj.group(2)
            com_suffix = matchobj.group(3)
            sci = matchobj.group(4)
            sci_suffix = matchobj.group(5)

            if com_suffix:
                if sci_suffix:
                    error(f'Two suffixes used in child declaration in page "{self.full()}"')
                suffix = com_suffix
            elif sci_suffix:
                suffix = sci_suffix
            else:
                suffix = ''
                
            if not sci:
                if is_sci(com):
                    sci = com
                    com = None
                else:
                    sci = None

            if sci:
                # If the child's genus is abbreviated, expand it using
                # the genus of the current page.
                sci = self.expand_abbrev(sci)

            child_page = find_page2(com, sci)

            if not child_page:
                # If the child does not exist, create it.
                child_page = Page(com, sci, src='child of '+self.name+'.txt')

            try:
                self.assign_child(child_page)
            except FatalError:
                warn(f'was adding {child_page.full()} as a child of {self.full()}')
                raise

            if is_rep:
                if self.rep_child is not None:
                    error(f'{self.full()} declares multiple representative children (with ==*...)')
                self.rep_child = child_page

            # Replace the =={...} field with a simplified =={suffix} line.
            # This will create the appropriate link later in the parsing.
            return f'=={suffix}'

        c_list = []
        data_object = self
        for c in self.txt.split('\n'):
            # Look for a child declaration:
            #   ==
            #   optional asterix denoting a representative child: *
            #   common name (or scientific name): ([^:]*?)
            #   optional jpg suffix: (,[-0-9][^,:]*|,)?
            #   optional colon then scientific name: (?::\s*(.+?))?
            #     followed by optional jpg suffix: (,[-0-9][^,:]*|,)?
            # All can be separated by whitespace: \s*
            matchobj = re.match(r'==\s*(\*?)\s*([^:]*?)\s*(,[-0-9][^,:]*|,)?\s*(?::\s*(.+?)\s*(,[-0-9][^,:]*|,)?)?\s*$', c)
            if matchobj:
                c_list.append(repl_child(matchobj))
                data_object = self.child[-1]
                continue

            matchobj = re.match(r'rep:\s*(.+?)\s*$', c)
            if matchobj:
                jpg = matchobj.group(1)
                if jpg.startswith(','):
                    jpg = data_object.name + jpg
                    if jpg not in jpg_photos:
                        error(f'Broken rep: {jpg} in {self.full()}')
                        continue
                if jpg in jpg_photos:
                    data_object.rep_jpg = jpg
                else:
                    # If it's not a jpg, then maybe it's a child name.
                    # Unfortunately, we don't have all names yet, so record
                    # the name for now and resolve it later.
                    data_object.rep_child = jpg
                continue

            matchobj = re.match(r'acom:\s*(.+?)$', c)
            if matchobj:
                data_object.acom = split_strip_quoted(matchobj.group(1))
                continue

            matchobj = re.match(r'sci_([fpjib]+):\s*(.+?)$', c)
            if matchobj:
                data_object.set_sci_alt(matchobj.group(1),
                                        self.expand_abbrev(matchobj.group(2)))
                continue

            matchobj = re.match(r'^asci:\s*(.+?)\s*?$', c)
            if matchobj:
                sci = strip_sci(matchobj.group(1))
                if sci in sci_page:
                    fatal(f'{self.full()} specifies asci: {sci}, but that name already exists')
                sci_page[sci] = data_object
                continue

            matchobj = re.match(r'is_top\s*$', c)
            if matchobj:
                data_object.is_top = True
                continue

            matchobj = re.match(r'default_ancestor\s*$', c)
            if matchobj:
                global default_ancestor
                if default_ancestor:
                    error(f'default_ancestor specified for both {default_ancestor.full()} and {data_object.full()}')
                else:
                    default_ancestor = self
                continue

            matchobj = re.match(rf'^(?:(\w+)\s+)?({prop_re})\s*:\s*(.+?)$', c)
            if matchobj:
                data_object.declare_property(matchobj.group(1),
                                             matchobj.group(2),
                                             matchobj.group(3))
                continue

            matchobj = re.match(r'\s*(?:([^:\n]*?)\s*:\s*)?(https://(?:calphotos.berkeley.edu/|www.calflora.org/cgi-bin/noccdetail.cgi)[^\s]+)\s*?$', c)
            if matchobj:
                # Attach the external photo to the current child, else to self.
                data_object.record_ext_photo(matchobj.group(1),
                                             matchobj.group(2))
                continue

            matchobj = re.match(r'subset\s+(\S*)\s*:\s*(.+?)\s*(?:,\s*(.+?)\s*)?,\s*(.+?)\s*$', c)
            if matchobj:
                data_object.record_subset(matchobj.group(1),
                                          matchobj.group(2),
                                          matchobj.group(3),
                                          matchobj.group(4))
                continue

            for trait in traits:
                matchobj = re.match(rf'{trait}\s*:\s*(.+?)\s*$', c)
                if matchobj:
                    data_object.set_trait_values(trait, matchobj.group(1))
                    break
            if matchobj:
                continue

            matchobj = re.match(r'list_hierarchy\s*$', c)
            if matchobj:
                data_object.list_hierarchy = True
                continue

            matchobj = re.match(r'end_hierarchy\s*$', c)
            if matchobj:
                data_object.end_hierarchy = True
                continue

            matchobj = re.match(r'taxon_id\s*:\s*(\d+)$', c)
            if matchobj:
                data_object.set_taxon_id(matchobj.group(1))
                continue

            matchobj = re.match(r'bug\s*:\s*(\d+|n/a)$', c)
            if matchobj:
                id = matchobj.group(1)
                if data_object.bugguide_id and id != data_object.bugguide_id:
                    error(f'conflicting bugg IDs in {data_object.full()}')
                data_object.bugguide_id = id
                continue

            matchobj = re.match(r'(x|xx):\s*(!?)(.*?)\s*$', c)
            if matchobj:
                data_object.set_complete(matchobj)
                continue

            # Look for a group declaration, e.g. 'family: [name]'
            matchobj = re_group.match(c)
            if matchobj:
                # We don't create the Linnaean link right away because
                # doing so could create a shadow page, and we don't
                # want to create any shadow pages until all real
                # children have been processed from the txt files
                # (thus giving them their official common and scientific
                # names).  So instead we record the group for later.
                rank = Rank[matchobj.group(1)]
                name = matchobj.group(2)
                if not is_sci(name) and rank in (Rank.species, Rank.genus):
                    # Only a common name is given, but we can derive the
                    # scientific name.
                    if rank == Rank.genus:
                        sci = data_object.sci.split(' ')[0]
                    else:
                        sci = ' '.join(data_object.sci.split(' ')[0:2])
                else:
                    sci = None
                data_object.group_items.append((rank, name, sci));
                continue

            matchobj = re.match(r'\s*member:\s*([^:]+)(?:\:(.+?))?\s*$', c);
            if matchobj:
                # We don't create the Linnaean link right away because
                # doing so could create a shadow page, and we don't
                # want to create any shadow pages until all real
                # children have been processed from the txt files
                # (thus giving them their official common and scientific
                # names).  So instead we record the group for later.
                name = matchobj.group(1)
                sci = matchobj.group(2)
                data_object.group_items.append((None, name, sci))
                continue

            if c in ('', '[', ']'):
                data_object = self

            c_list.append(c)
        self.txt = '\n'.join(c_list) + '\n'

    def link_style(self):
        if self.has_child_key:
            return 'parent'
        elif self.child or self.subset_of_page:
            return 'family'
        elif self.photo_dict:
            return 'leaf'
        else:
            return 'unobs'

    def create_link(self, lines, text=None):
        pageurl = self.get_url()
        if text is None:
            text = self.format_full(lines)
        return f'<a href="{pageurl}.html" class="{self.link_style()}">{text}</a>'

    def align_column(self, intro, c_list):
        if len(c_list) == 1:
            return f'<p>\n{intro} {c_list[0]}\n</p>\n'
        elif c_list:
            # Line up the members in a column with the first item just to
            # the right of the intro text.
            #
            # Note that the white space after "of" creates a "space"-sized
            # gap between the intro and the following div.
            s = '<br>\n'.join(c_list)
            return f'<p>\n{intro}\n<span class="membership">\n{s}\n</span>\n</p>\n'
        else:
            return ''

    # Create a link to a page that this page is a member of.
    # Also include any trait subsets of that page that this page is part of.
    def member_of(self, ancestor):
        value_list = []
        for trait in sorted(ancestor.subset_pages):
            for subset_page in ancestor.subset_pages[trait]:
                if (trait in self.trait_values and
                    subset_page.subset_value in self.trait_values[trait]):
                    value_list.append(subset_page.create_link(1, subset_page.subset_list_name))
        if value_list:
            # When there is a matching value list, it makes the member line long
            # and complicated.  Simplify it somewhat by using the ancestor's
            # short name instead of its full name.
            return (', '.join(value_list) + ' in ' +
                    ancestor.create_link(1, ancestor.format_short()))
        else:
            return ancestor.create_link(1)

    def write_membership(self):
        c_list = []

        # Subset pages are a special case which are always a member of
        # their parent page regardless of properties.
        if self.subset_of_page:
            if self.subset_of_page not in self.membership_list:
                self.membership_list.append(self.subset_of_page)

        # If the page has autopopulated parents,
        # add them to the membership list.
        # Parents with keys are listed more prominently in a separate section.
        for parent in self.parent:
            if not parent.has_child_key:
                self.membership_list.append(parent)

        # membership_list lists the ancestors that this page should
        # be listed as a 'member of', unsorted.
        #
        # If this page isn't a direct child of its real ancestor, provide
        # a link to it.  (A direct child would have been listed above
        # or will be listed further below.)  Note that the family page
        # is likely to have been autopopulated, but not necessarily.
        #
        # For a shadow ancestor, write it as unlinked text.
        ordered_list = sort_pages(self.membership_list,
                                  with_depth=True, with_count=False)
        for ancestor in reversed(ordered_list):
            if ancestor.shadow:
                if (not (ancestor.com or ancestor.no_com) and
                    not ancestor.com_checked):
                    
                    if ancestor.rank:
                        ancestor_txt = f'its {ancestor.rank.name}'
                    else:
                        ancestor_txt = f'{ancestor.elab()}'
                    ancestor.rp_check('no_com',
                                      f'{self.full()} lists {ancestor_txt} as an ancestor, but that has no common name',
                                      shadow_bad=True)
                    ancestor.com_checked = True
                
                if (ancestor.rank in (Rank.genus, Rank.species) and
                    self.rank in (Rank.species, Rank.below) and
                    not ancestor.com):
                    # If the scientific name is trivially derived from
                    # the species/subspecies/variety name, and the ancestor
                    # doesn't have a common name, don't bother to list it.
                    pass
                else:
                    c_list.append(ancestor.format_full(1))
            else:
                c_list.append(self.member_of(ancestor))

        return self.align_column('Member of', c_list)

    def write_keyed_parents(self):
        c_list = []
        for parent in sort_pages(self.parent):
            if parent.has_child_key:
                c_list.append(parent.create_link(1))
        return self.align_column('Key to', c_list)

    def page_matches_trait_value(self, trait, value):
        return (trait is None or
                (trait in self.trait_values and
                 value in self.trait_values[trait]))

    def count_matching_obs(self, obs):
        obs.count_matching_obs(self)

    # Write the iNaturalist observation data.
    def write_obs(self, w, obs=None):
        if not obs:
            obs = Obs(None, None)
            self.count_matching_obs(obs)

        if self.taxon_id:
            link = f'https://www.inaturalist.org/observations/chris_nelson?taxon_id={self.taxon_id}&order_by=observed_on'
        elif self.sci:
            elab = self.choose_elab(self.elab_inaturalist)
            sci = strip_sci(elab)
            sciurl = url(sci)
            link = f'https://www.inaturalist.org/observations/chris_nelson?taxon_name={sciurl}&order_by=observed_on'
        else:
            link = None

        obs.write_obs(link, w)

    def choose_elab(self, elab_alt):
        if elab_alt and elab_alt != 'n/a':
            elab = elab_alt
        else:
            elab = self.elab
        return elab

    def write_external_links(self, w):
        sci = self.sci
        if self.rank and self.rank is Rank.below:
            # Anything below species level should be elaborated as necessary.
            elab = self.elab
        else:
            # A one-word genus should be sent as is, not as '[genus] spp.'
            # A higher-level classification should be sent with the group type
            # removed.
            elab = sci

        elab_list = []
        link_list = {} # list of links for each elab

        def add_link(elab, elab_alt, link):
            if elab_alt == 'n/a':
                elab = 'not listed'
                link = re.sub(r'<a ', '<a class="missing" ', link)
            if elab not in link_list:
                elab_list.append(elab)
                link_list[elab] = []
            link_list[elab].append(link)

        if self.rp_do('link_inaturalist'):
            elab = self.choose_elab(self.elab_inaturalist)
            if self.taxon_id:
                elab = format_elab(elab)
                add_link(elab, None, f'<a href="https://www.inaturalist.org/taxa/{self.taxon_id}" target="_blank" rel="noopener noreferrer">iNaturalist</a>')
            elif self.elab_inaturalist != 'n/a':
                sci = strip_sci(elab, keep='x')
                sci = re.sub(r' X', ' \xD7 ', sci)
                sciurl = url(sci)
                elab = format_elab(elab)
                add_link(elab, None, f'<a href="https://www.inaturalist.org/taxa/search?q={sciurl}&view=list" target="_blank" rel="noopener noreferrer">iNaturalist</a>')

        if self.bugguide_id and self.bugguide_id != 'n/a':
            elab = self.choose_elab(self.elab_bugguide)
            elab = format_elab(elab)
            add_link(elab, None, f'<a href="https://bugguide.net/node/view/{self.bugguide_id}" target="_blank" rel="noopener noreferrer">BugGuide</a>')

        if self.rp_do('link_calflora'):
            # Calflora can be searched by family,
            # but not by other high-level classifications.
            elab = self.choose_elab(self.elab_calflora)
            sci = strip_sci(elab, keep='b')
            sciurl = url(sci)
            elab = format_elab(elab)
            add_link(elab, self.elab_calflora, f'<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup={sciurl}" target="_blank" rel="noopener noreferrer">Calflora</a>');

        if self.rp_do('link_calphotos'):
            # CalPhotos cannot be searched by high-level classifications.
            # It can be searched by genus, but I don't find that at all useful.
            elab = self.choose_elab(self.elab_calphotos)
            elab_terms = elab.split('|')
            sci_terms = []
            formatted_elab_terms = []
            for e in elab_terms:
                sci_terms.append(strip_sci(e, keep='b'))
                formatted_elab_terms.append(format_elab(e))

            sci = strip_sci(self.elab, keep='b')
            if sci not in sci_terms and elab != 'n/a':
                # CalPhotos can search for multiple names, and for cases such
                # as Erythranthe, it may have photos under both names.
                # Use both names when linking to CalPhotos, but for simplicity
                # list only the txt-specified name in the HTML listing.
                sci_terms.insert(0, sci)
            sci = '|'.join(sci_terms)
            sciurl = url(sci)
            elab = ' / '.join(formatted_elab_terms)
            # rel-taxon=begins+with -> allows matches with lower-level detail
            add_link(elab, self.elab_calphotos, f'<a href="https://calphotos.berkeley.edu/cgi/img_query?rel-taxon=begins+with&where-taxon={sciurl}" target="_blank" rel="noopener noreferrer">CalPhotos</a>');

        if self.rp_do('link_jepson'):
            # Jepson can be searched by family,
            # but not by other high-level classifications.
            elab = self.choose_elab(self.elab_jepson)
            # Jepson uses "subsp." instead of "ssp.", but it also allows us to
            # search with that qualifier left out entirely.
            sci = strip_sci(elab)
            sciurl = url(sci)
            elab = format_elab(elab)
            add_link(elab, self.elab_jepson, f'<a href="http://ucjeps.berkeley.edu/eflora/search_eflora.php?name={sciurl}" target="_blank" rel="noopener noreferrer">Jepson&nbsp;eFlora</a>');

        if self.com and self.rp_do('link_birds'):
            # AllAboutBirds can only be searched by species name
            # and can only be directly linked by common name.
            elab = format_elab(self.elab)

            birds_com = self.com
            # apostrophes are dropped
            birds_com = re.sub(r"'", '', birds_com)
            # spaces are converted to underscores
            birds_com = re.sub(r" ", '_', birds_com)
            birds_com = birds_com.title() # AllAboutBirds URL uses title case
            comurl = url(birds_com)

            add_link(elab, None, f'<a href="https://www.allaboutbirds.org/guide/{comurl}/id" target="_blank" rel="noopener noreferrer">AllAboutBirds</a>')

        link_list_txt = []
        for elab in elab_list:
            txt = '\n&ndash;\n'.join(link_list[elab])
            if len(elab_list) > 1:
                txt = f'{elab} &rarr; {txt}'
            link_list_txt.append(txt)
        txt = '</li>\n<li>'.join(link_list_txt)

        if len(elab_list) > 1:
            w.write(f'<p class="list-head">Not all sites agree about the scientific name:</p>\n<ul>\n<li>{txt}</li>\n</ul>\n')
        elif elab_list:
            w.write(f'<p>\nTaxon info:\n{txt}\n</p>\n')

        species_maps = []

        if self.rp_do('link_bayarea_inaturalist'):
            if self.taxon_id and self.rank and self.rank >= Rank.genus:
                query = f'taxon_id={self.taxon_id}'
            else:
                elab = self.choose_elab(self.elab_inaturalist)
                if elab[0].islower():
                    # Drop the rank specifier from the name.
                    barename = elab.split(' ')[1]
                else:
                    # Drop any species/sub-species elaboration, keeping only
                    # the genus.
                    barename = elab.split(' ')[0]
                barenameurl = url(barename)
                query = f'taxon_name={barenameurl}'
            species_maps.append(f'<a href="https://www.inaturalist.org/observations?captive=false&nelat=38&nelng=-121.35&swlat=36.85&swlng=-122.8&{query}&view=species" target="_blank" rel="noopener noreferrer">iNaturalist</a>')

        if self.rp_do('link_bayarea_calflora'):
            elab = self.choose_elab(self.elab_calflora)
            # srch=t -> search
            # taxon={name} -> scientific name to filter for (genus or below)
            # family={name} -> scientific name to filter for (family)
            # group=none -> just one list; not groups of annual, perennial, etc.
            # sort=count -> sort from most records to fewest
            #   (removed because it annoyingly breaks up subspecies)
            # fmt=photo -> list results with info + sample photos
            # y={},x={},z={} -> longitude, latitude, zoom
            # wkt={...} -> search polygon with last point matching the first
            sci = strip_sci(elab)
            taxon = sci.split(' ')[0]
            taxonurl = url(taxon)
            if self.rank and self.rank is Rank.family:
                query = f'family={taxonurl}'
            else:
                query = f'taxon={taxonurl}'
            species_maps.append(f'<a href="https://www.calflora.org/entry/wgh.html#srch=t&group=none&{query}&fmt=photo&y=37.5&x=-122&z=8&wkt=-123.1+38,-121.95+38,-121.05+36.95,-122.2+36.95,-123.1+38" target="_blank" rel="noopener noreferrer">Calflora</a>')

        if species_maps:
            txt = '\n&ndash;\n'.join(species_maps)
            w.write(f'<p>\nBay&nbsp;Area&nbsp;species:\n{txt}\n</p>\n')


    # List a single page, indented if it is under a parent.
    def list_page(self, w, indent, has_children):
        if indent:
            indent_class = ' indent'
        else:
            indent_class = ''

        if has_children:
            # A parent with listed children puts itself in a box.
            # The box may be indented depending on the indent parameter.
            # The page is then not indented within the box.
            w.write(f'<div class="box{indent_class}">\n')
            indent_class = ''

        w.write(f'<div class="list-box{indent_class}">')

        if self.photo_dict or self.end_hierarchy:
            jpg = self.get_jpg('')
        else:
            jpg = None

        if jpg:
            pageurl = self.get_url()
            w.write(f'<a href="{pageurl}.html"><div class="list-thumb"><img class="boxed" src="{thumb_url(jpg)}" alt="photo"></div></a>')

        w.write(f'{self.create_link(2)}</div>\n')

#    def get_ancestor_set(self):
#        ancestor_set = set()
#        ancestor_set.add(self)
#        for parent in self.parent:
#            ancestor_set.update(parent.get_ancestor_set())
#        return ancestor_set

    def cross_out_children(self, page_list):
        if self in page_list:
            page_list.remove(self)
        for child in self.child:
            child.cross_out_children(page_list)

    def set_glossary(self, glossary, jepson_glossary, glossary_warn):
        if self.glossary:
            if not glossary or self.glossary.has_ancestor(glossary):
                # The glossary that we want to set is the same as is already
                # in self.glossary, or it is a higher-level glossary (or none).
                # In all these cases, the existing glossary is fine for this
                # node and its children, so there's no need to continue the
                # tree traversal through this node.
                return

            if glossary.has_ancestor(self.glossary):
                # The glossary that is already set is a higher level of
                # the one that we want to set.  We don't need to adjust the
                # glossary hierarchy, but we do need to update this node
                # and its descendents to use the lower-level glossary.
                self.assign_glossary(glossary, jepson_glossary, glossary_warn)
                return

            # The glossary that we want to set has a hierarchy incompatible
            # with the glossary that is already set.  Print an error message.

            if self.name in glossary_taxon_dict:
                if self.glossary.parent:
                    parent = self.glossary.parent.name
                else:
                    parent = 'None'
            else:
                parent = self.glossary.name

            error(f'{self.full()} has incompatible parent glossaries, {parent_name} and {glossary.name}')
            return

        # This node doesn't have a glossary yet.

        if jepson_glossary and self.name == jepson_glossary.taxon:
            jepson_glossary.set_parent(glossary)
            glossary = jepson_glossary

        if self.name in glossary_taxon_dict:
            # Set the glossary of this taxon as a child of
            # the parent glossary of this taxon.
            sub_glossary = glossary_taxon_dict[self.name]
            sub_glossary.set_parent(glossary)
            glossary = sub_glossary

        self.assign_glossary(glossary, jepson_glossary, glossary_warn)

    def assign_glossary(self, glossary, jepson_glossary, glossary_warn):
        self.glossary = glossary
        self.glossary_warn.update(glossary_warn)

        for child in self.child:
            child.set_glossary(glossary, jepson_glossary, self.glossary_warn)

    def parse_child_and_key(self, child, suffix, text, match_set):
        def repl_example(matchobj):
            suffix = matchobj.group(1)
            if suffix in child.photo_dict:
                jpg = child.photo_dict[suffix]
            else:
                error(f'Broken [example{suffix}] for child {child.full()} in {self.full()}')
                jpg = suffix
            return f'<a class="leaf" href="../photos/{url(jpg)}.jpg">[example]</a>'

        # If the key includes '[example,<suffix>]', create an [example]
        # link in the parent text, but remove the link from the child key.
        key_txt = re.sub(r'\s*\[example(,.*?)\]', '', text)
        text = re.sub(r'\[example(,.*?)\]', repl_example, text)

        # Give the child a copy of the text from the parent's key
        # (minus any [example] links).  The child can use this (pre-parsed)
        # text if it has no text of its own.
        #
        # If a child has more than one parent key, priority for key_txt
        # is given to the ranked parent.
        if key_txt and (self.rank or not child.key_txt):
            child.key_txt = key_txt

            # Remember that at least one child was given key info.
            self.has_child_key = True

        link = child.create_link(2)

        name = child.name
        jpg = child.get_jpg(suffix)

        if not jpg:
            ext_photo = child.get_ext_photo()

        pageurl = child.get_url()
        if jpg:
            img = f'<a href="{pageurl}.html"><div class="key-thumb"><img class="boxed" src="{thumb_url(jpg)}" alt="photo"></div></a>'
        elif ext_photo:
            img = f'<a href="{pageurl}.html" class="enclosed {child.link_style()}"><div class="key-thumb-text">'
            n_photos = len(child.ext_photo_list)
            if n_photos > 1:
                photo_text = f'photos &times; {n_photos}'
            elif ext_photo[0]:
                photo_text = ext_photo[0]
            else:
                photo_text = 'photo'
            img += f'<span>{photo_text}</span>'
            img += '</div></a>'
        else:
            img = None

        if self.list_hierarchy:
            s = io.StringIO()
            list_matches(s, [child], False, None, None, match_set)
            return s.getvalue()
        elif not img:
            return '<p>' + link + '</p>\n' + text
        elif text:
            # Duplicate and contain the text link so that the following text
            # can either be below the text link and next to the image or
            # below both the image and text link, depending on the width of
            # the viewport.
            return f'<div class="flex-width"><div class="photo-box">{img}\n<span class="show-narrow">{link}</span></div><div class="key-text"><span class="show-wide">{link}</span>{text}</div></div>'
        else:
            return f'<div class="photo-box">{img}\n<span>{link}</span></div>'


    def parse(self):
        # If a parent already parsed this page (as below), we shouldn't
        # try to parse it again.
        if self.parsed:
            return
        self.parsed = True

        # A parent's link to a child may be styled depending on whether the
        # child is itself a key (has_child_key).  Which means that a parent
        # wants to parse its children before parsing itself.
        for child in self.child:
            child.parse()

        s = self.txt

        s = parse_txt(self.name, s, self, self.glossary)

        if not self.has_child_key:
            # No child has a key, so reduce the size of child photos.
            # This applies to both key-thumb and key-thumb-text
            s = re.sub(r'class="key-thumb', r'class="list-thumb', s)

        self.txt = s

    def parse2(self):
        # Use the text supplied in the text file if present.
        # Otherwise use the key text from its parent.
        # If the page's text file contains only metadata (e.g.
        # scientific name or trait value) so that the remaining text is
        # blank, then use the key text from its parent in that case, too.
        if re.search('\S', self.txt):
            s = self.txt
        else:
            s = self.key_txt

        self.txt = parse2_txt(self.name, s, self.glossary)

    # Check whether this page is the top real page within its Linnaean group
    # designated by 'rank'.  E.g. if a species page does not have a real page
    # for its genus, it is the top of its genus (and species, of course).
    def is_top_of(self, rank):
        if not self.rank or self.rank > rank:
            return False

        ancestor = self.linn_parent
        while ancestor and ancestor.rank <= rank:
            if not ancestor.shadow: return False
            ancestor = ancestor.linn_parent
        return True

    def taxon_unknown_completion(self):
        if self.rank >= Rank.genus:
            complete = self.genus_complete
        else:
            complete = self.species_complete
        return complete in ('ba', 'ca', 'any', 'none')

    def lower_complete(self):
        if self.genus_complete:
            return self.genus_complete
        elif self.child:
            # Use the loosest constraint among children.
            complete = 'any' # start with a tight constraint, then loosen it
            for child in self.child:
                child_complete = child.lower_complete()
                complete = looser_complete(complete, child_complete)
            return complete
        else:
            # No completeness constraint specified
            return None

    def ancestor_matches_complete(self, complete):
        if self.genus_complete == complete:
            return True

        for parent in self.parent:
            if parent.ancestor_matches_complete(complete):
                return True

        # No ancestor matched
        return False

    # Find the loosest child completeness constraint, then look to see if
    # that matches any parent constraint.  If so, use it.
    #
    # Note that parent constraints ought to be at least as loose.  If
    # a parent is looser, then it's not clear whether this page should
    # also be similarly loose, so we leave it as unknown.
    #
    # The child and parent searches both include the page itself,
    # so if the page has genus_complete set, then it is directly used.
    def get_complete(self):
        complete = self.lower_complete()

        if not complete:
            # early exit for efficiency
            return None

        if self.ancestor_matches_complete(complete):
            return complete
        else:
            return None

    def write_html(self):
        def write_complete(w, complete, key_incomplete, is_top, top):
            if top == 'genus':
                members = 'species'
            else:
                members = 'members'

            if is_top:
                w.write('<p>')

                if (self.child or
                    (top == 'genus' and self.rank is not Rank.genus) or
                    (top == 'species' and self.rank is not Rank.species)):
                    other = ' other'
                else:
                    other = ''

                # We might be checking the completeness at a different level
                # than the current page's rank.  The property propagation
                # code gave us an assist by recording the appropriate action
                # at the genus and species level with a modified property name.
                if top in ('genus', 'species'):
                    prop = 'default_completeness_' + top
                else:
                    prop = 'default_completeness'

                if complete is None:
                    # We don't want to expose the hacked property name to
                    # the user, so we check for error/warn manually and not
                    # through the usual rp_check() function.
                    if prop in self.prop_action_set:
                        if ((top == 'genus' and self.rank is not Rank.genus) or
                            (top == 'species' and self.rank is not Rank.species)):
                            msg = f'completeness not specified at the {top} level in {self.full()}'
                        else:
                            msg = f'completeness not specified in {self.full()}'

                        if 'error' in self.prop_action_set[prop]:
                            error(f'error default_completeness: {msg}')
                        elif 'warn' in self.prop_action_set[prop]:
                            warn(f'warn default_completeness: {msg}')

                    if self.rp_action(prop, 'caution'):
                        w.write(f'<b>Caution: There may be{other} wild {members} of this {top} not yet included in this guide.</b>')
                    elif self.rp_action(prop, 'do'):
                        w.write(f'<b>Caution: There may be{other} wild {members} of this {top} not yet included in this guide.</b>')
                    else:
                        # Don't write anything, including the </p> at the end
                        return
                elif complete == 'none':
                    if top == 'species':
                        w.write('This species has no subspecies or variants.')
                    else:
                        error("x:none used for " + self.full())
                elif complete == 'uncat':
                    if top == 'genus':
                        error("x:uncat used for " + self.full())
                    else:
                        w.write("This species has subspecies or variants that don't seem worth distinguishing.")
                elif complete == 'more':
                    if self.rp_action(prop, 'caution'):
                        caution = 'Caution: '
                    else:
                        caution = ''
                    if other:
                        w.write(f'<b>{caution}There are other wild {members} of this {top} not yet included in this guide.</b>')
                    elif top == 'species':
                        w.write(f'<b>{caution}This {top} has wild {members}, but they are not yet included in this guide.</b>')
                    else:
                        w.write(f'<b>{caution}Members of this {top} are not yet included in this guide.</b>')
                elif complete in ('ba', 'ca', 'any',
                                     'hist', 'rare', 'hist/rare'):
                    if complete == 'hist':
                        prolog = f"Except for historical records that I'm ignoring, there are no{other}"
                    elif complete == 'rare':
                        prolog = f"Except for extremely rare examples that I don't expect to encounter, there are no{other}"
                    elif complete == 'hist/rare':
                        prolog = f"Except for old historical records and extremely rare examples that I don't expect to encounter, there are no{other}"
                    else:
                        prolog = f'There are no{other}'

                    if complete == 'ca':
                        epilog = 'in California'
                    elif complete == 'any':
                        epilog = 'anywhere'
                    else:
                        epilog = 'in the bay area'

                    w.write(f'{prolog} wild {members} of this {top} {epilog}.')
                else:
                    # user-specified text instead of a standard abbreviation
                    w.write(complete);
                if key_incomplete:
                    w.write(f'<br>\n<b>Caution: The key to distinguish these {members} is not complete.</b>')
                w.write('</p>\n')
            elif complete:
                if top == 'genus':
                    error(f'{self.full()} uses the x: keyword but is not the top of genus')
                else:
                    error(f'{self.full()} uses the xx: keyword but is not the top of species')

        with write_and_hash(f'html/{self.get_filename()}.html') as w:
            com = self.com
            elab = self.elab

            if com:
                title = self.format_com()
                h1 = title
            else:
                # If the page has no common name (only a scientific name),
                # then the h1 header should be italicized and elaborated.
                title = self.format_elab(ital=False)
                h1 = self.format_elab()

            full = self.format_full(lines=1, ital=False)
            what = f'{full} in the Bay Area Wildflower Guide.'
            if self.list_hierarchy:
                desc = f'Hierarchy of {what}'
            elif self.has_child_key:
                desc = f'Key to {what}'
            elif self.child or self.subset_of_page:
                desc = f'List of {what}'
            elif self.txt:
                desc = f'Description of {what}'
            else:
                desc = f'Stub for {what}'

            # Calculate other names that should be cuddled up with the
            # title name.
            c_list = []

            # List the iNaturalist common name if it's different.
            if self.acom:
                acom = ', '.join(self.acom)
                c_list.append(f'(<b>{acom}</b>)')

            # If the common name was listed in the <h1> header,
            # list the scientific name as a smaller line below.
            if com and elab:
                c_list.append(f'<b>{self.format_elab()}</b>')

            write_header(w, title, h1, nospace=bool(c_list), desc=desc)

            if c_list:
                c = '<br>\n'.join(c_list)
                w.write(f'<p class="names">\n{c}\n</p>\n')

            s = self.write_keyed_parents()
            w.write(s)

            s = self.write_membership()
            w.write(s)

            # Write the completeness of the taxon (from the 'x' or 'xx' flags).

            is_top_of_genus = self.is_top_of(Rank.genus)

            complete = self.get_complete()

            # We usually write something only if the completeness is explicit,
            # but completeness is always expected for a genus, so we'll write
            # a warning if it's missing.
            if complete or is_top_of_genus:
                if is_top_of_genus:
                    rank_name = 'genus'
                elif self.rank:
                    rank_name = self.rank.name
                else:
                    rank_name = 'group'
                write_complete(w,
                               complete, self.genus_key_incomplete,
                               True, rank_name)

            is_top_of_species = self.is_top_of(Rank.species)

            write_complete(w,
                           self.species_complete, self.species_key_incomplete,
                           is_top_of_species, 'species')

            w.write('<hr>\n')

            if self.subset_of_page:
                w.write(self.txt)

                # Subset pages don't have real children.
                # Instead, we get the page that it is a subset of to write
                # the appropriate subset of its own hierarchy.
                self.subset_of_page.write_subset_hierarchy(w, self.subset_trait, self.subset_value, self.subset_page_list)

                # Since subset pages don't have real children, the normal
                # observation count won't work properly, which means that
                # the subset pages won't sort correctly (e.g. in pages.js).
                # To fix this, we count the observations of the appropriate
                # trait value and cache it as the normal observation count
                # for the subset page.
                n = self.subset_of_page.count_flowers(trait=self.subset_trait,
                                                      value=self.subset_value)
                self.cum_obs_n[None] = {}
                self.cum_obs_n[None][None] = n
            else:
                if self.photo_dict or self.ext_photo_list:
                    for suffix in sorted(self.photo_dict):
                        jpg = self.photo_dict[suffix]
                        # Do not put newlines between jpgs because that would
                        # put an unwanted text space between them in addition
                        # to their desired margin.
                        w.write(f'<a href="../photos/{url(jpg)}.jpg"><img class="leaf-thumb" src="{thumb_url(jpg)}" alt="photo"></a>')

                    for (label, link) in self.ext_photo_list:
                        w.write(f'<a href="{link}" target="_blank" rel="noopener noreferrer" class="enclosed"><div class="leaf-thumb-text">')
                        if label:
                            w.write('<span>')
                        if 'calphotos' in link:
                            text = 'CalPhotos'
                        elif 'calflora' in link:
                            text = 'Calflora'
                        else:
                            text = 'external photo'
                        w.write(f'<span style="text-decoration:underline;">{text}</span>')
                        if label:
                            w.write(f'<br>{label}</span>')

                        # As with the jpgs above, there is no newline between
                        # the external photo boxes.
                        w.write('</div></a>')

                    w.write('\n')

                w.write(self.txt)

                if self.photo_dict or self.ext_photo_list or self.txt:
                    w.write('<hr>\n')

                self.write_obs(w)

            if self.sci:
                self.write_external_links(w)
            write_footer(w)

    def record_genus(self):
        # record all pages that are within each genus
        sci = self.sci
        if self.rank and self.rank <= Rank.genus:
            genus = sci.split(' ')[0]
            if genus not in genus_page_list:
                genus_page_list[genus] = []
            genus_page_list[genus].append(self)

    def write_subset_hierarchy(self, w, trait, value, page_list):
        # We write out the matches to a string first so that we can get
        # the total statistics across the matches (including children).
        s = io.StringIO()
        list_matches(s, page_list, False, trait, value, set())

        obs = Obs(trait, value)
        self.count_matching_obs(obs)
        w.write(s.getvalue())
        w.write('<hr>\n')
        obs.write_obs(None, w)

# End of Page class
###############################################################################


###############################################################################
# Related helper functions are below.

# Find all flowers that match the specified trait's value.
# Also find all pages that include *multiple* child pages that match.
# If a parent includes multiple matching child pages, those child pages are
# listed only under the parent and not individually.
# If a parent includes only one matching child page, that child page is
# listed individually, and the parent is not listed.
#
# If trait is None, every page matches.
def find_matches(child_list, trait, value):
    match_list = []
    for page in child_list:
        child_subset = find_matches(page.child, trait, value)
        if len(child_subset) == 1 and trait is not None:
            # The page has only one matching child, so we add the child
            # directly to the list and not its parent.
            match_list.extend(child_subset)
        elif page.page_matches_trait_value(trait, value) or child_subset:
            match_list.append(page)
        if trait not in page.traits_used:
            page.traits_used[trait] = set()
        page.traits_used[trait].add(value)
    return match_list

# match_set can be either a set or list of pages.
# If indent is False, we'll sort them into a list by reverse order of
# observation counts.  If indent is True, match_set must be a list, and
# its order is retained.
def list_matches(w, match_set, indent, trait, value, seen_set):
    if indent and not trait:
        # We're under a parent with an ordered child list.  Retain its order.
        match_list = match_set
    else:
        # We're at the top level, so sort to put common pages first.
        match_list = sort_pages(match_set, trait=trait, value=value)

    for page in match_list:
        if page.end_hierarchy and not trait:
            child_matches = []
        else:
            child_matches = find_matches(page.child, trait, value)
        if child_matches:
            page.list_page(w, indent, child_matches)
            list_matches(w, child_matches, True, trait, value, seen_set)
            w.write('</div>\n')
        else:
            page.list_page(w, indent, None)

        seen_set.add(page)
