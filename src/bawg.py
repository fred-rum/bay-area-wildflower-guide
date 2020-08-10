#!/cygdrive/c/Python37/python.exe
#!/usr/bin/env python

# Run as:
# /cygdrive/c/Users/Chris/Documents/GitHub/bay-area-flowers/src/bawg.py

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

# My files
from trie import *
from easy import *
from obs import *
from page import *
from files import *

# Theoretically I could find all flower pages because their iNaturalist
# observations include a subphylum of Angiospermae.  But there are a few
# flower pagse that aren't (yet) included in observations.csv, and I
# don't want them to float to the top.  So instead, I explicitly name
# the non-flower top pages, and assume that everything not in those
# hierarchies is a flower.
non_flower_top_pages = ('conifers', 'ferns')

year = datetime.datetime.today().year

if os.path.isfile(root_path + '/html/_mod.html'):
    # Keep a copy of the previous html files so that we can
    # compare differences after creating the new html files.
    shutil.rmtree(root_path + '/prev', ignore_errors=True)

    # Apparently Windows sometimes lets the call complete when the
    # remove is not actually done yet, and then the rename fails.
    # In that case, keep retrying the rename until it succeeds.
    done = False
    while not done:
        try:
            os.rename(root_path + '/html', root_path + '/prev')
            done = True
        except WindowsError as error:
            pass
else:
    # _mod.html doesn't exist, which implies that the most recent run
    # crashed before creating it.  There's no point in comparing the changes
    # with the crashed run, so we discard it and keep the previous run to
    # compare against instead.
    shutil.rmtree(root_path + '/html', ignore_errors=True)

os.mkdir(root_path + '/html')

# key: color
# value: page list
color_page_list = {}


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
        if '#' in term:
            (name, partition, term) = term.partition('#')
            if term == '':
                # I'd love to print what file this error occured in, but
                # that requires an exception or a global variable or passing
                # more data around, none of which I like.  The user will just
                # have to grep for the broken reference in the HTML.
                print(f'unrecognized glossary cross reference starting with "{name}#')
                return f'{name}#broken ref'
            elif name == 'none':
                # 'none#[term]' means that we don't want a glossary link.
                # Discard the 'none#' and return only the term.
                return term
            else:
                return glossary_title_dict[name + ' glossary'].get_link(term)

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

    def create_cross_set(self):
        if self.is_jepson:
            short_name = 'Jepson'
        else:
            short_name = re.sub(r' glossary$', '', glossary.title)

        for anchor in self.glossary_dict.keys():
            # Create a glossary entry tied to a specific glossary.
            glossary_cross_set.add(f'{short_name}#{anchor}')

            # Also create an entry tied to no glossary.  If this gets matched,
            # it prevents the creation of a glossary link.  Note that multiple
            # glossaries might create the same entry, but the set removes
            # duplicates, and they all behave the same.
            glossary_cross_set.add(f'none#{anchor}')

        # Also include entries with no term listed.  This gets matched if
        # the intended link doesn't exist, and thus an error can be flagged.
        # Note that this matches only at a word boundary, meaning that there
        # is a word immediately following the #, which is what we expect.
        glossary_cross_set.add(f'{short_name}#')
        glossary_cross_set.add('none#')


    def create_local_set(self):
        self.glossary_local_set = set(iter(self.glossary_dict.keys()))

    def create_hierarchy_set(self):
        self.glossary_set = self.glossary_local_set
        parent = self.parent
        while parent:
            self.glossary_set = self.glossary_set.union(parent.glossary_local_set)
            parent = parent.parent

        self.glossary_set = self.glossary_set.union(glossary_cross_set)

    def create_regex_old(self):
        # sort the glossary list in reverse order so that for cases where two
        # phrases start the same and one is a subset of the other, the longer
        # phrase is checked first.  (This relies on the fact that expression
        # checking is done primarily in order through the searched text, and
        # secondarily in order through the regex.)
        glossary_list = sorted(iter(self.glossary_set), reverse=True)

        ex = '|'.join(map(re.escape, glossary_list))
        self.glossary_regex = re.compile(rf'\b({ex})\b', re.IGNORECASE)

    def create_regex(self):
        ex = trie_pattern(self.glossary_set)
        self.glossary_regex = re.compile(rf'\b({ex})\b', re.IGNORECASE)

    def record_in_glossary_dict(self, anchor, word):
        word = easy_sub_safe(word.lower())
        self.glossary_dict[word] = anchor

    def read_terms(self):
        def repl_title(matchobj):
            self.title = matchobj.group(1)
            glossary_title_dict[self.title] = self
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

        with open(f'{root_path}/glossary/{self.name}.txt', mode='r') as f:
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

        with open(f'{root_path}/data/jepson_glossary.txt', mode='r') as f:
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

        self.txt = easy_sub(self.txt)

        self.txt = self.link_glossary_words(self.txt, is_glossary=True)

        # Remove the inserted 'glossaryX' text to return the (unlinked)
        # glossary terms to their normal text.
        self.txt = re.sub(r'glossaryX', '', self.txt)

        self.txt = re.sub(r'^{([^\}]+)}\s+(.*)$',
                          repl_defns, self.txt, flags=re.MULTILINE)

        with open(f'{root_path}/html/{self.name}.html', mode='w') as w:
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

        if len(sys.argv) > 2 and sys.argv[2] == 'j':
            # List the top 10 glossary terms that link to Jepson instead of
            # one of my glossaries, in order of number of references.
            anchor_list = sorted(self.used_dict, key=by_usage, reverse=True)
            for anchor in anchor_list[:10]:
                print(f'{anchor}: {self.used_dict[anchor]}')


###############################################################################
# end of Glossary class
###############################################################################


# Read the mapping of iNaturalist observation locations to short park names.
park_map = {}
park_loc = {}
with open(root_path + '/data/parks.yaml', mode='r', encoding='utf-8') as f:
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

txt_list = get_file_list('txt', 'txt')
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
        thumb_file = root_path + '/thumbs/' + name + '.jpg'
        os.remove(thumb_file)

mod_list = []
for name in jpg_list:
    photo_file = root_path + '/photos/' + name + '.jpg'
    thumb_file = root_path + '/thumbs/' + name + '.jpg'
    if (name not in thumb_list or
        os.path.getmtime(photo_file) > os.path.getmtime(thumb_file)):
        mod_list.append(photo_file)

if mod_list:
    with open(root_path + "/convert.txt", "w") as w:
        for filename in mod_list:
            filename = convert_path_to_windows(filename)
            w.write(filename + '\n')
    convert_list = convert_path_to_windows(f'{root_path}/convert.txt')
    thumb_glob = convert_path_to_windows(f'{root_path}/thumbs/*.jpg')
    cmd = ['C:/Program Files (x86)/IrfanView/i_view32.exe',
           f'/filelist={convert_list}',
           '/aspectratio',
           '/resize_long=200',
           '/resample',
           '/jpgq=80',
           f'/convert={thumb_glob}']
    subprocess.Popen(cmd).wait()

###############################################################################

# Read the txt for all txt files.  Also perform a first pass on
# the txt pages to initialize common and scientific names.  This
# ensures that when we parse children (next), any name can be used and
# linked correctly.
for name in txt_list:
    page = Page(name)
    page.name_from_txt = True
    with open(root_path + "/txt/" + name + ".txt", "r", encoding="utf-8") as r:
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

with open(root_path + '/data/ignore species.yaml', encoding='utf-8') as f:
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
with open(root_path + '/data/observations.csv', mode='r', newline='', encoding='utf-8') as f:
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

with open(root_path + '/data/family names.yaml', encoding='utf-8') as f:
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

glossary_title_dict = {}
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

# Create a set of anchors of the form '{glossary}:{anchor}' which can be
# used to link to a specific glossary.  This set includes every anchor in
# every glossary.
glossary_cross_set = set()
jepson_glossary.create_local_set()
jepson_glossary.create_cross_set()
for glossary in glossary_list:
    glossary.create_local_set()
    glossary.create_cross_set()

# Now that we know the glossary hierarchy, we can apply glossary links
# within each glossary and finally write out the HTML.
for glossary in glossary_list:
    glossary.create_hierarchy_set()
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
    # List the top 5 genus pages with an incomplete key,
    # as ordered by number of observations.
    # (If there are fewer than 5, then some random pages are listed as well.)
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

    with open(root_path + f"/html/{color}.html", "w", encoding="utf-8") as w:
        title = color.capitalize() + ' flowers'
        write_header(w, title, title)
        obs = Obs(color_match)
        for page in top_flower_list:
            page.count_matching_obs(obs)
        obs.write_page_counts(w)
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

search_file = root_path + "/pages.js"
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

file_list = sorted(os.listdir(root_path + '/html'))
new_list = []
mod_list = []
for name in file_list:
    if name.endswith('.html'):
        if not os.path.isfile(root_path + '/prev/' + name):
            new_list.append(name)
        elif not filecmp.cmp(root_path + '/prev/' + name,
                             root_path + '/html/' + name):
            mod_list.append(name)

if mod_list or new_list:
    mod_file = root_path + "/html/_mod.html"
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
        mod_file = root_path + '/html/' + total_list[0]
    os.startfile(mod_file)
else:
    print("No files modified.")
