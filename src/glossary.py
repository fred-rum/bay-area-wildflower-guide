import re
from operator import attrgetter

# My files
from args import *
from error import *
from files import *
from find_page import *
from easy import *
from trie import *
from parse import *
from cache import *

glossary_taxon_dict = {}

class Glossary:
    pass

    def __init__(self, name):
        self.name = name

        # user-visible name of this glossary's coverage
        # (defaults to its top-level taxon)
        self.title = None

        # name of this glossary's top-level taxon
        # (or None, if it includes all taxons)
        self.taxon = None

        # top page used by this glossary (or None, if it applies to all pages)
        self.page = None

        self.parent = None # a single parent glossary (or None)
        self.child = set() # an unordered set of child glossaries

        self.is_jepson = False # changed to True for the Jepson glossary

        # changed to True for a glossary that shouldn't appear in the ToC
        self.invisible = False

        # search_terms is an ordered list of term lists to be written
        # to pages.js.  The first term in each list is also the anchor.
        #
        # The anchor and all other terms are unmodified:
        # - capitalization is retained for optimal display in auto-complete.
        # - easy_sub is not applied because it would confuse search matching.
        #   (And the original punctuation can match any user punctuation.)
        self.search_terms = []

        # term_anchor is a mapping from each term to an HTML anchor.
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

        # anchor_list is a list of anchors, in glossary order.
        # It is only used with arg -jepson_usage.
        self.anchor_list = []

        # figure_list is a list of filenames for figures used in the
        # glossary page.
        self.figure_list = []

    def set_parent(self, parent):
        self.parent = parent
        if parent:
            parent.child.add(self)

    def get_link_class(self):
        if self.is_jepson:
            return 'glossary-jepson'
        else:
            return 'glossary'

    def get_filename(self):
        no_spaces = re.sub(r' ', '-', self.name)
        return filename(no_spaces)

    def get_url(self):
        if self.is_jepson:
            return 'https://ucjeps.berkeley.edu/eflora/glossary.html'
        else:
            pageurl = url(self.get_filename())
            return f'{pageurl}.html'

    def create_link(self):
        link_class = self.get_link_class()
        pageurl = self.get_url()
        return f'<a href="{pageurl}" class="{link_class}">{self.name}</a>'

    def glossary_link(self, anchor, term):
        link_class = self.get_link_class()
        pageurl = self.get_url()
        anchorurl = url(anchor)
        return f'<a class="{link_class}" href="{pageurl}#{anchorurl}">{term}</a>'

    def find_dups(self, term):
        dup_list = []

        # Find ancestors of this glossary that define the same term.
        ancestor = self.parent
        while ancestor:
            if term in ancestor.term_anchor:
                link = ancestor.glossary_link(ancestor.term_anchor[term],
                                              ancestor.name)
                dup_list.append(link)

            ancestor = ancestor.parent

        # We built the list of shared ancestors from lowest ancestor to
        # highest ancestor, but we want the full dup_list to be from
        # highest glossary to lowest.
        dup_list.reverse()

        for child in sorted(self.child, key=attrgetter('name')):
            dup_list.extend(child.find_dups_in_children(term))

        return dup_list

    def find_dups_in_children(self, term):
        dup_list = []

        if term in self.term_anchor:
            link = self.glossary_link(self.term_anchor[term], self.name)
            dup_list.append(link)

        for child in sorted(self.child, key=attrgetter('name')):
            dup_list.extend(child.find_dups_in_children(term))

        return dup_list

    # For the given term, get a link within the glossary or its ancestors.
    # Search ancestors only when deep=True.
    # Return None if the term isn't in the glossary (or its ancestors).
    def get_link(self, term, is_glossary, deep, child=None):
        lower = term.lower()
        if lower in self.link_set:
            anchor = self.term_anchor[lower]
            if self.is_jepson:
                if anchor in self.used_dict:
                    self.used_dict[anchor] += 1
                else:
                    self.used_dict[anchor] = 1
            return self.glossary_link(anchor, term)
        elif deep and self.parent:
            return self.parent.get_link(term, is_glossary, True, child=self)
        else:
            return None

    def link_glossary_words(self, assoc_name, assoc_page, txt,
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
                    error(f'unrecognized glossary cross reference starting with "{name}#" in {assoc_name}')
                    return f'{name}#broken ref'
                elif name == 'none':
                    # 'none#[term]' means that we don't want a glossary link.
                    # Discard the 'none#' and return only the bare term.
                    return bare_term
                else:
                    glossary = glossary_name_dict[name + ' glossary']
                    link = glossary.get_link(bare_term, is_glossary, False)
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
                            if not term1.endswith('#'):
                                alt_term = link_safe(term1) + link_safe(term2)
                                if alt_term != term:
                                    link = alt_term

                        if link:
                            return alt_term
                        else:
                            error(f'bad glossary cross reference {term}')
                            return term

            # Continue for the default case without a '#' cross-ref.

            exclude_term = (exclude and term.lower() in exclude)

            if exclude_term:
                # Don't make a link for an excluded term.  Instead, check
                # for potential links in subsets of the term, then default
                # to returning the unmodified term.
                link = None
            else:
                link = self.get_link(term, is_glossary, True)

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
            if not link:
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
                # Term not found in the applicable glossaries.
                # Check whether the term is in any of the glossaries for which
                # a warning should be printed.
                if assoc_page:
                    for glossary in assoc_page.glossary_warn:
                        if term.lower() in glossary.link_set:
                            error(f'{term} in {assoc_name}',
                                  prefix='Glossary term is used outside of its glossary hierarchy:')
                            break
                return term

        # Perform glossary substitution on a fragment of "safe text", i.e.
        # one without HTML tags or other complications.
        def link_safe(txt):
            return glossary_regex.sub(repl_glossary, txt)

        # Add glossary links in group 1, but leave group 2 unchanged.
        def repl_glossary_pair(matchobj):
            safe = matchobj.group(1)
            unsafe = matchobj.group(2)
            return link_safe(safe) + unsafe

        # Find safe text followed (optionally) by unsafe text.
        # We'll perform glossary link insertion only on the safe text.
        #
        # The first group (for safe text) starts as soon as possible
        # (i.e. at the beginning of the string or just after the previous
        # match), but it has a non-greedy end so that it ends before anything
        # that matches the second group.
        #
        # The second group (for unsafe text) is also non-greedy, looking for the
        # shortest amount of text to close the link.  The second group either
        # starts with an opening tag and ends with a closing tag, or it matches
        # the end of the string (after matching the final safe text).
        #
        # Unsafe text includes anything within a tag itself, <...>.  Because
        # my HTML is sloppy with less-than/greater-than signs that technically
        # ought to be escaped, I actually look for a tag starting with a
        # letter, e.g. <a...>.  This misses closing tags (e.g. </a>), but
        # those have a limited enough scope that I can be comfortable that
        # they'll never match a glossary word.
        # 
        # Unsafe text also includes anything between link tags, <a>...</a>.
        # Text between these tags is already linked to something, so trying
        # to add another link to the glossary would be dumb.
        #
        # Term lists and child links in braces have already been dealt with
        # before link_glossary() is called, so we don't need to recognize
        # braces as a type of unsafe text.
        #
        # Within the glossary, unsafe text also includes anything between
        # header tags, <h#>...</h#>.  Linking header text to the glossary is
        # fine in regular pages where the word may be unknown, but it looks
        # weird in the glossary where the word is defined right there.
        if is_glossary:
            sub_re = r'(.*?)(\Z|<(?:a\s|h\d).*?</(?:a|h\d)>|<\w.*?>|{.*?})'
        else:
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

    def record_terms(self, anchor, word_list):
        self.anchor_terms[anchor] = set()
        for word in word_list:
            word = easy_sub_safe(word.lower())
            self.term_anchor[word] = anchor
            self.anchor_terms[anchor].add(word)

    def parse_terms(self, txt):
        def repl_defn(matchobj):
            words = matchobj.group(1)

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
            self.anchor_list.append(anchor)
            return '{' + anchor + '}'

        def repl_warn(matchobj):
            name = matchobj.group(1)
            page = find_page1(name)
            if page:
                page.glossary_warn.add(self)
            else:
                error(f'No page found for glossary warn:{name}')
            return ''

        # self.taxon is now a page name or None.
        # Any of these values is appropriate for the glossary_taxon_dict key.
        glossary_taxon_dict[self.taxon] = self

        glossary_name_dict[self.name] = self

        # Read declarations of glossary terms and replace each set
        # with a bare {anchor}.
        txt = re.sub(r'^{([^-].*?)}',
                     repl_defn, txt, flags=re.MULTILINE)

        # For my glossaries, no words are excluded.
        self.link_set = set(self.term_anchor.keys())

        # Add the glossary and its terms to the top-level sets.
        short_name = re.sub(r' glossary$', '', self.name)
        name_set.add(short_name)
        term_set.update(self.link_set)

        # Set a flag to print a warning if a word from this glossary is
        # used in some other named taxon hierarchy.
        txt = re.sub(r'^warn:\s*(.*?)\s*$',
                     repl_warn, txt, flags=re.MULTILINE)

        return txt

    def set_taxon(self, name):
        page = find_page1(name)
        if page:
            self.page = page
            self.taxon = page.name
        else:
            error(f'No page found for glossary taxon {name}')
        if not self.title:
            self.title = self.taxon

    def read_terms(self):
        def repl_taxon(matchobj):
            self.set_taxon(matchobj.group(1))
            return ''

        def repl_title(matchobj):
            self.title = matchobj.group(1)
            return ''

        with open(f'{root_path}/glossary/{self.name}.txt', mode='r') as f:
            self.txt = f.read()

        self.txt = re.sub(r'^taxon:\s*(.*?)\s*$',
                          repl_taxon, self.txt, flags=re.MULTILINE)

        self.txt = re.sub(r'^title:\s*(.*?)\s*$',
                          repl_title, self.txt, flags=re.MULTILINE)

        self.txt = self.parse_terms(self.txt)

    def read_jepson_terms(self, f):
        self.name = 'Jepson' # used only for self links from a glossary defn
        self.is_jepson = True
        self.invisible = True
        self.used_dict = {}
        self.link_set = set()
        self.txt = None # No associated HTML

        txt = f.read()
        for c in txt.split('\n'):
            # remove comments
            c = re.sub(r'\s*#.*$', '', c)

            if not c: # ignore blank lines (and comment-only lines)
                continue

            matchobj = re.match(r'taxon:\s*(.*?)\s*$', c)
            if matchobj:
                self.set_taxon(matchobj.group(1))
                continue

            if c.startswith('-'):
                dont_link = True
                c = c[1:]
            else:
                dont_link = False

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

            if not dont_link:
                for term in word_list:
                    # Don't allow a word to link to Jepson if it is defined
                    # in any of my glossaries.  Thus, if a term is used at the
                    # wrong level of hierarchy, we flag an error instead.
                    # Note that term_set was previously populated from my
                    # glossaries in read_terms().
                    if term not in term_set:
                        self.link_set.add(term)

        # Add the glossary and its terms to the top-level sets.
        short_name = re.sub(r' glossary$', '', self.name)
        name_set.add('Jepson')
        term_set.update(self.link_set)

    def init_master(self):
        self.name = 'master'
        self.invisible = True
        self.link_set = set()
        self.txt = None # No associated HTML

    # return True if self is the check_glossary is the same as self or
    # is an ancestor of self.
    def has_ancestor(self, check_glossary):
        while check_glossary:
            if check_glossary == self:
                return True
            check_glossary = check_glossary.parent
        return False

    def write_toc(self, w, current):
        if self.invisible:
            # Write nothing for the jepson glossary,
            # but continue into its children.
            pass
        elif self == current:
            w.write(f'<b>{self.title}</b><br>')
        else:
            pageurl = self.get_url()
            w.write(f'<a href="{pageurl}">{self.title}</a><br>')

        if self.child:
            if not self.invisible:
                w.write('<div class="toc-indent">\n')

            for child in sorted(self.child, key=attrgetter('name')):
                child.write_toc(w, current)

            if not self.invisible:
                w.write('</div>\n')

    # link_glossary() is called for each paragraph of txt.
    def link_glossary_words_or_defn(self, assoc_name, assoc_page, c,
                                    is_glossary):
        # Check if the paragraph is a glossary definition.
        matchobj = re.match(r'{([^-].*?)}\s+(.*)$', c, flags=re.DOTALL)
        if matchobj:
            anchor = matchobj.group(1)
            defn = matchobj.group(2)

            # Link glossary terms in the definition, but excluding any
            # terms being defined on this line.  Although it seems
            # intuitive to remove the excluded terms from glossary_regex,
            # recompiling the monster regex hundreds of times is a huge
            # performance hit.  Instead, we leave the regex alone and
            # handle the excluded terms as they are matched.
            exclude_set = self.anchor_terms[anchor]
            defn = self.link_glossary_words(assoc_name, assoc_page, defn,
                                            is_glossary=False,
                                            exclude=exclude_set)

            # Add links to other glossaries
            # where they define the same words.
            related_str = ''
            dup_list = self.find_dups(anchor)
            if dup_list:
                related_str = ' [' + ', '.join(dup_list) + ']'
            else:
                related_str = ''

            defined_term = self.anchor_defined[anchor]

            anchorurl = url(anchor)
            if is_glossary:
                # Discard the normal <p> tag when constructing a definition
                # within a glossary page.  The definition is surrounded by a
                # div so that both the <dt> and <dd> contents get highlighted.
                return f'<div class="defn" id="{anchorurl}"><dt>{defined_term}</dt><dd>{defn}{related_str}</dd></div>'
            else:
                # Modify the <p> tag to give it an anchor that can be linked
                # to (and highlighed when targeted).
                p_tag = f'<p class="defn" id="{anchorurl}">'
                return f'{p_tag}{defn}{related_str}</p>'
        else:
            # It's not a definition line, so just link glossary words
            # normally within the line.
            c = self.link_glossary_words(assoc_name, assoc_page, c,
                                         is_glossary=False)
            return f'<p>{c}</p>'

    def write_html(self):
        # There are sources of data for glossaries:
        #   - from its own glossary txt file
        #   - from glossary declarations within a taxon page's txt file
        #   - from the Jepson term list
        # Only the first of these should create its own HTML file.
        if self.txt:
            self.txt = parse_txt(self.name, self.txt, None, self)

            with write_and_hash(f'html/{self.get_filename()}.html') as w:
                if self.taxon:
                    desc = f'Glossary of terms used for {self.taxon} in the Bay Area Wildflower Guide.'
                else:
                    desc = f'Glossary of terms used in the Bay Area Wildflower Guide.'
                write_header(w, self.name, None, desc=desc)
                w.write('<h4 id="title">Glossary table of contents</h4>\n')
                master_glossary.write_toc(w, self)
                w.write(f'<a href="http://ucjeps.berkeley.edu/IJM_glossary.html">Jepson eFlora</a>\n')
                w.write(f'<h1>{self.name}</h1>\n')
                w.write(self.txt)
                write_footer(w)

        for child in sorted(self.child, key=attrgetter('name')):
            child.write_html()

    # Write search terms for my glossaries to pages.js
    def write_search_terms(self, w):
        if not self.invisible:
            w.write(f'{{page:"{self.name}",com:["{self.title}"],x:"g",glossary:[\n')
            for term in self.search_terms:
                terms_str = '","'.join(term)
                w.write(f'{{terms:["{terms_str}"]}},\n')
            w.write(f']}},\n')

        for child in sorted(self.child, key=attrgetter('name')):
            child.write_search_terms(w)

    # Write filenames of figures used in my glossaries to photos.js
    def write_figures(self, w):
        if not self.invisible and self.figure_list:
            figure_list = '","'.join(self.figure_list);
            w.write(f'["{self.name}","{figure_list}"],\n')

        for child in sorted(self.child, key=attrgetter('name')):
            child.write_figures(w)

    # Write search terms for Jepson's glossary to pages.js
    def write_jepson_search_terms(self, w):
        w.write('{page:"Jepson eFlora",com:["Jepson eFlora"],x:"j",glossary:[\n')
        for term in self.search_terms:
            terms_str = '","'.join(term)
            anchor = self.term_anchor[term[0]]
            if term[0] == anchor:
                anchor_str = ''
            else:
                anchor_str = f',anchor:"{anchor}"'
            w.write(f'{{terms:["{terms_str}"]{anchor_str}}},\n')
        w.write(']},\n')

        if arg('-jepson_usage'):
            # List the top 10 glossary terms that link to Jepson instead of
            # one of my glossaries, in order of number of references.
            anchor_list = sorted(self.used_dict, key=self.used_dict.get,
                                 reverse=True)
            for anchor in anchor_list[:10]:
                print(f'{anchor}: {self.used_dict[anchor]}')

###############################################################################
# end of Glossary class
###############################################################################

glossary_files = get_file_set('glossary', 'txt')

# name_set is the set of short glossary names that is used to support
# cross-references of the form <short_glossary_name>#<term>
name_set = set()

# 'none' is not a real glossary, but the cross reference 'none#[term]'
# may be used to prevent glossary references
name_set.add('none')

# term_set is the union of terms used in all glossaries
term_set = set()

def create_regex():
    name_ex = '(?:' + '|'.join(map(re.escape, name_set)) + ')'

    trie = Trie(term_set)
    term_ex = trie.get_pattern()

    # Construct the regex pattern to look for 'term' or 'name#term'.
    # We specifically exclude '...term#' because e.g. we don't want to match
    # 'pistillate flower' from the text 'pistillate flower#flower'.
    ex = rf'\b((?:{name_ex}#)?{term_ex}|(?:{name_ex}#))\b(?!#)'

    global glossary_regex
    glossary_regex = re.compile(ex, re.IGNORECASE)

def parse_glossaries(top_list):
    global master_glossary, jepson_glossary

    for glossary_file in glossary_files:
        glossary = Glossary(glossary_file)
        glossary.read_terms()

    jepson_glossary = Glossary('Jepson eFlora glossary')
    read_data_file('jepson_glossary.txt', jepson_glossary.read_jepson_terms)
    if not jepson_glossary.is_jepson:
        # We failed to read the file.  Let's make it super clear that the
        # Jepson glossary can't be used.
        jepson_glossary = None

    if jepson_glossary and jepson_glossary.taxon == None:
        master_glossary = jepson_glossary

        if None in glossary_taxon_dict:
            top_glossary = glossary_taxon_dict[None]
            top_glossary.set_parent(jepson_glossary)
    elif None in glossary_taxon_dict:
        master_glossary = glossary_taxon_dict[None]
        top_glossary = master_glossary
    else:
        master_glossary = Glossary('master glossary')
        master_glossary.init_master()
        top_glossary = master_glossary

    # Determine the primary glossary to use for each page *and*
    # determine the hierarchy among glossaries.
    for page in top_list:
        page.set_glossary(top_glossary, jepson_glossary, set())

    # Now that we know the glossary hierarchy, we can apply glossary links
    # within each glossary and finally write out the glossary HTML.
    create_regex()
    error_begin_section()
    master_glossary.write_html()
    error_end_section()

def write_glossary_search_terms(w):
    master_glossary.write_search_terms(w)

    if jepson_glossary:
        jepson_glossary.write_jepson_search_terms(w)

def write_glossary_figures(w):
    master_glossary.write_figures(w)
