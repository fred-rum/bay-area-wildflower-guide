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

import os
import shutil
import sys
import filecmp
import re
import csv
import io
import yaml
from unidecode import unidecode # ? from https://pypi.org/project/Unidecode/
import datetime
import time

# The specified version (or later) of Python is required for at least the
# following reasons.
#
# Python 3 is required in general for good Unicode support and other features.
#
# Python 3.5 is required for subprocess.run()
#
# Python 3.7 is required for the dictionaries to be ordered by default.
# I don't generally rely on this, but the first dictionary entry in
# parks.yaml is treated specially, so that requires an ordered dictionary.
if sys.version_info < (3, 7):
    sys.exit('Python 3.7 or later is required.\n')

# My files
from args import *
from error import *
from files import *
from strip import *
from easy import *
from obs import *
from page import *
from photo import *
from glossary import *
from cache import *

strip_comments('bawg.css')
strip_comments('search.js')

strip_comments('gallery.css')
strip_comments('gallery.js')

if arg('-without_cache'):
    shutil.copy('src/no_sw.js', 'swi.js')
    shutil.copy('src/no_sw.js', 'sw.js')
else:
    strip_comments('swi.js')

year = datetime.datetime.today().year

# Read the mapping of iNaturalist observation locations to short park names.
park_map = {}
park_loc = {}

def read_parks(f):
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

read_data_file('parks.yaml', read_parks)

txt_files = get_file_set('txt', 'txt')

###############################################################################

if arg('-steps'):
    info('Step 1: Reading primary names from txt files')

# Read the txt for all txt files.  We could do more in this first pass,
# but I want to be able to measure the time of reading the files separately
# from any additional work.

def read_txt_files():
    for name in txt_files:
        page = Page(name, name_from_txt=True, src=name+'.txt')
        with open(f'{root_path}/txt/{name}.txt', 'r', encoding='utf-8') as r:
            page.txt = r.read()

read_txt_files()

# Perform a first pass on the txt pages to initialize common and
# scientific names.  This ensures that when we parse children (next),
# any name can be used and linked correctly.

def parse_names():
    for page in page_array:
        page.remove_comments()
        page.parse_names()
        page.parse_glossary()

parse_names()

# Now that we know the names of all the traits, we can initialize the
# list of properties that we support.
init_props()

def print_trees():
    tree_taxon = arg('-tree_taxon')
    if tree_taxon:
        page = find_page1(tree_taxon)
        if page:
            page.print_tree()
        else:
            error(f'-tree taxon "{tree_taxon}" not found.')
    else:
        exclude_set = set()
        for page in full_page_array:
            if not page.parent and not page.linn_parent:
                page.print_tree(exclude_set=exclude_set)
    sys.stdout.flush()

if arg('-tree') == '1':
    print_trees()

if arg('-steps'):
    info('Step 2: Parse child info')

# parse_children_and_attributes() can add new pages, so we make a copy
# of the list to iterate through.  parse_children_and_attributes()
# also checks for external photos and various other page attributes.
# If this info is within a child key, it is assigned to the child.
# Otherwise it is assigned to the parent.
for page in page_array[:]:
    page.parse_children_and_attributes()

if arg('-tree') == '2':
    print_trees()

if arg('-steps'):
    info('Step 3: Attach photos to pages')

# Record jpg names for associated pages.
# Create a blank page for all unassociated jpgs.
def assign_jpgs():
    for jpg in sorted(jpg_files):
        name,suffix = separate_name_and_suffix(jpg)
        if not name:
            error(f'No name for {jpg}')
        else:
            page = find_page1(name)
            if not page:
                page = Page(name, src=jpg+'.jpg')
            page.add_photo(jpg, suffix)

assign_jpgs()

if arg('-tree') == '3':
    print_trees()

def read_taxon_names(f):
    taxon_names = yaml.safe_load(f)
    create_taxon_pages(taxon_names)

def create_taxon_pages(d, prefix=''):
    for sci, com in d.items():
        if isinstance(com, dict):
            d = com
            prefix = sci + ' '
            create_taxon_pages(d, prefix)
        else:
            if sci == '':
                elab = prefix[:-1] # remove the trailing space
            else:
                elab = prefix + sci
            if com == 'n/a':
                com = None
            page = find_page2(com, elab)
            if not page:
                page = Page(com, elab, shadow=True, src='taxon_names.yaml')
            #info(f'{page.com} <-> {page.elab}')

if arg('-steps'):
    info('Step 4: Parse taxon_names.yaml')

read_data_file('taxon_names.yaml', read_taxon_names)

if arg('-tree') == '4':
    print_trees()

if arg('-steps'):
    info('Step 5: Update taxonomic links')

# Linnaean descendants links are automatically created whenever a page
# is assigned a child, but this isn't reliable during initial child
# assignment when not all of the scientific names are known yet.
# Therefore, once all the names are in, we make another pass through
# the pages to ensure that all Linnaean links are complete.
for page in page_array:
    page.link_linn_descendants()

if arg('-tree') == '5':
    print_trees()

if arg('-steps'):
    info('Step 6: Add explicit and implied ancestors')

for page in page_array[:]:
    page.assign_groups()

if arg('-tree') == '6':
    print_trees()

# Find any genus with multiple species.
# Check whether all of those species share an ancestor key page in common.
# If not, print a warning.
for page in page_array:
    page.record_genus()

if arg('-steps'):
    info('Step 7: Create taxonomic chains from observations.csv')

# Read the taxonomic chains from the observations file (exported from
# iNaturalist).  There is more data in there that we'll read later, but
# first we want to complete the Linnaean tree so that properties can be
# properly applied.
def read_obs_chains(f):
    def get_field(fieldname):
        if fieldname in row:
            return row[fieldname]
        else:
            return None

    csv_reader = csv.DictReader(f)

    for row in csv_reader:
        sci = get_field('scientific_name')
        taxon_id = get_field('taxon_id')

        # In the highly unusual case of no scientific name for an
        # observation, just throw it out.  And if there is a scientific
        # name, I'd expect that there should be a taxon_id as well.
        if not sci or not taxon_id: continue

        orig_sci = sci

        # Remove the special 'x' sign used by hybrids since I
        # can't (yet) support it cleanly.  Note that I *don't* use
        # the r'' string format here because I want the \N to be
        # parsed during string parsing, not during RE parsing.
        sci = re.sub('\N{MULTIPLICATION SIGN} ', r'X', sci)

        sci_words = sci.split(' ')
        if get_field('taxon_subspecies_name'):
            sci = ' '.join((sci_words[0], sci_words[1], 'ssp.', sci_words[2]))
        elif get_field('taxon_variety_name'):
            sci = ' '.join((sci_words[0], sci_words[1], 'var.', sci_words[2]))

        com = get_field('common_name')

        # The common name is forced to all lower case to match my
        # convention.
        if com:
            com = com.lower()

        found_lowest_level = False
        try:
            # Read the taxonomic chain from observations.csv and create
            # Linnaean links accordingly.
            for rank in Rank:
                group = get_field(f'taxon_{rank.name}_name')

                # ignore an empty group string
                if not group:
                    continue

                # The first non-empty group that is found usually tells us
                # the rank of the observed taxon.  Find or create a page
                # with the appropriate rank.
                if not found_lowest_level:
                    if ' ' in sci:
                        # If the scientific name has at least one space,
                        # then it is a species, subspecies, or variety that
                        # should have already been elaborated as necessary.
                        pass
                    elif group == orig_sci:
                        # If the first name in the taxonomic chain matches
                        # the observed taxon name, then it directly tells
                        # us the taxon rank.
                        sci = f'{rank.name} {sci}'
                    else:
                        # If the first name in the taxonomic chain doesn't
                        # match the observed taxon name, then the observed
                        # taxon must be an unrecognized rank.  Try to find
                        # a matching page of any rank.
                        pass

                    # Check whether a page already exists for the taxon.
                    # If find_page2() finds a match, it automatically sets the
                    # taxon_id for the page if it didn't have it already.
                    page = find_page2(com, sci, from_inat=True,
                                      taxon_id=taxon_id)

                    # if find_page2() didn't find a match, create a shadow
                    # page for the taxon.
                    if not page:
                        if group != orig_sci and ' ' not in sci:
                            # We have to create a page for a taxon of unknown
                            # rank.  On the assumption that the observation
                            # will get promoted to a higher-level taxon, we
                            # fudge it here by pretending it's the lowest rank.
                            sci = f'below {sci}'

                        page = Page(com, sci, shadow=True, from_inat=True,
                                    src='observations.csv')
                        page.set_taxon_id(taxon_id)

                    if group != orig_sci:
                        # This is the lowest-level group we found, but
                        # since the taxon name doesn't match, the observed
                        # taxon must be at a lower level that isn't included
                        # in the observations.csv ranks.
                        #
                        # Note: this test isn't mixed in with the above
                        # 'group == orig_sci' tests because we don't want
                        # to exclude species/subspecies/varieties here.
                        found_lowest_level = True

                if found_lowest_level:
                    # add_linn_parent() adds the page for the parent
                    # (if necessary) and the link from parent to child.
                    page = page.add_linn_parent(rank, group, from_inat=True)

                found_lowest_level = True
        except FatalError:
            warn(f'was creating taxonomic chain from {page.full()}')
            raise

read_data_file('observations.csv', read_obs_chains,
               msg='taxon hierarchy')

if arg('-tree') == '7':
    print_trees()

if arg('-steps'):
    info("Step 8: Assign ancestors to pages that don't have scientific names")

for page in page_array:
    if not page.rank and not page.linn_parent:
        page.resolve_lcca()
    elif page.is_top:
        page.propagate_is_top()

if arg('-tree') == '8':
    print_trees()

if arg('-steps'):
    info('Step 9: Assign default ancestor to floating trees')

default_ancestor = get_default_ancestor()
if default_ancestor:
    for page in full_page_array:
        if (not page.is_top and not page.linn_parent and
            (not page.rank or page.rank < default_ancestor.rank)):
            default_ancestor.link_linn_child(page)

if arg('-tree') == '9':
    print_trees()

if arg('-steps'):
    info('Step 10: Propagate properties')

# Assign properties to the appropriate ranks.
for page in page_array:
    page.propagate_props()

if arg('-tree') == '10':
    print_trees()

if arg('-steps'):
    info('Step 11: Apply create and link properties')

# Apply link-creation and related properties
# in order from the lowest ranked pages to the top.
for rank in Rank:
    for page in full_page_array:
        if page.rank is rank:
            page.apply_prop_link()

if arg('-tree') == '11':
    print_trees()

if arg('-steps'):
    info('Step 12: Read observation counts and common names from observations.csv')

sci_ignore = {}

def read_ignore_species(f):
    global sci_ignore
    sci_ignore = yaml.safe_load(f)

    for sci in sci_ignore:
        # Keep only the first character ('+' or '-') and ignore the comment.
        sci_ignore[sci] = sci_ignore[sci][0]

        if sci in isci_page:
            page = isci_page[sci]
        else:
            page = find_page1(sci)

        if page and not page.shadow:
            error(f'{sci} is ignored, but there is a real page for it: {page.full()}')

read_data_file('ignore_species.yaml', read_ignore_species)

# Read my observations file (exported from iNaturalist) and use it as follows
# for each observed taxon:
#   Associate common names with scientific names.  (Previously we didn't have
#     the properties in place to know what to do with common names.)
#   Get a count of observations (total and research grade).
#   Get an iNaturalist taxon ID.
def read_observation_data(f):
    def get_field(fieldname):
        if fieldname in row:
            return row[fieldname]
        else:
            return None

    set_any_observations()

    error_begin_section()

    csv_reader = csv.DictReader(f)

    if 'quality_grade' in csv_reader.fieldnames:
        set_rg_supported()

    for row in csv_reader:
        sci = get_field('scientific_name')
        taxon_id = get_field('taxon_id')

        # In the highly unusual case of no scientific name for an
        # observation, just throw it out.  And if there is a scientific
        # name, I'd expect that there should be a taxon_id as well.
        if not sci or not taxon_id: continue

        # Remove the special 'x' sign used by hybrids since I
        # can't (yet) support it cleanly.  Note that I *don't* use
        # the r'' string format here because I want the \N to be
        # parsed during string parsing, not during RE parsing.
        sci = re.sub('\N{MULTIPLICATION SIGN} ', r'X', sci)

        com = get_field('common_name')

        # The common name is forced to all lower case to match my
        # convention.
        if com:
            com = com.lower()

        rg = get_field('quality_grade')

        park = get_field('private_place_guess')
        if not park:
            park = get_field('place_guess')

        for x in park_map:
            if re.search(x, park):
                short_park = park_map[x]
                loc = park_loc[x]
                break
        else:
            error(park, prefix='Parks not found:')
            short_park = park
            loc = 'bay area'

        date = get_field('observed_on')
        month = int(date.split('-')[1], 10) - 1 # January = month 0

        # This call to find_page2() should always match a taxon_id
        # from the first pass through observations.csv.  However, that
        # first pass didn't yet have the property information to know
        # whether to add an alternative name from iNaturalist.  So we
        # supply the names again for that purpose.
        page = find_page2(com, sci, from_inat=True, taxon_id=taxon_id)

        # A Linnaean page should have been created during the first path
        # through observations.csv, so it'd be weird if we can't find it.
        assert page

        if page:
            taxon_id = get_field('taxon_id')
            if taxon_id:
                page.taxon_id = taxon_id
            else:
                error(f'no taxon_id for {page.full()}')

        if loc != 'bay area':
            # If the location is outside the bay area, properties may
            # allow us to count it.  If so, list the outside observation
            # by general location, rather than the specific park.
            short_park = loc

        # If we haven't matched the observation to a real page, advance
        # up the Linnaean hierarchy until we find a real page.  We'll
        # check later whether this promotion is allowed.
        orig_sci = sci
        orig_page = page
        while page.shadow:
            if sci in sci_ignore:
                if sci_ignore[sci] == '+':
                    # Update orig_page to match the new promoted page,
                    # thus pretending that there was no promotion.
                    orig_page = page.linn_parent
                else: # '-'
                    # The obesrvations should be entirely ignored.
                    # Stop promoting on the ignored page.
                    break
            page = page.linn_parent
            if not page:
                break
            sci = page.sci

        if not page or (sci in sci_ignore and sci_ignore[sci] == '-'):
            # the observation is not contained by *any* page, or
            # the observation'so taxon (or some taxon it was promoted through)
            # should be completely ignored.
            continue

        if (loc != 'bay area' and
            not page.rp_do('outside_obs')):
            continue

        if (rg == 'casual' and
            not page.rp_do('casual_obs')):
            continue

        if page != orig_page:
            # The page got promoted.

            if loc != 'bay area' and not page.rp_do('outside_obs_promotion'):
                continue

            if orig_page.rank_unknown:
                # If an observation has an unknown rank, then we *always*
                # promote it without complaint.
                pass
            elif (rg != 'research' and
                  orig_page.rank <= Rank.species and
                  page.rp_do('casual_obs_promotion')):
                # This property allows a non-research-grade observation to be
                # promoted without complaint.
                pass
            else:
                # If the observation's original page has real Linnaean
                # descendants, then we don't know what it is, but it could
                # be something we've documented, so it's always OK.  But
                # if it doesn't have real Linnaean descendants, and the
                # promoted page does, then it's definitely something we
                # haven't documented.
                if (not orig_page.has_real_linnaean_descendants() and
                    page.has_real_linnaean_descendants()):
                    orig_page.rp_check('obs_promotion_above_peers',
                                       f'{orig_page.full()} observation promoted to {page.full()}',
                                       shadow_bad=True)

                if page.taxon_unknown_completion():
                    page.rp_check('obs_promotion_without_x',
                                  f'{orig_page.full()} observation promoted to {page.full()}')

                if not page.rp_do('obs_promotion',
                                  f'{orig_page.full()} observation promoted to {page.full()}'):
                    continue

        page.obs_n += 1
        if rg == 'research':
            page.obs_rg += 1
        if short_park not in page.parks:
            page.parks[short_park] = 0
        page.parks[short_park] += 1
        page.month[month] += 1

    error_end_section()

read_data_file('observations.csv', read_observation_data,
               msg='observation data')

if arg('-tree') == '12':
    print_trees()

top_list = [x for x in page_array if not x.parent]

for page in full_page_array:
    page.apply_most_props()
    if not (page.sci or page.no_sci):
        error(page.name, prefix='No scientific name given for the following pages:')

if arg('-steps'):
    info('Step 13: Parse remaining text, including glossary terms')

# If we got this far and a page still doesn't have a name, give it one.
for page in page_array:
    page.infer_name()

parse_glossaries(top_list)

for page in page_array:
    page.sort_children()

for page in page_array:
    page.check_traits()

if arg('-tree') == '13':
    print_trees()

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

    is_top_of_genus = page.is_top_of(Rank.genus)
    if is_top_of_genus and page.genus_complete in (None, 'more'):
        return count_flowers(page)
    else:
        return 0

if arg('-steps'):
    info('Writing HTML')

for page in page_array:
    page.write_html()

if arg('-incomplete_keys'):
    # List the top 5 genus pages with an incomplete key,
    # as ordered by number of observations.
    # (If there are fewer than 5, then some random pages are listed as well.)
    page_list = page_array[:]
    page_list.sort(key=by_incomplete_obs, reverse=True)
    for page in page_list[:5]:
        info(page.full())


###############################################################################
# Process 'other' files

other_files = get_file_set('other', 'txt')
parse_other_txt_files(other_files)


###############################################################################
# Create pages.js
#
# We create it in root_path instead of working_path because we're just about
# done.  Since pages.js isn't compared to the previous version, the only
# disadvantage is if the script crashes just after creating pages.js, it may
# point to pages that don't exist.  Whatever.

def add_elab(elabs, elab):
    if elab and elab[0].isupper():
        # convert the hybrid symbol to a colon so that it is easy to recognize
        # and also easy to skip over during matching.
        elab = re.sub(' X', ' :', elab)
    if elab and elab != 'n/a' and elab not in elabs:
        elabs.append(unidecode(elab))

search_file = f'{root_path}/pages.js'
with open(search_file, 'w', encoding='utf-8') as w:
    w.write('var pages=[\n')

    # Sort in reverse order of observation count (most observations first).
    for page in sort_pages(page_array, with_depth=True):
        name = filename(page.name)
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
            if page.has_child_key:
                w.write(',x:"k"')
            else:
                w.write(',x:"f"')
        else:
            if page.photo_dict:
                w.write(',x:"o"')
            else:
                w.write(',x:"u"')
        w.write('},\n')

    write_glossary_search_terms(w)
    w.write('];\n')
    w.write('''
if (typeof main !== 'undefined') {
  main();
}
''')


###############################################################################
# Create photos.js

photos_file = f'{root_path}/photos.js'
with open(photos_file, 'w', encoding='utf-8') as w:
    w.write('var pages=[\n')

    # The sort order here is arbirtary as long as it is consistent.
    # We sort in the same order as pages.js for convenience of comparing them.
    for page in sort_pages(page_array, with_depth=True):
        # Each page that links to full-sized photos gets an entry.
        # Pages without photos are not included in the list.
        if (not page.photo_dict):
            continue

        # The entry consists of the page name followed by the photo URLs.
        #
        # The page name may include spaces, even though gallery.js will be
        #   comparing it to a value that doesn't use spaces.  See gallary.js
        #   for why the spaces in the page name are useful.
        #
        # The photo URLs are compressed to save space:
        #   The 'photos/' prefix and '.jpg' suffix is dropped.
        #   If the first photo's base name can be derived from the page name
        #     (e.g. by replacing ' ' with '-'), that part is dropped.
        #   If a subsequent photo's base name is the same as the previous
        #     photos, that part is also dropped.
        #   If only the suffix is emitted, the ',' separating it from the
        #     photo suffix is also dropped.
        #   If only the suffix is emitted and it is a simple decimal, it
        #     is emitted as an unquoted integer rather than a quoted string.
        #   What remains is often simply a list of photo suffixes,
        #     e.g. 1,3,7
        name = page.name
        w.write(f'["{name}",')
        photos = []
        recent_name = name
        for suffix in sorted(page.photo_dict):
            jpg = page.photo_dict[suffix]
            base,suffix1 = separate_name_and_suffix(jpg)
            if base == recent_name:
                suffix1 = suffix1[1:]
                if re.match(r'0|[1-9][0-9]*$', suffix1):
                    photos.append(suffix1)
                else:
                    photos.append(f'"{suffix1}"')
            else:
                recent_name = base
                photos.append(f'"{jpg}"')
        for file in page.figure_list:
            photos.append(file)
        photo_list = ','.join(photos)
        w.write(f'{photo_list}],\n')
    write_glossary_figures(w)
    w.write(f'["home","figures/bay-area.jpg"],\n')
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
        if not os.path.isfile(f'{root_path}/html/' + name):
            new_list.append(name)
        elif not filecmp.cmp(f'{root_path}/html/' + name,
                             f'{working_path}/html/' + name):
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
    info("No HTML files modified.")

# All working files have been created.  Move the files/directories out
# of the working directory and into their final places.
#
# We do this even if no files have apparently been modified because
# there could be other changes not detected, e.g. deleted files.
shutil.rmtree(f'{root_path}/html', ignore_errors=True)

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
        os.rename(f'{working_path}/html', f'{root_path}/html')
        done = True
    except WindowsError as error:
        if tries == 1:
            warn('Having trouble removing the old html and renaming the new html...')
        time.sleep(0.1)
if tries > 1:
    warn(f'Completed in {tries} tries.')

if total_list:
    # open the default browser with the created HTML file
    if len(total_list) == 1:
        mod_file = f'{root_path}/html/' + total_list[0]
    else:
        mod_file = f'{root_path}/html/_mod.html'

    # os.startfile in Windows requires an absolute path
    abs_mod_file = os.path.abspath(mod_file)
    os.startfile(abs_mod_file)


###############################################################################
# Update base64 cache and sw.js

def by_filename(name):
    slash_pos = name.find('/')
    return name[slash_pos+1:].casefold()

if not arg('-without_cache'):
    path_list = [
        # Start with the files most needed for interfacing with the worker.
        # Not 'sw.js' because it's not necessary and could be really bad.
        # Actually, order doesn't matter much for loading, but depending
        # on the browser implementation, it might make a difference when
        # deleting files.
        'swi.js',
        'bawg.css',
        'search.js',
        'pages.js',
        'gallery.html',
        'photos.js',
        'gallery.js',
        'gallery.css',
    ]
    for other in sorted(other_files):
        path_list.append(other + '.html')

    icon_set = get_file_set('icons', None)
    path_list += get_file_list('icons', icon_set, None)

    if os.access(f'{root_path}/manifest.webmanifest', os.R_OK):
        path_list.append('manifest.webmanifest')

    favicon_set = get_file_set('favicon', None)
    path_list += get_file_list('favicon', favicon_set, None)

    alpha_list = []

    html_set = set()
    for page in page_array:
        html_set.add(page.get_filename())
    alpha_list += get_file_list('html', html_set, 'html')

    glossary_set = set()
    for glossary in glossary_taxon_dict.values():
        glossary_set.add(glossary.get_filename())
    alpha_list += get_file_list('html', glossary_set, 'html')

    alpha_list += get_file_list('thumbs', valid_thumb_set, 'jpg')

    alpha_list += get_file_list('photos', jpg_files, 'jpg')

    figure_set = get_file_set('figures', 'svg')
    figure_set.discard('_figure template')
    alpha_list += get_file_list('figures', figure_set, 'svg')

    figure_set = get_file_set('figures', 'jpg')
    alpha_list += get_file_list('figures', figure_set, 'jpg')

    path_list += sorted(alpha_list, key=by_filename)

    update_cache(path_list)
    gen_url_cache()

error_end()
