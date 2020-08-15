#!/cygdrive/c/Python37/python
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
import re
import csv
import io
import yaml
import codecs
from unidecode import unidecode
import datetime
import time

# My files
from error import *
from files import *
from easy import *
from obs import *
from page import *
from photo import *
from glossary import *

# Theoretically I could find all flower pages because their iNaturalist
# observations include a subphylum of Angiospermae.  But there are a few
# flower pagse that aren't (yet) included in observations.csv, and I
# don't want them to float to the top.  So instead, I explicitly name
# the non-flower top pages, and assume that everything not in those
# hierarchies is a flower.
non_flower_top_pages = ('conifers', 'ferns')

year = datetime.datetime.today().year

shutil.rmtree(working_path, ignore_errors=True)
os.mkdir(working_path)
os.mkdir(working_path + '/html')

# key: color
# value: page list
color_page_list = {}


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

txt_files = get_file_set('txt', 'txt')

###############################################################################

# Read the txt for all txt files.  Also perform a first pass on
# the txt pages to initialize common and scientific names.  This
# ensures that when we parse children (next), any name can be used and
# linked correctly.
for name in txt_files:
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

assign_jpgs()

# Although other color checks are done later, we check for excess colors
# here before propagating color to parent pages that might not have photos.
for page in page_array:
    if page.color and not page.jpg_list:
        error(f'page {page.name} has a color assigned but has no photos')

with open(root_path + '/data/ignore species.yaml', encoding='utf-8') as f:
    sci_ignore = yaml.safe_load(f)

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
            for page in page_list:
                error(page.format_full(1), prefix=f'The following species are not included under the {genus} spp. key:')
        else:
            ancestor_set = page_list[0].get_ancestor_set()
            for page in page_list[1:]:
                set2 = page.get_ancestor_set()
                ancestor_set.intersection_update(set2)
            if not ancestor_set:
                for page in page_list:
                    error(page.format_full(1), prefix=f'The following pages in {genus} spp. are not under a common ancestor:')

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

    # surprise_obs and park_nf_list have their errors printed at the end
    # so that they don't end up interleaved together.

    # Record species or subspecies observations that don't have a page
    # even though there is a genus or species page that they could fit
    # under.
    surprise_obs = set()

    # Record parks that don't have a short name defined.
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
                error(f'{sci} is ignored, but there is a page for it ({page.name})')

            # For sci_ignore == '+...', the expectation is that we'll fail
            # to find a page for it, but we'll find a page at a higher level.
            # But if sci_ignore == '-...', we do nothing with the observation.
            if sci_ignore[sci][0] != '+':
                continue
        elif not page and com in com_page:
            error(f'observation {com} ({sci}) matches the common name for a page, but not its scientific name')
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
                    #error(f"iNaturalist's common name {com} differs from mine: {page.com} ({page.elab})")
            if com and not page.com:
                error(f"iNaturalist supplies a missing common name for {com} ({page.elab})")

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

for sci in sorted(surprise_obs):
    error(sci, prefix="The following observations don't have a page even though a page exists in the same genus:")

for park in sorted(park_nf_list):
    error(park, prefix='Parks not found:')

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
        error(page.name, prefix='No scientific name given for the following pages:')

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
        error(f'No common name for family {family}')
        com = 'n/a' # family names.yaml uses 'n/a' when there is no common name
    child_set = family_child_set[family]
    if family in sci_page:
        sci_page[family].cross_out_children(child_set)
        for child in child_set:
            error(child.format_full(1), prefix=f'The following pages are not included by the page for family {family}:')
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

parse_glossaries(top_list)

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

if len(sys.argv) > 1 and sys.argv[1] == 'x':
    # List the top 5 genus pages with an incomplete key,
    # as ordered by number of observations.
    # (If there are fewer than 5, then some random pages are listed as well.)
    page_list = page_array[:]
    page_list.sort(key=by_incomplete_obs, reverse=True)
    for page in page_list[:5]:
        print(page.name)

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

    with open(working_path + f"/html/{color}.html", "w", encoding="utf-8") as w:
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
#
# We create it in root_path instead of working_path because we're just about
# done.  Since pages.js isn't compared to the previous version, the only
# disadvantage if the script crashes just after creating pages.js, it may
# point to pages that don't exist.  Whatever.

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

    write_glossary_search_terms(w)
    w.write('];\n')

    w.write('var glossaries=[\n')
    for glossary in glossary_list:
        w.write(f'"{glossary.name}",\n')
    w.write('];\n')


###############################################################################
# Compare the new html files with the prev files.
# Create an HTML file with links to all new files and all modified files.
# (Ignore deleted files.)

file_list = sorted(os.listdir(working_path + '/html'))
new_list = []
mod_list = []
for name in file_list:
    if name.endswith('.html'):
        if not os.path.isfile(root_path + '/html/' + name):
            new_list.append(name)
        elif not filecmp.cmp(root_path + '/html/' + name,
                             working_path + '/html/' + name):
            mod_list.append(name)

total_list = mod_list + new_list
if total_list:
    mod_file = working_path + "/html/_mod.html"
    with open(mod_file, "w", encoding="utf-8") as w:
        if new_list:
            w.write('<h1>New files</h1>\n')
            for name in new_list:
                w.write(f'<a href="{name}">{name}</a><p/>\n')
        if mod_list:
            w.write('<h1>Modified files</h1>\n')
            for name in mod_list:
                w.write(f'<a href="{name}">{name}</a><p/>\n')
else:
    print("No files modified.")

# All working files have been created.  Move the files/directories out
# of the working directory and into their final places.
#
# We do this even if no files have apparently been modified because
# there could be other changes not detected, e.g. deleted files.
shutil.rmtree(root_path + '/html', ignore_errors=True)

# shutil.rmtree theoretically waits for the operation to complete, but
# Windows apparently claims to be complete while the delete is still
# in progress, e.g. if the directory is locked because it is the working
# directory of a cmd shell.  If the problem is only brief, then we want
# to quietly wait it out.  (For now, there is no quiet period, but I'll
# adjust it based on what I see.)  If the problem continues, print a
# message to let the user know to either unlock the directory manually
# or kill the script.
done = False
tries = 0
while not done:
    try:
        tries += 1
        os.rename(working_path + '/html', root_path + '/html')
        done = True
    except WindowsError as error:
        if tries == 1:
            warning('Having trouble removing the old html and renaming the new html...')
        time.sleep(0.1)
if tries > 1:
    warning(f'Completed in {tries} tries.')

if total_list:
    # open the default browser with the created HTML file
    if len(total_list) == 1:
        mod_file = root_path + '/html/' + total_list[0]
    else:
        mod_file = root_path + '/html/_mod.html'
    os.startfile(mod_file)

end()
