# My files
from files import *

def strip_comments(to_filename, from_filename=None,
                   code=None, debug_gallery=False):
    def repl_string_or_comment(matchobj):
        string = matchobj.group(1)
        comment = matchobj.group(2)

        if string is not None:
            return string
        elif 'Copyright' in comment:
            return comment
        else:
            return ''

    if not from_filename:
        from_filename = to_filename

    is_js = (to_filename.endswith('.js'))
    is_html = (to_filename.endswith('.html'))

    with open(f'{src_path}/{from_filename}', mode='r', encoding='utf-8') as r:
        txt = r.read()

    if code:
        txt = re.sub(r'/\* insert code here \*/', code, txt)

    if debug_gallery:
        # Change the gallery.js and gallery.css references to point to the
        # src directory.
        txt = re.sub(r'"gallery\.', '"src/gallery.', txt)

    if is_html:
        # When I'm debugging with -debug_js, advanced-search.html and
        # gallery.html need ../ to reach the directory with pages.js and
        # photos.js.  Strip away ../ when files are stripped and copied.
        txt = re.sub(r'src="../', 'src="', txt)

    if is_js:
        # When I'm debugging with -debug_js, the scripts running in
        # advanced-search.html and galley.html need extra code to prepend ../
        # to a URL.  Discard that code when files are stripped and copied.
        txt = re.sub(r'^\s*/\* -debug_js only \*/.*$', '', txt,
                     flags=re.MULTILINE)

        # On the other hand, the URL to gallery.html is relative to the
        # page it's being used in, so search.js needs to include 'src/'.
        # Strip that away when files are stripped and copied.
        txt = re.sub(r"'src/", "'", txt)


    # These days strip_comments() is called with -debug_js only for sw.js.
    # strip_comments() isn't called at all for the other JavaScript files.
    if not is_html and not arg('-debug_js'):
        # JavaScript and CSS both use the same /* comment */ syntax,
        # which we strip here.
        # 
        # Match either a complete quoted string (which is returned
        # unchanged) or whitespace followed by a comment (which is
        # removed).
        #
        # If a string contains what appears to be a comment, the
        # string is matched because it starts first.  And vice versa
        # for a comment that contains quotation marks.
        #
        # Note that a JavaScript regex (surrounded by slashes) could
        # include a quotation mark and/or something that looks like
        # the start of a comment, but it's impossible to reliably
        # detect a regex without a full Javascript parser.  So we
        # exclude an escaped quotation mark to start a string (in case
        # that appears in a regex) and otherwise hope for the best.
        quote1 = r'(?<!\\)"(?:[^"\\]|\\.)*"'
        quote2 = r"(?<!\\)'(?:[^'\\]|\\.)*'"
        comment = r'/\s+?$|\s*/\*.*?\*/'

        if is_js:
            # JavaScript (but not JS) also includes // comments.
            #
            # Match a single-line comment beginning with '//',
            # but not if it's actually part of a regular expression
            # that includes a slash, i.e. '\//'.
            comment += r'|\s*(?<!\\)//[^\r\n]*$'

            # Also treat console debug statements as comments.
            comment += r'|\s*console\.(error|warn|info|log)\([^\r\n]*\)(;?)\s*$'

        pattern = fr'({quote1}|{quote2})|({comment})'
        txt = re.sub(pattern, repl_string_or_comment, txt,
                     flags=re.DOTALL|re.MULTILINE)

        # Collapse blank lines and whitespace at the end of lines.
        txt = re.sub(r'\s+\n', '\n', txt)

    with open(f'{root_path}/{to_filename}', mode='w', encoding='utf-8') as w:
        w.write(txt)
