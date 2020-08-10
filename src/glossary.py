import re

# My files
from files import *
from find_page import *
from easy import *
from trie import *

glossary_taxon_dict = {}
glossary_title_dict = {}

class Glossary:
    pass

    def __init__(self, name):
        self.name = name
        self.title = None
        self.taxon = None
        self.parent = None # a single parent glossary (or None)
        self.child = set() # an unordered set of child glossaries
        self.term = [] # an ordered list of term lists
        self.glossary_dict = {} # mapping of term to anchor
        self.is_jepson = False

    def set_parent(self, parent):
        self.parent = parent
        parent.child.add(self)

    def glossary_link(self, anchor, term):
        if self.is_jepson:
            return f'<a class="glossary-jepson" href="https://ucjeps.berkeley.edu/eflora/glossary.html#{anchor}">{term}</a>'
        else:
            return f'<a class="glossary" href="{self.name}.html#{anchor}">{term}</a>'

    def find_dups(self, skip_glossary, term):
        def by_name(glossary):
            return glossary.title

        dup_list = []
        if self != skip_glossary and term in self.glossary_dict:
            dup_list.append(self.glossary_link(self.glossary_dict[term],
                                               self.title))

        for child in sorted(self.child, key=by_name):
            dup_list.extend(child.find_dups(skip_glossary, term))

        return dup_list

    def get_link(self, term):
        if '#' in term:
            (name, partition, term) = term.partition('#')
            if term == '':
                # I'd love to print what file this error occured in, but
                # that requires an exception or a global variable or passing
                # more data around, none of which I like.  The user will just
                # have to grep for the broken reference in the HTML.
                print(f'unrecognized glossary cross reference starting with "{name}#')
                return f'{name}#broken ref'
            elif name == 'none':
                # 'none#[term]' means that we don't want a glossary link.
                # Discard the 'none#' and return only the term.
                return term
            else:
                return glossary_title_dict[name + ' glossary'].get_link(term)

        lower = term.lower()
        if lower in self.glossary_dict:
            anchor = self.glossary_dict[lower]
            if self.is_jepson:
                if anchor in self.used_dict:
                    self.used_dict[anchor] += 1
                else:
                    self.used_dict[anchor] = 1
            return self.glossary_link(anchor, term)
        else:
            return self.parent.get_link(term)

    def link_glossary_words(self, txt, is_glossary=False):
        # This function is called for a glossary word match.
        # Replace the matched word with a link to the primary term
        # in the glossary.
        def repl_glossary(matchobj):
            term = matchobj.group(1)
            return self.get_link(term)

        # Add glossary links in group 1, but leave group 2 unchanged.
        def repl_glossary_pair(matchobj):
            allowed = matchobj.group(1)
            disallowed = matchobj.group(2)
            allowed = re.sub(self.glossary_regex, repl_glossary, allowed)
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

    def create_cross_set(self):
        if self.is_jepson:
            short_name = 'Jepson'
        else:
            short_name = re.sub(r' glossary$', '', self.title)

        for anchor in self.glossary_dict.keys():
            # Create a glossary entry tied to a specific glossary.
            glossary_cross_set.add(f'{short_name}#{anchor}')

            # Also create an entry tied to no glossary.  If this gets matched,
            # it prevents the creation of a glossary link.  Note that multiple
            # glossaries might create the same entry, but the set removes
            # duplicates, and they all behave the same.
            glossary_cross_set.add(f'none#{anchor}')

        # Also include entries with no term listed.  This gets matched if
        # the intended link doesn't exist, and thus an error can be flagged.
        # Note that this matches only at a word boundary, meaning that there
        # is a word immediately following the #, which is what we expect.
        glossary_cross_set.add(f'{short_name}#')
        glossary_cross_set.add('none#')


    def create_local_set(self):
        self.glossary_local_set = set(iter(self.glossary_dict.keys()))

    def create_hierarchy_set(self):
        self.glossary_set = self.glossary_local_set
        parent = self.parent
        while parent:
            self.glossary_set = self.glossary_set.union(parent.glossary_local_set)
            parent = parent.parent

        self.glossary_set = self.glossary_set.union(glossary_cross_set)

    def create_regex_old(self):
        # sort the glossary list in reverse order so that for cases where two
        # phrases start the same and one is a subset of the other, the longer
        # phrase is checked first.  (This relies on the fact that expression
        # checking is done primarily in order through the searched text, and
        # secondarily in order through the regex.)
        glossary_list = sorted(iter(self.glossary_set), reverse=True)

        ex = '|'.join(map(re.escape, glossary_list))
        self.glossary_regex = re.compile(rf'\b({ex})\b', re.IGNORECASE)

    def create_regex(self):
        ex = trie_pattern(self.glossary_set)
        self.glossary_regex = re.compile(rf'\b({ex})\b', re.IGNORECASE)

    def record_in_glossary_dict(self, anchor, word):
        word = easy_sub_safe(word.lower())
        self.glossary_dict[word] = anchor

    def read_terms(self):
        def repl_title(matchobj):
            self.title = matchobj.group(1)
            glossary_title_dict[self.title] = self
            return ''

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
            word_list = [x.strip() for x in words.split(',')]
            anchor = word_list[0]
            self.term.append(word_list)
            for word in word_list:
                self.record_in_glossary_dict(anchor, word)
                # Prevent a glossary definition from linking the terms
                # it is currently defining, either to its own
                # definition or to a higher-level glossary.
                # (Higher-level glossary links will be added later.)
                # We do this by prepending 'glossaryX' to any
                # occurance of the defined terms in the definition.
                # We'll remove this after glossary links are created.
                defn = re.sub(r'\b' + word + r'\b', 'glossaryX' + word, defn,
                              re.IGNORECASE)
            return '{' + words + '} ' + defn

        with open(f'{root_path}/glossary/{self.name}.txt', mode='r') as f:
            self.txt = f.read()

        # Link figures prior to parsing glossary terms so that they're
        # properly recognized as not to be touched.
        self.txt = link_figures(self.name, self.txt)

        self.txt = re.sub(r'^title:\s*(.*?)\s*$',
                          repl_title, self.txt, flags=re.MULTILINE)
        self.txt = re.sub(r'^taxon:\s*(.*?)\s*$',
                          repl_taxon, self.txt, flags=re.MULTILINE)

        # self.taxon is now either a name or (if unset) None.
        # Either value is appropriate for the glossary_dict key.
        glossary_taxon_dict[self.taxon] = self

        if not self.title:
            print(f'title not defind for glossary "{self.name}"')
            self.title = 'unknown glossary'

        # Read definitions and modify them to avoid self-linking.
        self.txt = re.sub(r'^{([^\}]+)}\s+(.*)$',
                          repl_defn, self.txt, flags=re.MULTILINE)

    def read_jepson_terms(self):
        self.title = 'Jepson' # used only self links from a glossary definition
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

            self.term.append(word_list)
            for word in word_list:
                self.record_in_glossary_dict(anchor, word)

    def set_index(self):
        def by_name(glossary):
            return glossary.title

        self.index = len(glossary_list)
        glossary_list.append(self)
        for child in sorted(self.child, key=by_name):
            child.set_index()

    def write_toc(self, w, current):
        def by_name(glossary):
            return glossary.title

        if self == current:
            w.write(f'<b>{self.title}</b></br>')
        else:
            w.write(f'<a href="{self.name}.html">{self.title}</a></br>')

        if self.child:
            w.write('<div class="toc-indent">\n')
            for child in sorted(self.child, key=by_name):
                child.write_toc(w, current)
            w.write('</div>\n')

    def write_html(self):
        def repl_defns(matchobj):
            words = matchobj.group(1)
            defn = matchobj.group(2)

            word_list = [x.strip() for x in words.split(',')]
            anchor = word_list[0]

            # Add links to other glossaries where they define the same words.
            related_str = ''
            dup_list = jepson_glossary.find_dups(self, anchor)
            if dup_list:
                related_str = ' [' + ', '.join(dup_list) + ']'
            else:
                related_str = ''

            return f'<div class="defn" id="{anchor}"><dt>{anchor}</dt><dd>{defn}{related_str}</dd></div>'

        self.txt = easy_sub(self.txt)

        self.txt = self.link_glossary_words(self.txt, is_glossary=True)

        # Remove the inserted 'glossaryX' text to return the (unlinked)
        # glossary terms to their normal text.
        self.txt = re.sub(r'glossaryX', '', self.txt)

        self.txt = re.sub(r'^{([^\}]+)}\s+(.*)$',
                          repl_defns, self.txt, flags=re.MULTILINE)

        with open(f'{root_path}/html/{self.name}.html', mode='w') as w:
              write_header(w, self.title, None, nospace=True)
              w.write('<h4 class="title">Glossary table of contents</h4>\n')
              master_glossary.write_toc(w, self)
              w.write(f'<a href="http://ucjeps.berkeley.edu/IJM_glossary.html">Jepson eFlora glossary</a>')
              w.write(f'<h1>{self.title}</h1>\n')
              w.write(self.txt)
              write_footer(w)

    # Write search terms for my glossaries to pages.js
    def write_search_terms(self, w):
        def by_name(glossary):
            return glossary.title

        # The glossary page without a named term can be treated just like
        # an unobserved (low-priority) page.  It's simply a link to an
        # HTML page with its name being the search term.
        w.write(f'{{page:"{self.name}",x:"u"}},\n')

        for term in self.term:
            terms_str = '","'.join(term)
            w.write(f'{{idx:{self.index},com:["{terms_str}"],x:"g"}},\n')

        for child in sorted(self.child, key=by_name):
            child.write_search_terms(w)

    # Write search terms for Jepson's glossary to pages.js
    def write_jepson_search_terms(self, w):
        for term in self.term:
            coms_str = '","'.join(term)
            anchor = self.glossary_dict[term[0]]
            if term[0] == anchor:
                anchor_str = ''
            else:
                anchor_str = f',anchor:"{anchor}"'
            w.write(f'{{com:["{coms_str}"]{anchor_str},x:"j"}},\n')

        def by_usage(anchor):
            return self.used_dict[anchor]

        if len(sys.argv) > 2 and sys.argv[2] == 'j':
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

    # Create a set of anchors of the form '{glossary}:{anchor}' which can be
    # used to link to a specific glossary.  This set includes every anchor in
    # every glossary.
    jepson_glossary.create_local_set()
    jepson_glossary.create_cross_set()
    for glossary in glossary_list:
        glossary.create_local_set()
        glossary.create_cross_set()

    # Now that we know the glossary hierarchy, we can apply glossary links
    # within each glossary and finally write out the HTML.
    for glossary in glossary_list:
        glossary.create_hierarchy_set()
        glossary.create_regex()
        glossary.write_html()

def write_glossary_search_terms(w):
    master_glossary.write_search_terms(w)
    jepson_glossary.write_jepson_search_terms(w)
