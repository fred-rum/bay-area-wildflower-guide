import sys
import os
import re

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
src_path = convert_path_to_unix(sys.path[0])
root_path = re.sub(r'/src$', r'', src_path)

# Get the set of files that have the expected suffix in the designated
# directory.  The set includes only the base filename without the
# extension.
def get_file_set(subdir, ext):
    file_list = os.listdir(root_path + '/' + subdir)
    base_list = set()
    for filename in file_list:
        pos = filename.rfind(os.extsep)
        if pos > 0:
            file_ext = filename[pos+len(os.extsep):].lower()
            if file_ext == ext:
                base = filename[:pos]
                base_list.add(base)
    return base_list

jpg_files = get_file_set('photos', 'jpg')


def link_figures(name, txt):
    def repl_figure_thumb(matchobj):
        file = matchobj.group(1)
        if not os.path.isfile(f'{root_path}/figures/{file}.svg'):
            print(f'Broken figure link to {file}.svg in {name}')
        return f'<a href="../figures/{file}.svg"><img src="../figures/{file}.svg" height="200" class="leaf-thumb"></a>'

    def repl_figure_thumbs(matchobj):
        inner = matchobj.group(1)
        inner = re.sub(r'^figure:(.*?)(?:\.svg|)$',
                       repl_figure_thumb, inner, flags=re.MULTILINE)
        return f'<div class="photo-box">\n{inner}\n</div>'

    def repl_figure_text(matchobj):
        file = matchobj.group(1)
        if not os.path.isfile(f'{root_path}/figures/{file}.svg'):
            print(f'Broken figure link to {file}.svg in {name}')
        return f'<a href="../figures/{file}.svg">[figure]</a>'

    txt = re.sub(r'^(figure:.*?(?:\.svg|)(?:\nfigure:.*?(?:\.svg|))*)$',
                 repl_figure_thumbs, txt, flags=re.MULTILINE)
    txt = re.sub(r'\[figure:(.*?)(?:\.svg|)\]',
                 repl_figure_text, txt, flags=re.MULTILINE)
    return txt

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
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
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
<link rel="stylesheet" href="../bawg.css">
</head>
<body>
''')
    w.write('<div id="body">\n')
    if h1:
        w.write(f'<h1 id="title"{space_class}>{h1}</h1>\n')

def write_footer(w):
    # I don't put the year in the copyright because it's a pain to determine
    # given the different creation/modification dates of the pages *plus*
    # the photos on them.  The Berne Convention applies in any case.
    w.write(f'''
<hr/>
<a href="../index.html">BAWG</a> <span class="copyright">&ndash; &copy; Chris Nelson</span>
</div>
<script src="../pages.js"></script>
<script src="../search.js"></script>
</body>
''')
