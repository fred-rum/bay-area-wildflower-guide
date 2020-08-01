#!/cygdrive/c/Python37/python.exe c:/Users/Chris/Documents/GitHub/bay-area-flowers/flowers.py
#!/usr/bin/env python

# Run as:
# /cygdrive/c/Users/Chris/Documents/GitHub/bay-area-flowers/flowers.py

# terminology (e.g. for variable names):
# page - a flower or container HTML page, and the info associated with it
# txt - the text that defines the contents of a page, often from a .txt file
# jpg - a photo; a page can include multiple photos (or none)
#
# flower - a flower.
#          Some flowers don't have an associated page,
#          and container pages don't have a (specific) associated flower.
#
# name - the name of a page and/or flower, or of an associated txt file
#        and/or jpg files
#        (i.e. ignorning the filename extension and the "-#" jpg number).
#        a flower uses its common name (not scientific name).
#
# color - a flower color.
#
# The variable name for a dictionary is constructed as
# {what it's for}_{what it holds}.
# E.g. page_parent holds the parent info for a page.
#
# In many cases, a dictionary does not necessarily contain data for every key.
# So when it is accessed, we must first check whether the key exists in the
# dictionary before getting its contents.

import sys
import os
import shutil
import filecmp
import subprocess
import re
import csv
import io
import yaml
import codecs
from unidecode import unidecode
import datetime

non_flower_top_pages = ('conifers', 'ferns')

year = datetime.datetime.today().year

class Obs:
    pass

    def __init__(self, color):
        self.match_set = set() # pages already searched, to avoid doublecounting
        self.color = color # color being searched for

        self.n = 0 # accumulated number of observations from observations.csv
        self.rg = 0 # number of research-grade observations as above
        self.parks = {} # subcounts for each park with observations
        self.month = [0] * 12 # subcounts for each month with observations

        self.key = 0 # number of key pages found in the hierarchy
        self.leaf_obs = 0 # number of leaf pages found with photos
        self.leaf_unobs = 0 # number of leaf pages found without photos

    def write_obs(self, page, w):
        n = self.n
        rg = self.rg

        if page:
            if n == 0 and not page.sci:
                return

            if page.taxon_id:
                link = f'https://www.inaturalist.org/observations/chris_nelson?taxon_id={page.taxon_id}&order_by=observed_on'
            elif page.sci:
                elab = page.choose_elab(page.elab_inaturalist)
                sci = strip_sci(elab)
                link = f'https://www.inaturalist.org/observations/chris_nelson?taxon_name={sci}&order_by=observed_on'
            else:
                link = None
        else:
            link = None

        w.write('<p/>\n')

        if link:
            w.write(f'<a href="{link}" target="_blank">Chris&rsquo;s observations</a>: ')
        else:
            w.write('Chris&rsquo;s observations: ')

        if n == 0:
            w.write('none')
        elif rg == 0:
            w.write(f'{n} (none are research grade)')
        elif rg == n:
            if n == 1:
                w.write('1 (research grade)')
            else:
                w.write(f'{n} (all are research grade)')
        else:
            if rg == 1:
                w.write(f'{n} ({rg} is research grade)')
            else:
                w.write(f'{n} ({rg} are research grade)')

        if n:
            w.write('''
<span class="toggle-details" onclick="fn_details(this)">[show details]</span><p/>
<div id="details">
Locations:
<ul>
''')
            park_list = sorted(self.parks)
            park_list = sorted(park_list,
                               key = lambda x: self.parks[x],
                               reverse=True)
            for park in park_list:
                count = self.parks[park]
                if count == 1:
                    w.write(f'<li>{park}</li>\n')
                else:
                    w.write(f'<li>{park}: {count}</li>\n')

            w.write('</ul>\nMonths:\n<ul>\n')

            # break_month = None
            # for i in range(12):
            #     weight = 0
            #     for j in range(12):
            #         factor = abs((i+5.5-j) % 12 - 6)
            #         weight += self.month[j] / factor
            #     if i == 0: # bias toward January unless there's a clear winner
            #         weight /= 1
            #     if break_month == None or weight < break_weight:
            #         break_month = i
            #         break_weight = weight

            # first = None
            # for i in range(12):
            #     m = (i + break_month) % 12
            #     if self.month[m]:
            #         if first == None:
            #             first = i
            #         last = i

            # Search for the longest run of zeros in the month data.
            z_first = 0
            z_length = 0
            for i in range(12):
                for j in range(12):
                    if self.month[(i+j) % 12]:
                        # break ties around January
                        if (j > z_length or
                            (j == z_length and (i == 0 or i+j >= 12))):
                            z_first = i
                            z_length = j
                        break

            month_name = ['Jan.', 'Feb.', 'Mar.', 'Apr.', 'May', 'Jun.',
                          'Jul.', 'Aug.', 'Sep.', 'Oct.', 'Nov.', 'Dec.']

            # Iterate through all months that are *not* part of the longest
            # run of zeros (even if some of those months are themselves zero).
            for i in range(12 - z_length):
                m = (i + z_first + z_length) % 12
                w.write(f'<li>{month_name[m]}: {self.month[m]}</li>\n')
            w.write('</ul>\n</div>\n')
        else:
            w.write('<p/>\n')

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

        if page and sci and page.sci and page.sci != sci:
            # If the common name matches a page with a different scientific
            # name, it's treated as not a match.
            return None
        else:
            return page

    return None

def find_page1(name):
    if is_sci(name):
        return find_page2(None, name)
    else:
        return find_page2(name, None)


###############################################################################
# start of Page class
###############################################################################

class Page:
    pass

    def __init__(self, name):
        self.set_name(name)

        self.index = len(page_array)
        page_array.append(self)

        self.com = None # a common name
        self.sci = None # a scientific name stripped of elaborations
        self.elab = None # an elaborated scientific name
        self.family = None # the scientific family
        self.level = None # taxonomic level: above, genus, species, or below

        self.no_sci = False # true if it's a key page for unrelated species
        self.no_family = False # true if it's a key page for unrelated genuses

        self.top_level = None # 'flowering plants', 'ferns', etc.

        self.elab_calflora = None
        self.elab_calphotos = None
        self.elab_jepson = None
        self.elab_inaturalist = None

        # the iNaturalist common name.
        # must be None if the common name isn't set.
        # if valid, must be different than the common name.
        self.icom = None

        self.autogenerated = False # true if it's an autogenerated family page

        self.ext_photo_list = [] # list of (text, calphotos_link) tuples
        self.genus_complete = None # indicates the completeness of the genus
        self.genus_key_incomplete = False # indicates if the key is complete
        self.species_complete = None # the same for the species
        self.species_key_incomplete = False

        # Give the page a default common or scientific name as appropriate.
        # Either or both names may be modified later.
        if is_sci(name):
            self.set_sci(name)
        else:
            self.set_com(name)

        self.txt = ''
        self.key_txt = ''
        self.jpg_list = [] # an ordered list of jpg names

        self.parent = set() # an unordered set of parent pages
        self.child = [] # an ordered list of child pages
        self.key = False # true if the page has child pages or CalFlora links

        # A set of color names that the page is linked from.
        # (Initially this is just the flower colors,
        # but container pages get added later.)
        self.color = set()

        self.taxon_id = None # iNaturalist taxon ID
        self.obs_n = 0 # number of observations
        self.obs_rg = 0 # number of observations that are research grade
        self.parks = {} # a dictionary of park_name : count
        self.month = [0] * 12

        self.glossary = None

    def url(self):
        return unidecode(self.name)

    def change_name_to_sci(self):
        del name_page[self.name]
        self.set_name(self.sci)

    def set_name(self, name):
        if name in name_page:
            print(f'Multiple pages created with name "{name}"')
        self.name = name
        name_page[name] = self

    def set_com(self, com):
        self.com = com
        if com in com_page:
            if com_page[com] != self:
                com_page[com] = 'multiple'
        else:
            com_page[com] = self

    # set_sci() can be called with a stripped or elaborated name.
    # Either way, both a stripped and elaborated name are recorded.
    def set_sci(self, sci):
        sci_words = sci.split(' ')
        if (len(sci_words) >= 2 and
            sci_words[0][0].isupper() and
            sci_words[1][0] == 'X'):
            sci_words[1] = sci_words[1][1:]
            sci = ' '.join(sci_words)
            self.is_hybrid = True
        else:
            self.is_hybrid = False

        elab = elaborate_sci(sci)
        sci = strip_sci(sci)

        if sci in sci_page and sci_page[sci] != self:
            print(f'Same scientific name ({sci}) set for {sci_page[sci].name} and {self.name}')

        if elab[0].islower():
            self.level = 'above'
        else:
            sci_words = sci.split(' ')
            if len(sci_words) == 1:
                self.level = 'genus'
            elif len(sci_words) == 2:
                self.level = 'species'
            else:
                self.level = 'below'

        self.sci = sci
        self.elab = elab
        sci_page[sci] = self

    def set_top_level(self, top_level, tree_top):
        if self.top_level == None:
            self.top_level = top_level
            for child in self.child:
                child.set_top_level(top_level, tree_top)
        elif self.top_level == top_level:
            # The top level has already been set
            # (which implies that its children have had it set, too).
            return
        else:
            print(f'{name} is under both {self.top_level} and {top_level} ({tree_top})')

    def set_family(self):
        if self.family or self.no_family:
            # The page's family has already been set
            # (which implies that its children have had their family set, too).
            return

        # set the family of all children
        for child in self.child:
            child.set_family()

        # if all children appear share the same family, use that as the
        # current page's family.  But if the children have different families,
        # set self.no_family.
        for child in self.child:
            if child.no_family:
                self.family = None
                self.no_family = True
                return
            elif child.family:
                if self.family == None:
                    self.family = child.family
                elif self.family != child.family:
                    self.family = None
                    self.no_family = True
                    return
            else:
                # The child doesn't know its family, but also isn't obviously
                # in multiple families.  Just ignore it.
                pass

        # If we didn't set the family and also didn't return with no_family,
        # it's because we have no children or the children don't have a clear
        # family.  Try to get the family from the genus instead.
        if not self.family and self.sci:
            genus = self.sci.split(' ')[0]
            if genus in genus_family:
                self.family = genus_family[genus]

        family = self.family
        if family:
            # This page has a family.  family_child_set keeps track of the
            # top-level pages within the family, so add this page to the set
            # and remove its children.
            if family not in family_child_set:
                family_child_set[family] = set()
            family_child_set[family].add(self)
            for child in self.child:
                if child in family_child_set[family]:
                    family_child_set[family].remove(child)

    def get_com(self):
        if self.com:
            return self.com
        else:
            return self.name

    def format_com(self):
        com = self.com
        if not com:
            return None
        return repl_easy_regex.sub(repl_easy, com)

    def format_elab(self):
        elab = self.elab
        if not elab:
            return None
        elif self.level == 'above':
            (gtype, name) = elab.split(' ')
            return f'{gtype} <i>{name}</i>'
        else:
            if self.is_hybrid:
                elab = re.sub(r' ', ' &times; ', elab)
            return f'<i>{elab}</i>'

    def format_full(self, lines=2):
        com = self.format_com()
        elab = self.format_elab()
        if not com:
            return elab
        elif not elab:
            return com
        elif lines == 1:
            return f'{com} ({elab})'
        else:
            return f'{com}<br/>{elab}'

    def add_jpg(self, jpg):
        self.jpg_list.append(jpg)

    def get_jpg(self):
        if self.jpg_list:
            return self.jpg_list[0]
        else:
            # Search this key page's children for a jpg to use.
            for child in self.child:
                jpg = child.get_jpg()
                if jpg:
                    return jpg
            return None

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

    def remove_comments(self):
        self.txt = re.sub(r'^#.*\n', '', self.txt, flags=re.MULTILINE)

    def parse_names(self):
        def repl_com(matchobj):
            com = matchobj.group(1)
            self.set_com(com)
            return ''

        def repl_sci(matchobj):
            sci = matchobj.group(1)
            if sci == 'n/a':
                self.no_sci = True
            else:
                self.set_sci(sci)
            return ''

        self.txt = re.sub(r'^com:\s*(.*?)\s*?\n',
                          repl_com, self.txt, flags=re.MULTILINE)
        self.txt = re.sub(r'^sci:\s*(.*?)\s*?\n',
                          repl_sci, self.txt, flags=re.MULTILINE)

    def set_sci_alt(self, sites, elab):
        if 'f' in sites:
            self.elab_calflora = elab
        if 'p' in sites:
            self.elab_calphotos = elab
        if 'j' in sites:
            self.elab_jepson = elab
        if 'i' in sites:
            self.elab_inaturalist = elab

    def set_complete(self, matchobj):
        if matchobj.group(1) == 'x':
            self.genus_complete = matchobj.group(3)
            if matchobj.group(2):
                self.genus_key_incomplete = True
        else:
            self.species_complete = matchobj.group(3)
            if matchobj.group(2):
                self.species_key_incomplete = True
        return ''

    def set_colors(self, color_str):
        if self.color:
            print(f'color is defined more than once for page {self.name}')

        self.color = set([x.strip() for x in color_str.split(',')])

        # record the original order of colors in case we want to write
        # it out.
        self.color_txt = color_str

        # check for bad colors.
        for color in self.color:
            if color not in color_list:
                print(f'page {self.name} uses undefined color {color}')

    def record_ext_photo(self, label, link):
        if (label, link) in self.ext_photo_list:
            print(f'{link} is specified more than once for page {self.name}')
        else:
            if label:
                label = sub_easy_safe(label)
            self.ext_photo_list.append((label, link))

    # Check if check_page is an ancestor of this page (for loop checking).
    def is_ancestor(self, check_page):
        if self == check_page:
            return True

        for parent in self.parent:
            if parent.is_ancestor(check_page):
                return True

        return False

    def assign_child(self, child):
        if self.is_ancestor(child):
            print(f'circular loop when creating link from {self.name} to {child.name}')
        elif self in child.parent:
            print(f'{child.name} added as child of {self.name} twice')
        else:
            self.child.append(child)
            child.parent.add(self)
            self.key = True

    def expand_genus(self, sci):
        if (self.cur_genus and len(sci) >= 3 and
            sci[0:3] == self.cur_genus[0] + '. '):
            return self.cur_genus + sci[2:]
        else:
            return sci

    def parse_children(self):
        # Replace a ==[name] link with ==[page] and record the
        # parent->child relationship.
        def repl_child(matchobj):
            com = matchobj.group(1)
            suffix = matchobj.group(2)
            sci = matchobj.group(3)
            if not suffix:
                suffix = ''
            if not sci:
                if is_sci(com):
                    sci = com
                    com = ''
                else:
                    sci = ''
            # ==com[,suffix][:sci] -> creates a child relationship with the
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
            #   The genus can also be abbreviated as '[cap.letter]. '
            if sci:
                # If the child's genus is abbreviated, expand it using
                # the genus of the current page.
                sci = self.expand_genus(sci)
            child_page = find_page2(com, sci)
            if not child_page:
                # If the child does not exist, create it.
                # The name for the page depends on what names were provided
                # and whether any collide with existing names.
                if not com:
                    strip = strip_sci(sci)
                    child_page = Page(strip)
                elif com in com_page:
                    # The common name is shared by a flower with a
                    # different scientific name.
                    if not sci:
                        print(f'page {self.name} has ambiguous child {com}')
                        return '==' + com + suffix

                    if (com in name_page and
                        com not in txt_list):
                        # The user didn't explicitly say that the previous
                        # user of the common name should name its page that
                        # way.  Since we now know that there are two with
                        # the same name, *neither* of them should use the
                        # common name as the page name.  So change the other
                        # page's page name to its scientific name.
                        name_page[com].change_name_to_sci()
                    strip = strip_sci(sci)
                    child_page = Page(strip)
                else:
                    # Prefer the common name in most cases.
                    child_page = Page(com)
            name = child_page.name
            self.assign_child(child_page)
            if com:
                if child_page.com:
                    if com != child_page.com:
                        print(f"page {self.name} refers to child {com}:{sci}, but the common name doesn't match")
                else:
                    child_page.set_com(com)
            if sci:
                child_page.set_sci(sci)

            # Replace the =={...} field with a simplified =={name,suffix} line.
            # This will create the appropriate link later in the parsing.
            return '==' + str(child_page.index) + suffix

        # If the page's genus is explicitly specified,
        # make it the default for child abbreviations.
        if self.level in ('genus', 'species', 'below'):
            self.cur_genus = self.sci.split(' ')[0]
        else:
            self.cur_genus = None

        c_list = []
        data_object = self
        for c in self.txt.split('\n'):
            matchobj = re.match(r'==\s*([^:]*?)\s*?(,[-0-9]\S*|,)?\s*?(?::\s*(.+?))?\s*$', c)
            if matchobj:
                c_list.append(repl_child(matchobj))
                data_object = self.child[-1]
                continue

            matchobj = re.match(r'sci([_fpji]+):\s*(.*?)$', c)
            if matchobj:
                data_object.set_sci_alt(matchobj.group(1),
                                        self.expand_genus(matchobj.group(2)))
                continue

            matchobj = re.match(r'\s*(?:([^:\n]*?)\s*:\s*)?(https://(?:calphotos.berkeley.edu/|www.calflora.org/cgi-bin/noccdetail.cgi)[^\s]+)\s*?$', c)
            if matchobj:
                # Attach the external photo to the current child, else to self.
                data_object.record_ext_photo(matchobj.group(1),
                                             matchobj.group(2))
                continue

            matchobj = re.match(r'color:(.*)$', c)
            if matchobj:
                data_object.set_colors(matchobj.group(1))
                continue

            matchobj = re.match(r'(x|xx):\s*(!?)(none|ba|ca|any|hist|rare|hist/rare|more|uncat)$', c)
            if matchobj:
                data_object.set_complete(matchobj)
                continue

            if c in ('', '[', ']'):
                data_object = self

            c_list.append(c)
        self.txt = '\n'.join(c_list) + '\n'

    def write_txt(self):
        def expand_child(matchobj):
            name = matchobj.group(1)
            suffix = matchobj.group(2)
            if not suffix:
                suffix = ''
            child_page = find_page1(name)
            if not child_page:
                print(name)
            com = child_page.com
            elab = child_page.elab
            if not elab:
                return '==' + com + suffix
            elab_words = elab.split(' ')
            if self.cur_genus and elab_words[0] == self.cur_genus:
                elab = elab_words[0][0] + '. ' + ' '.join(elab_words[1:])
            if com and com_page[com] == 'multiple':
                com = None
            if not com:
                return '==' + elab + suffix
            return '==' + com + suffix + ':' + elab

        if self.sci and self.level in ('genus', 'species', 'below'):
            self.cur_genus = self.sci.split(' ')[0]
        else:
            self.cur_genus = None

        with open(root + f'/txt2/{self.name}.txt', 'w') as w:
            if self.com and self.com != self.name:
                w.write(f'com:{self.com}\n')
            if self.elab and self.elab != self.name:
                w.write(f'sci:{self.elab}\n')
            if self.no_sci:
                w.write('sci:n/a\n')
            if self.color:
                w.write(f'color:{self.color_txt}\n')
            if self.genus_complete:
                if self.genus_key_incomplete:
                    w.write(f'x:!{self.genus_complete}\n')
                else:
                    w.write(f'x:{self.genus_complete}\n')
            if self.species_complete:
                if self.species_key_incomplete:
                    w.write(f'xx:!{self.species_complete}\n')
                else:
                    w.write(f'xx:{self.species_complete}\n')
            for tuple in self.ext_photo_list:
                if tuple[0]:
                    w.write(tuple[0] + ':' + tuple[1] + '\n')
                else:
                    w.write(tuple[1] + '\n')
            s = self.txt
            s = re.sub(r'^==([^,\n]+)(,[-0-9]\S*|,)?$',
                       expand_child, s, flags=re.MULTILINE)
            s = re.sub(r'^\n+', '', s)
            s = re.sub(r'\n*$', '\n', s, count=1)
            if s and s != '\n':
                if ((self.com and (self.sci or self.no_sci)) or
                    self.color or
                    self.ext_photo_list):
                    w.write('\n')
                w.write(s)

    def link_style(self):
        if self.autogenerated:
            return 'family'
        elif self.key:
            return 'parent'
        elif self.jpg_list:
            return 'leaf'
        else:
            return 'unobs'

    def create_link(self, lines):
        return f'<a href="{self.url()}.html" class="{self.link_style()}">{self.format_full(lines)}</a>'

    def write_parents(self, w):
        for parent in sort_pages(self.parent):
            if not parent.autogenerated:
                w.write(f'Key to {parent.create_link(1)}<br/>\n')
        if self.parent:
            w.write('<p/>\n')

    def page_matches_color(self, color):
        return (color == None or color in self.color)

    # Accumulate the observations for the page and all its children
    # into the obs object.  Page must match the color declared in obs
    # in order to count.
    def count_matching_obs(self, obs):
        if self in obs.match_set: return

        old_leaf_obs = obs.leaf_obs

        for child in self.child:
            child.count_matching_obs(obs)

        # If a container page contains exactly one descendant with a matching
        # color, the container isn't listed on the color page, and the color
        # isn't listed in page_color for the page.  Therefore, we follow all
        # child links blindly and only compare the color when we reach a flower
        # with an observation count.
        if self.page_matches_color(obs.color):
            obs.match_set.add(self)
            obs.n += self.obs_n
            obs.rg += self.obs_rg
            for park in self.parks:
                if park not in obs.parks:
                    obs.parks[park] = 0
                obs.parks[park] += self.parks[park]
            for i in range(12):
                obs.month[i] += self.month[i]

            if self.child:
                if not self.autogenerated:
                    obs.key += 1
                if self.jpg_list and obs.leaf_obs == old_leaf_obs:
                    # If a page is both a key and an observed flower and none
                    # of its descendents is observed, then treat it as if one
                    # of its descendents is observed instead.
                    # However, if any descendent is observed, then we can't
                    # guarantee that the photos for the key page are of a
                    # different species, so we ignore the key photos.
                    obs.leaf_obs += 1
                    obs.leaf_unobs -= 1
            elif self.jpg_list:
                obs.leaf_obs += 1
            else:
                obs.leaf_unobs += 1

    # Write the iNaturalist observation data.
    def write_obs(self, w):
        obs = Obs(None)
        self.count_matching_obs(obs)
        obs.write_obs(self, w)

    def choose_elab(self, elab_alt):
        if elab_alt and elab_alt != 'n/a':
            elab = elab_alt
        else:
            elab = self.elab
        elab_words = elab.split(' ')
        if len(elab_words) == 2 and '|' not in elab:
            # Always strip the "spp." suffix or [lowercase type] prefix.
            elab = strip_sci(elab)
        return elab

    def write_external_links(self, w):
        sci = self.sci
        if self.level == 'below':
            # Anything below species level should be elaborated as necessary.
            elab = self.elab
        else:
            # A one-word genus should be sent as is, not as '[genus] spp.'
            # A higher-level classification should be sent with the group type
            # removed.
            elab = sci

        w.write('<p/>')

        elab_list = []
        link_list = {}

        def add_link(elab, elab_alt, link):
            if elab_alt == 'n/a':
                elab = 'not listed'
                link = re.sub(r'<a ', '<a class="missing" ', link)
            elab = re.sub(r'\|', ' / ', elab)
            if elab not in link_list:
                elab_list.append(elab)
                link_list[elab] = []
            link_list[elab].append(link)

        if self.taxon_id:
            elab = self.choose_elab(self.elab_inaturalist)
            sci = strip_sci(elab)
            add_link(elab, None, f'<a href="https://www.inaturalist.org/taxa/{self.taxon_id}" target="_blank">iNaturalist</a>')
        else:
            elab = self.choose_elab(self.elab_inaturalist)
            sci = strip_sci(elab)
            if self.is_hybrid:
                sci = re.sub(r' ', ' \xD7 ', sci)
            add_link(elab, None, f'<a href="https://www.inaturalist.org/taxa/search?q={sci}&view=list" target="_blank">iNaturalist</a>')

        if self.level != 'above' or self.elab.startswith('family '):
            # CalFlora can be searched by family,
            # but not by other high-level classifications.
            elab = self.choose_elab(self.elab_calflora)
            add_link(elab, self.elab_calflora, f'<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup={elab}" target="_blank">CalFlora</a>');

        if self.level in ('species', 'below'):
            # CalPhotos cannot be searched by high-level classifications.
            # It can be searched by genus, but I don't find that at all useful.
            elab = self.choose_elab(self.elab_calphotos)
            if elab != self.elab:
                # CalPhotos can search for multiple names, and for cases such
                # as Erythranthe, it may have photos under both names.
                # Use both names when linking to CalPhotos, but for simplicity
                # list only the txt-specified name in the HTML listing.
                expanded_elab = self.elab + '|' + elab
            else:
                expanded_elab = elab
            # rel-taxon=begins+with -> allows matches with lower-level detail
            add_link(elab, self.elab_calphotos, f'<a href="https://calphotos.berkeley.edu/cgi/img_query?rel-taxon=begins+with&where-taxon={expanded_elab}" target="_blank">CalPhotos</a>');

        if self.level != 'above' or self.elab.startswith('family '):
            # Jepson can be searched by family,
            # but not by other high-level classifications.
            elab = self.choose_elab(self.elab_jepson)
            # Jepson uses "subsp." instead of "ssp.", but it also allows us to
            # search with that qualifier left out entirely.
            sci = strip_sci(elab)
            add_link(elab, self.elab_jepson, f'<a href="http://ucjeps.berkeley.edu/eflora/search_eflora.php?name={sci}" target="_blank">Jepson&nbsp;eFlora</a>');

        if self.level in ('genus', 'species', 'below'):
            elab = self.choose_elab(self.elab_calflora)
            genus = elab.split(' ')[0]
            # srch=t -> search
            # taxon={name} -> scientific name to filter for
            # group=none -> just one list; not annual, perennial, etc.
            # sort=count -> sort from most records to fewest
            #   (removed because it annoyingly breaks up subspecies)
            # fmt=photo -> list results with info + sample photos
            # y={},x={},z={} -> longitude, latitude, zoom
            # wkt={...} -> search polygon with last point matching the first
            add_link(elab, self.elab_calflora, f'<a href="https://www.calflora.org/entry/wgh.html#srch=t&taxon={genus}&group=none&fmt=photo&y=37.5&x=-122&z=8&wkt=-123.1+38,-121.95+38,-121.05+36.95,-122.2+36.95,-123.1+38" target="_blank">Bay&nbsp;Area&nbsp;species</a>')

        link_list_txt = []
        for elab in elab_list:
            txt = ' &ndash;\n'.join(link_list[elab])
            if len(elab_list) > 1:
                txt = f'{elab}: {txt}'
            link_list_txt.append(txt)
        txt = '</li>\n<li>'.join(link_list_txt)

        if len(elab_list) > 1:
            w.write(f'<p class="list-head">Not all sites agree about the scientific name:</p>\n<ul>\n<li>{txt}</li>\n</ul>\n')
        else:
            w.write(f'{txt}<p/>\n')

    def write_lists(self, w):
        if self.top_level != 'flowering plants':
            return

        if not self.child and not self.jpg_list:
            return

        w.write('<p class="list-head">Flower lists that include this page:</p>\n')
        w.write('<ul>\n')

        for color in color_list:
            if color in self.color:
                w.write(f'<li><a href="{color}.html">{color} flowers</a></li>\n')

        w.write('<li><a href="all.html">all flowers</a></li>\n')
        w.write('</ul>\n')

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

        if self.jpg_list:
            w.write(f'<a href="{self.url()}.html"><img src="../thumbs/{self.jpg_list[0]}.jpg" width="200" height="200" class="list-thumb"></a>')

        w.write(f'{self.create_link(2)}</div>\n')

    def get_ancestor_set(self):
        ancestor_set = self.parent.copy()
        for parent in self.parent:
            ancestor_set.update(parent.get_ancestor_set())
        return ancestor_set

    def cross_out_children(self, page_list):
        if self in page_list:
            page_list.remove(self)
        for child in self.child:
            child.cross_out_children(page_list)

    def set_glossary(self, glossary):
        if self.glossary:
            # We seem to be setting the glossary via two different
            # tree paths.  Make sure that the parent taxon's glossary
            # is the same on both paths.
            if self.name in glossary_taxon_dict:
                if glossary != self.glossary.glossary_parent:
                    print(f'{self.name} has two different parent glossaries')
            else:
                if glossary != self.glossary:
                    print(f'{self.name} gets two different glossaries')

            # No need to continue the tree traversal through this node
            # since it and its children have already set the glossary.
            return

        if self.name in glossary_taxon_dict:
            # Append the parent glossary list to the taxon's assigned
            # glossary list.
            sub_glossary = glossary_taxon_dict[self.name]
            sub_glossary.set_parent(glossary)
            glossary = sub_glossary

        self.glossary = glossary

        for child in self.child:
            child.set_glossary(glossary)

    def parse(self):
        s = self.txt
        s = re.sub(r'^\n+', '', s)
        s = re.sub(r'\n*$', '\n', s, count=1)

        def end_paragraph(start_list=False):
            nonlocal p_start
            if p_start == None:
                return

            if start_list:
                p_tag = '<p class="list-head">'
            else:
                p_tag = '<p>'
            c_list[p_start] = p_tag + c_list[p_start]
            c_list[-1] += '</p>'
            p_start = None

        def end_child_text():
            nonlocal child_start, c_list
            if child_start == None:
                return

            child = page_array[int(child_matchobj.group(1))]
            suffix = child_matchobj.group(2)
            if not suffix:
                suffix = ''

            text = '\n'.join(c_list[child_start:])
            c_list = c_list[:child_start]
            child_start = None

            # Give the child a copy of the text from the parent's key.
            # The child can use this (pre-parsed) text if it has no text
            # of its own.
            if ((self.level == 'genus' and child.level in ('species', 'below')) or
                (self.level == 'species' and child.level == 'below') or
                not child.key_txt):
                child.key_txt = text

            link = child.create_link(2)

            name = child.name
            jpg = None
            if suffix:
                if name + suffix in jpg_list:
                    jpg = name + suffix
                else:
                    print(name + suffix + '.jpg not found on page ' + self.name)

            if not jpg:
                jpg = child.get_jpg()

            if not jpg:
                ext_photo = child.get_ext_photo()

            if jpg:
                if self.autogenerated:
                    img_class = 'list-thumb'
                else:
                    img_class = 'page-thumb'
                img = f'<a href="{child.url()}.html"><img src="../thumbs/{jpg}.jpg" width="200" height="200" class="{img_class}"></a>'
            elif ext_photo:
                img = f'<a href="{child.url()}.html" class="enclosed {child.link_style()}"><div class="page-thumb-text">'
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

            if not img:
                c_list.append('<p>' + link + '</p>\n' + text)
            elif text:
                # Duplicate and contain the text link so that the following text
                # can either be below the text link and next to the image or
                # below both the image and text link, depending on the width of
                # the viewport.
                c_list.append(f'<div class="flex-width"><div class="photo-box">{img}\n<span class="show-narrow">{link}</span></div><span><span class="show-wide">{link}</span>{text}</span></div>')
            else:
                c_list.append(f'<div class="photo-box">{img}\n<span>{link}</span></div>')

        # replace the easy (fixed-value) stuff.
        # Break the text into lines, then perform easy substitutions on
        # non-keyword lines and decorate bullet lists.
        c_list = []
        p_start = None
        child_start = None
        list_depth = 0
        bracket_depth = 0
        for c in s.split('\n'):
            matchobj = re.match(r'\.*', c)
            new_list_depth = matchobj.end()
            if new_list_depth:
                end_paragraph(True)
            if new_list_depth > list_depth+1:
                print('Jump in list depth on page ' + self.name)
            while list_depth < new_list_depth:
                if list_depth == 0:
                    c_list.append('<ul>')
                else:
                    c_list.append('<ul class="list-sub">')
                list_depth += 1
            while list_depth > new_list_depth:
                c_list.append('</ul>')
                list_depth -= 1
            c = c[list_depth:].strip()

            matchobj = re.match(r'==(\d+)(,[-0-9]\S*|,)?\s*$', c)
            if matchobj:
                end_paragraph()
                end_child_text()
                child_matchobj = matchobj
                child_start = len(c_list)
                continue

            if c == '[':
                end_paragraph()
                end_child_text()
                c_list.append('<div class="box">')
                bracket_depth += 1
                continue

            if c == ']':
                end_paragraph()
                end_child_text()
                c_list.append('</div>')
                bracket_depth -= 1
                continue

            # Replace HTTP links in the text with ones that open a new tab.
            # (Presumably they're external links or they'd be in {...} format.)
            c = re.sub(r'<a href=', '<a target="_blank" href=', c)

            if list_depth:
                c_list.append(f'<li>{c}</li>')
                continue

            if c == '':
                end_paragraph()
                end_child_text()
                continue

            if p_start == None:
                p_start = len(c_list)
            c_list.append(c)
        end_paragraph()
        end_child_text()

        if bracket_depth != 0:
            print(f'"[" and "]" bracket depth is {bracket_depth} on page {self.name}')

        s = '\n'.join(c_list)
        self.txt = s

    def parse2(self):
        # Replace {-[name]} with an inline link to the page.
        def repl_link(matchobj):
            name = matchobj.group(1)
            page = find_page1(name)
            if page:
                return page.create_link(1)
            else:
                print(f'Broken link {{-{name}}} on page {self.name}')
                return '{-' + name + '}'

        # Use the text supplied in the text file if present.
        # Otherwise use the key text from its parent.
        # If the page's text file contains only metadata (e.g.
        # scientific name or color) so that the remaining text is
        # blank, then use the key text from its parent in that case, too.
        if re.search('\S', self.txt):
            s = self.txt
        else:
            s = self.key_txt

        s = link_figures(self.name, s)
        s = re.sub(r'{-([^}]+)}', repl_link, s)
        s = sub_easy(s)
        s = self.glossary.link_glossary_words(s, is_glossary=False)
        self.txt = s

    def any_parent_within_level(self, within_level_list):
        for parent in self.parent:
            if parent.level == None:
                if parent.any_parent_within_level(within_level_list):
                    return True
            elif parent.level in within_level_list:
                return True
        return False

    def is_top_of(self, level):
        if level == 'genus':
            within_level_list = ('genus', 'species', 'below')
        else:
            within_level_list = ('species', 'below')
        is_top_of_level = (self.level in within_level_list)
        if self.any_parent_within_level(within_level_list):
            is_top_of_level = False
        return is_top_of_level

    def write_html(self):
        def write_complete(w, complete, key_incomplete, is_top, top, members):
            if (self.child or
                (top == 'genus' and self.level != 'genus') or
                (top == 'species' and self.level != 'species')):
                other = ' other'
            else:
                other = ''
            if is_top:
                if complete == None:
                    if top == 'genus':
                        w.write(f'<b>Caution: There may be{other} {members} of this {top} not yet included in this guide.</b>')
                    else:
                        return # Don't write the <p/> at the end
                elif complete == 'none':
                    if top == 'genus':
                        print("x:none used for " + self.name)
                    else:
                        w.write('This species has no subspecies or variants.')
                elif complete == 'uncat':
                    if top == 'genus':
                        print("x:uncat used for " + self.name)
                    else:
                        w.write("This species has subspecies or variants that don't seem worth distinguishing.")
                elif complete == 'more':
                    w.write(f'<b>Caution: There are{other} {members} of this {top} not yet included in this guide.</b>')
                else:
                    prolog = f'There are no{other}'
                    if complete == 'hist':
                        prolog = f"Except for historical records that I'm ignoring, there are no{other}"
                    elif complete == 'rare':
                        prolog = f"Except for extremely rare plants that I don't expect to encounter, there are no{other}"
                    elif complete == 'hist/rare':
                        prolog = f"Except for old historical records and extremely rare plants that I don't expect to encounter, there are no{other}"

                    epilog = 'in the bay area'
                    if complete == 'ca':
                        epilog = 'in California'
                    elif complete == 'any':
                        epilog = 'anywhere'

                    w.write(f'{prolog} {members} of this {top} {epilog}.')
                if key_incomplete:
                    w.write(f'<br/>\n<b>Caution: The key to distinguish these {members} is not complete.</b>')
                w.write('<p/>\n')
            elif complete:
                if top == 'genus':
                    print(f'{self.name} uses the x: keyword but is not the top of genus')
                else:
                    print(f'{self.name} uses the xx: keyword but is not the top of species')

        def format_br(br):
            # br is True if there is more text on the next line.
            # br is False at the end of the 'paragraph'.
            if br:
                return '<br/>\n'
            else:
                return '<p/>\n'

        with open(root + "/html/" + self.url() + ".html",
                  "w", encoding="utf-8") as w:
            com = self.com
            elab = self.elab

            if com:
                title = self.format_com()
                h1 = title
            else:
                # If the page has no common name (only a scientific name),
                # then the h1 header should be italicized and elaborated.
                title = elab
                h1 = self.format_elab()

            # True if an extra line is needed for the scientific name
            # and/or family name.
            has_sci = (com and elab)
            family = self.family
            if family:
                # Do not emit a line for the family if:
                # - the current page *is* the family page, or
                # - the family page is an explict key and this page's
                #   immediate parent (in which case it'll be listed as
                #   a key page instead).
                family_page = sci_page[family]
                has_family = not (family == self.sci or
                                  (not family_page.autogenerated and
                                   family_page in self.parent))
            else:
                has_family = False
            write_header(w, title, h1, nospace=has_sci or has_family)

            if self.icom:
                w.write(f'(<b>{self.icom}</b>){format_br(elab)}')

            if has_sci:
                w.write(f'<b>{self.format_elab()}</b>{format_br(has_family)}')
            if has_family:
                family_link = family_page.create_link(1)
                w.write(f'{family_link}<p/>\n')

            self.write_parents(w)

            is_top_of_genus = self.is_top_of('genus')
            is_top_of_species = self.is_top_of('species')
            write_complete(w,
                           self.genus_complete, self.genus_key_incomplete,
                           is_top_of_genus, 'genus', 'species')
            write_complete(w,
                           self.species_complete, self.species_key_incomplete,
                           is_top_of_species, 'species', 'members')

            w.write('<hr/>\n')

            if len(self.jpg_list) or len(self.ext_photo_list):
                w.write('<div class="photo-box">\n')

                for jpg in self.jpg_list:
                    w.write(f'<a href="../photos/{jpg}.jpg"><img src="../thumbs/{jpg}.jpg" width="200" height="200" class="leaf-thumb"></a>\n')

                for (label, link) in self.ext_photo_list:
                    w.write(f'<a href="{link}" target="_blank" class="enclosed"><div class="leaf-thumb-text">')
                    if label:
                        w.write('<span>')
                    if 'calphotos' in link:
                        text = 'CalPhotos'
                    elif 'calflora' in link:
                        text = 'CalFlora'
                    else:
                        text = 'external photo'
                    w.write(f'<span style="text-decoration:underline;">{text}</span>')
                    if label:
                        w.write(f'<br/>{label}</span>')
                    w.write('</div></a>\n')

                w.write('</div>\n')

            s = self.txt
            w.write(s)

            if self.jpg_list or self.ext_photo_list or s:
                w.write('<hr/>\n')

            self.write_obs(w)
            if self.sci:
                self.write_external_links(w)
            self.write_lists(w)
            write_footer(w)

        if self.taxon_id and not (self.jpg_list or self.child):
            print(f'{self.name} is observed, but has no photos')

        if self.top_level == 'flowering plants':
            if self.jpg_list and not self.color:
                print(f'No color for flower: {self.name}')
        elif self.color:
            print(f'Color specified for non-flower: {self.name}')

    def record_genus(self):
        # record all pages that are within each genus
        sci = self.sci
        if self.level in ('genus', 'species', 'below'):
            genus = sci.split(' ')[0]
            if genus not in genus_page_list:
                genus_page_list[genus] = []
            genus_page_list[genus].append(self)

###############################################################################
# end of Page class
###############################################################################


root = 'c:/Users/Chris/Documents/GitHub/bay-area-flowers'

if os.path.isfile(root + '/html/_mod.html'):
    # Keep a copy of the previous html files so that we can
    # compare differences after creating the new html files.
    shutil.rmtree(root + '/prev', ignore_errors=True)

    # Apparently Windows sometimes lets the call complete when the
    # remove is not actually done yet, and then the rename fails.
    # In that case, keep retrying the rename until it succeeds.
    done = False
    while not done:
        try:
            os.rename(root + '/html', root + '/prev')
            done = True
        except WindowsError as error:
            pass
else:
    # _mod.html doesn't exist, which implies that the most recent run
    # crashed before creating it.  There's no point in comparing the changes
    # with the crashed run, so we discard it and keep the previous run to
    # compare against instead.
    shutil.rmtree(root + '/html', ignore_errors=True)

os.mkdir(root + '/html')

name_page = {} # original page name -> page [final file name may vary]
com_page = {} # common name -> page (or 'multiple' if there are name conflicts)
sci_page = {} # scientific name -> page
genus_page_list = {} # genus name -> list of pages in that genus
genus_family = {} # genus name -> family name
family_child_set = {} # family name -> set of top-level pages in that family

# Define a list of supported colors.
color_list = ['blue',
              'purple',
              'red purple',
              'red',
              'orange',
              'yellow',
              'white',
              'pale blue',
              'pale purple',
              'pink',
              'salmon',
              'cream',
              'other']

# key: color
# value: page list
color_page_list = {}

def write_header(w, title, h1, nospace=False):
    if nospace:
        space_class = ' class="nospace"'
    else:
        space_class = ''
    w.write(f'''<!-- Copyright Chris Nelson - All rights reserved. -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="shortcut icon" href="../favicon/favicon.ico">
<link rel="icon" sizes="16x16 32x32 64x64" href="../favicon/favicon.ico">
<link rel="icon" type="image/png" sizes="192x192" href="../favicon/favicon-192.png">
<link rel="icon" type="image/png" sizes="160x160" href="../favicon/favicon-160.png">
<link rel="icon" type="image/png" sizes="96x96" href="../favicon/favicon-96.png">
<link rel="icon" type="image/png" sizes="64x64" href="../favicon/favicon-64.png">
<link rel="icon" type="image/png" sizes="32x32" href="../favicon/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="../favicon/favicon-16.png">
<link rel="apple-touch-icon" href="../favicon/favicon-57.png">
<link rel="apple-touch-icon" sizes="114x114" href="../favicon/favicon-114.png">
<link rel="apple-touch-icon" sizes="72x72" href="../favicon/favicon-72.png">
<link rel="apple-touch-icon" sizes="144x144" href="../favicon/favicon-144.png">
<link rel="apple-touch-icon" sizes="60x60" href="../favicon/favicon-60.png">
<link rel="apple-touch-icon" sizes="120x120" href="../favicon/favicon-120.png">
<link rel="apple-touch-icon" sizes="76x76" href="../favicon/favicon-76.png">
<link rel="apple-touch-icon" sizes="152x152" href="../favicon/favicon-152.png">
<link rel="apple-touch-icon" sizes="180x180" href="../favicon/favicon-180.png">
<meta name="msapplication-TileColor" content="#FFFFFF">
<meta name="msapplication-TileImage" content="../favicon/favicon-144.png">
<meta name="msapplication-config" content="../favicon/browserconfig.xml">
<link rel="stylesheet" href="../bawg.css">
</head>
<body>
''')
    w.write('<div id="body">\n')
    if h1:
        w.write(f'<h1 id="title"{space_class}>{h1}</h1>\n')


def write_footer(w):
    # I don't put the year in the copyright because it's a pain to determine
    # given the different creation/modification dates of the pages *plus*
    # the photos on them.  The Berne Convention applies in any case.
    w.write(f'''
<hr/>
<a href="../index.html">BAWG</a> <span class="copyright">&ndash; &copy; Chris Nelson</span>
</div>
<script src="../pages.js"></script>
<script src="../search.js"></script>
</body>
''')

def link_figures(name, txt):
    def repl_figure_thumb(matchobj):
        file = matchobj.group(1)
        if not os.path.isfile(f'{root}/figures/{file}.svg'):
            print(f'Broken figure link to {file}.svg in {name}')
        return f'<a href="../figures/{file}.svg"><img src="../figures/{file}.svg" height="200" class="leaf-thumb"></a>'

    def repl_figure_thumbs(matchobj):
        inner = matchobj.group(1)
        inner = re.sub(r'^figure:(.*?)(?:\.svg|)$',
                       repl_figure_thumb, inner, flags=re.MULTILINE)
        return f'<div class="photo-box">\n{inner}\n</div>'

    def repl_figure_text(matchobj):
        file = matchobj.group(1)
        if not os.path.isfile(f'{root}/figures/{file}.svg'):
            print(f'Broken figure link to {file}.svg in {name}')
        return f'<a href="../figures/{file}.svg">[figure]</a>'

    txt = re.sub(r'^(figure:.*?(?:\.svg|)(?:\nfigure:.*?(?:\.svg|))*)$',
                 repl_figure_thumbs, txt, flags=re.MULTILINE)
    txt = re.sub(r'\[figure:(.*?)(?:\.svg|)\]',
                 repl_figure_text, txt, flags=re.MULTILINE)
    return txt


###############################################################################
# start of Glossary class
###############################################################################

class Glossary:
    pass

    def __init__(self, name):
        self.name = name
        self.title = None
        self.taxon = None
        self.parent = None # a single parent glossary (or None)
        self.child = set() # an unordered set of child glossaries
        self.term = [] # an ordered list of term lists
        self.glossary_dict = {} # mapping of term to anchor
        self.glossary_set = set() # all terms in this glossary and ancestors
        self.is_jepson = False

    def set_parent(self, parent):
        self.parent = parent
        parent.child.add(self)

    def glossary_link(self, anchor, term):
        if self.is_jepson:
            return f'<a class="glossary-jepson" href="https://ucjeps.berkeley.edu/eflora/glossary.html#{anchor}">{term}</a>'
        else:
            return f'<a class="glossary" href="{self.name}.html#{anchor}">{term}</a>'

    def find_dups(self, skip_glossary, term):
        def by_name(glossary):
            return glossary.title

        dup_list = []
        if self != skip_glossary and term in self.glossary_dict:
            dup_list.append(self.glossary_link(self.glossary_dict[term],
                                               self.title))

        for child in sorted(self.child, key=by_name):
            dup_list.extend(child.find_dups(skip_glossary, term))

        return dup_list

    def get_link(self, term):
        lower = term.lower()
        if lower in self.glossary_dict:
            anchor = self.glossary_dict[lower]
            if self.is_jepson:
                if anchor in self.used_dict:
                    self.used_dict[anchor] += 1
                else:
                    self.used_dict[anchor] = 1
            return self.glossary_link(anchor, term)
        else:
            return self.parent.get_link(term)

    def link_glossary_words(self, txt, is_glossary=False):
        # This function is called for a glossary word match.
        # Replace the matched word with a link to the primary term
        # in the glossary.
        def repl_glossary(matchobj):
            term = matchobj.group(1)
            return self.get_link(term)

        # Add glossary links in group 1, but leave group 2 unchanged.
        def repl_glossary_pair(matchobj):
            allowed = matchobj.group(1)
            disallowed = matchobj.group(2)
            allowed = re.sub(self.glossary_regex, repl_glossary, allowed)
            return allowed + disallowed

        # Find non-tagged text followed (optionally) by tagged text.
        # We'll perform glossary link insertion only on the non-tagged text.
        #
        # The first group (for non-tagged text) is non-greedy, but still starts
        # as soon as possible (i.e. at the beginning of the string or just after
        # the previous match).
        #
        # The second group (for tagged text) is also non-greedy, looking for the
        # shortest amount of text to close the link.  The second group either
        # starts with an opening tag and ends with a closing tag, or it matches
        # the end of the string (after matching the final non-tagged text).
        #
        # Tagged text is anything between link tags, <a>...</a>.
        # It also includes the URL in <a href="...">.  Anything between braces
        # {...} is also captured here.
        #
        # Within the glossary, tagged text also includes anything between
        # header tags, <h#>...</h#>.  Linking a header tag to the glossary is
        # fine in regular pages where the word may be unknown, but it looks
        # weird in the glossary where the word is defined right there.
        if is_glossary:
            # Don't replace any text between link tags <a>...</a>
            # (including the URL in <a href="...">) or between header tags
            # <h#>...</h#> or within a tag <...> or special syntax {...}. 
            # Linking a header tag to the glossary is fine in regular pages
            # where the word may be unknown, but it looks weird in the
            # glossary where the word is defined right there.
            sub_re = r'(.*?)(\Z|<(?:a\s|h\d).*?</(?:a|h\d)>|<\w.*?>|{.*?})'
        else:
            # Don't replace any text between link tags <a>...</a>
            # (including the URL in <a href="...">) or within a tag <...>
            # or special syntax {...}.
            sub_re = r'(.*?)(\Z|<a\s.*?</a>|<\w.*?>|{.*?})'

        # Perform the glossary link substitution for each non-tag/tag
        # pair throughout the entire multi-line txt string.
        txt = re.sub(sub_re, repl_glossary_pair, txt,
                     flags=re.DOTALL)

        return txt

    def create_regex(self):
        if not self.glossary_set:
            self.glossary_set = set(iter(self.glossary_dict.keys()))
            if self.parent:
                self.parent.create_regex()
                self.glossary_set = self.glossary_set.union(self.parent.glossary_set)

        # sort the glossary list in reverse order so that for cases where two
        # phrases start the same and one is a subset of the other, the longer
        # phrase is checked first.
        glossary_list = sorted(iter(self.glossary_set), reverse=True)

        ex = '|'.join(map(re.escape, glossary_list))
        self.glossary_regex = re.compile(rf'\b({ex})\b', re.IGNORECASE)

    def record_in_glossary_dict(self, anchor, word):
        word = sub_easy_safe(word.lower())
        self.glossary_dict[word] = anchor

    def read_terms(self):
        def repl_title(matchobj):
            self.title = matchobj.group(1)
            return ''

        def repl_taxon(matchobj):
            name = matchobj.group(1)
            if name == 'flowering plants':
                # Special case since there is no page for flowering plants.
                self.taxon = name
            else:
                self.taxon = find_page1(name).name
            return ''

        def repl_defn(matchobj):
            words = matchobj.group(1)
            defn = matchobj.group(2)
            word_list = [x.strip() for x in words.split(',')]
            anchor = word_list[0]
            self.term.append(word_list)
            for word in word_list:
                self.record_in_glossary_dict(anchor, word)
                # Prevent a glossary definition from linking the terms
                # it is currently defining, either to its own
                # definition or to a higher-level glossary.
                # (Higher-level glossary links will be added later.)
                # We do this by prepending 'glossaryX' to any
                # occurance of the defined terms in the definition.
                # We'll remove this after glossary links are created.
                defn = re.sub(r'\b' + word + r'\b', 'glossaryX' + word, defn,
                              re.IGNORECASE)
            return '{' + words + '} ' + defn

        with open(f'{root}/glossary/{self.name}.txt', mode='r') as f:
            self.txt = f.read()

        # Link figures prior to parsing glossary terms so that they're
        # properly recognized as not to be touched.
        self.txt = link_figures(self.name, self.txt)

        self.txt = re.sub(r'^title:\s*(.*?)\s*$',
                          repl_title, self.txt, flags=re.MULTILINE)
        self.txt = re.sub(r'^taxon:\s*(.*?)\s*$',
                          repl_taxon, self.txt, flags=re.MULTILINE)

        # self.taxon is now either a name or (if unset) None.
        # Either value is appropriate for the glossary_dict key.
        glossary_taxon_dict[self.taxon] = self

        if not self.title:
            print(f'title not defind for glossary "{self.name}"')
            self.title = 'unknown glossary'

        # Read definitions and modify them to avoid self-linking.
        self.txt = re.sub(r'^{([^\}]+)}\s+(.*)$',
                          repl_defn, self.txt, flags=re.MULTILINE)

    def read_jepson_terms(self):
        self.title = 'Jepson' # used only self links from a glossary definition
        self.is_jepson = True
        self.used_dict = {}

        with open(f'{root}/jepson_glossary.txt', mode='r') as f:
            txt = f.read()
        for c in txt.split('\n'):
            # remove comments
            c = re.sub(r'\s*#.*$', '', c)

            if not c: # ignore blank lines (and comment-only lines)
                continue

            if c.startswith('-'):
                # I eventually want lines that start with '-' to be handled
                # in a special way, but for now I just ignore them.
                continue

            # Jepson's anchor is usually the whole text, including commas
            # and parentheses.  If there are additional terms I'd like to
            # associate with the entry, I've added them after a semicolon.
            anchor = re.sub(r'\s*;.*$', r'', c)

            # Normalize the separator between all terms to a comma.
            c = re.sub(r'\((.*)\)', r', \1', c)
            c = re.sub(r';', r',', c)
            word_list = [x.strip() for x in c.split(',')]

            self.term.append(word_list)
            for word in word_list:
                self.record_in_glossary_dict(anchor, word)

    def set_index(self):
        def by_name(glossary):
            return glossary.title

        self.index = len(glossary_list)
        glossary_list.append(self)
        for child in sorted(self.child, key=by_name):
            child.set_index()

    def write_toc(self, w, current):
        def by_name(glossary):
            return glossary.title

        if self == current:
            w.write(f'<b>{self.title}</b></br>')
        else:
            w.write(f'<a href="{self.name}.html">{self.title}</a></br>')

        if self.child:
            w.write('<div class="toc-indent">\n')
            for child in sorted(self.child, key=by_name):
                child.write_toc(w, current)
            w.write('</div>\n')

    def write_html(self):
        def repl_defns(matchobj):
            words = matchobj.group(1)
            defn = matchobj.group(2)

            word_list = [x.strip() for x in words.split(',')]
            anchor = word_list[0]

            # Add links to other glossaries where they define the same words.
            related_str = ''
            dup_list = jepson_glossary.find_dups(self, anchor)
            if dup_list:
                related_str = ' [' + ', '.join(dup_list) + ']'
            else:
                related_str = ''

            return f'<div class="defn" id="{anchor}"><dt>{anchor}</dt><dd>{defn}{related_str}</dd></div>'

        self.txt = sub_easy(self.txt)

        self.txt = self.link_glossary_words(self.txt, is_glossary=True)

        # Remove the inserted 'glossaryX' text to return the (unlinked)
        # glossary terms to their normal text.
        self.txt = re.sub(r'glossaryX', '', self.txt)

        self.txt = re.sub(r'^{([^\}]+)}\s+(.*)$',
                          repl_defns, self.txt, flags=re.MULTILINE)

        with open(f'{root}/html/{self.name}.html', mode='w') as w:
              write_header(w, self.title, None, nospace=True)
              w.write('<h4 class="title">Glossary table of contents</h4>\n')
              master_glossary.write_toc(w, self)
              w.write(f'<a href="http://ucjeps.berkeley.edu/IJM_glossary.html">Jepson eFlora glossary</a>')
              w.write(f'<h1>{self.title}</h1>\n')
              w.write(self.txt)
              write_footer(w)

    # Write search terms for my glossaries to pages.js
    def write_search_terms(self, w):
        def by_name(glossary):
            return glossary.title

        # The glossary page without a named term can be treated just like
        # an unobserved (low-priority) page.  It's simply a link to an
        # HTML page with its name being the search term.
        w.write(f'{{page:"{self.name}",x:"u"}},\n')

        for term in self.term:
            terms_str = '","'.join(term)
            w.write(f'{{idx:{self.index},com:["{terms_str}"],x:"g"}},\n')

        for child in sorted(self.child, key=by_name):
            child.write_search_terms(w)

    # Write search terms for Jepson's glossary to pages.js
    def write_jepson_search_terms(self, w):
        for term in self.term:
            coms_str = '","'.join(term)
            anchor = self.glossary_dict[term[0]]
            if term[0] == anchor:
                anchor_str = ''
            else:
                anchor_str = f',anchor:"{anchor}"'
            w.write(f'{{com:["{coms_str}"]{anchor_str},x:"j"}},\n')

        def by_usage(anchor):
            return self.used_dict[anchor]

        for anchor in sorted(self.used_dict, key=by_usage):
            print(f'{anchor}: {self.used_dict[anchor]}')


###############################################################################
# end of Glossary class
###############################################################################


# Read the mapping of iNaturalist observation locations to short park names.
park_map = {}
park_loc = {}
with open(root + '/parks.yaml', mode='r', encoding='utf-8') as f:
    yaml_data = yaml.safe_load(f)
for loc in yaml_data:
    for x in yaml_data[loc]:
        if isinstance(x, str):
            park_map[x] = x
            park_loc[x] = loc
        else:
            for y in x:
                park_map[x[y]] = y
                park_loc[x[y]] = loc

# Get a list of files with the expected suffix in the designated directory.
def get_file_list(subdir, ext):
    file_list = os.listdir(root + '/' + subdir)
    base_list = []
    for filename in file_list:
        pos = filename.rfind(os.extsep)
        if pos > 0:
            file_ext = filename[pos+len(os.extsep):].lower()
            if file_ext == ext:
                base = filename[:pos]
                base_list.append(base)
    return base_list

page_array = [] # array of pages; only appended to; never otherwise altered
txt_list = get_file_list('txt', 'txt')
jpg_list = get_file_list('photos', 'jpg')
thumb_list = get_file_list('thumbs', 'jpg')
glossary_list = get_file_list('glossary', 'txt')

def get_name_from_jpg(jpg):
    name = re.sub(r',([-0-9]\S*|)$', r'', jpg)

    if is_sci(name):
        # If the jpg uses an elaborated name, remove the elaborations to
        # form the final page name.
        name = strip_sci(name)

    return name

# Compare the photos directory with the thumbs directory.
# If a file exists in photos and not thumbs, create it.
# If a file is newer in photos than in thumbs, re-create it.
# If a file exists in thumbs and not photos, delete it.
# If a file is newer in thumbs than in photos, leave it unchanged.
for name in thumb_list:
    if name not in jpg_list:
        thumb_file = root + '/thumbs/' + name + '.jpg'
        os.remove(thumb_file)

mod_list = []
for name in jpg_list:
    photo_file = root + '/photos/' + name + '.jpg'
    thumb_file = root + '/thumbs/' + name + '.jpg'
    if (name not in thumb_list or
        os.path.getmtime(photo_file) > os.path.getmtime(thumb_file)):
        mod_list.append(photo_file)

if mod_list:
    with open(root + "/convert.txt", "w") as w:
        for filename in mod_list:
            filename = re.sub(r'/', r'\\', filename)
            w.write(filename + '\n')
    root_mod = re.sub(r'/', r'\\', root)
    cmd = ['C:/Program Files (x86)/IrfanView/i_view32.exe',
           f'/filelist={root_mod}\\convert.txt',
           '/aspectratio',
           '/resize_long=200',
           '/resample',
           '/jpgq=80',
           f'/convert={root_mod}\\thumbs\\*.jpg']
    subprocess.Popen(cmd).wait()

###############################################################################

repl_easy_dict = {
    # Replace common Jepson codes.
    '+-' : '&plusmn;',
    '--' : '&ndash;',
    '<=' : '&le;',
    '>=' : '&ge;',
    '<<' : '&#8810',
    '>>' : '&#8811',

    "'"  : '&rsquo;',
    '"'  : '&rdquo;',

    # '<' and '>' should be escaped, but for now I'll leave them alone
    # because the browser seems to figure them out correctly, and it's
    # probably smarter about it than I would be.
}

ex = '|'.join(map(re.escape, list(repl_easy_dict.keys())))
repl_easy_regex = re.compile(f'({ex})')

def repl_easy(matchobj):
    return repl_easy_dict[matchobj.group(1)]

def sub_easy_safe(txt):
    # I assume that I only use double-quotes to quote a passage
    # of text.  If I try to do something similar for single-quotes,
    # I could use the wrong smart quote for something like the '80s.
    txt = re.sub(r'(?<![\w.,])"|\A"', r'&ldquo;', txt)
    txt = repl_easy_regex.sub(repl_easy, txt)
    return txt

# Perform easy substitutions in group 1, but leave group 2 unchanged.
def repl_easy_pair(matchobj):
    allowed = matchobj.group(1)
    disallowed = matchobj.group(2)
    return sub_easy_safe(allowed) + disallowed

# Make easy substitutions in the text, such as "+-" and smart quotes.
# We do this before glossary substitutions because the HTML added for
# glossary links confuses the heuristic for smart-quote direction.
def sub_easy(txt):
    # Don't replace any text within a tag <...> or special syntax {...}.
    # Note that a tag is assumed to start with a word character, e.g. "<a".
    # Thus, we won't get thrown off by a non-tag angle bracket such as "< "
    # or "<=".
    sub_re = r'(.*?)(\Z|<\w.*?>|{.*?})'

    # Perform the easy substitution for each non-tag/tag
    # pair throughout the entire multi-line txt string.
    return re.sub(sub_re, repl_easy_pair, txt,
                  flags=re.DOTALL)


# Read the txt for all txt files.  Also perform a first pass on
# the txt pages to initialize common and scientific names.  This
# ensures that when we parse children (next), any name can be used and
# linked correctly.
for name in txt_list:
    page = Page(name)
    with open(root + "/txt/" + name + ".txt", "r", encoding="utf-8") as r:
        page.txt = r.read()
    page.remove_comments()
    page.parse_names()

# parse_children() can add new pages, so we make a copy of the list to
# iterate through.  parse_children() also checks for external photos,
# color, and completeness information.  If this info is within a child
# key, it is assigned to the child.  Otherwise it is assigned to the
# parent.
for page in page_array[:]:
    page.parse_children()

# Record jpg names for associated pages.
# Create a blank page for all unassociated jpgs.
for jpg in sorted(jpg_list):
    name = get_name_from_jpg(jpg)
    if name == '':
        print(f'No name for {jpg}')
    else:
        page = find_page1(name)
        if not page:
            page = Page(name)
        page.add_jpg(jpg)

# Although other color checks are done later, we check for excess colors
# here before propagating color to parent pages that might not have photos.
for page in page_array:
    if page.color and not page.jpg_list:
        print(f'page {page.name} has a color assigned but has no photos')

with open(root + '/ignore species.yaml', encoding='utf-8') as f:
    sci_ignore = yaml.safe_load(f)

# Track species or subspecies observations that don't have a page even though
# there is a genus or species page that they could fit under.  We'll emit an
# error message for these once all the observations are read.
surprise_obs = set()

# Remove characters that are allowed to be different between names
# while the names are still considered identical.
# This is mostly non-alphabetic characters, but also plural endings.
def shrink(name):
    name = name.lower()
    name = re.sub(r'\W', '', name)
    name = re.sub(r'(s|x|ch|sh)es$', r'$1', name)
    name = re.sub(r'zzes$', 'z', name)
    name = re.sub(r'ies$', 'y', name)
    name = re.sub(r's$', '', name)
    return name

# Read my observations file (exported from iNaturalist) and use it as follows:
#   Associate common names with scientific names
#   Get a count of observations (total and research grade) of each flower.
#   Get an iNaturalist taxon ID for each flower.
with open(root + '/observations.csv', mode='r', newline='', encoding='utf-8') as f:
    csv_reader = csv.reader(f)
    header_row = next(csv_reader)

    com_idx = header_row.index('common_name')
    sci_idx = header_row.index('scientific_name')
    rg_idx = header_row.index('quality_grade')
    taxon_idx = header_row.index('taxon_id')
    family_idx = header_row.index('taxon_family_name')
    place_idx = header_row.index('place_guess')
    private_place_idx = header_row.index('private_place_guess')
    date_idx = header_row.index('observed_on')

    park_nf_list = set()

    for row in csv_reader:
        sci = row[sci_idx]

        # In the highly unusual case of no scientific name for an observation,
        # just throw it out.
        if not sci: continue

        # The common name is forced to all lower case to match my convention.
        # The scientific name is left in its standard case, but a hybrid
        # indicator is removed.
        com = row[com_idx].lower()
        # Remove the {multiplication sign} used by hybrids since I can't
        # (yet) support it cleanly.  Note that I *don't* use the r'' string
        # format here because I want the \N to be parsed during string parsing,
        # not during RE parsing.
        sci = re.sub('\N{MULTIPLICATION SIGN} ', r'', sci)
        taxon_id = row[taxon_idx]
        rg = row[rg_idx]

        family = row[family_idx]
        genus = sci.split(' ')[0] # could be a higher level, too, but that's OK.
        genus_family[genus] = family

        park = row[private_place_idx]
        if not park:
            park = row[place_idx]

        for x in park_map:
            if re.search(x, park):
                short_park = park_map[x]
                loc = park_loc[x]
                break
        else:
            park_nf_list.add(park)
            short_park = park
            loc = 'bay area'

        date = row[date_idx]
        month = int(date.split('-')[1], 10) - 1 # January = month 0

        page = find_page2(com, sci)

        if sci in sci_ignore:
            if sci_ignore[sci][0] == '+':
                page = None
            elif page:
                print(f'{sci} is ignored, but there is a page for it ({page.name})')

            # For sci_ignore == '+...', the expectation is that we'll fail
            # to find a page for it, but we'll find a page at a higher level.
            # But if sci_ignore == '-...', we do nothing with the observation.
            if sci_ignore[sci][0] != '+':
                continue
        elif not page and com in com_page:
            print(f'observation {com} ({sci}) matches the common name for a page, but not its scientific name')
            continue

        if page:
            page.taxon_id = taxon_id
            if not page.sci:
                page.set_sci(sci)
            if com and page.com:
                i_com_shrink = shrink(com)
                p_com_shrink = shrink(page.com)
                if i_com_shrink != p_com_shrink and com != page.icom:
                    page.icom = com
                    #print(f"iNaturalist's common name {com} differs from mine: {page.com} ({page.elab})")
            if com and not page.com:
                print(f"iNaturalist supplies a missing common name for {com} ({page.elab})")

        if loc != 'bay area':
            if page:
                # If the location is outside the bay area, we'll still count
                # it as long as it's a bay area taxon; i.e. if a page exists
                # for it.  In this case, list the outside observations by
                # general location, rather than the specific park.
                short_park = loc
            else:
                # But if there isn't an exact page for it, throw the
                # observation away; i.e. don't look for a higher-level match.
                continue

        # If a page isn't found for the observation, but a page exists for
        # a different member of the genus, print a warning.
        genus = sci.split(' ')[0]
        if not page and genus in genus_page_list and sci not in sci_ignore:
            surprise_obs.add(sci)

        # If we haven't matched the observation to a page, try stripping
        # components off the scientific name until we find a higher-level
        # page to attach the observation to.
        orig_sci = sci
        while not page and sci:
            sci_words = sci.split(' ')
            sci = ' '.join(sci_words[:-1])
            if sci in sci_page:
                page = sci_page[sci]

        if (page and (orig_sci not in sci_ignore or
                      sci_ignore[orig_sci][0] == '+')):
            page.obs_n += 1
            if rg == 'research':
                page.obs_rg += 1
            if short_park not in page.parks:
                page.parks[short_park] = 0
            page.parks[short_park] += 1
            page.month[month] += 1

if surprise_obs:
    print("The following observations don't have a page even though a page exists in the same genus:")
    for sci in sorted(surprise_obs):
        print('  ' + repr(sci))

if park_nf_list:
    print("Parks not found:")
    for x in park_nf_list:
        print("  " + repr(x))

# try:
#     os.mkdir(root + '/txt2')
# except:
#     pass
#
#for page in page_array:
#    if page.name in txt_list or page.ext_photo_list or page.jpg_list:
#        page.write_txt()        

# Get a list of pages without parents (top-level pages).
top_list = [x for x in page_array if not x.parent]

# Find all flowers that match the specified color.
# Also find all pages that include *multiple* child pages that match.
# If a parent includes multiple matching child pages, those child pages are
# listed only under the parent and not individually.
# If a parent includes only one matching child page, that child page is
# listed individually, and the parent is not listed.
#
# If color == None, every page matches.
def find_matches(page_subset, color):
    match_list = []
    for page in page_subset:
        child_subset = find_matches(page.child, color)
        if len(child_subset) == 1 and color != None:
            match_list.extend(child_subset)
        elif child_subset:
            match_list.append(page)
            if color != None:
                # Record this container page's newly discovered color.
                page.color.add(color)
        elif page.jpg_list and page.page_matches_color(color):
            # only include the page on the list if it is a key or observed
            # flower (not an unobserved flower).
            match_list.append(page)
    return match_list

# We don't need color_page_list yet, but we go through the creation process
# now in order to populate page_color for all container pages.
for color in color_list:
    color_page_list[color] = find_matches(top_list, color)

did_intro = False
for page in page_array:
    if not (page.sci or page.no_sci):
        if not did_intro:
            print('No scientific name given for the following pages:')
            did_intro = True
        print('  ' + page.name)

for name in non_flower_top_pages:
    name_page[name].set_top_level(name, name)

for page in top_list:
    if not page.top_level:
        page.set_top_level('flowering plants', page.name)
        page.set_family()

def sort_pages(page_set, color=None, with_depth=False):
    # helper function to sort by name
    def by_name(page):
        if page.com:
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

    # helper function to sort by observation count
    def count_flowers(page):
        obs = Obs(color)
        page.count_matching_obs(obs)
        return obs.n

    # Sort in reverse order of observation count.
    # We initialize the sort with match_set sorted alphabetically.
    # We then sort by hierarchical depth, retaining the previous alphabetical
    # order for ties.  Finally, we sort by observation count, again retaining
    # the most recent order for ties.
    page_list = sorted(page_set, key=by_name)
    if with_depth:
        page_list.sort(key=by_depth)
    page_list.sort(key=count_flowers, reverse=True)
    return page_list

with open(root + '/family names.yaml', encoding='utf-8') as f:
    family_com = yaml.safe_load(f)

for family in family_child_set:
    if family in family_com:
        com = family_com[family]
    else:
        print(f'No common name for family {family}')
        com = 'n/a' # family names.yaml uses 'n/a' when there is no common name
    child_set = family_child_set[family]
    if family in sci_page:
        sci_page[family].cross_out_children(child_set)
        if child_set:
            print(f'The following pages are not included by the page for family {family}')
            for child in child_set:
                print('  ' + child.format_full(1))
    else:
        if com == 'n/a':
            page = Page(family)
        else:
            page = Page(com)
        page.set_sci('family ' + family)
        page.top_level = 'flowering plants'
        page.autogenerated = True
        for child in sort_pages(family_child_set[family]):
            page.txt += f'=={child.name}\n\n'
        page.parse_children()

# Regenerate the list of top-level pages
# now that we've added pages for families.
top_list = [x for x in page_array if not x.parent]
top_flower_list = [x for x in top_list if x.top_level == 'flowering plants']

glossary_taxon_dict = {}
for glossary_file in glossary_list:
    glossary = Glossary(glossary_file)
    glossary.read_terms()

master_glossary = glossary_taxon_dict[None]
flower_glossary = glossary_taxon_dict['flowering plants']
flower_glossary.set_parent(master_glossary)

jepson_glossary = Glossary('Jepson eFlora glossary')
jepson_glossary.read_jepson_terms()
master_glossary.set_parent(jepson_glossary)

# Determine the primary glossary to use for each page *and*
# determine the hierarchy among glossaries.
for page in top_list:
    if page.top_level == 'flowering plants':
        page.set_glossary(flower_glossary)
    else:
        page.set_glossary(master_glossary)

# Created an ordered list of the glossaries.  The purpose of this is
# to allow a glossary to be referenced by its index number in page.js.
# Note that the Jepson glossary is included in this list with index 0.
glossary_list = []
master_glossary.set_index()

# Now that we know the glossary hierarchy, we can apply glossary links
# within each glossary and finally write out the HTML.
for glossary in glossary_list:
    glossary.create_regex()
    glossary.write_html()

# Turn txt into html for all normal and default pages.
for page in page_array:
    page.parse()

for page in page_array:
    page.parse2()

def by_incomplete_obs(page):
    def count_flowers(page):
        obs = Obs(None)
        page.count_matching_obs(obs)
        return obs.n

    is_top_of_genus = page.is_top_of('genus')
    if is_top_of_genus and page.genus_complete in (None, 'more'):
        return count_flowers(page)
    else:
        return 0

for page in page_array:
    page.write_html()

if len(sys.argv) > 2 and sys.argv[2] == 'x':
    page_list = page_array[:]
    page_list.sort(key=by_incomplete_obs, reverse=True)
    for page in page_list[:5]:
        print(page.name)

# Find any genus with multiple species.
# Check whether all of those species share an ancestor key page in common.
# If not, print a warning.
for page in page_array:
    page.record_genus()

for genus in genus_page_list:
    page_list = genus_page_list[genus]
    if len(page_list) > 1:
        if genus in sci_page:
            sci_page[genus].cross_out_children(page_list)
            if page_list:
                print(f'The following species are not included under the {genus} spp. key')
                for page in page_list:
                    print('  ' + page.format_full(1))
        else:
            ancestor_set = page_list[0].get_ancestor_set()
            for page in page_list[1:]:
                set2 = page.get_ancestor_set()
                ancestor_set.intersection_update(set2)
            if not ancestor_set:
                print(f'The following pages in {genus} spp. are not under a common ancestor:')
                for page in page_list:
                    print('  ' + page.format_full(1))

###############################################################################
# The remaining code is for creating useful lists of pages:
# all pages, and pages sorted by flower color.

# match_set can be either a set or list of pages.
# If indent is False, we'll sort them into a list by reverse order of
# observation counts.  If indent is True, match_set must be a list, and
# its order is retained.
def list_matches(w, match_set, indent, color, seen_set):
    if indent:
        # We're under a parent with an ordered child list.  Retain its order.
        match_list = match_set
    else:
        # We're at the top level, so sort to put common pages first.
        match_list = sort_pages(match_set, color=color)

    for page in match_list:
        child_matches = find_matches(page.child, color)
        if child_matches:
            page.list_page(w, indent, child_matches)
            list_matches(w, child_matches, True, color, seen_set)
            w.write('</div>\n')
        else:
            page.list_page(w, indent, None)

        seen_set.add(page)

def write_page_list(page_list, color, color_match):
    # We write out the matches to a string first so that we can get
    # the total number of keys and flowers in the list (including children).
    s = io.StringIO()
    list_matches(s, page_list, False, color_match, set())

    with open(root + f"/html/{color}.html", "w", encoding="utf-8") as w:
        title = color.capitalize() + ' flowers'
        write_header(w, title, title)
        obs = Obs(color_match)
        for page in top_flower_list:
            page.count_matching_obs(obs)
        w.write(f'<span class="parent">{obs.key} keys</span>')
        w.write(f' / <span class="leaf">{obs.leaf_obs} observed flowers</span>')
        if color_match == None:
            # Unobserved colors don't have an assigned color, so it doesn't
            # make sense to try to print out how many match the current color.
            w.write(f' / <span class="unobs">{obs.leaf_unobs} unobserved flowers</span>')
        w.write('\n')
        w.write(s.getvalue())
        obs.write_obs(None, w)
        write_footer(w)

for color in color_list:
    write_page_list(color_page_list[color], color, color)

write_page_list(top_flower_list, 'all', None)

###############################################################################
# Create pages.js

def add_elab(elabs, elab):
    if elab and elab != 'n/a' and elab not in elabs:
        elabs.append(unidecode(elab))

search_file = root + "/pages.js"
with open(search_file, "w", encoding="utf-8") as w:
    w.write('var pages=[\n')

    # Sort in reverse order of observation count.
    # In case of ties, pages are sorted alphabetically.
    # This order tie-breaker isn't particularly useful to the user, but
    # it helps prevent pages.js from getting random changes just because
    # the dictionary hashes differently.
    # The user search also wants autogenerated family pages to have lower
    # priority, but that's handled in search.js, not here.
    for page in sort_pages(page_array, with_depth=True):
        name = page.url()
        w.write(f'{{page:"{name}"')
        coms = []
        if page.com and (page.com != page.name or
                         not page.com.islower() or
                         page.icom):
            coms.append(unidecode(page.com))
        if page.icom:
            coms.append(page.icom)
        if coms:
            coms_str = '","'.join(coms)
            w.write(f',com:["{coms_str}"]')

        elabs = []
        add_elab(elabs, page.elab)
        add_elab(elabs, page.elab_inaturalist)
        add_elab(elabs, page.elab_jepson)
        add_elab(elabs, page.elab_calflora)
        if page.elab_calphotos:
            for elab in page.elab_calphotos.split('|'):
                add_elab(elabs, elab)
        if elabs and not (len(elabs) == 1 and page.name == elabs[0]):
            elabs_str = unidecode('","'.join(elabs))
            w.write(f',sci:["{elabs_str}"]')
        if page.child:
            if page.autogenerated:
                w.write(',x:"f"')
            else:
                w.write(',x:"k"')
        else:
            if page.jpg_list:
                w.write(',x:"o"')
            else:
                w.write(',x:"u"')
        w.write('},\n')

    master_glossary.write_search_terms(w)
    jepson_glossary.write_jepson_search_terms(w)
    w.write('];\n')

    w.write('var glossaries=[\n')
    for glossary in glossary_list:
        w.write(f'"{glossary.name}",\n')
    w.write('];\n')


###############################################################################
# Compare the new html files with the prev files.
# Create an HTML file with links to all new files and all modified files.
# (Ignore deleted files.)

file_list = sorted(os.listdir(root + '/html'))
new_list = []
mod_list = []
for name in file_list:
    if name.endswith('.html'):
        if not os.path.isfile(root + '/prev/' + name):
            new_list.append(name)
        elif not filecmp.cmp(root + '/prev/' + name,
                             root + '/html/' + name):
            mod_list.append(name)

if mod_list or new_list:
    mod_file = root + "/html/_mod.html"
    with open(mod_file, "w", encoding="utf-8") as w:
        if new_list:
            w.write('<h1>New files</h1>\n')
            for name in new_list:
                w.write(f'<a href="{name}">{name}</a><p/>\n')
        if mod_list:
            w.write('<h1>Modified files</h1>\n')
            for name in mod_list:
                w.write(f'<a href="{name}">{name}</a><p/>\n')

    # open the default browser with the created HTML file
    total_list = mod_list + new_list
    if len(total_list) == 1:
        os.startfile(root + '/html/' + total_list[0])
    else:
        os.startfile(mod_file)
else:
    print("No files modified.")
