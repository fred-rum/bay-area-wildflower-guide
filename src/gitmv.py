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

# This script must be run from the project's git directory so that the
# relative paths are all exactly one directory deep.

# Performs 'git mv' to rename one taxon to another and/or to change a
# photo suffix.  If a txt/... path is given, all corresponding fiels in
# txt, html, photos, and thumbs are moved.  If an html/... path is given,
# the html, photos, and thumbs are moved.  If a photos/... path is given,
# the photos and thumbs are moved.  In this last case, the [suffix] can be
# given in the second argument to move only one photo and its corresponding
# thumbnail, or it can be omitted to move them all (in which case the suffix
# doesn't matter in the first argument).

def run(cmd):
    # Run a command and capture its returncode.
    # If the command emits any messages, let those go to STDOUT/STDERR
    # per the default behavior.
    result = subprocess.run(cmd)

    if result.returncode:
        print(' '.join(cmd))
        print(f'Command returned non-zero exit status {result.returncode}')
        sys.exit(result.returncode)

arg1 = sys.argv[1]
arg2 = sys.argv[2]

(base, filename) = os.path.split(arg1)
(name, ext) = os.path.splitext(filename)

git = shutil.which('git')
if not git:
    git = 'c:/Program Files/Git/bin/git'

if base == 'txt':
    cmd = (git, 'mv', f'txt/{name}.txt', f'txt/{arg2}.txt')
    subprocess.run(cmd)

if base in ('txt', 'html'):
    html_from = re.sub(r' ', '-', name)
    html_to = re.sub(r' ', '-', arg2)
    cmd = (git, 'mv', f'html/{html_from}.txt', f'html/{html_to}.txt')
    subprocess.run(cmd)

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

matchobj = re.match(r'(?:(.*?),?)([-0-9][^,:]*|,)$', arg2)
if matchobj:
    # Move photo from one suffix to another
    to_name = matchobj.group(1) or basename # keep the same name if unspecified
    to_suffix = matchobj.group(2)

    cmd = (git, 'mv', f'photos/{name}.jpg', f'photos/{to_name},{to_suffix}.jpg')
    subprocess.run(cmd)

    cmd = (git, 'mv', f'thumbs/{name}.jpg', f'thumbs/{to_name},{to_suffix}.jpg')
    subprocess.run(cmd)
else:
    # Move all photos from one name to another
    file_list = os.listdir('photos')
    for filename in file_list:
        if filename.startswith(basename):
            suffix = filename[len(basename):]
            if re.match(r',[-0-9][^,:]*$', suffix):
                cmd = (git, 'mv', f'photos/{basename}{suffix}.jpg',
                       f'photos/{arg2}{suffix}.jpg')
                subprocess.run(cmd)

                cmd = (git, 'mv', f'thumbs/{basename}{suffix}.jpg',
                       f'thumbs/{arg2}{suffix}.jpg')
                subprocess.run(cmd)
