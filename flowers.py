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

# key: flower page name
flower_sci = {} # scientific name
flower_obs = {} # number of observations
flower_obs_rg = {} # number of observations that are research grade
flower_taxon_id = {} # iNaturalist taxon ID
flower_color = {} # a set of color names
# first jpg associated with the flower page (used for flower lists)
flower_primary_jpg = {}

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
        flower_color[name] = set(yaml_data[name]['color'].split(','))

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
        print "circular loop when creating link from %s to %s" % (parent, child)
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

def emit_footer(w):
    w.write('''
&mdash;<br/>
<a href="index.html">BAFG</a> <span style="color:gray">Copyright 2019 Chris Nelson</span>
</body>
''')

horiz_spacer = '<div style="min-width:10;"></div>'

def parse(page, s):
    # Replace {default} with all the default fields.
    s = re.sub(r'{default}', '{sci}\n{jpgs}\n\n{obs}', s)

    # Replace {sci} with the flower's scientific name.
    def repl_sci(matchobj):
        if page in flower_sci:
            return '<b><i>%s</i></b><p/>' % flower_sci[page]
        else:
            return '<b><i><span style="color:red">Scientific name not found.</span></i></b><p/>'

    s = re.sub(r'{sci}', repl_sci, s)

    # Replace {obs} with iNaturalist observation count.
    def repl_obs(matchobj):
        if page in flower_obs:
            n = flower_obs[page]
            rc = flower_obs_rg[page]
            obs_str = '<a href="https://www.inaturalist.org/observations/chris_nelson?taxon_id=%s">Chris&rsquo;s observations</a>: ' % flower_taxon_id[page]
            if rc == 0:
                obs_str += '%d (none research grade)' % n
            elif rc == n:
                if n == 1:
                    obs_str += '1 (research grade)'
                else:
                    obs_str += '%d (all research grade)' % n
            else:
                obs_str += '%d (%d research grade)' % (n, rc)
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
                jpg_sublist.append('{%s.jpg}' % jpg)
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
        filename = "../photos/%s.jpg" % jpg
        if jpg in jpg_list:
            img = '<a href="%s"><img src="%s" height="%d"></a>' % (filename, filename, jpg_height)
            if page not in flower_primary_jpg:
                flower_primary_jpg[page] = jpg
        else:
            img = '<a href="%s" style="color:red;"><div style="display:flex;border:1px solid black;padding:10;height:%d;min-width:%d;align-items:center;justify-content:center"><span style="color:red;">%s</span></div></a>' % (filename, jpg_height-22, jpg_height-22, jpg)

        return img + horiz_spacer

    s = re.sub(r'{([^}]+).jpg}', repl_jpg, s)

    # Replace a {CalPhotos:text} reference with a 200px box with
    # "CalPhotos: text" in it.
    # The entire box is a link to CalPhotos.
    # The ":text" part is optional.
    def repl_calphotos(matchobj):
        target = matchobj.group(1)
        pos = target.find(':') # find the colon in "http:"
        pos = target.find(':', pos+1) # find the next colon, if any
        if pos > 0:
            text = ': ' + target[pos+1:]
            target = target[:pos]
        else:
            text = ''

        img = '<a href="%s" style="text-decoration:none"><div style="display:flex;border:1px solid black;padding:10;height:178;min-width:178;align-items:center;justify-content:center"><span><span style="text-decoration:underline;">CalPhotos</span>%s</span></div></a>' % (target, text)

        return img + horiz_spacer

    s = re.sub(r'\{(https://calphotos.berkeley.edu/[^\}]+)\}', repl_calphotos, s)

    # Any remaining {reference} should refer to another flower page.
    # Replace it with a link, colored depending on whether the link is valid.
    def repl_link(matchobj):
        link = matchobj.group(1)
        if link in page_list:
            link_style = ''
        else:
            link_style = ' style="color:red;"'
        return '<a href="%s.html"%s>%s</a>' % (link, link_style, link)

    s = re.sub(r'{([^}]+)}', repl_link, s)

    with open(root + "/html/" + page + ".html", "w") as w:
        w.write('<head><title>%s</title></head>\n' % page)
        w.write('<body>\n')
        w.write('<h1>%s</h1>' % page)
        w.write(s)

        # TODO: list all containers of the flower, including the top level.

        emit_footer(w)

jpg_height = 200
for page in page_list:
    read_txt(page)

for name in sorted(jpg_list):
    page = re.sub(r'[-0-9]+$', r'', name)
    if page not in page_list:
        page_list.append(page)
        page_txt[page] = '{default}'

for page in page_list:
    parse(page, page_txt[page])

f = cStringIO.StringIO()
for name in sorted(flower_obs):
    if name not in page_list:
        f.write("%s<br/>\n" % name)
s = f.getvalue()
f.close()
jpg_height = 50
parse("other observations", s)

def list_flower(w, name, indent):
    w.write('<div style="display:flex;align-items:center;">')
    if indent:
        w.write('<div style="min-width:%d;"></div>' % (indent * 80))
    w.write('<a href="%s.html">' % name)
    if name in flower_primary_jpg:
        w.write('<img src="../photos/%s.jpg" height="100">' % flower_primary_jpg[name])
    else:
        w.write('<div style="display:flex;border:1px solid black;height=98;min-width:98"></div>')
    if name in flower_sci:
        name_str = "%s (<i>%s</i>)" % (name, flower_sci[name])
    else:
        name_str = name
    w.write('</a>%s<a href="%s.html">%s</a></div><p></p>\n' % (horiz_spacer, name, name_str))

def find_matches(name_set, c):
    match_list = []
    for name in name_set:
        if name in page_child:
            sub_list = find_matches(page_child[name], c)
            if len(sub_list) == 1:
                match_list.extend(sub_list)
            elif len(sub_list) > 1:
                match_list.append(name)
        elif name in page_list and (c == None or
                                    (name in flower_color and c in flower_color[name])):
            match_list.append(name)
    return match_list

def list_flower_matches(w, match_list, indent, c):
    for name in sorted(match_list):
        list_flower(w, name, indent)

        if name in page_child:
            list_flower_matches(w, find_matches(page_child[name], c), indent+1, c)

def emit_color(primary, clist):
    with open(root + "/html/%s.html" % primary, "w") as w:
        w.write('<head><title>%s Flowers</title></head>\n' % primary.capitalize())
        w.write('<body>\n')
        for c in clist:
            top_list = [x for x in page_list if x not in page_parent]
            match_list = find_matches(top_list, c)

            if match_list:
                w.write('<h1>%s flowers</h1>\n' % c.capitalize())
                list_flower_matches(w, match_list, 0, c)

        emit_footer(w)

emit_color('yellow', ['yellow', 'orange'])

with open(root + "/html/all.html", "w") as w:
    w.write('<head><title>All Flowers</title></head>\n')
    w.write('<body>\n')
    w.write('<h1>All flowers</h1>\n')

    top_list = [x for x in page_list if x not in page_parent]
    list_flower_matches(w, top_list, 0, None)

    emit_footer(w)

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
                w.write('<a href="%s">%s</a><p/>\n' % (name, name))
        if mod_list:
            w.write('<h1>Modified files</h1>\n')
            for name in mod_list:
                w.write('<a href="%s">%s</a><p/>\n' % (name, name))
    os.startfile(mod_file)
else:
    print "No files modified."

# TODO:
# handle all colors, including "other" colors.
# improve all variable names.
# link to CalFlora in the form
#   https://www.calflora.org/cgi-bin/specieslist.cgi?namesoup=Mesembryanthemum+nodiflorum
# link to CalPhotos in the form
#   https://calphotos.berkeley.edu/cgi/img_query?where-taxon=Carpobrotus+edulis
# link to Jepson eFlora in the form
#   http://ucjeps.berkeley.edu/eflora/search_eflora.php?name=Carpobrotus+edulis
# sort lists by number of observations
