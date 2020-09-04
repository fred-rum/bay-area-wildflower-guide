# My files
from files import *

def copy_css():
    with open(root_path + '/src/bawg.css', mode='r', encoding='utf-8') as r:
        txt = r.read()

    # Remove /* comments */, but not the /* Copyright ... */ comment.
    # Also remove whitespace, but not newlines.  Perl has \h for
    # horizontal whitespace, but in Python we have to use [^\S\r\n],
    # which means "everything except visible characters or line feeds or
    # carriage returns", which can be rephrased as "all white space
    # except line feeds and carriage returns".
    txt = re.sub(r'/[^\S\r\n]*\*(?! Copyright).*?\*/[^\S\r\n]*', '', txt, flags=re.DOTALL)

    # Collapse blank lines.
    txt = re.sub(r'\n\n+', '\n', txt)

    with open(root_path + '/bawg.css', mode='w', encoding='utf-8') as w:
        w.write(txt)
