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

    ###########################################################################
    # Full-text parsing

    # Replace HTTP links in the text with ones that open a new tab.
    # (Presumably they're external links or they'd be in {...} format.)
    s = re.sub(r'<a href=', '<a target="_blank" href=', s)

    s = link_figures(name, s)

    ###########################################################################
    # Line-by-line parsing

    # Break the text into lines, then perform easy substitutions on
    # non-keyword lines and decorate bullet lists.  Also, keep track
    # of lines associated with a child; we'll copy those into the
    # child's text if it doesn't have any.
    c_list = []
    p_start = None
    child_start = None
    list_depth = 0
    bracket_depth = 0
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

        if (page):
            # For taxon pages only, accumulate key text for a child page.
            matchobj = re.match(r'==(\d+)(,[-0-9]\S*|,)?\s*$', c)
            if matchobj:
                end_paragraph()
                end_child_text()
                child_matchobj = matchobj
                child_start = len(c_list)
                continue

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

        if p_start is None:
            p_start = len(c_list)
        c_list.append(c)
    end_paragraph()
    end_child_text()

    if bracket_depth != 0:
        error(f'"[" and "]" bracket depth is {bracket_depth} on page {name}')

    return '\n'.join(c_list)
