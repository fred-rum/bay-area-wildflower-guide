# This module provides some file-related functions that are used in
# multiple other modules.

import sys
import os
import re
from unidecode import unidecode
import urllib.parse

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

if arg('-dir'):
    root_path = arg('-dir')
    if root_path.endswith('/'):
        root_path = root_path[0:-1]
else:
    root_path = re.sub(r'/src$', r'', src_path)

# Create new files in the working_path.  This has a few advantages:
# - Allow the user to continue browsing old files while updates are in
#   progress.
# - If the script crashes, the previous valid files remain in place so
#   that the next run can compare against them and not against the files
#   from the crashed run.
working_path = root_path + '/.in_progress'

# Get the set of files that have the expected suffix in the designated
# directory.  The set includes only the base filename without the
# extension.
def get_file_set(subdir, ext):
    subdir_path = root_path + '/' + subdir
    if not os.path.isdir(subdir_path):
        return set()

    file_list = os.listdir(subdir_path)
    base_set = set()
    for filename in file_list:
        if ext:
            pos = filename.rfind(os.extsep)
            if pos > 0:
                file_ext = filename[pos+len(os.extsep):].lower()
                if file_ext == ext:
                    base = filename[:pos]
                    base_set.add(base)
        else:
            base_set.add(filename)
    return base_set

jpg_files = get_file_set(f'photos', 'jpg')

svg_figures = get_file_set(f'figures', 'svg')
jpg_figures = get_file_set(f'figures', 'jpg')

# Turn a set of files back into a file list.
def get_file_list(subdir, base_set, ext):
    file_list = []
    for base in sorted(base_set, key=str.casefold):
        file = subdir + '/' + base
        if ext:
            file += '.' + ext
        file_list.append(file)
    return file_list

def figure_url(name, file):
    if file in svg_figures:
        return f'../figures/{url(file)}.svg'
    elif file in jpg_figures:
        return f'../figures/{url(file)}.jpg'
    else:
        error(f'Broken figure link to {file}.svg/jpg in {name}')
        return f'../figures/{url(file)}.svg'

def link_figures_thumb(name, txt):
    def repl_figure_thumb(matchobj):
        file = matchobj.group(1)
        fileurl = figure_url(name, file)
        return f'<a href="{fileurl}"><img src="{fileurl}" alt="figure" height="200" class="leaf-thumb"></a>'

    def repl_figure_thumbs(matchobj):
        inner = matchobj.group(1)
        inner = re.sub(r'^figure:(.*?)(?:\.svg|)$',
                       repl_figure_thumb, inner, flags=re.MULTILINE)
        return f'<div class="photo-box">\n{inner}\n</div>'

    return re.sub(r'^(figure:.*?(?:\.svg)?(?:\nfigure:.*?(?:\.svg|))*)$',
                  repl_figure_thumbs, txt, flags=re.MULTILINE)

def link_figures_text(name, txt):
    def repl_figure_text(matchobj):
        file = matchobj.group(1)
        text = matchobj.group(2)
        if not text:
            text = 'figure'
        fileurl = figure_url(name, file)
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

    w.write(f'''<!-- Copyright Chris Nelson - All rights reserved. -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">{content}
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script async src="{path}search.js"></script>
<script async src="{path}pages.js"></script>
<script async src="{path}swi.js"></script>
<link rel="apple-touch-icon" sizes="180x180" href="{path}favicon/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="{path}favicon/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="{path}favicon/favicon-16x16.png">
<link rel="manifest" href="{path}manifest.webmanifest">
<link rel="mask-icon" href="{path}favicon/safari-pinned-tab.svg" color="#106110">
<link rel="shortcut icon" href="{path}favicon/favicon.ico">
<meta name="msapplication-TileColor" content="#106110">
<meta name="msapplication-config" content="{path}favicon/browserconfig.xml">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="{path}bawg.css">
</head>
<body>
<a id="home-icon" tabindex="0" href="{path}index.html"><img src="{path}icons/home.png" alt="home"></a>
<div class="body-container">
<div id="search-container">
<input type="search" id="search" autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" placeholder="flower or glossary term" aria-label="search for a flower or glossary term">
<noscript><input type="search" value="search requires Javascript"disabled></noscript>
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

def write_footer(w, incl_footer=True, at_root=False):
    if at_root:
        path = ''
    else:
        path = '../'

    # The "home-link" tag is empty because it gets filled in by the CSS
    # with either "BAWG" or "Bay Area Wildflower Guide", depending on how
    # much space is available.
    #
    # I don't put the year in the copyright because it's a pain to determine
    # given the different creation/modification dates of the pages *plus*
    # the photos on them.  The Berne Convention applies in any case.
    if (incl_footer):
        w.write(f'''<div class="footer">
<span class="foot-left"><a class="home-link" href="{path}index.html" aria-label="home"></a> <span class="foot-fade"> &copy; Chris Nelson</span></span><a class="foot-fade" href="{path}index.html#contact">Contact me</a>
</div>
''')
    w.write('''</div>
</div>
</body>
''')

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

# Wrap the process of reading a data file so that the common log messages are
# printed and a read failure is handled appropriately.
# If the file can be read, the 'fn' function is called with the file descriptor.
# If the file cannot be read, the 'fn' function is not called.
def read_data_file(filename, fn, msg=None):
    if msg:
        msg += ' from '
    else:
        msg = ''

    try:
        with open(f'{root_path}/data/{filename}', mode='r', encoding='utf-8') as f:
            if arg('-steps'):
                info(f'Reading {msg}data/{filename}')
            fn(f)
    except FileNotFoundError:
        if arg('-steps'):
            info(f'Skipping {msg}data/{filename}')
