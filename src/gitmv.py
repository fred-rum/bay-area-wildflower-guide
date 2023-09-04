#!/usr/bin/env python

import sys
import os
import subprocess
import shutil
import re

# Run as:
# src/gitmv.py txt/[name].txt [name]
# src/gitmv.py html/[name].txt [name]
# src/gitmv.py photos/[name],[suffix].jpg {[name] or [suffix] or [name],[suffix]}

# If the second arg includes a directory prefix or a file extension suffix,
# it is ignored.  So, e.g. this also works:
# src/gitmv.py photos/[name],[suffix].jpg {[name] or [suffix] or photos/[name],[suffix]}.jpg

# This script must be run from the project's git directory so that the
# relative paths are all exactly one directory deep.

# Performs 'git mv' to rename one taxon to another and/or to change a
# photo suffix.
#
# If a txt/... path is given, all corresponding fiels in txt, html, photos,
# and thumbs are moved.
#
# If an html/... path is given, the html, photos, and thumbs are moved.
# In this case, the html path uses hyphens instead of spaces, but the
# new name in the second argument should be provided with spaces.
#
# If a photos/... path is given, the photos and thumbs are moved.
# In this last case, the [suffix] can be given in the second argument
# to move only one photo and its corresponding thumbnail, or it can
# be omitted to move them all (in which case the suffix doesn't matter
# in the first argument).

arg1 = sys.argv[1]
arg2 = sys.argv[2]

(base, filename) = os.path.split(arg1)
(name, ext) = os.path.splitext(filename)

arg2 = re.sub(r'^.*/', '', arg2);
arg2 = re.sub(r'\.*$', '', arg2);

git = shutil.which('git')
if not git:
    git = 'c:/Program Files/Git/bin/git'

def gitmv(file1, file2, optional=False):
    # Run 'git mv' to move <file1> to <file2>.
    # If <file1> isn't under GIT control, then just rename the file instead.
    cmd = (git, 'mv', file1, file2)
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8')

    if result.returncode:
        if result.stderr.startswith('fatal: bad source') and optional:
            pass
        elif result.stderr.startswith('fatal: not under version control'):
            print(f'mv {file1} {file2}')
            os.rename(file1, file2)
        else:
            print(f'git mv {file1} {file2}')
            print(result.stderr, end='')
            print(f'Command returned non-zero exit status {result.returncode}')
            sys.exit(result.returncode)
    else:
        print(f'git mv {file1} {file2}')

if base == 'txt':
    gitmv(f'txt/{name}.txt', f'txt/{arg2}.txt')

if base in ('txt', 'html'):
    html_from = re.sub(r' ', '-', name)
    html_to = re.sub(r' ', '-', arg2)
    gitmv(f'html/{html_from}.html', f'html/{html_to}.html')

def separate_name_and_suffix(name):
    # this always matches something, although the suffix may be empty
    matchobj = re.match(r'(.+?)\s*(,[-0-9][^,:]*|,)?$', name)
    name = matchobj.group(1)
    suffix = matchobj.group(2) or ''
    return name, suffix

matchobj = re.match(r'(.+?)(,[-0-9][^,:]*|,)$', name)
if matchobj:
    basename = matchobj.group(1)
else:
    basename = name

matchobj = re.match(r'(?:(.*?),)?([-0-9][^,:]*|,)$', arg2)
if matchobj:
    # Move photo from one suffix to another
    to_name = matchobj.group(1) or basename # keep the same name if unspecified
    to_suffix = matchobj.group(2)

    gitmv(f'photos/{name}.jpg', f'photos/{to_name},{to_suffix}.jpg')
    gitmv(f'thumbs/{name}.jpg', f'thumbs/{to_name},{to_suffix}.jpg',
          optional=True)
else:
    # Move all photos from one name to another
    file_list = os.listdir('photos')
    for filename in file_list:
        # If an html name was specified with dashes,
        # accept a match for a filename with spaces instead,
        # and use the name with spaces for the move.
        dashname = re.sub(r' ', '-', filename)
        if dashname.startswith(basename):
            basename = filename[:len(basename)]

        if filename.startswith(basename):
            suffix_and_ext = filename[len(basename):]
            (suffix, ext) = os.path.splitext(suffix_and_ext)
            if re.match(r',(?:[-0-9][^,:]*)?$', suffix):
                gitmv(f'photos/{basename}{suffix}.jpg',
                      f'photos/{arg2}{suffix}.jpg')
                gitmv(f'thumbs/{basename}{suffix}.jpg',
                      f'thumbs/{arg2}{suffix}.jpg', optional=True)
