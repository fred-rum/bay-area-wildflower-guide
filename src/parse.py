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

def parse_txt(name, s, page):
    def end_paragraph(start_list=False):
        nonlocal p_start
        if p_start is None:
            return

        if start_list:
            p_tag = '<p class="list-head">'
        else:
            p_tag = '<p>'
        c_list[p_start] = p_tag + c_list[p_start]
        c_list[-1] += '</p>'
        p_start = None

    def end_child_text():
        nonlocal child_start, c_list
        if child_start is None:
            return

        child_idx = int(child_matchobj.group(1))
        suffix = child_matchobj.group(2)
        if not suffix:
            suffix = ''

        text = '\n'.join(c_list[child_start:])
        c_list = c_list[:child_start]
        child_start = None

        c_list.append(page.parse_child_and_key(child_idx, suffix, text))

    # Replace HTTP links in the text with ones that open a new tab.
    # This must be done before inserting internal links, e.g. ==... or {-...}.
    s = re.sub(r'<a href=', '<a target="_blank" href=', s)

    # Break the text into lines, then perform easy substitutions on
    # non-keyword lines and decorate bullet lists.  Also, keep track
    # of lines associated with a child; we'll copy those into the
    # child's text if it doesn't have any.
    c_list = []
    p_start = None
    child_start = None
    list_depth = 0
    bracket_depth = 0
    in_heading = None
    for c in s.split('\n'):
        matchobj = re.match(r'\.*', c)
        new_list_depth = matchobj.end()
        if new_list_depth:
            end_paragraph(True)
        if new_list_depth > list_depth+1:
            error('Jump in list depth on page ' + name)
        while list_depth < new_list_depth:
            if list_depth == 0:
                c_list.append('<ul>')
            else:
                c_list.append('<ul class="list-sub">')
            list_depth += 1
        while list_depth > new_list_depth:
            c_list.append('</ul>')
            list_depth -= 1
        c = c[list_depth:].strip()

        # non_p gets set to True if text is passed through that shouldn't
        # be wrapped in a paragraph tag.  Note that this is different from
        # the case in which text is suppressed with a 'continue' statement.
        non_p = False

        if (page):
            # For taxon pages only, accumulate key text for a child page.
            matchobj = re.match(r'==(\d+)(,[-0-9]\S*|,)?\s*$', c)
            if matchobj:
                end_paragraph()
                end_child_text()
                child_matchobj = matchobj
                child_start = len(c_list)
                continue

        if re.match(r'<h\d>', c):
            # It doesn't actually hurt the user to wrap heading tags in
            # paragraph tags, but it hurts my soul.  I don't care what
            # kind of heading it is (<h1>, <h2>, etc.) since it should
            # be closed with a matching tag without nesting.
            in_heading = True

        if in_heading:
            # We remain outside of paragraph tags until the headin ends,
            # whether that is on the same line or a later line.
            non_p = True
            if re.search(r'</h\d>', c):
                in_heading = False

        if c.startswith('{') and not c.startswith('{-'):
            # Leave glossary definitions untouched and not embedded in
            # paragraphs.
            non_p = True

        if c.startswith('figure:'):
            # Leave figure links untouched and not embedded in paragraphs.
            non_p = True

        if c == '[':
            end_paragraph()
            end_child_text()
            c_list.append('<div class="box">')
            bracket_depth += 1
            continue

        if c == ']':
            end_paragraph()
            end_child_text()
            c_list.append('</div>')
            bracket_depth -= 1
            continue

        if list_depth:
            c_list.append(f'<li>{c}</li>')
            continue

        if c == '':
            end_paragraph()
            end_child_text()
            continue

        if non_p:
            end_paragraph()
            end_child_text()
        elif p_start is None:
            p_start = len(c_list)
        c_list.append(c)
    end_paragraph()
    end_child_text()

    if bracket_depth != 0:
        error(f'"[" and "]" bracket depth is {bracket_depth} on page {name}')

    s = '\n'.join(c_list)

    s = link_figures(name, s)

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

    # Make easy substitutions in the text, such as "+-" and smart quotes.
    # Do this before linking to glossaries because the HTML added for
    # glossary links confuses the heuristic for smart-quote direction.
    s = easy_sub(s)

    error_begin_section()
    s = glossary.link_glossary_words(s, name, is_glossary=False)
    error_end_section()

    return s
