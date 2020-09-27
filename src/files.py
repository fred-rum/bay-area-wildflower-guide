# This module provides some file-related functions that are used in
# multiple other modules.

import sys
import os
import re
from unidecode import unidecode
import urllib.parse

# My files
from error import *

def convert_path_to_unix(path):
    return re.sub(r'\\', r'/', path)

def convert_path_to_windows(path):
    return re.sub(r'/', r'\\', path)

# I don't really understand what Windows is doing with / vs. \ path
# separators or how they impact .. path handling.  So I avoid the ..
# stuff by getting the path of the script and stripping off the
# trailing /src part.  (Obviously, this assumes that no one has mucked
# with the directory hierarchy, but that assumption would be baked in
# regardless.)
src_path = os.path.dirname(os.path.abspath( __file__ ))
# sys.path[0] is sometimes a relative path, e.g. when run under cProfile
src_path = convert_path_to_unix(src_path)
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
        pos = filename.rfind(os.extsep)
        if pos > 0:
            file_ext = filename[pos+len(os.extsep):].lower()
            if file_ext == ext:
                base = filename[:pos]
                base_set.add(base)
    return base_set

jpg_files = get_file_set(f'{db_pfx}photos', 'jpg')


def link_figures_thumb(name, txt):
    def repl_figure_thumb(matchobj):
        file = matchobj.group(1)
        fileurl = url(file)
        if not os.path.isfile(f'{root_path}/figures/{file}.svg'):
            error(f'Broken figure link to {file}.svg in {name}')
        return f'<a href="../figures/{fileurl}.svg"><img src="../figures/{fileurl}.svg" alt="figure" height="200" class="leaf-thumb"></a>'

    def repl_figure_thumbs(matchobj):
        inner = matchobj.group(1)
        inner = re.sub(r'^figure:(.*?)(?:\.svg|)$',
                       repl_figure_thumb, inner, flags=re.MULTILINE)
        return f'<div class="photo-box">\n{inner}\n</div>'

    return re.sub(r'^(figure:.*?(?:\.svg|)(?:\nfigure:.*?(?:\.svg|))*)$',
                  repl_figure_thumbs, txt, flags=re.MULTILINE)

def link_figures_text(name, txt):
    def repl_figure_text(matchobj):
        file = matchobj.group(1)
        fileurl = url(file)
        if not os.path.isfile(f'{root_path}/figures/{file}.svg'):
            error(f'Broken figure link to {file}.svg in {name}')
        return f'<a href="../figures/{fileurl}.svg">[figure]</a>'

    return re.sub(r'\[figure:(.*?)(?:\.svg|)\]',
                  repl_figure_text, txt, flags=re.MULTILINE)


# Write a standard HTML header.
# title must always be valid and defines the window/tab title in the metadata.
# h1 is optional and specifies text for an h1 header at the top of the page.
# nospace indicates whether to omit the standard vertical whitespace below
# the h1 header (e.g. because alternative taxon names will be listed below it).
def write_header(w, title, h1, nospace=False):
    if nospace:
        space_class = ' class="nospace"'
    else:
        space_class = ''
    w.write(f'''<!-- Copyright Chris Nelson - All rights reserved. -->
<!DOCTYPE html>
<html lang="en">
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script async src="../search.js"></script>
<script async src="../pages.js"></script>
<link rel="apple-touch-icon" sizes="180x180" href="../favicon/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="../favicon/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="../favicon/favicon-16x16.png">
<link rel="manifest" href="../favicon/site.webmanifest">
<link rel="mask-icon" href="../favicon/safari-pinned-tab.svg" color="#106110">
<link rel="shortcut icon" href="../favicon/favicon.ico">
<meta name="msapplication-TileColor" content="#106110">
<meta name="msapplication-config" content="../favicon/browserconfig.xml">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="../bawg.css">
</head>
<body>
<div class="body-container">
<div id="search-container">
<input type="search" id="search" autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" placeholder="flower or glossary term" aria-label="search for a flower or glossary term">
<noscript><input type="search" value="search requires Javascript"disabled></noscript>
<div id="autocomplete-box"></div>
</div>
<div id="body">
''')
    if h1:
        w.write(f'<h1 id="title"{space_class}>{h1}</h1>\n')

def write_footer(w):
    # The "home-link" tag is empty because it gets filled in by the CSS
    # with either "BAWG" or "Bay Area Wildflower Guide", depending on how
    # much space is available.
    #
    # I don't put the year in the copyright because it's a pain to determine
    # given the different creation/modification dates of the pages *plus*
    # the photos on them.  The Berne Convention applies in any case.
    w.write(f'''</div>
<div class="footer">
<span class="foot-left"><a class="home-link" href="../index.html"></a> <span class="foot-fade"> &copy; Chris Nelson</span></span><a class="foot-fade" href="../contact.html">Contact me</a>
</div>
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
def url(name):
    return urllib.parse.quote(filename(name), safe='/,')
