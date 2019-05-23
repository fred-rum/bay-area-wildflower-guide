#!/usr/bin/python

# Run as:
# /cygdrive/c/Users/Chris/Documents/GitHub/bay-area-flowers/flowers.py

import os
import shutil
import filecmp
import subprocess
import re
import csv
import cStringIO

root = '/cygdrive/c/Users/Chris/Documents/GitHub/bay-area-flowers'

shutil.rmtree(root + '/prev', ignore_errors=True)
os.rename(root + '/html', root + '/prev')
os.mkdir(root + '/html')

parent = {}
child = {}
first_img = {}

sci = {}
obs = {}
rg = {}
color = {}
type = {}
described = set()
with open(root + '/observations.csv', 'r') as f:
    reader = csv.reader(f)
    header = reader.next()
    sci_idx = header.index('scientific_name')
    com_idx = header.index('common_name')
    rg_idx = header.index('quality_grade')
    for row in reader:
        sci_name = row[sci_idx]
        com_name = row[com_idx].lower()
        if com_name and sci_name:
            sci[com_name] = sci_name
        if com_name:
            if com_name not in obs:
                obs[com_name] = 0
                rg[com_name] = 0
            obs[com_name] += 1
            if row[rg_idx] == 'research':
                rg[com_name] += 1

# The string replacement functions need context to operate,
# and I don't feel like messing around with lambda functions.
# So I'll use a global variable instead.
context = None

def is_ancestor(node, name):
    if node == name:
        return True

    if node in parent:
        for p in parent[node]:
            if is_ancestor(p, name):
                return True

    return False

def repl_link(matchobj):
    name = matchobj.group(1)

    if name.startswith('child:'):
        name = name[6:]

        if is_ancestor(context, name):
            print "circular loop when creating link from %s to %s" % (context, name)
        else:
            if name not in parent:
                parent[name] = set()
            parent[name].add(context)

            if context not in child:
                child[context] = []
            child[context].append(name)

    if name in base_list:
        link_style = ''
    else:
        link_style = ' style="color:red;"'

    return '<a href="%s.html"%s>%s</a>' % (name, link_style, name)

spacer = '<div style="min-width:10;"></div>'

def repl_color(matchobj):
    color[context] = matchobj.group(1).split(',')
    return ''        

def repl_type(matchobj):
    type[context] = matchobj.group(1)
    return ''        

def repl_jpg(matchobj):
    name = matchobj.group(1)
    filename = "../photos/%s.jpg" % name
    if name in jpg_list:
        img = '<a href="%s"><img src="%s" height="%d"></a>' % (filename, filename, jpg_height)
        jpg_used.add(name)
        if context not in first_img:
            first_img[context] = name
    else:
        img = '<a href="%s" style="color:red;"><div style="display:flex;border:1px solid black;padding:10;height:%d;min-width:%d;align-items:center;justify-content:center"><span style="color:red;">%s</span></div></a>' % (filename, jpg_height-22, jpg_height-22, name)

    return img + spacer

def repl_jpgs(matchobj):
    jpg_sublist = []
    ext_pos = len(context)
    for jpg in sorted(jpg_list):
        if jpg.startswith(context) and re.match(r'[-0-9]+$', jpg[ext_pos:]):
            jpg_sublist.append('{%s.jpg}' % jpg)

    if jpg_sublist:
        return ' '.join(jpg_sublist)
    else:
        return '{no photos.jpg}'

def repl_calphotos(matchobj):
    #r'<a href="\1" style="text-decoration:none"><div style="display:flex;border:1px solid black;padding:10;height:178;min-width:178;align-items:center;justify-content:center"><span><span style="text-decoration:underline;">CalPhotos</span>: \2</span></div></a>'

    target = matchobj.group(1)
    pos = target.find(':') # find the colon in "http:"
    pos = target.find(':', pos+1) # find the next colon, if any
    if pos > 0:
        text = ': ' + target[pos+1:]
        target = target[:pos]
    else:
        text = ''

    img = '<a href="%s" style="text-decoration:none"><div style="display:flex;border:1px solid black;padding:10;height:178;min-width:178;align-items:center;justify-content:center"><span><span style="text-decoration:underline;">CalPhotos</span>%s</span></div></a>' % (target, text)

    return img + spacer

def repl_sci_name(matchobj):
    name = matchobj.group(1)
    sci[context] = name
    return '<b><i>%s</i></b><p/>' % name

def repl_sci(matchobj):
    if context in sci:
        return '<b><i>%s</i></b><p/>' % sci[context]
    else:
        return '<b><i><span style="color:red">Scientific name not found.</span></i></b><p/>'

def end_file(w):
    w.write('''
&mdash;<br/>
<a href="index.html">BAFG</a> <span style="color:gray">Copyright 2019 Chris Nelson</span>
</body>
''')

def parse(base, s=None):
    global context
    context = base

    if not s:
        with open(root + "/" + base + ".txt", "r") as r:
            # reading in text mode doesn't convert EOLs correctly?
            s = r.read().replace('\015\012', '\012')

    # Replace {default} with all the default fields.
    s = re.sub(r'{default}', '{sci}\n{jpgs}\n\n{obs}', s)

    s = re.sub(r'{sci:\s*(.*\S)\s*}', repl_sci_name, s)
    s = re.sub(r'{sci}', repl_sci, s)

    if base in obs:
        n = obs[base]
        rc = rg[base]
    else:
        n = 0
    if n == 0:
        obs_str = 'Chris&rsquo;s observations: none'
    elif rc == 0:
        obs_str = 'Chris&rsquo;s observations: %d (none research grade)' % n
    elif rc == n:
        if n == 1:
            obs_str = 'Chris&rsquo;s observations: 1 (research grade)'
        else:
            obs_str = 'Chris&rsquo;s observations: %d (all research grade)' % n
    else:
        obs_str = 'Chris&rsquo;s observations: %d (%d research grade)' % (n, rc)
    s = re.sub(r'{obs}', obs_str + '<p/>', s)

    # Replace {jpgs} with all jpgs that exist for the flower.
    s = re.sub(r'{jpgs}', repl_jpgs, s)

    # Look for any number of {photos} followed by all text up to the
    # first \n\n or \n+EOF.  Photos can be my own or CalPhotos.
    # The photos and text are grouped together and vertically centered.
    # The text is also put in a <span> for correct whitespacing.
    s = re.sub(r'((?:\{(?:jpgs|[^\}]+.jpg|https://calphotos.berkeley.edu/[^\}]+)\} *)+)(((?!\n\n).)*)(?=\n(\n|\Z))', r'<div style="display:flex;align-items:center;">\1<span>\2</span></div>', s, flags=re.DOTALL)

    # Replace a pair of newlines with a paragraph separator.
    s = s.replace('\n\n', '\n<p/>\n')

    s = re.sub(r'{color:([^\}]+)}', repl_color, s)
    s = re.sub(r'{(tree|bush)}', repl_type, s)

    # Replace {*.jpg} with a 200px image and a link to the full-sized image.
    s = re.sub(r'{([^}]+).jpg}', repl_jpg, s)

    # Replace a {CalPhotos:text} reference with a 200px box with
    # "CalPhotos: text" in it.
    # The entire box is a link to CalPhotos.
    # The ":text" part is optional.  The second line below handles the case
    # where it is not present.
    s = re.sub(r'\{(https://calphotos.berkeley.edu/[^\}]+)\}', repl_calphotos, s)

    # Any remaining {reference} should refer to another flower page.
    # Replace it with a link, colored depending on whether the link is valid.
    s = re.sub(r'{([^}]+)}', repl_link, s)

    with open(root + "/html/" + base + ".html", "w") as w:
        w.write('<head><title>%s</title></head>\n' % base)
        w.write('<body>\n')
        w.write('<h1>%s</h1>' % base)
        w.write(s)

        # TODO: list all containers of the flower, including the top level.

        end_file(w)


file_list = os.listdir(root)
base_list = []
for filename in file_list:
    pos = filename.rfind(os.extsep)
    if pos > 0:
        ext = filename[pos+len(os.extsep):].lower()
        if ext == 'txt':
            base = filename[:pos]
            base_list.append(base)

file_list = os.listdir(root + '/photos')
jpg_list = []
jpg_used = set()
for filename in file_list:
    pos = filename.rfind(os.extsep)
    if pos > 0:
        ext = filename[pos+len(os.extsep):].lower()
        if ext == 'jpg':
            base = filename[:pos]
            jpg_list.append(base)

jpg_height = 200
for name in base_list:
    described.add(name)
    parse(name)

f = cStringIO.StringIO()
for name in sorted([name for name in jpg_list if name not in jpg_used]):
    f.write('{%s.jpg} %s\n\n' % (name, name))
s = f.getvalue()
f.close()
if s:
    jpg_height = 100
    parse("unused jpgs", s)

f = cStringIO.StringIO()
for name in sorted(obs):
    if name not in described:
        context = name
        f.write(repl_jpgs(None))
        f.write(" %s\n\n" % name)
s = f.getvalue()
f.close()
jpg_height = 50
parse("other observations", s)

def list_flower(w, name, indent):
    w.write('<div style="display:flex;align-items:center;">')
    if indent:
        w.write('<div style="min-width:%d;"></div>' % (indent * 80))
    w.write('<a href="%s.html">' % name)
    if name in first_img:
        w.write('<img src="../photos/%s.jpg" height="100">' % first_img[name])
    else:
        w.write('<div style="display:flex;border:1px solid black;height=98;min-width:98"></div>')
    if name in sci:
        name_str = "%s (<i>%s</i>)" % (name, sci[name])
    else:
        name_str = name
    w.write('</a>%s<a href="%s.html">%s</a></div><p></p>\n' % (spacer, name, name_str))

def find_matches(name_list, c):
    match_list = []
    for name in name_list:
        if name in child:
            sub_list = find_matches(child[name], c)
            if len(sub_list) == 1:
                match_list.extend(sub_list)
            elif len(sub_list) > 1:
                match_list.append(name)
        elif name in base_list and (c == None or
                                    (name in color and c in color[name])):
            match_list.append(name)
    return match_list

def list_flower_matches(w, match_list, indent, c):
    for name in sorted(match_list):
        list_flower(w, name, indent)

        if name in child:
            list_flower_matches(w, find_matches(child[name], c), indent+1, c)

def emit_color(primary, clist):
    with open(root + "/html/%s.html" % primary, "w") as w:
        w.write('<head><title>%s Flowers</title></head>\n' % primary.capitalize())
        w.write('<body>\n')
        for c in clist:
            top_list = [x for x in base_list if x not in parent]
            match_list = find_matches(top_list, c)

            if match_list:
                w.write('<h1>%s flowers</h1>\n' % c.capitalize())
                list_flower_matches(w, match_list, 0, c)

        end_file(w)

emit_color('yellow', ['yellow', 'orange'])

with open(root + "/html/all.html", "w") as w:
    w.write('<head><title>All Flowers</title></head>\n')
    w.write('<body>\n')
    w.write('<h1>All flowers</h1>\n')

    top_list = [x for x in base_list if x not in parent]
    list_flower_matches(w, top_list, 0, None)

    end_file(w)

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
shutil.rmtree(root + '/prev', ignore_errors=True)

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
else:
    print "No files modified."

# TODO:
# handle all colors, including "other" colors.
# improve all variable names.
# link to CalPhotos in the form
#   https://calphotos.berkeley.edu/cgi/img_query?where-taxon=Carpobrotus+edulis
