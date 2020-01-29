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

class Obs:
    pass

    def __init__(self, color):
        self.match_set = set()
        self.color = color
        self.n = 0
        self.rg = 0
        self.parks = {}
        self.month = [0] * 12
        self.key = 0
        self.leaf_obs = 0
        self.leaf_unobs = 0

    def write_obs(self, page, w):
        n = self.n
        rg = self.rg

        if page:
            sci = page.sci
            if n == 0 and not sci:
                return

            if page.taxon_id:
                link = 'https://www.inaturalist.org/observations/chris_nelson?taxon_id={taxon_id}&order_by=observed_on'.format(taxon_id=page.taxon_id)
            elif sci:
                link = 'https://www.inaturalist.org/observations/chris_nelson?taxon_name={sci}&order_by=observed_on'.format(sci=sci)
            else:
                link = None
        else:
            link = None

        w.write('<p/>\n')

        if link:
            w.write('<a href="{link}" target="_blank">Chris&rsquo;s observations</a>: '.format(link=link))
        else:
            w.write('Chris&rsquo;s observations: ')

        if n == 0:
            w.write('none')
        elif rg == 0:
            w.write('{n} (none are research grade)'.format(n=n))
        elif rg == n:
            if n == 1:
                w.write('1 (research grade)')
            else:
                w.write('{n} (all are research grade)'.format(n=n))
        else:
            if rg == 1:
                w.write('{n} ({rg} is research grade)'.format(n=n, rg=rg))
            else:
                w.write('{n} ({rg} are research grade)'.format(n=n, rg=rg))

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
                    w.write('<li>{park}</li>\n'.format(park=park))
                else:
                    w.write('<li>{park}: {count}</li>\n'.format(park=park, count=count))

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
                w.write('<li>{m}: {n}</li>\n'.format(m=month_name[m], n=self.month[m]))
            w.write('</ul>\n</div>\n')
        else:
            w.write('<p/>\n')

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
    if name.islower():
        return find_page2(name, None)
    else:
        return find_page2(None, name)

class Page:
    pass

    def __init__(self, name):
        if name in name_page:
            print('Multiple pages created with name "{name}"'.format(name=name))
        self.name = name
        name_page[name] = self

        self.com = None # a common name
        self.sci = None # a scientific name stripped of elaborations
        self.elab = None # an elaborated scientific name
        self.family = None # the scientific family
        self.level = None # taxonomic level: above, genus, species, or below

        self.no_sci = False # true if it's a key page for unrelated species
        self.no_family = False # true if it's a key page for unrelated genuses

        self.elab_calflora = None
        self.elab_calphotos = None
        self.elab_jepson = None

        self.autogenerated = False # true if it's an autogenerated family page

        self.ext_photo_list = [] # list of (text, calphotos_link) tuples
        self.genus_complete = None # indicates the completeness of the genus
        self.genus_key_incomplete = False # indicates if the key is complete
        self.species_complete = None # the same for the species
        self.species_key_incomplete = False

        # Give the page a default common or scientific name as appropriate.
        # Either or both names may be modified later.
        if name.islower():
            # If there isn't an uppercase letter anywhere, it's a common name.
            self.set_com(name)
        else:
            # If there is an uppercase letter somewhere, it's a scientific name.
            self.set_sci(name)

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

    def url(self):
        return unidecode(self.name)

    def set_com(self, com):
        self.com = com
        if com in com_page:
            if com != com_page[com]:
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
            print('Same scientific name ({sci}) set for {name1} and {name2}'.format(sci=sci, name1=sci_page[sci].name, name2=self.name))

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
                    

    def set_family(self):
        if self.family or self.no_family: # it's already been set
            return
        for child in self.child:
            child.set_family()
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
        if not self.family and self.sci:
            genus = self.sci.split(' ')[0]
            if genus in genus_family:
                self.family = genus_family[genus]
        family = self.family
        if family:
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
            elab_words = elab.split(' ')
            return '{type} <i>{name}</i>'.format(type=elab_words[0],
                                                 name=elab_words[1])
        else:
            if self.is_hybrid:
                elab = re.sub(r' ', ' &times; ', elab)
            return '<i>{elab}</i>'.format(elab=elab)

    def format_full(self, lines=2):
        com = self.format_com()
        elab = self.format_elab()
        if not com:
            return elab
        elif not elab:
            return com
        elif lines == 1:
            return '{com} ({elab})'.format(com=com, elab=elab)
        else:
            return '{com}<br/>{elab}'.format(com=com, elab=elab)

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

        def repl_sci_fpj(matchobj):
            sites = matchobj.group(1)
            elab = matchobj.group(2)
            if 'f' in sites:
                self.elab_calflora = elab
            if 'p' in sites:
                self.elab_calphotos = elab
            if 'j' in sites:
                self.elab_jepson = elab
            return ''

        self.txt = re.sub(r'^com:\s*(.*?)\s*?\n',
                          repl_com, self.txt, flags=re.MULTILINE)
        self.txt = re.sub(r'^sci:\s*(.*?)\s*?\n',
                          repl_sci, self.txt, flags=re.MULTILINE)
        self.txt = re.sub(r'^sci([_fpj]+):\s*(.*?)\s*?\n',
                          repl_sci_fpj, self.txt, flags=re.MULTILINE)

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
            print('color is defined more than once for page {name}'.format(name=self.name))

        self.color = set([x.strip() for x in color_str.split(',')])

        # record the original order of colors in case we want to write
        # it out.
        self.color_txt = color_str

        # check for bad colors.
        for color in self.color:
            if color not in color_list and color != 'n/a':
                print('page {name} uses undefined color {color}'.format(name=self.name, color=color))

    def record_ext_photo(self, label, link):
        if (label, link) in self.ext_photo_list:
            print('{link} is specified more than once for page {name}'.format(link=link, name=self.name))
        else:
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
            print("circular loop when creating link from {parent} to {child}".format(parent=self.name, child=child.name))
        elif self in child.parent:
            print("{child} added as child of {parent} twice".format(parent=self.name, child=child.name))
        else:
            self.child.append(child)
            child.parent.add(self)
            self.key = True

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
                if com.islower():
                    sci = ''
                else:
                    sci = com
                    com = ''
            # +com[,suffix][:sci] -> creates a child relationship with the
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
                if (self.cur_genus and len(sci) >= 3 and
                    sci[0:3] == self.cur_genus[0] + '. '):
                    sci = self.cur_genus + sci[2:]
                elif sci[0].isupper():
                    # If the child's genus is explicitly specified,
                    # make it the default for future abbreviations.
                    self.cur_genus = sci.split(' ')[0]
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
                        print('page {parent} has ambiguous child {child}'.format(parent=self.name, child=com))
                        return '==' + com + suffix

                    if (com in name_page and
                        com not in txt_list and
                        com not in jpg_list):
                        # The user didn't explicitly say that the previous
                        # user of the common name should name its page that
                        # way.  Since we now know that there are two with
                        # the same name, *neither* of them should use the
                        # common name as the page name.  So change the other
                        # page's page name to its scientific name.
                        name_page[com].name = name_page[com].sci
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
                        print("page {parent} refers to child {com}:{sci}, but the common name doesn't match".format(parent=self.name, com=com, sci=sci))
                else:
                    child_page.set_com(com)
            if sci:
                child_page.set_sci(sci)

            # Replace the {+...} or {...} field with a bare +... line.
            # This will create the appropriate link later in the parsing.
            return '==' + name + suffix

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

        with open(root + "/txt2/{name}.txt".format(name=self.name), "w") as w:
            if self.com and self.com != self.name:
                w.write('com:{com}\n'.format(com=self.com))
            if self.elab and self.elab != self.name:
                w.write('sci:{elab}\n'.format(elab=self.elab))
            if self.no_sci:
                w.write('sci:n/a\n')
            if self.color:
                w.write('color:{color}\n'.format(color=self.color_txt))
            if self.genus_complete:
                if self.genus_key_incomplete:
                    w.write('x:!{complete}\n'.format(complete=self.genus_complete))
                else:
                    w.write('x:{complete}\n'.format(complete=self.genus_complete))
            if self.species_complete:
                if self.species_key_incomplete:
                    w.write('xx:!{complete}\n'.format(complete=self.species_complete))
                else:
                    w.write('xx:{complete}\n'.format(complete=self.species_complete))
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

    def parse_glossary(self):
        self.txt = link_glossary_words(self.txt)

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
        return '<a href="{name}.html" class="{style}">{full}</a>'.format(name=self.url(), style=self.link_style(), full=self.format_full(lines))

    def write_parents(self, w):
        for parent in sort_pages(self.parent):
            if not parent.autogenerated:
                w.write('Key to {link}<br/>\n'.format(link=parent.create_link(1)))
        if self.parent:
            w.write('<p/>\n')

    def page_matches_color(self, color):
        return (color == None or color in self.color)

    # Accumulate the observation for the page and all its children
    # into the obs object.  Page must match the color declared in obs
    # in order to count.
    def count_matching_obs(self, obs):
        if self in obs.match_set: return

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
                if self.jpg_list:
                    # If a page is both a key and an observed flower, pretend
                    # that one of its (unobserved) children is observed instead.
                    obs.leaf_obs += 1
                    obs.leaf_unobs -= 1
            elif self.jpg_list:
                obs.leaf_obs += 1
            else:
                obs.leaf_unobs += 1

        for child in self.child:
            child.count_matching_obs(obs)

    # Write the iNaturalist observation data.
    def write_obs(self, w):
        obs = Obs(None)
        self.count_matching_obs(obs)
        obs.write_obs(self, w)

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

        def choose_elab(elab_base, elab_alt):
            if elab_alt and elab_alt != 'n/a':
                elab = elab_alt
            else:
                elab = elab_base
            elab_words = elab.split(' ')
            if len(elab_words) == 2 and '|' not in elab:
                # Always strip the "spp." suffix or [lowercase type] prefix.
                elab = strip_sci(elab)
            return elab

        if self.taxon_id:
            elab = choose_elab(self.elab, None)
            sci = strip_sci(elab) # Should equal self.sci
            add_link(elab, None,
                     '<a href="https://www.inaturalist.org/taxa/{taxon_id}" target="_blank">iNaturalist</a>'.format(taxon_id=self.taxon_id))
        else:
            i_sci = sci
            if self.is_hybrid:
                i_sci = re.sub(r' ', ' \xD7 ', i_sci)
            add_link(elab, None,
                     '<a href="https://www.inaturalist.org/taxa/search?q={sci}&view=list" target="_blank">iNaturalist</a>'.format(sci=i_sci))

        if self.level != 'above' or self.elab.startswith('family '):
            # CalFlora can be searched by family,
            # but not by other high-level classifications.
            elab = choose_elab(self.elab, self.elab_calflora)
            add_link(elab, self.elab_calflora,
                     '<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup={elab}" target="_blank">CalFlora</a>'.format(elab=elab));

        if self.level in ('species', 'below'):
            # CalPhotos cannot be searched by high-level classifications.
            # It can be searched by genus, but I don't find that at all useful.
            elab = choose_elab(self.elab, self.elab_calphotos)
            if elab != self.elab:
                # CalPhotos can search for multiple names, and for cases such
                # as Erythranthe, it may have photos under both names.
                elab = self.elab + '|' + elab
            # rel-taxon=begins+with -> allows matches with lower-level detail
            add_link(elab, self.elab_calphotos,
                     '<a href="https://calphotos.berkeley.edu/cgi/img_query?rel-taxon=begins+with&where-taxon={elab}" target="_blank">CalPhotos</a>\n'.format(elab=elab));

        if self.level != 'above' or self.elab.startswith('family '):
            # Jepson can be searched by family,
            # but not by other high-level classifications.
            elab = choose_elab(self.elab, self.elab_jepson)
            # Jepson uses "subsp." instead of "ssp.", but it also allows us to
            # search with that qualifier left out entirely.
            sci = strip_sci(elab)
            add_link(elab, self.elab_jepson,
                     '<a href="http://ucjeps.berkeley.edu/eflora/search_eflora.php?name={sci}" target="_blank">Jepson&nbsp;eFlora</a>'.format(sci=sci));

        if self.level in ('genus', 'species', 'below'):
            elab = choose_elab(self.elab, self.elab_calflora)
            genus = elab.split(' ')[0]
            # srch=t -> search
            # taxon={name} -> scientific name to filter for
            # group=none -> just one list; not annual, perennial, etc.
            # sort=count -> sort from most records to fewest
            #   (removed because it annoyingly breaks up subspecies)
            # fmt=photo -> list results with info + sample photos
            # y={},x={},z={} -> longitude, latitude, zoom
            # wkt={...} -> search polygon with last point matching the first
            add_link(elab, self.elab_calflora,
                     '<a href="https://www.calflora.org/entry/wgh.html#srch=t&taxon={genus}&group=none&fmt=photo&y=37.5&x=-122&z=8&wkt=-123.1+38,-121.95+38,-121.05+36.95,-122.2+36.95,-123.1+38" target="_blank">Bay&nbsp;Area&nbsp;species</a>'.format(genus=genus))

        link_list_txt = []
        for elab in elab_list:
            txt = ' &ndash;\n'.join(link_list[elab])
            if len(elab_list) > 1:
                txt = '{elab}: {txt}'.format(elab=elab, txt=txt)
            link_list_txt.append(txt)
        txt = '</li>\n<li>'.join(link_list_txt)

        if len(elab_list) > 1:
            w.write('<p class="list-head">Not all sites agree about the scientific name:</p>\n<ul>\n<li>{txt}</li>\n</ul>\n'.format(txt=txt))
        else:
            w.write('{txt}<p/>\n'.format(txt=txt))

    def write_lists(self, w):
        if not self.child and not self.jpg_list:
            return

        w.write('<p class="list-head">Flower lists that include this page:</p>\n')
        w.write('<ul>\n')

        for color in color_list:
            if color in self.color:
                w.write('<li><a href="{color}.html">{color} flowers</a></li>\n'.format(color=color))

        w.write('<li><a href="all.html">all flowers</a></li>\n')
        w.write('</ul>\n')

    # List a single page, indented if it is under a parent.
    # (But don't indent it if it is itself a parent, in which case it has
    # already put itself in an indented box.)
    def list_page(self, w, indent, has_children):
        if indent:
            indent_class = ' indent'
        else:
            indent_class = ''

        if has_children:
            # A parent with listed children puts itself in a box.
            # The box may be indented, in which case, the remainder
            # of the listing is not indented.
            w.write('<div class="box{indent_class}">\n'.format(indent_class=indent_class))
            indent_class = ''

        w.write('<div class="list-box{indent_class}">'.format(indent_class=indent_class))

        if self.jpg_list:
            w.write('<a href="{name}.html"><img src="../thumbs/{jpg}.jpg" width="200" height="200" class="list-thumb"></a>'.format(name=self.url(), jpg=self.jpg_list[0]))

        w.write('{link}</div>\n'.format(link=self.create_link(2)))

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

            name = child_matchobj.group(1)
            suffix = child_matchobj.group(2)
            if not suffix:
                suffix = ''

            text = '\n'.join(c_list[child_start:])
            c_list = c_list[:child_start]
            child_start = None

            child = find_page1(name)
            if not child:
                print('Broken link to +{name} on page {key}'.format(name=name, key=self.name))
                c_list.append('=={name}{suffix}\n'.format(name=name, suffix=suffix))
                c_list.append(text)
                return

            # Give the child a copy of the text from the parent's key.
            # The child can use this (pre-parsed) text if it has no text
            # of its own.
            if ((self.level == 'genus' and child.level in ('species', 'below')) or
                (self.level == 'species' and child.level == 'below')):
                child.key_txt = text

            link = child.create_link(2)

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
                img = '<a href="{name}.html"><img src="../thumbs/{jpg}.jpg" width="200" height="200" class="{img_class}"></a>'.format(name=child.url(), jpg=jpg, img_class=img_class)
            elif ext_photo:
                img = '<a href="{name}.html" class="enclosed {style}"><div class="page-thumb-text">'.format(name=child.url(), style=child.link_style())
                n_photos = len(child.ext_photo_list)
                if n_photos > 1:
                    photo_text = 'photos &times; {n}'.format(n=n_photos)
                elif ext_photo[0]:
                    photo_text = ext_photo[0]
                else:
                    photo_text = 'photo'
                img += '<span>{text}</span>'.format(text=photo_text)
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
                c_list.append('<div class="flex-width"><div class="photo-box">{img}\n<span class="show-narrow">{link}</span></div><span><span class="show-wide">{link}</span>{text}</span></div>'.format(img=img, link=link, text=text))
            else:
                c_list.append('<div class="photo-box">{img}\n<span>{link}</span></div>'.format(img=img, link=link))

        # replace the easy (fixed-value) stuff.
        # Break the text into lines, then perform easy substitutions on
        # non-keyword lines and decorate bullet lists.
        c_list = []
        p_start = None
        child_start = None
        list_depth = 0
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

            matchobj = re.match(r'==([^\n]*?)(,[-0-9]\S*|,)?\s*$', c)
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
                continue

            if c == ']':
                end_paragraph()
                end_child_text()
                c_list.append('</div>')
                continue

            if '{' not in c:
                c = repl_easy_regex.sub(repl_easy, c)

            if list_depth:
                c_list.append('<li>{c}</li>'.format(c=c))
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
                print('Broken link {{-{name}}} on page {page}'.format(name=name, page=self.name))
                return '{-' + name + '}'

        if re.search('\S', self.txt):
            s = self.txt
        else:
            s = self.key_txt
        s = link_glossary_words(s)
        s = re.sub(r'{-([^}]+)}', repl_link, s)
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
            if is_top:
                if complete == None:
                    if top == 'genus':
                        w.write('<b>Caution: There may be other {members} of this {top} not yet included in this guide.</b>'.format(members=members, top=top))
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
                        w.write("This species has subspecies or variants which I haven't yet categorized.")
                elif complete == 'more':
                    w.write('<b>Caution: There are other {members} of this {top} not yet included in this guide.</b>'.format(members=members, top=top))
                else:
                    prolog = 'There are no other'
                    if complete == 'hist':
                        prolog = "Except for historical records that I'm ignoring, there are no other"
                    elif complete == 'rare':
                        prolog = "Except for extremely rare plants that I don't expect to encounter, there are no other"
                    elif complete == 'hist/rare':
                        prolog = "Except for old historical records and extremely rare plants that I don't expect to encounter, there are no other"

                    epilog = 'in the bay area'
                    if complete == 'ca':
                        epilog = 'in California'
                    elif complete == 'any':
                        epilog = 'anywhere'

                    w.write('{prolog} {members} of this {top} {epilog}.'.format(prolog=prolog, members=members, top=top, epilog=epilog))
                if key_incomplete:
                    w.write('<br/>\n<b>Caution: The key to distinguish these {members} is not complete.</b>'.format(members=members))
                w.write('<p/>\n')
            elif complete:
                if top == 'genus':
                    print('{name} uses the x: keyword but is not the top of genus'.format(name=self.name))
                else:
                    print('{name} uses the xx: keyword but is not the top of species'.format(name=self.name))

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
                has_family = (family != self.sci and
                              (family_page.autogenerated or
                               family_page not in self.parent))
            else:
                has_family = False
            write_header(w, title, h1, has_sci or has_family)

            if has_sci:
                w.write('<b>{elab}</b>'.format(elab=self.format_elab()))
                if has_family:
                    w.write('<br/>\n')
                else:
                    w.write('<p/>\n')
            if has_family:
                family_link = family_page.create_link(1)
                w.write('{link}<p/>\n'.format(link=family_link))

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
                    w.write('<a href="../photos/{jpg}.jpg"><img src="../thumbs/{jpg}.jpg" width="200" height="200" class="leaf-thumb"></a>\n'.format(jpg=jpg))

                for tuple in self.ext_photo_list:
                    w.write('<a href="{link}" target="_blank" class="enclosed"><div class="leaf-thumb-text">'.format(link=tuple[1]))
                    if tuple[0]:
                        w.write('<span>')
                    if 'calphotos' in tuple[1]:
                        text = 'CalPhotos'
                    elif 'calflora' in tuple[1]:
                        text = 'CalFlora'
                    else:
                        text = 'external photo'
                    w.write('<span style="text-decoration:underline;">{text}</span>'.format(text=text))
                    if tuple[0]:
                        w.write('<br/>{text}</span>'.format(text=tuple[0]))
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
            print("{name} is observed, but has no photos".format(name=page.name))

        if self.jpg_list and not self.color:
            print('No color for {name}'.format(name=self.name))

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

name_page = {} # page (base file) name -> page
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

def write_header(w, title, h1, nospace=False, nosearch=False):
    if nospace:
        space_class = ' class="nospace"'
    else:
        space_class = ''
    w.write('''<!-- Copyright 2019 Chris Nelson - All rights reserved. -->
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
'''.format(title=title))
    if not nosearch:
        w.write('''<div id="search-bg"></div>
<div id="search-container">
<input type="search" id="search" autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" placeholder="search for a flower...">
<div id="autocomplete-box"></div>
</div>
''')
    w.write('''<div id="body">
<h1 id="title"{space_class}>{h1}</h1>
'''.format(title=title, space_class=space_class, h1=h1))


def write_footer(w):
    w.write('''
<hr/>
<a href="../index.html">BAWG</a> <span class="copyright">&ndash; Copyright 2019 Chris Nelson</span>
</div>
<script src="../pages.js"></script>
<script src="../search.js"></script>
</body>
''')

# Read the glossary.txt file and write the glossary.html file.
def link_glossary_words(txt):
    def repl_glossary(matchobj):
        word = matchobj.group(1)
        primary_word = glossary_dict[word.lower()]
        return '<a class="glossary" href="glossary.html#{primary_word}">{word}</a>'.format(word=word, primary_word=primary_word)

    def repl_sub_glossary(matchobj):
        allowed = matchobj.group(1)
        disallowed = matchobj.group(2)
        allowed = re.sub(glossary_regex, repl_glossary, allowed)
        return allowed + disallowed

    # find non-links followed (optionally) by links and
    # perform substitutions only on the non-link parts.
    # The first group is non-greedy, but still starts as soon as possible
    # (i.e. at the beginning of the string or just after the previous match).
    # The second part is also non-greedy, looking for the shortest amount
    # of text to close the link.
    txt = re.sub(r'(.*?)(\Z|<a\s.*?</a>|{.*?})', repl_sub_glossary, txt,
                 flags=re.DOTALL)
    return txt

with open(root + '/glossary.txt', mode='r') as f:
    glossary_txt = f.read()

glossary_dict = {}
for (words, defn) in re.findall(r'^{([^\}]+)}\s+(.*)$',
                                glossary_txt, flags=re.MULTILINE):
    word_list = [x.strip() for x in words.split(',')]
    primary_word = word_list[0]
    for word in word_list:
        glossary_dict[word] = primary_word

# sort the glossary list in reverse order so that for cases where two
# phrases start the same and one is a subset of the other, the longer phrase
# is checked first.
glossary_list = sorted(iter(glossary_dict.keys()), reverse=True)

glossary_regex = re.compile(r'\b({ex})\b'.format(ex='|'.join(map(re.escape, glossary_list))), re.IGNORECASE)

glossary_txt = link_glossary_words(glossary_txt)

def repl_glossary(matchobj):
    global glossary_dict
    words = matchobj.group(1)
    defn = matchobj.group(2)

    word_list = [x.strip() for x in words.split(',')]
    primary_word = word_list[0]

    return '<div class="defn" id="{word}"><dt>{word}</dt><dd>{defn}</dd></div>'.format(word=primary_word, defn=defn)

glossary_txt = re.sub(r'^{([^\}]+)}\s+(.*)$',
                      repl_glossary, glossary_txt, flags=re.MULTILINE)

with open(root + '/html/glossary.html', mode='w') as w:
      write_header(w, 'BAWG Glossary', 'Glossary', nosearch=False)
      w.write(glossary_txt)
      write_footer(w)

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

page_list = get_file_list('txt', 'txt')
txt_list = page_list[:]
jpg_list = get_file_list('photos', 'jpg')
thumb_list = get_file_list('thumbs', 'jpg')

def get_name_from_jpg(jpg):
    name = re.sub(r',([-0-9]\S*|)$', r'', jpg)

    if not name.islower():
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
           '/filelist={root}\\convert.txt'.format(root=root_mod),
           '/aspectratio',
           '/resize_long=200',
           '/resample',
           '/jpgq=80',
           '/convert={root}\\thumbs\\*.jpg'.format(root=root_mod)]
    subprocess.Popen(cmd).wait()

###############################################################################

repl_easy_dict = {
    # Replace HTTP links in the text with ones that open a new tab.
    # (Presumably they're external links or they'd be in {...} format.)
    '<a href=' : '<a target="_blank" href=',

    # Replace common Jepson codes.
    '+-' : '&plusmn;',
    '--' : '&ndash;',
    '<=' : '&le;',
    '>=' : '&ge;',
    '<<' : '&#8810',
    '>>' : '&#8811',

    "'" : '&rsquo;',

    # '<' and '>' should be escaped, but for now I'll leave them alone
    # because the browser seems to figure them out correctly, and it's
    # probably smarter about it than I would be.
}

repl_easy_regex = re.compile('({ex})'.format(ex='|'.join(map(re.escape, list(repl_easy_dict.keys())))))

def repl_easy(matchobj):
    return repl_easy_dict[matchobj.group(1)]



# Read the txt for all explicit page files.
for name in page_list:
    page = Page(name)
    with open(root + "/txt/" + name + ".txt", "r", encoding="utf-8") as r:
        page.txt = r.read()

# Record jpg names for associated pages.
# Create a blank page for all unassociated jpgs.
for jpg in sorted(jpg_list):
    name = get_name_from_jpg(jpg)
    if name in name_page:
        page = name_page[name]
    else:
        page = Page(name)
    page.add_jpg(jpg)

with open(root + '/family names.yaml', encoding='utf-8') as f:
    family_com = yaml.safe_load(f)

# Perform a first pass on all pages to initialize common and scientific names.
# This ensures that when we parse children (next), any name can be used and
# linked correctly.
for page in name_page.values():
    page.parse_names()

# parse_children() can add new pages, so we make a copy of the list to
# iterate through.  parse_children() also checks for external photos,
# color, and completeness information.  If this info is within a child
# key, it is assigned to the child.  Otherwise it is assigned to the
# parent.
for page in [x for x in name_page.values()]:
    page.parse_children()
    if page.color and not page.jpg_list:
        print('page {name} has a color assigned but has no photos'.format(name=page.name))

with open(root + '/ignore species.yaml', encoding='utf-8') as f:
    sci_ignore = yaml.safe_load(f)

# Track species or subspecies observations that don't have a page even though
# there is a genus or species page that they could fit under.  We'll emit an
# error message for these once all the observations are read.
surprise_obs = set()

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
        # The scientific name is left in its standard case.
        com = row[com_idx].lower()
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

        if loc != 'bay area':
            # Ignore the observation entirely
            continue

        date = row[date_idx]
        month = int(date.split('-')[1], 10) - 1 # January = month 0

        if sci in sci_ignore:
            page = find_page2(com, sci)
            if page:
                print('{sci} is ignored, but there is a page for it ({name})'.format(sci=sci, name=page.name))
        elif sci in sci_page:
            page = sci_page[sci]
        elif com in com_page:
            if com_page[com] == 'multiple':
                print('observation {com} ({sci}) matches multiple common names but no scientific name'.format(com=com, sci=sci))
                page = None
            else:
                page = com_page[com]
                if page.sci and sci != page.sci:
                    print('observation {com} ({sci}) matches the common name for a page, but not its scientific name ({sci_page})'.format(com=com, sci=sci, sci_page=page.sci))
                    page = None
                elif not page.no_sci:
                    page.set_sci(sci)
        else:
            page = None

        if page:
            page.taxon_id = taxon_id

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
#for page in name_page.itervalues():
#    if page.name in txt_list or page.ext_photo_list or page.jpg_list:
#        page.write_txt()        

# Get a list of pages without parents (top-level pages).
top_list = [x for x in name_page.values() if not x.parent]

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
for page in name_page.values():
    if not (page.sci or page.no_sci):
        if not did_intro:
            print('No scientific name given for the following pages:')
            did_intro = True
        print('  ' + page.name)

for page in top_list:
    page.set_family()

def sort_pages(page_set, color=None):
    # helper function to sort by name
    def by_name(page):
        if page.com:
            return page.com.lower()
        else:
            return page.sci.lower()

    # helper function to sort by observation count
    def count_flowers(page):
        obs = Obs(color)
        page.count_matching_obs(obs)
        return obs.n

    # Sort in reverse order of observation count.
    # We initialize the sort with match_set sorted alphabetically.
    # This order is retained for subsets with equal observation counts.
    page_list = sorted(page_set, key=by_name)
    page_list.sort(key=count_flowers, reverse=True)
    return page_list

for family in family_child_set:
    if family in family_com:
        com = family_com[family]
    else:
        print('No common name for family {family}'.format(family=family))
        com = 'n/a'
    child_set = family_child_set[family]
    if family in sci_page:
        sci_page[family].cross_out_children(child_set)
        if child_set:
            print('The following pages are not included by the page for family {family}'.format(family=family))
            for child in child_set:
                print('  ' + child.format_full(1))
    else:
        page = Page(family)
        page.autogenerated = True
        page.set_sci('family ' + family)
        if com != 'n/a':
            page.set_com(com)
        for child in sort_pages(family_child_set[family]):
            page.txt += '=={name}\n\n'.format(name=child.name)
        page.parse_children()

# Regenerate the list of top-level pages
# now that we've added pages for families.
top_list = [x for x in name_page.values() if not x.parent]
# top_list = []
# for page in name_page.itervalues():
#     if not page.parent:
#         if page.autogenerated and len(page.child) == 1:
#             # For an autogenerated family page with just one child,
#             # ignore the family page at the top level and directly list
#             # its child instead.
#             top_list.append(page.child[0])
#         else:
#             top_list.append(page)

# Turn txt into html for all normal and default pages.
for page in name_page.values():
    page.parse()

for page in name_page.values():
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

for page in name_page.values():
    page.write_html()

if len(sys.argv) > 2 and sys.argv[2] == 'x':
    page_list = [x for x in name_page.values()]
    page_list.sort(key=by_incomplete_obs, reverse=True)
    for page in page_list[:5]:
        print(page.name)

# Find any genus with multiple species.
# Check whether all of those species share an ancestor key page in common.
# If not, print a warning.
for page in name_page.values():
    page.record_genus()

for genus in genus_page_list:
    page_list = genus_page_list[genus]
    if len(page_list) > 1:
        if genus in sci_page:
            sci_page[genus].cross_out_children(page_list)
            if page_list:
                print('The following species are not included under the {genus} spp. key'.format(genus=genus))
                for page in page_list:
                    print('  ' + page.format_full(1))
        else:
            ancestor_set = page_list[0].get_ancestor_set()
            for page in page_list[1:]:
                set2 = page.get_ancestor_set()
                ancestor_set.intersection_update(set2)
            if not ancestor_set:
                print('The following pages in {genus} spp. are not under a common ancestor:'.format(genus=genus))
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

    with open(root + "/html/{color}.html".format(color=color), "w", encoding="utf-8") as w:
        title = color.capitalize() + ' flowers'
        write_header(w, title, title)
        obs = Obs(color_match)
        for page in top_list:
            page.count_matching_obs(obs)
        w.write('<span class="parent">{k} keys</span>'.format(k=obs.key))
        w.write(' / <span class="leaf">{f} observed flowers</span>'.format(f=obs.leaf_obs))
        if color_match == None:
            # Unobserved colors don't have a color, so it doesn't make sense
            # to try to print out how many match the current color.
            w.write(' / <span class="unobs">{u} unobserved flowers</span>'.format(u=obs.leaf_unobs))
        w.write('\n')
        w.write(s.getvalue())
        obs.write_obs(None, w)
        write_footer(w)

for color in color_list:
    write_page_list(color_page_list[color], color, color)

write_page_list(top_list, 'all', None)

###############################################################################
# Create pages.js

search_file = root + "/pages.js"
with open(search_file, "w", encoding="utf-8") as w:
    w.write('var pages=[\n')
    # Sort in reverse order of observation count, but with auto-generated
    # family lists and unobserved flowers pushed to the bottom.
    # We initialize the sort by sorting alphabetically.
    # This order is retained for subsets with equal observation counts.
    # This order tie-breaker isn't particularly useful to the user, but
    # it helps prevent pages.js from getting random changes just because
    # the dictionary hashes differently.
    page_list = sort_pages([x for x in name_page.values()])
    for page in page_list:
        name = page.url()
        if page.com:
            com = unidecode(page.com)
        else:
            com = None
        if page.elab:
            elab = unidecode(page.elab)
        else:
            elab = None
        w.write('{{page:"{name}"'.format(name=name))
        if com and com != name:
            w.write(',com:"{com}"'.format(com=com))
        if elab and elab != name:
            w.write(',sci:"{elab}"'.format(elab=elab))
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
                w.write('<a href="{name}">{name}</a><p/>\n'.format(name=name))
        if mod_list:
            w.write('<h1>Modified files</h1>\n')
            for name in mod_list:
                w.write('<a href="{name}">{name}</a><p/>\n'.format(name=name))

    # open the default browser with the created HTML file
    total_list = mod_list + new_list
    if len(total_list) == 1:
        os.startfile(root + '/html/' + total_list[0])
    else:
        os.startfile(mod_file)
else:
    print("No files modified.")
