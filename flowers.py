#!/cygdrive/c/Python27/python.exe c:/Users/Chris/Documents/GitHub/bay-area-flowers/flowers.py

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

import os
import shutil
import filecmp
import subprocess
import re
import csv
import cStringIO
import yaml
import codecs

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
            else:
                link = 'https://www.inaturalist.org/observations/chris_nelson?taxon_name={sci}&order_by=observed_on'.format(sci=sci)
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
            for park in sorted(self.parks,
                               key = lambda x: self.parks[x],
                               reverse=True):
                html_park = park.encode('ascii', 'xmlcharrefreplace')
                count = self.parks[park]
                if count == 1:
                    w.write('<li>{park}</li>\n'.format(park=html_park))
                else:
                    w.write('<li>{park}: {count}</li>\n'.format(park=html_park, count=count))

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
                w.write('<li>{m}: {n}</li>'.format(m=month_name[m], n=self.month[m]))
            w.write('</ul></div>\n')
        else:
            w.write('<p/>\n')

def strip_sci(sci):
    sci_words = sci.split(' ')
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
    if com and com in name_page:
        return name_page[com]

    if sci:
        sci = strip_sci(sci)
        if sci in sci_page:
            return sci_page[sci]

    if com and com in com_page and com_page[com] != 'multiple':
        page = com_page[com]
        if sci and page.sci and page.sci != sci:
            # If the common name matches a page with a different scientific
            # name, it's treated as not a match.
            return None
        else:
            return com_page[com]

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
            print 'Multiple pages created with name "{name}"'.format(name=name)
        self.name = name
        name_page[name] = self

        self.com = None # a common name
        self.sci = None # a scientific name stripped of elaborations
        self.elab = None # an elaborated scientific name
        self.family = None # the scientific family
        self.level = None # taxonomic level: above, genus, species, or below

        self.no_sci = False # true if it's a key page for unrelated species
        self.no_family = False # true if it's a key page for unrelated genuses

        self.autogenerated = False # true if it's an autogenerated family page

        self.calphotos = [] # list of (text, calphotos_link) tuples
        self.complete = None # indicates if the genus is complete for the area
        self.key_incomplete = False # indicates if the genus key is complete

        # Give the page a default common or scientific name as appropriate.
        # Either or both names may be modified later.
        if name.islower():
            # If there isn't an uppercase letter anywhere, it's a common name.
            self.set_com(name)
        else:
            # If there is an uppercase letter somewhere, it's a scientific name.
            self.set_sci(name)

        self.txt = ''
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
        elab = elaborate_sci(sci)
        sci = strip_sci(sci)

        if sci in sci_page and sci_page[sci] != self:
            print 'Same scientific name ({sci}) set for {name1} and {name2}'.format(sci=sci, name1=sci_page[sci].name, name2=self.name)

        self.sci = sci
        self.elab = elab
        sci_page[sci] = self

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

    def format_elab(self):
        elab = self.elab
        if not elab:
            return None
        elif self.level == 'above':
            elab_words = elab.split(' ')
            return '{type} <i>{name}</i>'.format(type=elab_words[0],
                                                 name=elab_words[1])
        else:
            return '<i>{elab}</i>'.format(elab=elab)

    def format_full(self, lines=2):
        com = self.com
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

        self.txt = re.sub(r'{com:(.*)}\n', repl_com, self.txt)
        self.txt = re.sub(r'{sci:(.*)}\n', repl_sci, self.txt)

    def parse_complete(self):
        def repl_complete(matchobj):
            self.complete = matchobj.group(2)
            if matchobj.group(1):
                self.key_incomplete = True
            return ''

        self.txt = re.sub(r'{(!?)(ba|ca|any|hist|rare|hist/rare|more)}\n', repl_complete, self.txt)

    def parse_child_calphotos(self):
        def repl_child_calphotos(matchobj):
            calphotos = (matchobj.group(2), matchobj.group(1))
            name = matchobj.group(3)
            if name in name_page:
                name_page[name].calphotos.append(calphotos)
            else:
                print 'calphotos could not be attached to child {child} in key {key}'.format(child=name, key=self.name)
            return '{' + name + '}'

        self.txt = re.sub(r'{(https://calphotos.berkeley.edu/[^\}: ]+)(?::([^\}]+))?}\s*{([^\}]+)}', repl_child_calphotos, self.txt)

    def parse_calphotos(self):
        def repl_calphotos(matchobj):
            self.calphotos.append((matchobj.group(1), matchobj.group(2)))
            return ''

        self.txt = re.sub(r'^\s*(?:([^:\}]*):)?(https://calphotos.berkeley.edu/[^\} ]+)\s*\n', repl_calphotos, self.txt, flags=re.MULTILINE)

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
            print "circular loop when creating link from {parent} to {child}".format(parent=self.name, child=child.name)
        elif self in child.parent:
            print "{child} added as child of {parent} twice".format(parent=self.name, child=child.name)
        else:
            self.child.append(child)
            child.parent.add(self)
            self.key = True

    def parse_children(self):
        # Replace a {child:[page]} link with just {[page]} and record the
        # parent->child relationship.
        def repl_child(matchobj):
            x = matchobj.group(1)
            name = matchobj.group(2)
            suffix = matchobj.group(3)
            sci = matchobj.group(4)
            if not suffix:
                suffix = ''
            if not sci:
                sci = ''
            repl_string = x + name + suffix + sci
            # I changed the order of replacements in order to handle
            # unobserved links here, but now the regex for unobserved links
            # catches too much.  The regex excludes newlines (to avoid stuff
            # like '{[' or '{-', but here I specifically exclude other stuff,
            # including anything in a bare {name} format without a scientific
            # name.  Excluded stuff is simply returned reformatted as its
            # original string so that (effectively) no substitution is
            # performed.
            if (repl_string.startswith('https:') or
                repl_string.endswith('.jpg') or
                not (x or sci) or
                not (name or sci)):
                # perform no substitution
                return '{' + repl_string + '}'
            # +name[,suffix][:sci] -> creates a child relationship with [name]
            #   and creates two links to it: an image link and a text link.
            #   If a suffix is specified, the jpg with that suffix is used for
            #   the image link.
            #   If a scientific name is specified, the child's scientific name
            #   is set to that value.  The name can be in elaborated or
            #   stripped format.
            # child:name[:sci] -> creates a child relationship with [name]
            #   and creates a text link to it.
            #   If a scientific name is specified, the child's scientific name
            #   is set to that value.
            # [name]:sci -> creates a photo-less page for [name] and
            #   gives it the specified scientific name.  The child page will
            #   be populated with the standard page information, particularly
            #   links to iNaturalist, CalFlora, CalPhotos, and Jepson.
            if sci:
                sci = sci[1:] # discard colon
                # If the child's genus is abbreviated, expand it using
                # the genus of the current page.
                if (self.cur_genus and len(sci) >= 3 and
                    sci[0:3] == self.cur_genus[0] + '. '):
                    sci = self.cur_genus + sci[2:]
                elif sci[0].isupper():
                    # If the child's genus is explicitly specified,
                    # make it the default for future abbreviations.
                    self.cur_genus = sci.split(' ')[0]
            child_page = find_page2(name, sci)
            if not child_page:
                if not name:
                    name = strip_sci(sci)
                # If the child does not exist, create it.
                child_page = Page(name)
                # We don't expect a '+' or 'child:' link to a missing page;
                # only a {name:sci} link should create a fresh page.
                if x:
                    print 'Broken link to {{{name}}} on page {page}'.format(name=name, page=self.name)
            name = child_page.name
            self.assign_child(child_page)
            # In addition to linking to the child,
            # also give a scientific name to it.
            if sci:
                child_page.set_sci(sci)
            if x == 'child:':
                print 'child: used on page {name}'.format(self.name)
            if x == '+':
                # Replace the {+...} field with two new fields:
                # - a photo that links to the child
                # - a text link to the child
                return ('{' + name + ':' + name + suffix + '.jpg}\n'
                        '{' + name + '}')
            else:
                # Replace the {child:name} or {name:sci} field with a new field:
                # - a text link to the child
                return '{' + name + '}'

        # If the page's genus is explicitly specified,
        # make it the default for child abbreviations.
        if self.level in ('genus', 'species', 'below'):
            self.cur_genus = self.sci.split(' ')[0]
        else:
            self.cur_genus = None

        if re.search(r'{([^}]+):([^}]+).jpg}', self.txt):
            print '{[page]:[jpg].jpg} used on page ' + self.name

        self.txt = re.sub(r'{(child:|\+|)([^\}:,\n]*)(,[-0-9]*)?(:[^\}\n]+)?}', repl_child, self.txt)

    def parse_glossary(self):
        def repl_glossary(matchobj):
            word = matchobj.group(1)
            primary_word = glossary_dict[word.lower()]
            return '<a class="glossary" href="glossary.html#{primary_word}">{word}</a>'.format(word=word, primary_word=primary_word)

        out_list = []
        for s in self.txt.split('\n'):
            if s and s[0] != '{':
                s = re.sub(glossary_regex, repl_glossary, s)
            out_list.append(s)
        self.txt = '\n'.join(out_list)

    def create_link(self, lines):
        if self.autogenerated:
            style = ' class="family"'
        elif self.key:
            style = ' class="parent"'
        elif self.jpg_list:
            style = ' class="leaf"'
        else:
            style = ' class="unobs"'
        return '<a href="{name}.html"{style}>{full}</a>'.format(name=self.name, style=style, full=self.format_full(lines))

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

        if self.taxon_id:
            w.write('<a href="https://www.inaturalist.org/taxa/{taxon_id}" target="_blank">iNaturalist</a> &ndash;\n'.format(taxon_id=self.taxon_id))
        else:
            w.write('<a href="https://www.inaturalist.org/search?q={sci}&source=taxa" target="_blank">iNaturalist</a> &ndash;\n'.format(sci=sci))

        if self.level != 'above' or self.elab.startswith('family '):
            # CalFlora can be searched by family,
            # but not by other high-level classifications.
            w.write('<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup={elab}" target="_blank">CalFlora</a> &ndash;\n'.format(elab=elab));

        if self.level in ('genus', 'species', 'below'):
            # CalPhotos cannot be searched by high-level classifications.
            # rel-taxon=begins+with -> allows matches with lower-level detail
            w.write('<a href="https://calphotos.berkeley.edu/cgi/img_query?rel-taxon=begins+with&where-taxon={elab}" target="_blank">CalPhotos</a> &ndash;\n'.format(elab=elab));

        # Jepson uses "subsp." instead of "ssp.", but it also allows us to
        # search with that qualifier left out entirely.
        w.write('<a href="http://ucjeps.berkeley.edu/eflora/search_eflora.php?name={sci}" target="_blank">Jepson eFlora</a>\n'.format(sci=sci));

        if self.level in ('genus', 'species', 'below'):
            genus = sci.split(' ')[0]
            # srch=t -> search
            # taxon={name} -> scientific name to filter for
            # group=none -> just one list; not annual, perennial, etc.
            # sort=count -> sort from most records to fewest
            #   (removed because it annoyingly breaks up subspecies)
            # fmt=photo -> list results with info + sample photos
            # y={},x={},z={} -> longitude, latitude, zoom
            # wkt={...} -> search polygon with last point matching the first
            w.write('&ndash; <a href="https://www.calflora.org/entry/wgh.html#srch=t&taxon={genus}&group=none&fmt=photo&y=37.5&x=-122&z=8&wkt=-123.1+38,-121.95+38,-121.05+36.95,-122.2+36.95,-123.1+38" target="_blank">Bay Area species\n'.format(genus=genus))

        w.write('<p/>\n');

    def write_lists(self, w):
        if not self.child and not self.jpg_list:
            return

        w.write('<hr/>\n')
        w.write('Flower lists that include this page:<p/>\n')
        w.write('<ul/>\n')

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

        w.write('<div class="photo-box{indent_class}">'.format(indent_class=indent_class))

        if self.jpg_list:
            w.write('<a href="{name}.html"><img src="../thumbs/{jpg}.jpg" width="200" height="200" class="list-thumb"></a>'.format(name=self.name, jpg=self.jpg_list[0]))

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

    # The giant 'parse' function, which turns txt into html
    # and writes the resulting file.
    def parse(self):
        s = self.txt

        def repl_easy(matchobj):
            return repl_easy_dict[matchobj.group(1)]

        # replace the easy (fixed-value) stuff.
        s = repl_easy_regex.sub(repl_easy, s)

        def repl_list(matchobj):
            c = matchobj.group(1)
            c = re.sub(r'\n', r'</li>\n<li>', c)

            # If there's a sublist, its <ul> & </ul> must be on their own lines,
            # in which case we remove the accidental surrounding <li>...</li>.
            c = re.sub(r'<li>(<(/?)ul>)</li>', r'\1', c)

            return '\n<ul>\n<li>{c}</li>\n</ul>\n'.format(c=c)

        s = re.sub(r'\n{-\n(.*?)\n-}\n', repl_list, s, flags=re.DOTALL)

        # Look for any number of {photos} followed by all text up to the
        # first \n\n or \n+EOF.  Photos can be my own or CalPhotos.
        # The photos and text are grouped together and vertically centered.
        # The text is also put in a <span> for correct whitespacing.
        def repl_photo_box(matchobj):
            imgs = matchobj.group(1)
            text = matchobj.group(2)

            if re.search(r'{.*{', imgs) and text:
                print 'multiple images used on page ' + self.name

            # If the text after the images appears to be a species link
            # followed by more text, then duplicate and contain the
            # species link so that the following text can either be in
            # the same column or on a different row, depending on the
            # width of the viewport.
            matchobj2 = re.match(r'({.*}\s*)\n(.*)', text, flags=re.DOTALL)
            if matchobj2:
                species = matchobj2.group(1)
                text = matchobj2.group(2)
                # [div-flex-horiz-or-vert
                #  [div-horiz photos, (narrow-only) species]
                #  [span-vert (wide-only) species, text]
                # ]
                return '<div class="flex-width"><div class="photo-box">{imgs}<span class="show-narrow">{species}</span></div><span><span class="show-wide">{species}</span>{text}</span></div>'.format(imgs=imgs, species=species, text=text)
            else:
                return '<div class="photo-box">{imgs}<span>{text}</span></div>'.format(imgs=imgs, text=text)

        s = re.sub(r'((?:\{(?:jpgs|[^\}]+.jpg|https://calphotos.berkeley.edu/[^\}]+)\} *(?:\n(?!\n))?)+)(.*?)(?=\n(\n|\Z))', repl_photo_box, s, flags=re.DOTALL)

        # Replace a pair of newlines with a paragraph separator.
        # (Do this after making specific replacements based on paragraphs,
        # but before replacements that might create empty lines.)
        s = s.replace('\n\n', '\n<p/>\n')

        # Replace {*.jpg} with a thumbnail image and either
        # - a link to the full-sized image, or
        # - a link to a child page.
        def repl_jpg(matchobj):
            jpg = matchobj.group(1)

            # Decompose a jpg reference of the form {[page]:[img].jpg}
            pos = jpg.find(':')
            if pos > 0:
                link = jpg[:pos]
                jpg = jpg[pos+1:]
                link_to_jpg = False
            else:
                link_to_jpg = True

            # Keep trying stuff until we find something in the global jpg_list
            # or until we explicitly give up.
            orig_jpg = jpg
            if jpg not in jpg_list and jpg in name_page:
                # If the "jpg" name is actually a page name, get a jpg
                # from that page.
                jpg_page = name_page[jpg]
                jpg = jpg_page.get_jpg()

            found = (jpg in jpg_list)
            if not found:
                jpg = orig_jpg

            thumb = '../thumbs/{jpg}.jpg'.format(jpg=jpg)

            if link_to_jpg:
                href = '../photos/{jpg}.jpg'.format(jpg=jpg)
                img_class = 'leaf-thumb'
            else:
                href = '{link}.html'.format(link=link)
                if page.autogenerated:
                    img_class = 'list-thumb'
                else:
                    img_class = 'page-thumb'

            if found:
                img = '<a href="{href}"><img src="{thumb}" width="200" height="200" class="{img_class}"></a>'.format(href=href, thumb=thumb, img_class=img_class)
            else:
                img = '<a href="{href}" class="missing"><div class="page-thumb-text"><span>{jpg}</span></div></a>'.format(jpg=jpg, href=href)
                print '{jpg}.jpg missing on page {name}'.format(jpg=jpg, name=self.name)

            return img

        s = re.sub(r'{([^}]+).jpg}', repl_jpg, s)

        # Replace a {CalPhotos:text} reference with a 200px box with
        # "CalPhotos: text" in it.
        # The entire box is a link to CalPhotos.
        # The ":text" part is optional.
        def repl_calphotos(matchobj):
            print 'lost calphotos reference in page ' + self.name
            href = matchobj.group(1)
            pos = href.find(':') # find the colon in "http:"
            pos = href.find(':', pos+1) # find the next colon, if any
            if pos > 0:
                text = '<br/>' + href[pos+1:]
                href = href[:pos]
            else:
                text = ''

            img = '<a href="{href}" target="_blank" class="enclosed"><div class="page-thumb-text"><span><span style="text-decoration:underline;">CalPhotos</span>{text}</span></div></a>'.format(href=href, text=text)

            return img

        s = re.sub(r'\{(https://calphotos.berkeley.edu/[^\}]+)\}', repl_calphotos, s)

        # Any remaining {reference} should refer to another page.
        # Replace it with a link to one of my pages (if I can).
        def repl_link(matchobj):
            name = matchobj.group(1)
            if name[0] == '-':
                name = name[1:]
                lines = 1
            else:
                lines = 2
            page = find_page1(name)
            if page:
                return page.create_link(lines)
            else:
                print 'Broken link {{{name}}} on page {page}'.format(name=name, page=self.name)
                return '{' + name + '}'

        s = re.sub(r'{([^}]+)}', repl_link, s)

        with open(root + "/html/" + self.name + ".html", "w") as w:
            com = self.com
            elab = self.elab

            if com:
                title = com
                h1 = com
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

            is_top_of_genus = True
            if self.level in (None, 'above'):
                is_top_of_genus = False
            for parent in self.parent:
                if parent.level in ('genus', 'species', 'below'):
                    is_top_of_genus = False
            if is_top_of_genus or self.complete:
                if is_top_of_genus:
                    top = 'genus'
                    members = 'species'
                else:
                    top = 'species'
                    members = 'members'
                if self.complete == None:
                    w.write('<b>Caution: There may be other {members} of this {top} not yet included in this guide.</b>'.format(members=members, top=top))
                elif self.complete == 'more':
                    w.write('<b>Caution: There are other {members} of this {top} not yet included in this guide.</b>'.format(members=members, top=top))
                else:
                    prolog = 'There are no other'
                    if self.complete == 'hist':
                        prolog = "Except for historical records that I'm ignoring, there are no other"
                    elif self.complete == 'rare':
                        prolog = "Except for extremely rare plants that I don't expect to encounter, there are no other"
                    elif self.complete == 'hist/rare':
                        prolog = "Except for old historical records and extremely rare plants that I don't expect to encounter, there are no other"

                    epilog = 'in the bay area'
                    if self.complete == 'ca':
                        epilog = 'in California'
                    elif self.complete == 'any':
                        epilog = 'anywhere'

                    w.write('{prolog} {members} of this {top} {epilog}.'.format(prolog=prolog, members=members, top=top, epilog=epilog))
                if self.key_incomplete:
                    w.write('<br/>\n<b>Caution: The key to distinguish these {members} is not complete.</b>'.format(members=members))
                w.write('<p/>\n')

            if len(self.jpg_list) or len(self.calphotos):
                w.write('<div class="photo-box">\n')

                for jpg in self.jpg_list:
                    w.write('<a href="../photos/{jpg}.jpg"><img src="../thumbs/{jpg}.jpg" width="200" height="200" class="leaf-thumb"></a>\n'.format(jpg=jpg))

                for tuple in self.calphotos:
                    w.write('<a href="{link}" target="_blank" class="enclosed"><div class="leaf-thumb-text">'.format(link=tuple[1]))
                    if tuple[0]:
                        w.write('<span>')
                    w.write('<span style="text-decoration:underline;">CalPhotos</span>'.format(link=tuple[1]))
                    if tuple[0]:
                        w.write('<br/>{text}</span>'.format(text=tuple[0], link=tuple[1]))
                    w.write('</div></a>\n')

                w.write('</div>\n')

            w.write(s)

            self.write_obs(w)
            if self.sci:
                self.write_external_links(w)
            self.write_lists(w)
            write_footer(w)

        if self.jpg_list and not self.color:
            print 'No color for {name}'.format(name=self.name)

        # record all pages that are within each genus
        sci = self.sci
        if self.level in ('species', 'below'):
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
<input type="search" id="search" autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" placeholder="search for a flower..." autofocus>
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
with open(root + '/glossary.txt', mode='r') as f:
    glossary_txt = f.read()

glossary_dict = {} # for fast access
glossary_list = [] # to retain order for proper matching priority
def repl_glossary(matchobj):
    global glossary_dict
    words = matchobj.group(1)
    defn = matchobj.group(2)

    word_list = [x.strip() for x in words.split(',')]
    primary_word = word_list[0]
    for word in word_list:
        glossary_dict[word] = primary_word
    glossary_list.extend(word_list)
    return '<div class="defn" id="{word}"><dt>{word}</dt><dd>{defn}</dd></div>'.format(word=primary_word, defn=defn)

glossary_txt = re.sub(r'{([^\}]+)}\s+(.*)', repl_glossary, glossary_txt)
glossary_regex = re.compile(r'\b({ex})\b'.format(ex='|'.join(map(re.escape, glossary_list))), re.IGNORECASE)

with (open(root + '/html/glossary.html', mode='w')) as w:
      write_header(w, 'BAWG Glossary', 'Glossary', nosearch=False)
      w.write(glossary_txt)
      write_footer(w)

# Read the mapping of iNaturalist observation locations to short park names.
park_map = {}
with codecs.open(root + '/parks.yaml', mode='r', encoding="utf-8") as f:
    yaml_data = yaml.safe_load(f)
for x in yaml_data:
    if isinstance(x, basestring):
        park_map[x] = x
    else:
        for y in x:
            park_map[x[y]] = y

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
jpg_list = get_file_list('photos', 'jpg')
thumb_list = get_file_list('thumbs', 'jpg')

def get_name_from_jpg(jpg):
    name = re.sub(r',([-0-9]*)$', r'', jpg)

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

    # Handle boxes on key pages.
    '{[' : '<div class="box">',
    ']}' : '</div>',

    # Replace common Jepson codes.
    '+-' : '&plusmn;',
    '--' : '&ndash;',
    '<=' : '&le;',
    '>=' : '&ge;',
    '<<' : '&#8810',
    '>>' : '&#8811',

    # '<' and '>' should be escaped, but for now I'll leave them alone
    # because the browser seems to figure them out correctly, and it's
    # probably smarter about it than I would be.
}

repl_easy_regex = re.compile('({ex})'.format(ex='|'.join(map(re.escape, repl_easy_dict.keys()))))


# Read the txt for all explicit page files.
for name in page_list:
    page = Page(name)
    with open(root + "/txt/" + name + ".txt", "r") as r:
        page.txt = r.read()

# Create implicit txt for all unassociated jpgs.
# Record jpg names for the jpgs' associated pages
# (whether those pages are old or new).
for jpg in sorted(jpg_list):
    name = get_name_from_jpg(jpg)
    if name in name_page:
        page = name_page[name]
    else:
        page = Page(name)
    page.add_jpg(jpg)

# Read color info from the YAML file.
with open(root + '/color.yaml') as f:
    yaml_data = yaml.safe_load(f)
for name in yaml_data:
    if name in name_page:
        page = name_page[name]
        page.color = set([x.strip() for x in yaml_data[name].split(',')])
        for color in page.color:
            if color not in color_list:
                print 'page {name} uses undefined color {color}'.format(name=name, color=color)
    else:
        print 'colors specified for non-existant page {name}'.format(name=name)

with open(root + '/family names.yaml') as f:
    family_com = yaml.safe_load(f)

# Perform a first pass on all pages to
# - initialize common and scientific names as specified
# - detect parent->child relationships among pages
# - add links to glossary words

# parse_children() can add new pages, so we make a copy of the list to
# iterate through.
for page in [x for x in name_page.itervalues()]:
    page.parse_names()
    page.parse_complete()
    page.parse_children()
    page.parse_child_calphotos()
    page.parse_calphotos()
    page.parse_glossary()

with open(root + '/ignore species.yaml') as f:
    sci_ignore = yaml.safe_load(f)

def unicode_csv_reader(unicode_csv_data, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]

def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')

# Track species or subspecies observations that don't have a page even though
# there is a genus or species page that they could fit under.  We'll emit an
# error message for these once all the observations are read.
surprise_obs = set()

# Read my observations file (exported from iNaturalist) and use it as follows:
#   Associate common names with scientific names
#   Get a count of observations (total and research grade) of each flower.
#   Get an iNaturalist taxon ID for each flower.
with codecs.open(root + '/observations.csv', mode='r', encoding="utf-8") as f:
    csv_reader = unicode_csv_reader(f)
    header_row = csv_reader.next()

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
            if x in park:
                short_park = park_map[x]
                break
        else:
            park_nf_list.add(park)
            short_park = park

        date = row[date_idx]
        month = int(date.split('-')[1], 10) - 1 # January = month 0

        if sci in sci_page:
            page = sci_page[sci]
        elif com in com_page:
            if com_page[com] == 'multiple':
                print 'observation {com} ({sci}) matches multiple common names but no scientific name'.format(com=com, sci=sci)
            else:
                page = com_page[com]
                if page.sci:
                    if sci != page.sci and sci not in sci_ignore:
                        print 'observation {com} ({sci}) matches the common name for a page, but not its scientific name ({sci_page})'.format(com=com, sci=sci, sci_page=page.sci)
                elif not page.no_sci:
                    page.set_sci(sci)
        else:
            page = None

        if page:
            page.taxon_id = taxon_id

        # If we haven't matched the observation to a page, try stripping
        # components off the scientific name until we find a higher-level
        # page to attach the observation to.
        orig_sci = sci
        while not page and sci:
            sci_words = sci.split(' ')
            sci = ' '.join(sci_words[:-1])
            if sci in sci_page:
                page = sci_page[sci]
                if orig_sci not in sci_ignore:
                    surprise_obs.add(orig_sci)

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
    print "The following observed species don't have a page even though a parent (genus or below) does:"
    for sci in sorted(surprise_obs):
        print '  ' + repr(sci)

if park_nf_list:
    print "Parks not found:"
    for x in park_nf_list:
        print "  " + repr(x)

# Get a list of pages without parents (top-level pages).
top_list = [x for x in name_page.itervalues() if not x.parent]

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
for page in name_page.itervalues():
    if not (page.sci or page.no_sci):
        if not did_intro:
            print 'No scientific name given for the following pages:'
            did_intro = True
        print '  ' + page.name

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
        print 'No common name for family {family}'.format(family=family)
        com = 'n/a'
    child_set = family_child_set[family]
    if family in sci_page:
        sci_page[family].cross_out_children(child_set)
        if child_set:
            print 'The following pages are not included by the page for family {family}'.format(family=family)
            for child in child_set:
                print '  ' + child.format_full(1)
    else:
        page = Page(family)
        page.autogenerated = True
        page.set_sci('family ' + family)
        if com != 'n/a':
            page.set_com(com)
        for child in sort_pages(family_child_set[family]):
            page.txt += '{{+{name}}}\n\n'.format(name=child.name)
        page.parse_children()

# Regenerate the list of top-level pages
# now that we've added pages for families.
top_list = [x for x in name_page.itervalues() if not x.parent]
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
for page in name_page.itervalues():
    page.parse()

# Find any genus with multiple species.
# Check whether all of those species share an ancestor key page in common.
# If not, print a warning.
for genus in genus_page_list:
    page_list = genus_page_list[genus]
    if len(page_list) > 1:
        if genus in sci_page:
            sci_page[genus].cross_out_children(page_list)
            if page_list:
                print 'The following species are not included under the {genus} spp. key'.format(genus=genus)
                for page in page_list:
                    print '  ' + page.format_full(1)
        else:
            ancestor_set = page_list[0].get_ancestor_set()
            for page in page_list[1:]:
                set2 = page.get_ancestor_set()
                ancestor_set.intersection_update(set2)
            if not ancestor_set:
                print 'The following pages in {genus} spp. are not under a common ancestor:'.format(genus=genus)
                for page in page_list:
                    print '  ' + page.format_full(1)

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
    s = cStringIO.StringIO()
    list_matches(s, page_list, False, color_match, set())

    with open(root + "/html/{color}.html".format(color=color), "w") as w:
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
with open(search_file, "w") as w:
    w.write('var pages=[\n')
    # Sort in reverse order of observation count.
    # We initialize the sort by sorting alphabetically.
    # This order is retained for subsets with equal observation counts.
    # This order tie-breaker isn't particularly useful to the user, but
    # it helps prevent pages.js from getting random changes just because
    # the dictionary hashes differently.
    page_list = sort_pages([x for x in name_page.itervalues()])
    for page in page_list:
        w.write('{{page:"{name}"'.format(name=page.name))
        if page.com and page.com != page.name:
            w.write(',com:"{com}"'.format(com=page.com))
        if page.elab and page.elab != page:
            w.write(',sci:"{elab}"'.format(elab=page.elab))
        if page.child:
            w.write(',key:true')
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
    with open(mod_file, "w") as w:
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
    print "No files modified."
