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

os.mkdir(root + '/html')

# key: page name
page_parent = {} # a set of names of the page's parent pages
page_child = {} # a set of names of the page's child pages
page_txt = {} # txt (string) (potentially with some parsing done to it)

# A set of color names that the page is linked from.
# (Initially this is just the flower colors,
# but container pages get added later.)
page_color = {}

page_com = {} # common name
page_sci = {} # scientific name
page_obs = {} # number of observations
page_obs_rg = {} # number of observations that are research grade
page_taxon_id = {} # iNaturalist taxon ID

sci_page = {} # scientific name -> page name

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

def get_page_from_jpg(jpg):
    return re.sub(r'[-0-9]+$', r'', jpg)

def get_com(page):
    if page in page_com:
        return page_com[page]
    else:
        return page

def get_elab(sci):
    matchobj = re.match(r'([^ ]+ [^ ]+) ([^ ]+)$', sci)
    if ' ' not in sci:
        # one word in the scientific name implies a genus.
        return '{genus} spp.'.format(genus=sci)
    elif matchobj:
        # three words in the scientific name implies a subspecies
        # (or variant, or whatever).  Default to "ssp."
        return '{species} ssp. {ssp}'.format(species=matchobj.group(1),
                                             ssp=matchobj.group(2))
    else:
        return sci

def get_full(page, lines=2):
    com = get_com(page)
    if page in page_sci:
        sci = page_sci[page]
        elab = get_elab(sci)
        if com == sci:
            return "<i>{elab}</i>".format(elab=elab)
        elif lines == 2:
            return "{com}<br/><i>{elab}</i>".format(com=com, elab=elab)
        else: # lines == 1
            return "{com} (<i>{elab}</i>)".format(com=com, elab=elab)
    else:
        return com

flower_jpg_list = {}
for jpg in sorted(jpg_list):
    matchobj = re.match(r'(.*[a-z])[-0-9]+$', jpg)
    if matchobj:
        flower = matchobj.group(1)
        if flower not in flower_jpg_list:
            flower_jpg_list[flower] = []
        flower_jpg_list[flower].append(jpg)
    else:
        print 'Unrecognized jpg file: {jpg}'.format(jpg=jpg)

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
        x = matchobj.group(1)
        child = matchobj.group(2)
        assign_child(page, child)
        if x == '+':
            return '{' + child + ':' + child + '.jpg} {' + child + '}'
        else:
            return '{' + child + '}'

    def repl_sci(matchobj):
        sci = matchobj.group(1)
        page_sci[page] = sci
        sci_page[sci] = page
        return ''

    def repl_com(matchobj):
        page_com[page] = matchobj.group(1)
        return ''

    s = re.sub(r'{(child:|\+)([^}]+)}', repl_child, s)
    s = re.sub(r'{sci:(.*)}\n', repl_sci, s)
    s = re.sub(r'{com:(.*)}\n', repl_com, s)
    page_txt[page] = s

def write_external_links(w, page):
    if page in page_sci:
        sci = page_sci[page]
        if ' ' in sci:
            elab = get_elab(sci)
        else:
            # A one-word genus should be sent as is, not as '[genus] spp.'
            elab = sci

        w.write('<p/>')
        w.write('<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup={elab}" target="_blank">CalFlora</a> &ndash;\n'.format(elab=elab));

        if ' ' in sci:
            # CalPhotos cannot be searched by genus only.
            w.write('<a href="https://calphotos.berkeley.edu/cgi/img_query?where-taxon={elab}" target="_blank">CalPhotos</a> &ndash;\n'.format(elab=elab));

        # Jepson uses "subsp." instead of "ssp.", but it also allows us to
        # search with that qualifier left out entirely.
        w.write('<a href="http://ucjeps.berkeley.edu/eflora/search_eflora.php?name={sci}" target="_blank">Jepson eFlora</a><p/>\n'.format(sci=sci));

def write_parents(w, page):
    w.write('<hr/>\n')
    w.write('Pages that link to this one:<p/>\n')
    w.write('<ul/>\n')

    if page in page_parent:
        for parent in sorted(page_parent[page]):
            w.write('<li><a href="{parent}.html">{full}</a></li>\n'.format(parent=parent, full=get_full(parent, lines=1)))

    if page in page_color:
        for primary in primary_color_list:
            for color in primary_color_list[primary]:
                if color in page_color[page]:
                    w.write('<li><a href="{primary}.html#{color}">{color} flowers</a></li>\n'.format(primary=primary, color=color))

    w.write('<li><a href="all.html">all flowers</a></li>\n')
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
    # (Presumably they're external links or they'd be in {...} format.)
    s = re.sub(r'<a href=', '<a target="_blank" href=', s)

    # Replace {default} with all the default fields.
    s = re.sub(r'{default}', '{jpgs}\n\n{obs}', s)

    # Replace {obs} with iNaturalist observation count.
    def repl_obs(matchobj):
        if page in page_obs:
            n = page_obs[page]
            rg = page_obs_rg[page]
            obs_str = '<a href="https://www.inaturalist.org/observations/chris_nelson?taxon_id={taxon_id}" target="_blank">Chris&rsquo;s observations</a>: '.format(taxon_id=page_taxon_id[page])
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

    def repl_list(matchobj):
        c = matchobj.group(1)
        c = re.sub(r'\n', r'</li>\n<li>', c)

        # If there's a sublist, it's <ul> and </ul> must be on their own lines,
        # in which case we remove the accidental surrounding <li>...</li>.
        c = re.sub(r'<li>(<(/?)ul>)</li>', r'\1', c)

        return '\n<ul>\n<li>{c}</li>\n</ul>\n'.format(c=c)

    s = re.sub(r'\n{-\n(.*?)\n-}\n', repl_list, s, flags=re.DOTALL)

    # Replace {jpgs} with all jpgs that exist for the flower.
    def repl_jpgs(matchobj):
        if page in flower_jpg_list:
            jpgs = ['{{{jpg}.jpg}}'.format(jpg=jpg) for jpg in flower_jpg_list[page]]
            return ' '.join(jpgs)
        else:
            return '{no photos.jpg}'

    s = re.sub(r'{jpgs}', repl_jpgs, s)

    # Look for any number of {photos} followed by all text up to the
    # first \n\n or \n+EOF.  Photos can be my own or CalPhotos.
    # The photos and text are grouped together and vertically centered.
    # The text is also put in a <span> for correct whitespacing.
    s = re.sub(r'((?:\{(?:jpgs|[^\}]+.jpg|https://calphotos.berkeley.edu/[^\}]+)\} *)+)(.*?)(?=\n(\n|\Z))', r'<div class="photo-box">\1<span>\2</span></div>', s, flags=re.DOTALL)

    # Replace a pair of newlines with a paragraph separator.
    # (Do this after making specific replacements based on paragraphs,
    # but before replacements that might create empty lines.)
    s = s.replace('\n\n', '\n<p/>\n')

    # Replace {*.jpg} with a thumbnail image and a link to the full-sized image.
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

        # If the "jpg" name is actually a flower name,
        # use the first jpg of that flower.
        if jpg not in jpg_list and jpg in flower_jpg_list:
            jpg = flower_jpg_list[jpg][0]

        thumb = '../thumbs/{jpg}.jpg'.format(jpg=jpg)

        if link_to_jpg:
            href = '../photos/{jpg}.jpg'.format(jpg=jpg)
        else:
            href = '{link}.html'.format(link=link)

        if jpg in jpg_list:
            if page in page_child:
                img_class = 'page-thumb'
            else:
                img_class = 'leaf-thumb'
            img = '<a href="{href}"><img src="{thumb}" width="200" height="200" class="{img_class}"></a>'.format(href=href, thumb=thumb, img_class=img_class)
        else:
            img = '<a href="{href}" class="missing"><div class="page-thumb-text"><span>{jpg}</span></div></a>'.format(href=href, jpg_height=jpg_height-22, jpg=jpg)

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

    # Rplace a {[common]:[scientific]} reference with a link to CalFlora.
    s = re.sub(r'{([^\}]+):([^\}]+)}',
               r'<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup=\2" target="_blank" class="external">\1<br/><i>\2</i></a>',
               s)

    # Any remaining {reference} should refer to another page.
    # Replace it with a link to one of my pages if I can,
    # or otherwise to CalFlora if it is a scientific species name,
    # or otherwise leave it unchanged.
    def repl_link(matchobj):
        link = matchobj.group(1)
        if link in page_list:
            return '<a href="{link}.html">{full}</a>'.format(link=link, full=get_full(link))
        elif link[0].isupper():
            # Starts with a capital letter: must be a scientific name.
            return '<a href="https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup={link}" target="_blank" class="external"><i>{link}</i></a>'.format(link=link)
        else:
            return link

    s = re.sub(r'{([^}]+)}', repl_link, s)

    with open(root + "/html/" + page + ".html", "w") as w:
        com = get_com(page)

        # If the page's common name is the same as its scientific name,
        # then the h1 header should be italicized and elaborated.
        if page in page_sci and page_sci[page] == com:
            h1 = '<i>{elab}</i>'.format(elab=get_elab(com))
        else:
            h1 = com

        write_header(w, com)
        w.write('<body>\n')
        w.write('<h1>{h1}</h1>\n'.format(h1=h1))

        if h1 == com and page in page_sci:
            # We printed the common name (not the italicized scientific name)
            # in the h1 header, and we have a scientific name.
            w.write('<b><i>{elab}</i></b><p/>\n'.format(elab=get_elab(page_sci[page])))

        w.write(s)
        write_external_links(w, page)
        write_parents(w, page)
        write_footer(w)

###############################################################################

# Read the txt files and record names and parent->child relationships.
for page in page_list:
    read_txt(page)

# Create txt for all unassociated jpgs.
for name in sorted(jpg_list):
    page = get_page_from_jpg(name)
    if page not in page_list:
        page_list.append(page)
        page_txt[page] = '{default}'

# Read my observations file (exported from iNaturalist) and use it as follows:
#   Associate common names with scientific names
#   Get a count of observations (total and research grade) of each flower.
#   Get an iNaturalist taxon ID for each flower.
with open(root + '/observations.csv', 'r') as f:
    csv_reader = csv.reader(f)
    header_row = csv_reader.next()

    com_idx = header_row.index('common_name')
    sci_idx = header_row.index('scientific_name')
    rg_idx = header_row.index('quality_grade')
    taxon_idx = header_row.index('taxon_id')

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

        if sci in sci_page:
            page = sci_page[sci]
        else:
            # We record observations even if we don't have a page for them
            # so that we can identify missing pages at the end.
            # If there is a page for the scientific name, use it.
            # Otherwise, prefer the common name if we have it.
            if sci in page_txt or not com:
                page = sci
            else:
                page = com
            page_sci[page] = sci
            sci_page[sci] = page

        if page not in page_obs:
            page_obs[page] = 0
            page_obs_rg[page] = 0
        page_obs[page] += 1
        if rg == 'research':
            page_obs_rg[page] += 1
        page_taxon_id[page] = taxon_id

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
unlisted_flowers = sorted([f for f in page_obs if f not in page_list])
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

    if page in flower_jpg_list:
        w.write('<a href="{page}.html"><img src="../photos/{jpg}.jpg" width="200" height="200" class="list-thumb"></a>{spacer}'.format(page=page, jpg=flower_jpg_list[page][0], spacer=horiz_spacer))

    w.write('<a href="{page}.html">{full}</a></div>\n'.format(page=page, full=get_full(page)))

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
    if page in page_obs and page_matches_color(page, color):
        count += page_obs[page]
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
        if page in page_child:
            w.write('<div class="box">\n')
            list_page(w, page, indent)
            list_matches(w, find_matches(page_child[page], color),
                         indent+1, color)
            w.write('</div>\n')
        else:
            list_page(w, page, indent)


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
    total_list = mod_list + new_list
    if len(total_list) == 1:
        os.startfile(root + '/html/' + total_list[0])
    else:
        os.startfile(mod_file)
else:
    print "No files modified."
