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
# primary - a top-level color.
# color - a color under a primary.
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

root = 'c:/Users/Chris/Documents/GitHub/bay-area-flowers'

# Keep a copy of the previous html files so that we can
# compare differences after creating the new html files.
shutil.rmtree(root + '/prev', ignore_errors=True)
os.rename(root + '/html', root + '/prev')
os.mkdir(root + '/html')


# key: page name
page_parent = {} # a set of names of the page's parent pages
page_child = {} # a set of names of the page's child pages
page_txt = {} # txt (string) (potentially with some parsing done to it)

# A set of color names that the page is linked from.
# (Initially this is just the flower colors,
# but container pages get added later.)
page_color = {}

# key: flower page name
flower_sci = {} # scientific name
flower_obs = {} # number of observations
flower_obs_rg = {} # number of observations that are research grade
flower_taxon_id = {} # iNaturalist taxon ID
# first jpg associated with the flower page (used for flower lists)
flower_first_jpg = {}

# Define a list of subcolors for each primary color.
# key: primary name
# value: list of color names
primary_color_list = {'purple': ['purple', 'purple fading to white',
                                 'pink', 'blue'],
                      'red': ['red', 'salmon'],
                      'white': ['white', 'cream'],
                      'yellow': ['yellow', 'orange'],
                      'other': ['other']}

# key: color
# value: page list
color_page_list = {}

# A few functions need a small horizontal spacer,
# so we define a common one here.
horiz_spacer = '<div style="min-width:10;"></div>'

# Read my observations file (exported iNaturalist) and use it as follows:
#   Associate common names with scientific names
#   Get a count of observations (total and research grade) of each flower.
#   Get an iNaturalist taxon ID for each flower.
with open(root + '/observations.csv', 'r') as f:
    csv_reader = csv.reader(f)
    header_row = csv_reader.next()

    sci_idx = header_row.index('scientific_name')
    com_idx = header_row.index('common_name')
    rg_idx = header_row.index('quality_grade')
    taxon_idx = header_row.index('taxon_id')

    for row in csv_reader:
        sci_name = row[sci_idx]
        com_name = row[com_idx].lower()
        if com_name:
            if sci_name:
                flower_sci[com_name] = sci_name

            if com_name not in flower_obs:
                flower_obs[com_name] = 0
                flower_obs_rg[com_name] = 0
            flower_obs[com_name] += 1
            if row[rg_idx] == 'research':
                flower_obs_rg[com_name] += 1

            flower_taxon_id[com_name] = row[taxon_idx]

# Read miscellaneous flower info from the YAML file.
with open(root + '/data.yaml') as f:
    yaml_data = yaml.safe_load(f)
for name in yaml_data:
    if 'color' in yaml_data[name]:
        page_color[name] = set(yaml_data[name]['color'].split(','))

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

# Check if check_page is an ancestor of cur_page (for loop checking).
def is_ancestor(cur_page, check_page):
    if cur_page == check_page:
        return True

    if cur_page in page_parent:
        for parent in page_parent[cur_page]:
            if is_ancestor(parent, check_page):
                return True

    return False

def assign_child(parent, child):
    if is_ancestor(parent, child):
        print "circular loop when creating link from {parent} to {child}".format(parent=parent, child=child)
    else:
        if child not in page_parent:
            page_parent[child] = set()
        page_parent[child].add(parent)

        if parent not in page_child:
            page_child[parent] = set()
        page_child[parent].add(child)

# Read txt files, but perform limited substitutions for now.
# More will be done once we have a complete set of parent->child relationships.
def read_txt(page):
    with open(root + "/txt/" + page + ".txt", "r") as r:
        s = r.read()

    # Replace a {child:[page]} link with just {[page]} and record the
    # parent->child relationship.
    # Define the re.sub replacement function inside the calling function
    # so that it has access to the calling context.
    def repl_child(matchobj):
        child = matchobj.group(1)
        assign_child(page, child)
        return '{' + child + '}'

    s = re.sub(r'{child:([^}]+)}', repl_child, s)
    page_txt[page] = s

def write_external_links(w, page):
    if page in flower_sci:
        sci = flower_sci[page]
        w.write('<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup={sci}">CalFlora</a> &ndash;\n'.format(sci=sci));
        w.write('<a href="https://calphotos.berkeley.edu/cgi/img_query?where-taxon={sci}">CalPhotos</a> &ndash;\n'.format(sci=sci));
        w.write('<a href="http://ucjeps.berkeley.edu/eflora/search_eflora.php?name={sci}">Jepson eFlora</a><p/>\n'.format(sci=sci));

def write_parents(w, page):
    w.write('<hr/>\n')
    w.write('Pages that link to this one:<p/>\n')
    w.write('<ul/>\n')

    if page in page_parent:
        for parent in sorted(page_parent[page]):
            w.write('<li><a href="{parent}.html">{parent}</a></li>\n'.format(parent=parent))

    if page in page_color:
        for primary in primary_color_list:
            for color in primary_color_list[primary]:
                if color in page_color[page]:
                    w.write('<li><a href="{primary}.html#{color}">{ucolor} flowers</a></li>\n'.format(primary=primary, color=color, ucolor=color.capitalize()))

    w.write('<li><a href="all.html">All flowers</a></li>\n')
    w.write('</ul>\n')
                    

def write_footer(w):
    w.write('''
<hr/>
<a href="../index.html">BAFG</a> <span style="color:gray">Copyright 2019 Chris Nelson</span>
</body>
''')

###############################################################################
# The giant 'parse' function, which turns txt into html
# and writes the resulting file.

def parse(page, s):
    # Replace {default} with all the default fields.
    s = re.sub(r'{default}', '{sci}\n{jpgs}\n\n{obs}', s)

    # Replace {sci} with the flower's scientific name.
    def repl_sci(matchobj):
        if page in flower_sci:
            return '<b><i>{sci}</i></b><p/>'.format(sci=flower_sci[page])
        else:
            return '<b><i><span style="color:red">Scientific name not found.</span></i></b><p/>'

    s = re.sub(r'{sci}', repl_sci, s)

    # Replace {obs} with iNaturalist observation count.
    def repl_obs(matchobj):
        if page in flower_obs:
            n = flower_obs[page]
            rg = flower_obs_rg[page]
            obs_str = '<a href="https://www.inaturalist.org/observations/chris_nelson?taxon_id={taxon_id}">Chris&rsquo;s observations</a>: '.format(taxon_id=flower_taxon_id[page])
            if rg == 0:
                obs_str += '{n} (none research grade)'.format(n=n)
            elif rg == n:
                if n == 1:
                    obs_str += '1 (research grade)'
                else:
                    obs_str += '{n} (all research grade)'.format(n=n)
            else:
                obs_str += '{n} ({rg} research grade)'.format(n=n, rg=rg)
        else:
            obs_str = 'Chris&rsquo;s observations: none'

        return obs_str + '<p/>'

    s = re.sub(r'{obs}', repl_obs, s)

    # Replace {jpgs} with all jpgs that exist for the flower.
    def repl_jpgs(matchobj):
        jpg_sublist = []
        ext_pos = len(page)
        for jpg in sorted(jpg_list):
            if jpg.startswith(page) and re.match(r'[-0-9]+$', jpg[ext_pos:]):
                jpg_sublist.append('{{{jpg}.jpg}}'.format(jpg=jpg))
        if jpg_sublist:
            return ' '.join(jpg_sublist)
        else:
            return '{no photos.jpg}'

    s = re.sub(r'{jpgs}', repl_jpgs, s)

    # Look for any number of {photos} followed by all text up to the
    # first \n\n or \n+EOF.  Photos can be my own or CalPhotos.
    # The photos and text are grouped together and vertically centered.
    # The text is also put in a <span> for correct whitespacing.
    s = re.sub(r'((?:\{(?:jpgs|[^\}]+.jpg|https://calphotos.berkeley.edu/[^\}]+)\} *)+)(((?!\n\n).)*)(?=\n(\n|\Z))', r'<div style="display:flex;align-items:center;">\1<span>\2</span></div>', s, flags=re.DOTALL)

    # Replace a pair of newlines with a paragraph separator.
    # (Do this after making specific replacements based on paragraphs,
    # but before replacements that might create empty lines.)
    s = s.replace('\n\n', '\n<p/>\n')

    # Replace {*.jpg} with a 200px image and a link to the full-sized image.
    def repl_jpg(matchobj):
        jpg = matchobj.group(1)
        filename = "../photos/{jpg}.jpg".format(jpg=jpg)
        if jpg in jpg_list:
            img = '<a href="{filename}"><img src="{filename}" height="{jpg_height}"></a>'.format(filename=filename, jpg_height=jpg_height)
            if page not in flower_first_jpg:
                flower_first_jpg[page] = jpg
        else:
            img = '<a href="{filename}" style="color:red;"><div style="display:flex;border:1px solid black;padding:10;height:{jpg_height};min-width:{jpg_height};align-items:center;justify-content:center"><span style="color:red;">{jpg}</span></div></a>'.format(filename=filename, jpg_height=jpg_height-22, jpg=jpg)

        return img + horiz_spacer

    s = re.sub(r'{([^}]+).jpg}', repl_jpg, s)

    # Replace a {CalPhotos:text} reference with a 200px box with
    # "CalPhotos: text" in it.
    # The entire box is a link to CalPhotos.
    # The ":text" part is optional.
    def repl_calphotos(matchobj):
        href = matchobj.group(1)
        pos = href.find(':') # find the colon in "http:"
        pos = href.find(':', pos+1) # find the next colon, if any
        if pos > 0:
            text = ': ' + href[pos+1:]
            href = href[:pos]
        else:
            text = ''

        img = '<a href="{href}" style="text-decoration:none"><div style="display:flex;border:1px solid black;padding:10;height:178;min-width:178;align-items:center;justify-content:center"><span><span style="text-decoration:underline;">CalPhotos</span>{text}</span></div></a>'.format(href=href, text=text)

        return img + horiz_spacer

    s = re.sub(r'\{(https://calphotos.berkeley.edu/[^\}]+)\}', repl_calphotos, s)

    # Any remaining {reference} should refer to another page.
    # Replace it with a link, colored depending on whether the link is valid.
    def repl_link(matchobj):
        link = matchobj.group(1)
        if link in page_list:
            link_style = ''
        else:
            link_style = ' style="color:red;"'
        return '<a href="{link}.html"{link_style}>{link}</a>'.format(link=link, link_style=link_style)

    s = re.sub(r'{([^}]+)}', repl_link, s)

    with open(root + "/html/" + page + ".html", "w") as w:
        w.write('<head><title>{page}</title></head>\n'.format(page=page))
        w.write('<body>\n')
        w.write('<h1>{page}</h1>'.format(page=page))
        w.write(s)
        write_external_links(w, page)
        write_parents(w, page)
        write_footer(w)

###############################################################################

# Read the txt files and record parent->child relationships.
for page in page_list:
    read_txt(page)

# Create txt for all unassociated jpgs.
for name in sorted(jpg_list):
    page = re.sub(r'[-0-9]+$', r'', name)
    if page not in page_list:
        page_list.append(page)
        page_txt[page] = '{default}'

# Get a list of pages without parents (top-level pages).
top_list = [x for x in page_list if x not in page_parent]

# Find all flowers that match the specified color.
# Also find all pages that include *multiple* child pages that match.
# If a parent includes multiple matching child pages, those child pages are
# listed only under the parent and not individually.
# If a parent includes only one matching child page, that child page is
# listed individually, and the parent is not listed.
#
# If color == None, every page matches.
def find_matches(page_subset, color):
    match_set = set()
    for page in page_subset:
        if page in page_list:
            if page in page_child:
                child_subset = find_matches(page_child[page], color)
                if len(child_subset) == 1:
                    match_set.update(child_subset)
                elif len(child_subset) > 1:
                    match_set.add(page)
                    # Record this container page's color.
                    if page not in page_color:
                        page_color[page] = set()
                    page_color[page].add(color)
            elif (color == None or
                  (page in page_color and color in page_color[page]) or
                  (page not in page_color and color == 'other')):
                match_set.add(page)
    return match_set

for primary in primary_color_list:
    for color in primary_color_list[primary]:
        color_page_list[color] = sorted(find_matches(top_list, color))

# Turn txt into html for all normal and default pages.
jpg_height = 200
for page in page_list:
    parse(page, page_txt[page])

# Create a txt listing all flowers without pages, then parse it into html.
jpg_height = 50
unlisted_flowers = sorted([f for f in flower_obs if f not in page_list])
s = '<br/>\n'.join(unlisted_flowers) + '<p/>\n'
parse("other observations", s)

###############################################################################
# The remaining code is for creating useful lists of pages:
# all pages, and pages sorted by flower color.

# List a single page, indented by some amount if it is under a parent.
def list_page(w, page, indent):
    w.write('<div style="display:flex;align-items:center;">')
    if indent:
        w.write('<div style="min-width:{indent};"></div>'.format(indent=indent*80))
    w.write('<a href="{page}.html">'.format(page=page))
    if page in flower_first_jpg:
        w.write('<img src="../photos/{jpg}.jpg" height="100">'.format(jpg=flower_first_jpg[page]))
    else:
        w.write('<div style="display:flex;border:1px solid black;height=98;min-width:98"></div>')
    if page in flower_sci:
        name_str = "{page} (<i>{sci}</i>)".format(page=page, sci=flower_sci[page])
    else:
        name_str = page
    w.write('</a>{spacer}<a href="{page}.html">{name_str}</a></div><p></p>\n'.format(spacer=horiz_spacer, page=page, name_str=name_str))

def list_matches(w, match_set, indent, color):
    for name in sorted(match_set):
        list_page(w, name, indent)

        if name in page_child:
            list_matches(w, find_matches(page_child[name], color),
                         indent+1, color)

for primary in primary_color_list:
    with open(root + "/html/{primary}.html".format(primary=primary), "w") as w:
        w.write('<head><title>{uprimary} Flowers</title></head>\n'.format(uprimary=primary.capitalize()))
        w.write('<body>\n')
        for color in primary_color_list[primary]:
            if color_page_list[color]:
                w.write('<h1 id="{color}">{ucolor} flowers</h1>\n'.format(color=color, ucolor=color.capitalize()))
                list_matches(w, color_page_list[color], 0, color)
        write_footer(w)

with open(root + "/html/all.html", "w") as w:
    w.write('<head><title>All Flowers</title></head>\n')
    w.write('<body>\n')
    w.write('<h1>All flowers</h1>\n')
    list_matches(w, top_list, 0, None)
    write_footer(w)

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
    os.startfile(mod_file)
else:
    print "No files modified."

# TODO:
# sort lists by number of observations
