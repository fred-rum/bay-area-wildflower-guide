#!/usr/bin/env python

import sys
import os
import subprocess
import shutil
import re

# Performs 'git mv' to rename one taxon to another and/or to change a
# photo suffix.

# Run as:
# src/gitmv.py [orig_name] [new_name]
# src/gitmv.py txt/[filename].txt [new_name]
# src/gitmv.py html/[filename].txt [new_name]
# src/gitmv.py photos/[filename],[suffix].jpg {[new_name] or [suffix] or [new_name],[suffix]}

# This script must be run from the project's git directory so that the
# relative paths are all exactly one directory deep.

# If the second arg includes a directory prefix or a file extension suffix,
# it is ignored.  So, e.g. this also works:
# src/gitmv.py photos/[name],[suffix].jpg photos/[name],[suffix].jpg

# If a txt/... path is given, all corresponding files in txt, html, photos,
# and thumbs are moved.
#
# If an html/... path is given, the html, photos, and thumbs are moved.
# In this case, the html path uses hyphens instead of spaces, but the
# new name in the second argument should be provided with spaces.
#
# If a photos/... path is given, the photos and thumbs are moved.
# If a destination suffix is given, only one photo and its corresponding
# thumbnail is moved to the designated destination.  If a destination
# name is given without a suffix, all photos are moved (in which case the
# filename suffix in the first argument doesn't matter).

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
    # If we get here, it's a name change, not a photo suffix change.
    # Change the txt and html files if they exist.
    from_file = f'txt/{name}.txt'
    if os.path.exists(from_file):
      to_file = f'txt/{arg2}.txt'
      gitmv(from_file, to_file)

    html_from = re.sub(r' ', '-', name)
    from_file = f'html/{html_from}.html'
    if os.path.exists(from_file):
        html_to = re.sub(r' ', '-', arg2)
        to_file = f'html/{html_to}.html'
        gitmv(from_file, to_file)

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
