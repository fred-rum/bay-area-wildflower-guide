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
try:
    shutil.rmtree(root + '/prev', ignore_errors=True)
except Exception as error:
    print type(error)
    print error
    raise
try:
    os.rename(root + '/html', root + '/prev')
except Exception as error:
    print type(error)
    print error
    raise
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
primary_color_list = {'purple': ['purple', 'pink', 'blue'],
                      'red': ['red', 'salmon'],
                      'white': ['white', 'cream'],
                      'yellow': ['yellow', 'orange'],
                      'other': ['other']}

# key: color
# value: page list
color_page_list = {}

# A few functions need a small horizontal spacer,
# so we define a common one here.
horiz_spacer = '<div class="horiz-space"></div>'

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
        taxon_id = row[taxon_idx]

        # Record observation data under both the common name and
        # the scientific name, so I can use either one for page names
        # and photo keywords.
        #
        # The common name is forced to all lower case to match my convention.
        # The scientific name is left in its standard case.

        if com_name:
            if sci_name:
                flower_sci[com_name] = sci_name

            if com_name not in flower_obs:
                flower_obs[com_name] = 0
                flower_obs_rg[com_name] = 0
            flower_obs[com_name] += 1
            if row[rg_idx] == 'research':
                flower_obs_rg[com_name] += 1

            flower_taxon_id[com_name] = taxon_id

        if sci_name and ' ' in sci_name: # at least to species level
            flower_sci[sci_name] = sci_name

            if sci_name not in flower_obs:
                flower_obs[sci_name] = 0
                flower_obs_rg[sci_name] = 0
            flower_obs[sci_name] += 1
            if row[rg_idx] == 'research':
                flower_obs_rg[sci_name] += 1

            flower_taxon_id[sci_name] = taxon_id

# Read miscellaneous flower info from the YAML file.
with open(root + '/color.yaml') as f:
    yaml_data = yaml.safe_load(f)
for name in yaml_data:
    page_color[name] = set(yaml_data[name].split(','))

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
        w.write('<p/>')
        w.write('<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup={sci}" target="_blank">CalFlora</a> &ndash;\n'.format(sci=sci));
        w.write('<a href="https://calphotos.berkeley.edu/cgi/img_query?where-taxon={sci}" target="_blank">CalPhotos</a> &ndash;\n'.format(sci=sci));
        w.write('<a href="http://ucjeps.berkeley.edu/eflora/search_eflora.php?name={sci}" target="_blank">Jepson eFlora</a><p/>\n'.format(sci=sci));

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

def write_header(w, title):
    w.write('''<!-- Copyright 2019 Chris Nelson - All rights reserved. -->
<html lang="en">
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width">
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
<link rel="stylesheet" href="../bafg.css">
</head>\n'''.format(title=title))

def write_footer(w):
    w.write('''
<hr/>
<a href="../index.html">BAFG</a> <span class="copyright">&ndash; Copyright 2019 Chris Nelson</span>
</body>
''')

###############################################################################
# The giant 'parse' function, which turns txt into html
# and writes the resulting file.

def parse(page, s):
    # Replace HTTP links in the text with ones that open a new tab.
    s = re.sub(r'<a href=', '<a target="_blank" href=', s)

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
            obs_str = '<a href="https://www.inaturalist.org/observations/chris_nelson?taxon_id={taxon_id}" target="_blank">Chris&rsquo;s observations</a>: '.format(taxon_id=flower_taxon_id[page])
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
    s = re.sub(r'((?:\{(?:jpgs|[^\}]+.jpg|https://calphotos.berkeley.edu/[^\}]+)\} *)+)(((?!\n\n).)*)(?=\n(\n|\Z))', r'<div class="photo-box">\1<span>\2</span></div>', s, flags=re.DOTALL)

    # Replace a pair of newlines with a paragraph separator.
    # (Do this after making specific replacements based on paragraphs,
    # but before replacements that might create empty lines.)
    s = s.replace('\n\n', '\n<p/>\n')

    # Replace {*.jpg} with a thumbnail image and a link to the full-sized image.
    def repl_jpg(matchobj):
        jpg = matchobj.group(1)
        photofile = "../photos/{jpg}.jpg".format(jpg=jpg)
        thumbfile = "../thumbs/{jpg}.jpg".format(jpg=jpg)
        if jpg in jpg_list:
            img = '<a href="{photofile}"><img src="{thumbfile}" width="200" height="200" class="page-thumb"></a>'.format(photofile=photofile, thumbfile=thumbfile)
            if page not in flower_first_jpg:
                flower_first_jpg[page] = jpg
        else:
            img = '<a href="{photofile}" class="missing"><div class="page-thumb-text"><span>{jpg}</span></div></a>'.format(photofile=photofile, jpg_height=jpg_height-22, jpg=jpg)

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
            text = '<br/>' + href[pos+1:]
            href = href[:pos]
        else:
            text = ''

        img = '<a href="{href}" target="_blank" class="enclosed"><div class="page-thumb-text"><span><span style="text-decoration:underline;">CalPhotos</span>{text}</span></div></a>'.format(href=href, text=text)

        return img + horiz_spacer

    s = re.sub(r'\{(https://calphotos.berkeley.edu/[^\}]+)\}', repl_calphotos, s)

    # Any remaining {reference} should refer to another page.
    # Replace it with a link to one of my pages if I can,
    # or otherwise to CalFlora if it is a scientific species name,
    # or otherwise leave it unchanged.
    def repl_link(matchobj):
        link = matchobj.group(1)
        if link in page_list:
            return '<a href="{link}.html">{link}</a>'.format(link=link)
        elif re.match(r'[A-Z][^\s]* [a-z][^\s]*$', link):
            return '<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup={link}" target="_blank" class="external">{link}</a>'.format(link=link)
        else:
            return link

    s = re.sub(r'{([^}]+)}', repl_link, s)

    with open(root + "/html/" + page + ".html", "w") as w:
        write_header(w, page)
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

def page_matches_color(page, color):
    return (color == None or
            (page in page_color and color in page_color[page]) or
            (page not in page_color and color == 'other'))

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
            elif page_matches_color(page, color):
                match_set.add(page)
    return match_set

# We don't need color_page_list yet, but we go through the creation process
# now in order to populate page_color for all container pages.
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
    if indent:
        indent_class = ' indent{indent}'.format(indent=indent)
    else:
        indent_class = ''
    w.write('<div class="photo-box {indent_class}">'.format(indent_class=indent_class))
    w.write('<a href="{page}.html">'.format(page=page))
    if page in flower_first_jpg:
        w.write('<img src="../photos/{jpg}.jpg" width="200" height="200" class="list-thumb">'.format(jpg=flower_first_jpg[page]))
    else:
        w.write('<div class="list-thumb-missing"></div>')
    if page in flower_sci:
        name_str = "{page}<br/><i>{sci}</i>".format(page=page, sci=flower_sci[page])
    else:
        name_str = page
    w.write('</a>{spacer}<a href="{page}.html">{name_str}</a></div><p></p>\n'.format(spacer=horiz_spacer, page=page, name_str=name_str))

# For containers, sum the observation counts of all children,
# *but* if a flower is found via multiple paths, count it only once.
def count_matching_obs(page, color, match_flowers):
    if page in match_flowers: return 0

    count = 0

    # If a container page contains exactly one descendant with a matching
    # color, the container isn't listed on the color page, and the color
    # isn't listed in page_color for the page.  Therefore, we follow all
    # child links blindly and only compare the color when we reach a flower
    # with an observation count.
    if page in flower_obs and page_matches_color(page, color):
        count += flower_obs[page]
        match_flowers.add(page)

    if page in page_child:
        for child in page_child[page]:
            count += count_matching_obs(child, color, match_flowers)

    return count

def list_matches(w, match_set, indent, color):
    # Sort by observation count.
    def count_flowers(page):
        return count_matching_obs(page, color, set())

    # Sort in reverse order of observation count.
    # We initialize the sort with match_set sorted alphabetically.
    # This order is retained for subsets with equal observation counts.
    for page in sorted(sorted(match_set), key=count_flowers, reverse=True):
        list_page(w, page, indent)

        if page in page_child:
            list_matches(w, find_matches(page_child[page], color),
                         indent+1, color)

for primary in primary_color_list:
    with open(root + "/html/{primary}.html".format(primary=primary), "w") as w:
        write_header(w, primary.capitalize())
        w.write('<body>\n')
        for color in primary_color_list[primary]:
            if color_page_list[color]:
                w.write('<h1 id="{color}">{ucolor} flowers</h1>\n'.format(color=color, ucolor=color.capitalize()))
                list_matches(w, color_page_list[color], 0, color)
        write_footer(w)

with open(root + "/html/all.html", "w") as w:
    write_header(w, 'All Flowers')
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
# remove photos from containers in page lists
# it would be nice to attach colors to individual jpgs of a flower,
#   e.g. for baby blue eyes (N. menziesii).
#
# An easy method to search would be nice.
#   I.e. a search bar on the home page (or every page) would be easier than
#   opening all.html, hitting the hamburger, and using find in page.
# Responsive image and text sizes would also be nice.
