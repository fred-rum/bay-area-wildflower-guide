# Perform standard txt->HTML substitutions, suitable for both taxon
# and glossary pages (except as noted below).  This includes full-text
# substitutions such as figure linking as well as line-by-line parsing
# for paragraphs and lists.
#
# Because child keys are intimately tied together with line-by-line
# paragraph parsing, these are also optionally recognized here if
# a page Object is passed in.  The page's parse_key() function is
# called to perform the taxon-specific processing once the key text
# is identified and extracted.

import re

# My files
from error import *
from files import *
from find_page import *
from easy import *

###############################################################################

def parse_txt(name, s, page, glossary):
    def end_paragraph(for_list=False, for_defn=False):
        nonlocal c_list, p_start, in_dl
        nonlocal child_start, child_idx, child_list, suffix

        if p_start is not None:
            # Join the paragraph back into a single string for convenience
            # of glossary linking.
            p = '\n'.join(c_list[p_start:])

            # We don't want to perform glossary linking on the whole
            # txt at once because we want special handling for the
            # lines that have glossary definitions.  We could do
            # glossary linking on a line-by-line basis, but then we'd
            # miss multi-word glossary terms that happen to be split
            # across lines.  So instead we carefully perform glossary
            # linking a paragraph at a time.  This not only recognizes
            # glossary terms split across lines, but also allows
            # glossary *definitions* to be split across lines.
            if glossary:
                p = glossary.link_glossary_words_or_defn(name, assoc_page, p,
                                                         not page)
            else:
                p = f'<p>{p}</p>'

            # Replace all the lines in c_list associated with the paragraph
            # with the new (single-string) paragraph.
            c_list[p_start:] = [p]
            p_start = None

        if not for_list and child_start is not None:
            child = page.child[child_idx]

            text = '\n'.join(c_list[child_start:])
            c_list = c_list[:child_start]
            child_start = None

            c_list.append(page.parse_child_and_key(child, suffix, text,
                                                   match_set))

            child_list.append(child)
            child_idx += 1

        # If beginning a new set of glossary definition, insert <dl>
        # after the previous paragraph (including all closing tags) and
        # before any lines that will be handled as part of the definitions.
        if for_defn and not in_dl:
            c_list.append('<dl>')

        # If ending set of glossary definition, insert </dl>
        # after the previous paragraph (including all closing tags)
        # before any lines that will be handled as part of the next paragraph.
        if in_dl and not for_defn:
            c_list.append('</dl>')

        in_dl = for_defn

    # When desired, reorder consecutive children in the parsed text to be
    # sorted by observation counts.
    def end_consecutive_children():
        nonlocal c_list, child_list, child_idx

        if not child_list or page.has_child_key:
            return

        num_children = len(child_list)
        child_text_list = c_list[-num_children:]
        c_list = c_list[:-num_children]

        sorted_child_list = page.sort_pages(child_list)

        page.child[child_idx - num_children:child_idx] = sorted_child_list

        for child in sorted_child_list:
            child_num = child_list.index(child)
            child_text = child_text_list[child_num]
            c_list.append(child_text)

        child_list = []


    # Figure out which page is most closely related so that glossary_warn
    # can be applied from that page.
    if page:
        assoc_page = page
    elif glossary:
        assoc_page = glossary.page
    else:
        assoc_page = None

    # Replace HTTP links in the text with ones that open a new tab.
    # This must be done before inserting internal links, e.g. ==... or {-...}.
    s = re.sub(r'<a\s*href\s*=\s*"http', '<a target="_blank" rel="noopener noreferrer" href="http', s)

    # Make easy substitutions in the text, such as "+-" and smart quotes.
    # Do this before linking to glossaries because the HTML added for
    # glossary links confuses the heuristic for smart-quote direction.
    # Its order with respect to other parsing isn't important.
    s = easy_sub(s)

    s = link_figures_text(name, s)

    # Break the text into lines, then perform easy substitutions on
    # non-keyword lines and decorate bullet lists.

    # c_list holds the parsed output as a list of strings.
    # When a number of lines go tother (as a paragraph or as a child
    # entry with optional key), c_list starts out partially processed,
    # and then we go back and replace the last few list entries when
    # we're ready to parse the complete chunk of lines.
    c_list = []

    # p_start keeps track of the start index of the current paragram in c_list.
    p_start = None

    # child_start keeps track of the start index in c_list of a child entry
    # in progress.
    child_start = None

    # child_idx keeps track of which child we're current working on.
    # It increments as we finish parsing each child.
    child_idx = 0

    # match_set keeps track of which descendants have been listed in the
    # hierarchy of this page so that they aren't repeated.
    match_set = set()

    # child_list tracks the pages of consecutively parsed children
    # in case we want to re-order them.
    child_list = []

    # Track the current indent level for a bulleted list in progress.
    list_depth = 0

    # Track the depth of nested boxes created by brackets.
    bracket_depth = 0

    # Are we in between heading tags (e.g. <h3>...</h3>)?
    in_heading = False

    # Are we in a glossary definition?
    in_dl = False

    for c in s.split('\n'):
        # non_p is set to True for lines that are not part of a paragraph.
        # I.e. the previous paragraph (if any) should be ended, and a new
        # paragraph should begin no earlier than with the following line.
        non_p = False

        # For a glossary definition, end the previous paragraph and
        # immediately start a new one to contain the definition.
        # (It will eventually be emitted with a paragraph tag or some
        # other appropriate enclosure.)
        if c.startswith('{') and not c.startswith('{-'):
            end_paragraph(for_defn=not page)

        # Determine the list depth.
        matchobj = re.match(r'\.*', c)
        new_list_depth = matchobj.end()

        # Insert <ul> or </ul> tags to get from current list_depth
        # to the new_list_depth.
        if new_list_depth > list_depth+1:
            error('Jump in list depth on page ' + name)

        if new_list_depth > 0 and list_depth == 0:
            end_paragraph(True)

        while new_list_depth > list_depth:
            # Open <ul> tags as part of the current line processing.
            # Thus, these tags appear after the previous paragraph is ended.
            c_list.append('<ul>')
            list_depth += 1

        while new_list_depth < list_depth:
            # Close <ul> tags as if they'd be processed on a previous line.
            # Thus, we're ready to begin a new paragraph as appropriate.
            c_list.append('</ul>')
            list_depth -= 1

        # Remove the leading dots that signified the list plus associated
        # extra spaces.
        c = c[list_depth:].strip()

        if list_depth:
            non_p = True
            if glossary:
                c = glossary.link_glossary_words(name, assoc_page, c)
            c = '<li>' + c + '</li>'

        if page:
            # For taxon pages only, accumulate key text for a child page.
            matchobj = re.match(r'==(,[-0-9]\S*|,)?\s*$', c)
            if matchobj:
                end_paragraph()
                suffix = matchobj.group(1)
                if not suffix:
                    suffix = ''
                child_start = len(c_list)
                continue

        if re.match(r'<h\d', c):
            # It doesn't actually hurt the user to wrap heading tags in
            # paragraph tags, but it hurts my soul.  I don't care what
            # kind of heading it is (<h1>, <h2>, etc.) since it should
            # be closed with a matching tag without nesting.
            in_heading = True

        if in_heading:
            # We remain outside of paragraph tags until the heading ends,
            # whether that is on the same line or a later line.
            non_p = True

            # taxon pages may link glossary terms in a heading,
            # but glossary pages should not (since the heading is
            # most likely one of the glossary words being defined,
            # making a link redundant).
            if page and glossary:
                c = glossary.link_glossary_words(name, assoc_page, c)

            if re.search(r'</h\d>', c):
                in_heading = False

        if c.startswith('<div'):
            # Keep a <div ...> tag out of paragraphs.
            non_p = True

        if c.endswith('</div>'):
            # Keep a </div> tag out of paragraphs, and if a paragraph has
            # been recorded to this point, discard it.  I.e.  What is between
            # <div ...> and </div> is only broken into paragraphs if it
            # has some sort of non-div paragraph divisions.
            non_p = True
            p_start = None

        if c.startswith('figure:'):
            # Leave figure links untouched and not embedded in paragraphs.
            non_p = True

        if c == '[':
            non_p = True
            c = '<div class="box">'
            bracket_depth += 1

        if c == ']':
            non_p = True
            c = '</div>'
            bracket_depth -= 1

        if c == '':
            non_p = True

        if non_p:
            end_paragraph(list_depth > 0)
        elif p_start is None:
            p_start = len(c_list)

        if c:
            if not child_start:
                end_consecutive_children()
            c_list.append(c)

    end_paragraph()
    end_consecutive_children()

    if bracket_depth != 0:
        error(f'"[" and "]" bracket depth is {bracket_depth} on page {name}')

    # Appending a newline after joining the list into a string would end
    # up copying the entire string.  Not a huge problem, but I might as well
    # avoid the extra copy by simply appending an empty string to the end of
    # the list prior to the join.
    c_list.append('')

    s = '\n'.join(c_list)

    s = link_figures_thumb(name, s)

    return s

# Links to taxon pages may be colored differently depending on whether the
# taxon has any child keys.  So we have to parse all taxon pages before
# inserting ilnks to taxon pagse.  I.e. we call parse_txt() on all taxon
# pages before calling parse2_txt() on all taxon pages.  As long as we've
# got this second function, we do some other last-minute parsing here
def parse2_txt(name, s, glossary):
    # Replace {-[link_name]} with an inline link to the page.
    def repl_link(matchobj):
        link_name = matchobj.group(1)
        page = find_page1(link_name)
        if page:
            return page.create_link(1)
        else:
            if link_name in glossary_name_dict:
                return glossary_name_dict[link_name].create_link()
            else:
                error(f'Broken link {{-{link_name}}} on page {name}')
                return '{-' + link_name + '}'

    # Replace {-[link_name]} with an inline link to the page.
    s = re.sub(r'{-([^}]+)}', repl_link, s)

    return s

def parse_other(name):
    def repl_title(matchobj):
        nonlocal title
        title = matchobj.group(1)
        return ''

    def repl_desc(matchobj):
        nonlocal desc
        desc = matchobj.group(1)
        return ''

    def repl_footer(matchobj):
        nonlocal incl_footer
        incl_footer = True
        return ''

    with open(f'{root_path}/other/{name}.txt', 'r', encoding='utf-8') as r:
        txt = r.read()

    # Default values; these can be overridden by lines within the txt.
    title = 'Bay Area Wildflower Guide'
    desc = 'A resource for identifying San Francisco Bay Area wildflowers.'
    incl_footer = False

    txt = re.sub(r'^\s*title\s*:\s*(.*?)\s*?\n',
                 repl_title, txt, flags=re.MULTILINE)
    txt = re.sub(r'^\s*desc\s*:\s*(.*?)\s*?\n',
                 repl_desc, txt, flags=re.MULTILINE)
    txt = re.sub(r'^\s*footer\s*\Z',
                 repl_footer, txt, flags=re.MULTILINE)

    txt = parse_txt(name, txt, None, None)

    with open(f'{root_path}/{name}.html', 'w', encoding='utf-8') as w:
        write_header(w, title, None, desc=desc, at_root=True)
        w.write(txt)
        write_footer(w, incl_footer, at_root=True)

def parse_other_txt_files(other_files):
    for file in other_files:
        parse_other(file)
