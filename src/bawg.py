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

# My files
from args import *
from error import *
from files import *
from strip import *
from easy import *
from cnt import *
from toxic import * # must be before page
from page import *
from photo import *
from glossary import *
from step import *
from cache import *
from inat import *
from core import *
from obs import *


##############################################################################
# First we declare a bunch of functions that will do the work for us.
# Then, at the bottom of this script file, we call these functions and
# those in other modules.

###############################################################################
# Read primary names from txt files

def read_txt():
    txt_files = get_file_set('txt', 'txt')

    # We read the files without parsing to make performance easier to measure.
    for name in txt_files:
        filename = f'{name}.txt'
        page = Page(name, name_from_txt=True, src=filename)
        read_file(f'txt/{filename}', page.read_txt)

    for page in page_array:
        with Progress(f'removing comments from "{page.name}"'):
            page.remove_comments()

        # Perform a first pass on the txt pages to initialize common and
        # scientific names.  This ensures that when we parse children (next),
        # any name can be used and linked correctly.
        with Progress(f'parsing names in "{page.name}"'):
            page.parse_names()

        # There are no prerequesites to parsing glossary definitions in
        # the page, so we go ahead and do that now.
        with Progress(f'parsing glossary in "{page.name}"'):
            page.parse_glossary()

    # Now that we know the names of all the traits, we can initialize the
    # list of properties that we support.
    init_props()

###############################################################################
# Parse attributes, properties, and child info

def parse_decl():
    # This code can add new pages, so we make a copy
    # of the list to iterate through.
    for page in page_array[:]:
        with Progress(f'in {page.full()}'):
            page.parse_attributes_properties_and_child_info()

###############################################################################
# Attach photos to pages

def assign_jpgs():
    for jpg in sorted(jpg_photos):
        name,suffix = separate_name_and_suffix(jpg)
        if not name:
            error(f'No name for {jpg}')
        else:
            page = find_page1(name)
            if not page:
                # Create a blank page for any unassociated jpg.
                # (Further photos with different suffixes for the same name
                # will then be associated with this page.)
                page = Page(name, src=jpg+'.jpg')
            page.add_photo(jpg, suffix)

###############################################################################
# Parse taxon_names.yaml

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
                page = find_page2(None, elab)
            else:
                page = find_page2(com, elab)
            if not page:
                page = Page(com, elab, shadow=True, src='taxon_names.yaml')
            #info(f'{page.com} <-> {page.elab}')

###############################################################################

def debug_js():
    # To avoid confusion when using the unstripped source files,
    # delete the stripped versions.
    delete_file('gallery.html')

    delete_file('bawg.css')
    delete_file('search.js')

    delete_file('gallery.css')
    delete_file('gallery.js')

    delete_file('swi.js')

    # sw.js currently requires script modification,
    # so it is always generated (and therefore not deleted).

def strip_js():
    strip_comments('bawg.css')
    strip_comments('search.js')

    strip_comments('gallery.css')
    strip_comments('gallery.js')

    if arg('-without_cache'):
        shutil.copy('src/no_sw.js', 'swi.js')
        shutil.copy('src/no_sw.js', 'sw.js')
    else:
        strip_comments('swi.js')
        # sw.js is generated below

###############################################################################
# Create pages.js

def add_elab(elabs, elab):
    if elab and elab[0].isupper():
        # convert the hybrid symbol to a colon so that it is easy to recognize
        # and also easy to skip over during matching.
        elab = re.sub(' X', ' :', elab)
    if elab and elab != 'n/a' and elab not in elabs:
        elabs.append(unidecode(elab))

def write_pages_js(w):
    w.write('const pages=[\n')

    # Sort in reverse order of observation count (most observations first).
    for page in sort_pages(page_array, with_depth=True):
        name = filename(page.name)
        w.write(f'{{p:"{name}"')

        # List all common names that should find this page when searching.
        coms = []
        if page.com:
            coms.append(page.com)
        else:
            # The first entry should be the default common name.
            # If there is no default common name, use a blank string
            # (which never matches anything the user types).
            coms.append('')

        # Add alternative common names.
        if page.acom:
            coms.extend(page.acom)

        # Add named ancestors.
        for ancestor in page.membership_list:
            if (ancestor.rp_do('member_name_alias') and
                ancestor.shadow and
                ancestor.com and
                ancestor.com not in coms and
                page.membership_dict[ancestor]):
                coms.append(ancestor.com)

        # Save bandwidth for the common case of a page that is named
        # the same as its common name.
        # Similarly, don't list anything if there are no common names.
        if (len(coms) > 1 or
            (page.com and (page.com != page.name or not page.com.islower()))):
            coms_str = unidecode('","'.join(coms))
            w.write(f',c:["{coms_str}"]')

        # List all scientific names that should find this page when searching.
        elabs = []
        add_elab(elabs, page.elab)
        add_elab(elabs, page.elab_inaturalist)
        add_elab(elabs, page.elab_jepson)
        add_elab(elabs, page.elab_calflora)
        if page.elab_calphotos:
            for elab in page.elab_calphotos.split('|'):
                add_elab(elabs, elab)

        # Add named ancestors if the scientific name is not trivially derived.
        for ancestor in page.membership_list:
            if (ancestor.rp_do('member_name_alias') and
                ancestor.shadow and
                ancestor.elab and
                (not page.elab or not page.elab.startswith(ancestor.elab)) and
                ancestor.elab not in elabs):
                elabs.append(ancestor.elab)

        # Save bandwidth for the common case of a page that is named
        # the same as its scientific name.
        # Similarly, don't list anything if there are no scientific names.
        if elabs and not (len(elabs) == 1 and page.name == elabs[0]):
            elabs_str = unidecode('","'.join(elabs))
            w.write(f',s:["{elabs_str}"]')

        if page.subset_of_page:
            w.write(',x:"s"')
        elif page.child:
            if page.has_child_key:
                w.write(',x:"k"')
            else:
                w.write(',x:"f"')
        else:
            if page.photo_dict:
                w.write(',x:"o"')
            else:
                w.write(',x:"u"')

        jpg = page.get_jpg(None);
        if jpg:
            base,suffix = separate_name_and_suffix(jpg)
            if base == name:
                suffix = suffix[1:]
                if re.match(r'0|[1-9][0-9]*$', suffix):
                    w.write(f',j:{suffix}')
                else:
                    w.write(f',j:"{suffix}"')
            else:
                w.write(f',j:"{jpg}"')

        if page.trait_names:
            w.write(',z:"')
            for name in page.trait_names:
                w.write(get_zstr(name))
            w.write('"')

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

def write_photos_js(w):
    w.write('const pages=[\n')

    # The sort order here is arbirtary as long as it is consistent.
    # We sort in the same order as pages.js for convenience of comparing them.
    for page in sort_pages(page_array, with_count=False):
        # Each page that links to full-sized photos gets an entry.
        # Pages without photos are not included in the list.
        if (not page.photo_dict):
            continue

        # The entry consists of a page name followed by the photo URLs.
        #
        # The page name is a user visible name, so instead of taking the
        #   page.name (which must be unique), we take either the common
        #   or scientific name (which might not be unique).
        #
        # The photo URLs are compressed to save space:
        #   The 'photos/' prefix and '.jpg' suffix are dropped.
        #   If the first photo's base name can be derived from the page name,
        #     that part is dropped.
        #   If a subsequent photo's base name is the same as the previous
        #     photos, that part is also dropped.
        #   If only the suffix is emitted, the ',' separating it from the
        #     photo suffix is also dropped.
        #   If only the suffix is emitted and it is a simple decimal, it
        #     is emitted as an unquoted integer rather than a quoted string.
        #   What remains is often simply a list of photo suffixes,
        #     e.g. 1,3,7
        if page.com:
            name = unidecode(page.com)
        else:
            name = unidecode(page.elab)
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
    w.write(f'["bay area","figures/bay-area.jpg"],\n')
    w.write('];\n')

###############################################################################
# Compare the new html files with the prev files.
# Create an HTML file with links to all new files and all modified files.
# (Ignore deleted files.)

def find_html_diffs():
    file_list = (sorted(get_file_set('', 'html', with_path=True)) +
                 sorted(get_file_set('html', 'html', with_path=True)))
    new_list = []
    mod_list = []
    del_list = []
    for name in file_list:
        if name in ('_mod.html', 'gallery.html'):
            pass
        elif name in new_cache and name not in old_cache:
            new_list.append(name)
        elif name in mod_files:
            mod_list.append(name)
        elif name not in new_cache:
            del_list.append(name)
            os.remove(name)

    if new_list or mod_list or del_list:
        mod_file = root_path + "/_mod.html"
        with open(mod_file, "w", encoding="utf-8") as w:
            if new_list:
                w.write('<h1>New files</h1>\n')
                for name in new_list:
                    w.write(f'<a href="{name}">{name}</a><p/>\n')
            if mod_list:
                w.write('<h1>Modified files</h1>\n')
                for name in mod_list:
                    w.write(f'<a href="{name}">{name}</a><p/>\n')
            if del_list:
                w.write('<h1>Deleted files</h1>\n')
                for name in del_list:
                    w.write(f'{name}<p/>\n')

        # open the default browser with the created HTML file
        changed_list = mod_list + new_list
        if len(changed_list) == 1 and not del_list:
            mod_file = f'{root_path}/' + changed_list[0]
        else:
            mod_file = f'{root_path}/_mod.html'

        # os.startfile in Windows requires an absolute path
        abs_mod_file = os.path.abspath(mod_file)
        os.startfile(abs_mod_file)
    else:
        info("No HTML files modified.")

###############################################################################
# Update base64 cache and sw.js

def by_filename(name):
    slash_pos = name.find('/')
    return name[slash_pos+1:].casefold()

def write_sw_js():
    if arg('-debug_js'):
        script_path = 'src/'
    else:
        script_path = ''

    path_list = [
        # Start with the files most needed for interfacing with the worker.
        # Not 'sw.js' because it's not necessary and could be really bad.
        # Actually, order doesn't matter much for loading, but depending
        # on the browser implementation, it might make a difference when
        # deleting files.
        script_path + 'swi.js',
        script_path + 'bawg.css',
        script_path + 'search.js',
        'pages.js',
        script_path + 'gallery.html',
        'photos.js',
        script_path + 'gallery.js',
        script_path + 'gallery.css',
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

    alpha_list += get_file_list('thumbs', jpg_files, 'jpg')

    alpha_list += get_file_list('photos', jpg_photos, 'jpg')

    alpha_list += get_file_list('figures', svg_figures, 'svg')

    alpha_list += get_file_list('figures', jpg_figures, 'jpg')

    path_list += sorted(alpha_list, key=by_filename)

    update_cache(path_list)
    gen_url_cache()

###############################################################################
# List the top 5 genus pages with an incomplete key,
# as ordered by number of observations.
# (If there are fewer than 5, then some random pages are listed as well.)

def by_incomplete_obs(page):
    is_top_of_genus = page.is_top_of(Rank.genus)
    if is_top_of_genus and page.genus_complete in (None, 'more'):
        cnt = Cnt(None, None)
        cnt.count_matching_obs(page)
        return cnt.n
    else:
        return 0

def list_incomplete_keys():
    print ('Top 5 genuses with incomplete keys:')
    for page in sorted(page_array, key=by_incomplete_obs, reverse=True)[:5]:
        info(page.full())

##############################################################################
# Perform all the steps of BAWG creation in one (relatively) compact chunk
# of code.  The main advantage of doing it this way is that it makes it
# easier to wrap multiple steps in a 'with' statement to ensure that caches
# get cleaned up properly.

# We have a few caches that we use to avoid unnecessary work.
# We protect these in a big 'try / except / finally' block so
# that any cache updates are written back to disk even if there
# is an exception.
try:
    with Step('read_parks', 'Read parks.yaml'):
        read_file('data/parks.yaml', read_parks, skippable=True)

    with Step('read_txt', 'Read primary names from txt files'):
        read_txt()

    with Step('parse_decl', 'Parse attributes, properties, and child info'):
        parse_decl()

    with Step('attach_jpg', 'Attach photos to pages'):
        assign_jpgs()

    with Step('taxon_names', 'Parse taxon_names.yaml'):
        read_file('data/taxon_names.yaml', read_taxon_names, skippable=True)

    # Although Linnaean descendants links are automatically created whenever
    # a page is assigned a child, this isn't reliable during initial child
    # assignment when not all of the scientific names are known yet (since
    # additional names can be attached as the child declaration is parsed).
    # Therefore, once all the names are in, we make another pass through
    # the pages to ensure that all Linnaean links are complete.
    with Step('update_linn', 'Update Linnaean links'):
        for page in page_array:
            page.link_linn_descendants()

    with Step('update_member', 'Add explicit and implied ancestors'):
        for page in page_array[:]:
            page.assign_groups()

    with Step('read_core', 'Read DarwinCore archive'):
        read_core()

    with Step('obs_chains', 'Create taxonomic chains from observations.csv'):
        read_file('data/observations.csv', read_obs_chains,
                  skippable=True, msg='taxon hierarchy')

    with Step('infer_names', 'Infer name from filename'):
        # If we got this far and a page still doesn't have a name, give it one.
        for page in page_array:
            page.infer_name()

    with Step('read_api', 'Read cached iNaturalist API data'):
        read_inat_files()

    with Step('core_chains', 'Create taxonomic chains from DarwinCore archive'):
        parse_core_chains()

    with Step('api_chains', 'Create taxonomic chains from iNaturalist API data'):
        page_set = set()
        for page in page_array:
            # link_inat() traverses up through all ancestors, and we don't
            # care about shadow descendents, so we prefer to call link_inat()
            # only for real leaf pages.
            #
            # This may miss some ancestor pages if the leaf page doesn't have
            # a scientific name.  But that would be unusual, and it's a pain to fix.
            if (((page.sci and page.elab_inaturalist != 'n/a') or page.taxon_id)
                and not page.shadow and not page.child):
                page_set.add(page)
        link_inat(page_set)

    with Step('lcca', "Assign ancestors to pages that don't have scientific names"):
        for page in page_array:
            if not page.rank:
                # If a page doesn't fit into the Linnaean hierarchy, try to find a
                # place for it.
                # We do this even if a Linnaean ancestor is given since it may not
                # be the best Linnaean parent.
                # This also propagates is_top, so we don't have to do it again.
                page.resolve_lcca()
            if page.is_top and not page.parent and not page.linn_parent:
                page.propagate_is_top()

    with Step('def_anc', 'Assign default ancestor to floating trees'):
        default_ancestor = get_default_ancestor()
        if default_ancestor:
            for page in full_page_array:
                if (not page.is_top
                    and not page.linn_parent
                    and (not page.rank or page.rank < default_ancestor.rank)):
                    if default_ancestor:
                        default_ancestor.link_linn_child(page)
                    else:
                        warn(f'is_top not declared for page at top of hierarchy: {page.full()}')

    with Step('prop_prop', 'Propagate properties'):
        # Assign properties to the appropriate ranks.
        for page in page_array:
            page.propagate_props()

    with Step('prop_link', 'Apply create and link properties'):
        # Apply link-creation and related properties
        # in order from the lowest ranked pages to the top.
        for rank in Rank:
            for page in full_page_array:
                if page.rank is rank:
                    page.apply_prop_link()

    with Step('ignore', 'Read ignore_species.yaml'):
        read_file('data/ignore_species.yaml', read_ignore_species, skippable=True)

    with Step('obs_data', 'Read observation counts and common names from observations.csv'):
        read_file('data/observations.csv', read_observation_data,
                  skippable=True, msg='observation data')

    with Step('api_names', 'Apply names from iNaturalist API data'):
        apply_inat_names()

    top_list = [x for x in page_array if not x.parent]

    with Step('prop_apply', 'Apply remaining properties'):
        for page in full_page_array:
            page.apply_most_props()

    with Step('parse_txt', 'Parse remaining text, including glossary terms'):
        parse_glossaries(top_list)

        for page in page_array:
            page.sort_children()

        for page in page_array:
            page.check_traits()

    with Step('toxic', 'Read and apply toxicity data'):
        read_toxicity()
        for page in page_array:
            page.propagate_toxicity()

    # We nneded to look up scientific name aliases for the toxicity data.
    # But after that, we're done with the API, so we can discard all unused
    # entries from the API cache.
    finalize_inat_db()

    with Step('write_html', 'Write HTML files'):
        for page in page_array:
            page.parse_line_by_line()

        for page in page_array:
            page.parse2()

        for page in page_array:
            with Progress(f'write_html for {page.full()}'):
                page.write_html()

    if arg('-debug_js'):
        with Step('strip', 'Delete stripped JS since -debug_js is specified'):
            debug_js()
    else:
        with Step('strip', 'Strip comments from ungenerated JS and HTML'):
            strip_js()

        strip_comments('gallery.html')

    with Step('other', 'Process "other/*.txt" files'):
        other_files = get_file_set('other', 'txt')
        parse_other_txt_files(other_files)

    with Step('pages_js', 'Create pages.js'):
        search_file = f'{root_path}/pages.js'
        with open(search_file, 'w', encoding='utf-8') as w:
            write_traits_to_pages_js(w)
            convert_zint_to_zstr();
            write_pages_js(w)

    with Step('photos_js', 'Create photos.js'):
        photos_file = f'{root_path}/photos.js'
        with open(photos_file, 'w', encoding='utf-8') as w:
            write_photos_js(w)

    with Step('html_diffs', 'Find modified HTML files'):
        find_html_diffs()

    if not arg('-without_cache'):
        with Step('sw_js', 'Write url_data.json and sw.js'):
            write_sw_js()

except:
    # Something went wrong.  Keep any new cache entries, but also copy over
    # the old cache entries so that no info gets lost.
    for name in old_cache:
        if name not in new_cache:
            new_cache[name] = old_cache[name]

finally:
    # Whether we took an exception or finished the script successfully,
    # write out the updated caches.
    with Progress('Write API cache'):
        dump_inat_db()
    with Progress('Write file hash cache'):
        dump_hash_cache()

if arg('-incomplete_keys'):
    list_incomplete_keys()
