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
    def end_child_text():
        nonlocal child_start, c_list
        if child_start is None:
            return

    def end_paragraph(for_list=False):
        nonlocal p_start, child_start, c_list
        if p_start is not None:
            if for_list:
                p_tag = '<p class="list-head">'
            else:
                p_tag = '<p>'

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
            p = glossary.link_glossary_words_or_defn(name, p, p_tag, not page)

            c_list[p_start:] = [p]
            p_start = None

        if not for_list and child_start is not None:
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

    # Make easy substitutions in the text, such as "+-" and smart quotes.
    # Do this before linking to glossaries because the HTML added for
    # glossary links confuses the heuristic for smart-quote direction.
    # Its order with respect to other parsing isn't important.
    s = easy_sub(s)

    s = link_figures_text(name, s)

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
        # Determine the list depth.
        matchobj = re.match(r'\.*', c)
        new_list_depth = matchobj.end()

        # If a list is present, end any previous paragraph and don't
        # start a new one until at least the *next* line.
        if new_list_depth:
            end_paragraph(for_list=True)

        # Insert <ul> or </ul> tags to get from current list_depth
        # to the new_list_depth.
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

        # Remove the leading dots that signified the list plus associated
        # extra spaces.
        c = c[list_depth:].strip()

        if page:
            # For taxon pages only, accumulate key text for a child page.
            matchobj = re.match(r'==(\d+)(,[-0-9]\S*|,)?\s*$', c)
            if matchobj:
                end_paragraph()
                child_matchobj = matchobj
                child_start = len(c_list)
                continue

        if list_depth:
            c = glossary.link_glossary_words(name, c)
            c_list.append(f'<li>{c}</li>')
            continue

        if re.match(r'<h\d>', c):
            # It doesn't actually hurt the user to wrap heading tags in
            # paragraph tags, but it hurts my soul.  I don't care what
            # kind of heading it is (<h1>, <h2>, etc.) since it should
            # be closed with a matching tag without nesting.
            in_heading = True

        if in_heading:
            # We remain outside of paragraph tags until the heading ends,
            # whether that is on the same line or a later line.
            end_paragraph()
            if page:
                c = glossary.link_glossary_words(name, c)
            c_list.append(c)
            if re.search(r'</h\d>', c):
                in_heading = False
            continue

        if c.startswith('{') and not c.startswith('{-'):
            end_paragraph()
            p_start = len(c_list)

        if c.startswith('figure:'):
            # Leave figure links untouched and not embedded in paragraphs.
            end_paragraph()
            c_list.append(c)
            continue

        if c == '[':
            end_paragraph()
            c_list.append('<div class="box">')
            bracket_depth += 1
            continue

        if c == ']':
            end_paragraph()
            c_list.append('</div>')
            bracket_depth -= 1
            continue

        if c == '':
            end_paragraph()
            continue

        if p_start is None:
            p_start = len(c_list)
        c_list.append(c)
    end_paragraph()

    if bracket_depth != 0:
        error(f'"[" and "]" bracket depth is {bracket_depth} on page {name}')

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
