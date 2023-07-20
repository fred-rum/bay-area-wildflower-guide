# This module provides some file-related functions that are used in
# multiple other modules.

import sys
import os
import shutil
import re
from unidecode import unidecode
import urllib.parse
import time

# My files
from args import *
from error import *

def convert_path_to_unix(path):
    return re.sub(r'\\', r'/', path)

def convert_path_to_windows(path):
    return re.sub(r'/', r'\\', path)

src_path = os.path.dirname(os.path.abspath( __file__ ))
# sys.path[0] is sometimes a relative path, e.g. when run under cProfile
src_path = convert_path_to_unix(src_path)

home_path = re.sub(r'/src$', r'', src_path)

if arg('-dir'):
    root_path = arg('-dir')
    if root_path.endswith('/'):
        root_path = root_path[0:-1]
else:
    root_path = home_path

def mkdir(dirname):
    try:
        os.mkdir(f'{root_path}/{dirname}')
    except FileExistsError:
        pass

mkdir('data')
mkdir('icons')
if arg('-api'):
    mkdir('inat')

# Get the set of files that have the expected suffix in the designated
# directory.  If with_path=False, the set includes only the base filename
# without the subdirectory or extension.
def get_file_set(subdir, ext, use_home=False, with_path=False):
    if use_home:
        root = home_path
    else:
        root = root_path

    if subdir:
        subdir_path = root + '/' + subdir
        rel_path = subdir + '/'
    else:
        subdir_path = ''
        rel_path = ''

    if not os.path.isdir(subdir_path):
        return set()

    file_list = os.listdir(subdir_path)
    base_set = set()
    for filename in file_list:
        if with_path:
            base_set.add(rel_path + filename)
        elif ext:
            pos = filename.rfind(os.extsep)
            if pos > 0:
                file_ext = filename[pos+len(os.extsep):].lower()
                if file_ext == ext:
                    base = filename[:pos]
                    base_set.add(base)
        else:
            base_set.add(filename)
    return base_set

jpg_photos = get_file_set(f'photos', 'jpg')

svg_figures = get_file_set(f'figures', 'svg')
svg_figures.discard('_figure template')

jpg_figures = get_file_set(f'figures', 'jpg')

# Copy icons from the home (src) directory to the root (-dir) directory
root_icons = get_file_set(f'icons', None)
home_icons = get_file_set(f'icons', None, use_home=True)
copy_icons = home_icons - root_icons
for icon in copy_icons:
    shutil.copy(home_path + '/icons/' + icon, root_path + '/icons')

# Turn a set of files back into a file list.
def get_file_list(subdir, base_set, ext):
    file_list = []
    for base in sorted(base_set, key=str.casefold):
        file = subdir + '/' + base
        if ext:
            file += '.' + ext
        file_list.append(file)
    return file_list

def figure_file(name, file):
    if file in svg_figures:
        return f'figures/{file}.svg'
    elif file in jpg_figures:
        return f'figures/{file}.jpg'
    else:
        error(f'Broken figure link to {file}.svg/jpg in {name}')
        return f'../figures/{file}.svg'

def figure_thumb(name, file):
    if file in svg_figures:
        return f'figures/{file}.svg'
    else:
        return f'thumbs/{file}.jpg'

def link_figures_thumb(name, txt, page, glossary):
    def repl_figure_thumb(matchobj):
        figure = matchobj.group(1)
        imagefile = figure_file(name, figure)
        fileurl = url('../' + imagefile)
        if page:
            page.figure_list.append(imagefile)
        if glossary:
            glossary.figure_list.append(imagefile)
        thumburl = url('../' + figure_thumb(name, figure))
        return f'<a href="{fileurl}"><img src="{thumburl}" alt="figure" height="200" class="leaf-thumb"></a>'

    def repl_figure_thumbs(matchobj):
        inner = matchobj.group(1)
        inner = re.sub(r'^figure:(.*?)(?:\.svg|)$',
                       repl_figure_thumb, inner, flags=re.MULTILINE)
        return f'<div class="photo-box">\n{inner}\n</div>'

    return re.sub(r'^(figure:.*?(?:\.svg)?(?:\nfigure:.*?(?:\.svg|))*)$',
                  repl_figure_thumbs, txt, flags=re.MULTILINE)

def link_figures_text(name, txt):
    def repl_figure_text(matchobj):
        figure = matchobj.group(1)
        text = matchobj.group(2)
        if not text:
            text = 'figure'
        file = figure_file(name, figure)
        fileurl = url('../' + file)
        return f'<a href="{fileurl}">[{text}]</a>'

    return re.sub(r'\[figure:(.*?)(?:\.svg)?(?:,(.*?))?\]',
                  repl_figure_text, txt, flags=re.MULTILINE)


# Write a standard HTML header.
# title must always be valid and defines the window/tab title in the metadata.
# h1 is optional and specifies text for an h1 header at the top of the page.
# nospace indicates whether to omit the standard vertical whitespace below
# the h1 header (e.g. because alternative taxon names will be listed below it).
def write_header(w, title, h1, nospace=False, desc=None, at_root=False):
    if desc:
        content = f'\n<meta name="description" content="{desc}">'
    else:
        content = ''

    if at_root:
        path = ''
    else:
        path = '../'

    if arg('-debug_js'):
        script_path = path + 'src/'
    else:
        script_path = path

    w.write(f'''<!-- Copyright Chris Nelson - All rights reserved. -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">{content}
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script async src="{script_path}search.js"></script>
<script async src="{path}pages.js"></script>
<script async src="{script_path}swi.js"></script>
<link rel="apple-touch-icon" sizes="180x180" href="{path}favicon/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="{path}favicon/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="{path}favicon/favicon-16x16.png">
<link rel="manifest" href="{path}manifest.webmanifest">
<link rel="mask-icon" href="{path}favicon/safari-pinned-tab.svg" color="#106110">
<link rel="shortcut icon" href="{path}favicon/favicon.ico">
<meta name="msapplication-TileColor" content="#106110">
<meta name="msapplication-config" content="{path}favicon/browserconfig.xml">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="{script_path}bawg.css">
</head>
<body>
<a id="home-icon" tabindex="0" href="{path}index.html"><img src="{path}icons/home.png" alt="home"></a>
<div id="search-container">
<input type="search" id="search" autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" placeholder="flower or glossary term" aria-label="search for a flower or glossary term" autofocus>
<noscript><input type="search" value="search requires JavaScript"disabled></noscript>
<div id="autocomplete-box"></div>
</div>
<div id="body">
''')

    if h1:
        if nospace:
            space_class = ' class="nospace"'
        else:
            space_class = ''
        w.write(f'<h1 id="title"{space_class}>{h1}</h1>\n')

# Convert non-ASCII characters to their closest ASCII equivalent.
# This is suitable for use as a filename or as a string that the user
# can actually type when searching.
def filename(name):
    return unidecode(name)

# Percent-encode characters that aren't supposed to be in a URL.
# E.g. encode " " as "%20".
# safe list taken from
# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/encodeURI
# In particular, I use ",", "'", and of course "/" in my filenames.
def url(name):
    return urllib.parse.quote(filename(name), safe=";,/?:@&=+$-_.!~*'()#")

def delete_file(filename):
    try:
        os.remove(f'{root_path}/{filename}')
    except FileNotFoundError:
        pass


# Wrap the process of reading a file so that the common log messages are
# printed and a read failure is handled appropriately.
# If the file can be read, the 'fn' function is called with the file handle.
#
# If skippable is True, and the file doesn't exist, then the 'fn' function
# is skipped.
# If skippable if False, then any file error triggers an exception as usual.
#
# If raw is True, the file is read in binary mode.
# If raw is False, the file is read as UTF-8.
#
# If msg gives a reason for the file access, that info is added to the tracking.
def read_file(filename, fn, skippable=False, raw=False, msg=None):
    if msg:
        # Ultimately, this becomes "Reading <msg> from <filename>".
        msg += ' from '
    else:
        msg = ''

    if raw:
        mode = 'rb'
        encoding = None
    else:
        mode = 'r'
        encoding = 'utf-8'

    with Progress(f'Read {msg}{filename}'):
        try:
            with open(f'{root_path}/{filename}',
                      mode=mode, encoding=encoding) as f:
                # Once the file is open, any further file exceptions should be
                # treated as usual (not skipped).
                skippable = False
                fn(f)
        except FileNotFoundError:
            if skippable:
                # We didn't find the file, but we're allowed to skip it.
                if arg('-steps'):
                    info(f'Skipping {msg}{filename} (file not found)')
                # Exit without doing any work.
                return
            else:
                # Propagate any other exception to the Progress tracker.
                raise


# Read the footer text from a file (if present).
def read_footer(f):
    global footer_txt
    footer_txt = f.read()
    footer_txt = re.sub(r'<!--.*?-->\s*', '', footer_txt, flags=re.DOTALL)

footer_txt = '' # in case there is no footer
read_file('other/footer.html', read_footer, skippable=True)

def write_footer(w, incl_footer=True, at_root=False):
    # Close the central division (id="body").
    w.write('</div>\n')

    if (incl_footer):
        # I assume that all href links in the footer are relative to the root
        # directory.  So if we're writing an HTML file that is *not* at the
        # root directory, modify the href links accordingly.
        if at_root:
            footer_mod = footer_txt
        else:
            footer_mod = re.sub(r'href="', r'href="../', footer_txt)

        w.write(footer_mod)

    w.write('</body>\n')
