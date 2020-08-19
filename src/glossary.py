import sys
import re

# My files
from error import *
from files import *
from find_page import *
from easy import *
from trie import *

glossary_taxon_dict = {}
glossary_name_dict = {}

class Glossary:
    pass

    def __init__(self, name):
        self.name = name
        self.taxon = None
        self.parent = None # a single parent glossary (or None)
        self.child = set() # an unordered set of child glossaries

        self.is_jepson = False # changed to True for the Jepson glossary

        # search_terms is an ordered list of term lists to be written
        # to pages.js.  The first term in each list is also the anchor.
        #
        # For the anchor and all other terms are unmodified:
        # - capitalization is retained for optimal display in auto-complete.
        # - easy_sub is not applied because it would confuse search matching.
        #   (And the original punctuation can match any user punctuation.)
        self.search_terms = []

        # term_anchor is a mapping from each term to an anchor.
        # This is used for creating glossary_regex and also for looking up
        # a matched term to get its anchor.
        #
        # The terms are modified somewhat:
        # - terms are lowercase as the canonical form for comparison.
        # - easy_sub is applied since that's what the regex will match.
        # The anchor remains unmodified:
        # - capitalization is retained for optimal display in the URL.
        # - easy_sub is not applied because a URL doesn't support special
        #   HTML characters.
        self.term_anchor = {}

        # anchor_terms is a mapping from each anchor to a set of terms.
        # This is used to exclude those terms within a definition line
        # from linking.  This is not used for the Jepson glossary
        # since we don't create HTML for it.
        #
        # The anchor remains unmodified as above.
        # The terms are modified as above.
        self.anchor_terms = {}

        # anchor_defined is a mapping from an anchor to the defined term
        # as listed in the HTML.  This is not used for the Jepson glossary
        # since we don't create HTML for it.
        #
        # The anchor remains unmodified as above.
        # The defined term is a string as follows:
        # - it includes the anchor and any parenthesized terms that we
        #   want to display beside it.
        # - capitalization is retained for optimal display in the HTML.
        # - easy_sub is applied for optimal display in the HTML.
        self.anchor_defined = {}

    def set_parent(self, parent):
        self.parent = parent
        parent.child.add(self)

    def get_link_class(self):
        if self.is_jepson:
            return 'glossary-jepson'
        else:
            return 'glossary'

    def get_url(self):
        if self.is_jepson:
            return 'https://ucjeps.berkeley.edu/eflora/glossary.html'
        else:
            return f'{self.name}.html'

    def create_link(self):
        link_class = self.get_link_class()
        url = self.get_url()
        return f'<a href="{url}" class="{link_class}">{self.name}</a>'

    def glossary_link(self, anchor, term):
        link_class = self.get_link_class()
        url = self.get_url()
        return f'<a class="{link_class}" href="{url}#{anchor}">{term}</a>'

    def find_dups(self, skip_glossary, term):
        def by_name(glossary):
            return glossary.name

        dup_list = []
        if self != skip_glossary and term in self.term_anchor:
            dup_list.append(self.glossary_link(self.term_anchor[term],
                                               self.name))

        for child in sorted(self.child, key=by_name):
            dup_list.extend(child.find_dups(skip_glossary, term))

        return dup_list

    # For the given term, get a link within the glossary or its ancestors.
    # Search ancestors only when deep=True.
    # Return None if the term isn't in the glossary (or its ancestors).
    def get_link(self, term, deep):
        lower = term.lower()
        if lower in self.term_anchor:
            anchor = self.term_anchor[lower]
            if self.is_jepson:
                if anchor in self.used_dict:
                    self.used_dict[anchor] += 1
                else:
                    self.used_dict[anchor] = 1
            return self.glossary_link(anchor, term)
        elif deep and self.parent:
            return self.parent.get_link(term, True)
        else:
            return None

    def link_glossary_words(self, txt, filename,
                            is_glossary=False, exclude=None):
        # This function is called for a glossary word match.
        # Replace the matched word with a link to the primary term
        # in the glossary.
        def repl_glossary(matchobj):
            term = matchobj.group(1)
            if '#' in term:
                (name, partition, bare_term) = term.partition('#')
                if bare_term == '':
                    # I'd love to print what file this error occured in, but
                    # that requires an exception or a global variable or passing
                    # more data around, none of which I like.  The user will
                    # have to grep for the broken reference in the HTML.
                    error(f'unrecognized glossary cross reference starting with "{name}#')
                    return f'{name}#broken ref'
                elif name == 'none':
                    # 'none#[term]' means that we don't want a glossary link.
                    # Discard the 'none#' and return only the bare term.
                    return bare_term
                else:
                    glossary = glossary_name_dict[name + ' glossary']
                    link = glossary.get_link(bare_term, False)
                    if link:
                        return link
                    else:
                        # We didn't find a link for the cross reference, but
                        # maybe we will if we use a shorter term.
                        # While keeping the cross-reference marker, cut off
                        # the end of the term and try glossary substitution
                        # again.
                        matchobj = re.match(r'(.*\W)(\w+)$', term)
                        if matchobj:
                            term1 = matchobj.group(1)
                            term2 = matchobj.group(2)
                            alt_term = link_safe(term1) + link_safe(term2)
                            if alt_term != term:
                                link = alt_term

                        if link:
                            return alt_term
                        else:
                            error(f'bad glossary cross reference {term}')
                            return term

            exclude_term = (exclude and term.lower() in exclude)

            if exclude_term:
                # Don't make a link for an excluded term.  Instead, check
                # for potential links in subsets of the term, then default
                # to returning the unmodified term.
                link = None
            else:
                link = self.get_link(term, True)

            if not link:
                # We can't find a link for the term (or it is excluded,
                # so we don't want to make a link for it.)  However,
                # a subset of the term might match a different glossary
                # entry.  So separate the last letter and try to link again.
                # This will perform the next-highest priority match if
                # possible.  If nothing changes, instead separate the first
                # letter and try to link again.  (Note that this doesn't
                # catch the case where a match could be made starting
                # inside the excluded term and extending beyond its end.
                # I doubt that would ever matter, and if it did we'd just
                # miss a link.  Not a big deal.)
                matchobj = re.match(r'(.*\W)(\w+)$', term)
                if matchobj:
                    term1 = matchobj.group(1)
                    term2 = matchobj.group(2)
                    alt_term = link_safe(term1) + link_safe(term2)
                    if alt_term != term:
                        link = alt_term

            if not link:
                matchobj = re.match(r'(\w+)(\W.*)$', term)
                if matchobj:
                    term1 = matchobj.group(1)
                    term2 = matchobj.group(2)
                    alt_term = link_safe(term1) + link_safe(term2)
                    if alt_term != term:
                        link = alt_term

            if link:
                return link
            elif exclude_term:
                return term
            else:
                error(f'{term} in {filename}',
                      prefix='Glossary term is used outside of its glossary hierarchy:')
                return term

        # Perform glossary substitution on a fragment of "safe text", i.e.
        # one without HTML tags or other complications.
        def link_safe(txt):
            return re.sub(glossary_regex, repl_glossary, txt)

        # Add glossary links in group 1, but leave group 2 unchanged.
        def repl_glossary_pair(matchobj):
            allowed = matchobj.group(1)
            disallowed = matchobj.group(2)
            allowed = link_safe(allowed)
            return allowed + disallowed

        # Find non-tagged text followed (optionally) by tagged text.
        # We'll perform glossary link insertion only on the non-tagged text.
        #
        # The first group (for non-tagged text) is non-greedy, but still starts
        # as soon as possible (i.e. at the beginning of the string or just after
        # the previous match).
        #
        # The second group (for tagged text) is also non-greedy, looking for the
        # shortest amount of text to close the link.  The second group either
        # starts with an opening tag and ends with a closing tag, or it matches
        # the end of the string (after matching the final non-tagged text).
        #
        # Tagged text is anything between link tags, <a>...</a>.
        # It also includes the URL in <a href="...">.  Anything between braces
        # {...} is also captured here.
        #
        # Within the glossary, tagged text also includes anything between
        # header tags, <h#>...</h#>.  Linking a header tag to the glossary is
        # fine in regular pages where the word may be unknown, but it looks
        # weird in the glossary where the word is defined right there.
        if is_glossary:
            # Don't replace any text between link tags <a>...</a>
            # (including the URL in <a href="...">) or between header tags
            # <h#>...</h#> or within a tag <...> or special syntax {...}. 
            # Linking a header tag to the glossary is fine in regular pages
            # where the word may be unknown, but it looks weird in the
            # glossary where the word is defined right there.
            sub_re = r'(.*?)(\Z|<(?:a\s|h\d).*?</(?:a|h\d)>|<\w.*?>|{.*?})'
        else:
            # Don't replace any text between link tags <a>...</a>
            # (including the URL in <a href="...">) or within a tag <...>
            # or special syntax {...}.
            sub_re = r'(.*?)(\Z|<a\s.*?</a>|<\w.*?>|{.*?})'

        # Perform the glossary link substitution for each non-tag/tag
        # pair throughout the entire multi-line txt string.
        txt = re.sub(sub_re, repl_glossary_pair, txt,
                     flags=re.DOTALL)

        return txt

    def get_short_name(self):
        if self.is_jepson:
            return 'Jepson'
        else:
            return re.sub(r' glossary$', '', self.name)

    def get_term_list(self):
        return iter(self.term_anchor.keys())

    def create_hierarchy_set(self):
        self.glossary_set = self.glossary_local_set
        parent = self.parent
        while parent:
            self.glossary_set = self.glossary_set.union(parent.glossary_local_set)
            parent = parent.parent

        self.glossary_set = self.glossary_set.union(glossary_cross_set)

    def record_terms(self, anchor, word_list):
        self.anchor_terms[anchor] = set()
        for word in word_list:
            word = easy_sub_safe(word.lower())
            self.term_anchor[word] = anchor
            self.anchor_terms[anchor].add(word)

    def read_terms(self):
        def repl_taxon(matchobj):
            name = matchobj.group(1)
            if name == 'flowering plants':
                # Special case since there is no page for flowering plants.
                self.taxon = name
            else:
                self.taxon = find_page1(name).name
            return ''

        def repl_defn(matchobj):
            words = matchobj.group(1)
            defn = matchobj.group(2)

            # Normalize the separator between all terms to a comma.
            comma_words = re.sub(r'\((.*)\)', r', \1', words)
            word_list = [x.strip() for x in comma_words.split(',')]
            anchor = word_list[0]

            matchobj = re.match(r'(.*\(.*\))', words) # not comma_words
            if matchobj:
                defined_term = easy_sub(matchobj.group(1))
            else:
                defined_term = easy_sub(anchor)

            self.search_terms.append(word_list)
            self.record_terms(anchor, word_list)
            self.anchor_defined[anchor] = defined_term
            return '{' + anchor + '} ' + defn

        with open(f'{root_path}/glossary/{self.name}.txt', mode='r') as f:
            self.txt = f.read()

        # Link figures prior to parsing glossary terms so that they're
        # properly recognized as not to be touched.
        self.txt = link_figures(self.name, self.txt)

        self.txt = re.sub(r'^taxon:\s*(.*?)\s*$',
                          repl_taxon, self.txt, flags=re.MULTILINE)

        # self.taxon is now either a name or (if unset) None.
        # Either value is appropriate for the term_anchor key.
        glossary_taxon_dict[self.taxon] = self

        glossary_name_dict[self.name] = self

        # Read definitions and modify them to avoid self-linking.
        self.txt = re.sub(r'^{([^\}]+)}\s+(.*)$',
                          repl_defn, self.txt, flags=re.MULTILINE)

    def read_jepson_terms(self):
        self.name = 'Jepson' # used only for self links from a glossary defn
        self.is_jepson = True
        self.used_dict = {}

        with open(f'{root_path}/data/jepson_glossary.txt', mode='r') as f:
            txt = f.read()
        for c in txt.split('\n'):
            # remove comments
            c = re.sub(r'\s*#.*$', '', c)

            if not c: # ignore blank lines (and comment-only lines)
                continue

            if c.startswith('-'):
                # I eventually want lines that start with '-' to be handled
                # in a special way, but for now I just ignore them.
                continue

            # Jepson's anchor is usually the whole text, including commas
            # and parentheses.  If there are additional terms I'd like to
            # associate with the entry, I've added them after a semicolon.
            anchor = re.sub(r'\s*;.*$', r'', c)

            # Normalize the separator between all terms to a comma.
            c = re.sub(r'\((.*)\)', r', \1', c)
            c = re.sub(r';', r',', c)
            word_list = [x.strip() for x in c.split(',')]

            self.search_terms.append(word_list)
            self.record_terms(anchor, word_list)

    def set_index(self):
        def by_name(glossary):
            return glossary.name

        self.index = len(glossary_list)
        glossary_list.append(self)
        for child in sorted(self.child, key=by_name):
            child.set_index()

    def write_toc(self, w, current):
        def by_name(glossary):
            return glossary.name

        if self == current:
            w.write(f'<b>{self.name}</b></br>')
        else:
            w.write(f'<a href="{self.name}.html">{self.name}</a></br>')

        if self.child:
            w.write('<div class="toc-indent">\n')
            for child in sorted(self.child, key=by_name):
                child.write_toc(w, current)
            w.write('</div>\n')

    def write_html(self):
        def repl_defns(matchobj):
            anchor = matchobj.group(1)
            defn = matchobj.group(2)

            # Add links to other glossaries where they define the same words.
            related_str = ''
            dup_list = jepson_glossary.find_dups(self, anchor)
            if dup_list:
                related_str = ' [' + ', '.join(dup_list) + ']'
            else:
                related_str = ''

            defined_term = self.anchor_defined[anchor]

            return f'<div class="defn" id="{anchor}"><dt>{defined_term}</dt><dd>{defn}{related_str}</dd></div>'

        self.txt = easy_sub(self.txt)

        # Link glossary words one line at a time because we want to take
        # special action on lines that define glossary words.
        c_list = []
        for c in self.txt.split('\n'):
            # Look for a glossary definition on the line.
            matchobj = re.match(r'^{([^\}]+)}\s+(.*)$', c)
            if matchobj:
                # Link glossary terms in the definition, but excluding any
                # terms being defined on this line.  Although it seems
                # intuitive to remove the excluded terms from glossary_regex,
                # recompiling the monster regex hundreds of times is a huge
                # performance hit.  Instead, we leave the regex alone and
                # handle the excluded terms as they are matched.
                anchor = matchobj.group(1)
                defn = matchobj.group(2)
                exclude_set = self.anchor_terms[anchor]
            else:
                exclude_set = None
            c = self.link_glossary_words(c, self.name,
                                         is_glossary=True,
                                         exclude=exclude_set)
            c_list.append(c)
        self.txt = '\n'.join(c_list)

        self.txt = re.sub(r'^{([^\}]+)}\s+(.*)$',
                          repl_defns, self.txt, flags=re.MULTILINE)

        with open(f'{working_path}/html/{self.name}.html', mode='w') as w:
              write_header(w, self.name, None, nospace=True)
              w.write('<h4 class="title">Glossary table of contents</h4>\n')
              master_glossary.write_toc(w, self)
              w.write(f'<a href="http://ucjeps.berkeley.edu/IJM_glossary.html">Jepson eFlora glossary</a>\n')
              w.write(f'<h1>{self.name}</h1>\n')
              w.write(self.txt)
              write_footer(w)

    # Write search terms for my glossaries to pages.js
    def write_search_terms(self, w):
        def by_name(glossary):
            return glossary.name

        # The glossary page without a named term can be treated just like
        # an unobserved (low-priority) page.  It's simply a link to an
        # HTML page with its name being the search term.
        w.write(f'{{page:"{self.name}",x:"u"}},\n')

        for term in self.search_terms:
            terms_str = '","'.join(term)
            w.write(f'{{idx:{self.index},com:["{terms_str}"],x:"g"}},\n')

        for child in sorted(self.child, key=by_name):
            child.write_search_terms(w)

    # Write search terms for Jepson's glossary to pages.js
    def write_jepson_search_terms(self, w):
        for term in self.search_terms:
            coms_str = '","'.join(term)
            anchor = self.term_anchor[term[0]]
            if term[0] == anchor:
                anchor_str = ''
            else:
                anchor_str = f',anchor:"{anchor}"'
            w.write(f'{{com:["{coms_str}"]{anchor_str},x:"j"}},\n')

        def by_usage(anchor):
            return self.used_dict[anchor]

        if len(sys.argv) > 1 and sys.argv[1] == 'j':
            # List the top 10 glossary terms that link to Jepson instead of
            # one of my glossaries, in order of number of references.
            anchor_list = sorted(self.used_dict, key=by_usage, reverse=True)
            for anchor in anchor_list[:10]:
                print(f'{anchor}: {self.used_dict[anchor]}')

###############################################################################
# end of Glossary class
###############################################################################

glossary_files = get_file_set('glossary', 'txt')
glossary_list = []
glossary_cross_set = set()

def create_regex():
    name_set = set()
    term_set = set()
    for glossary in glossary_list:
        name_set.add(glossary.get_short_name())
        term_set.update(glossary.get_term_list())
    name_set.add('none')

    name_ex = '(?:' + '|'.join(map(re.escape, name_set)) + ')'

    trie = Trie(term_set)
    term_ex = trie.get_pattern()

    # Construct the regex pattern to look for 'term' or 'name#term'.
    # We specifically exclude '...term#' because e.g. we don't want to match
    # 'pistillate flower' from the text 'pistillate flower#flower'.
    ex = rf'\b((?:{name_ex}#)?{term_ex})\b(?!#)'

    global glossary_regex
    glossary_regex = re.compile(ex, re.IGNORECASE)

def parse_glossaries(top_list):
    global master_glossary, flower_glossary, jepson_glossary

    for glossary_file in glossary_files:
        glossary = Glossary(glossary_file)
        glossary.read_terms()

    master_glossary = glossary_taxon_dict[None]
    flower_glossary = glossary_taxon_dict['flowering plants']
    flower_glossary.set_parent(master_glossary)

    jepson_glossary = Glossary('Jepson eFlora glossary')
    jepson_glossary.read_jepson_terms()
    master_glossary.set_parent(jepson_glossary)

    # Determine the primary glossary to use for each page *and*
    # determine the hierarchy among glossaries.
    for page in top_list:
        if page.top_level == 'flowering plants':
            page.set_glossary(flower_glossary)
        else:
            page.set_glossary(master_glossary)

    # Created an ordered list of the glossaries.  The purpose of this is
    # to allow a glossary to be referenced by its index number in page.js.
    # Note that the Jepson glossary is included in this list with index 0.
    # Other than the Jepson glossary, we index the glossaries in the same
    # order as they are listed in the glossary ToC, so a search for
    # "glossary" displays that same order.
    master_glossary.set_index()

    # Create a set of anchors of the form '{glossary}#{anchor}' which can be
    # used to link to a specific glossary.  This set includes every anchor in
    # every glossary.
    #jepson_glossary.create_local_set()
    #jepson_glossary.create_cross_set()
    #for glossary in glossary_list:
    #    glossary.create_local_set()
    #    glossary.create_cross_set()

    # Now that we know the glossary hierarchy, we can apply glossary links
    # within each glossary and finally write out the HTML.
    create_regex()
    error_begin_section()
    for glossary in glossary_list:
        glossary.write_html()
    error_end_section()

def write_glossary_search_terms(w):
    master_glossary.write_search_terms(w)
    jepson_glossary.write_jepson_search_terms(w)
