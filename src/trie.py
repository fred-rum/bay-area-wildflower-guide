# Create a regex pattern out of a set of strings.
# The corresponding regex is much faster than a simple regex union.

# original source:
# https://stackoverflow.com/questions/42742810/speed-up-millions-of-regex-replacements-in-python-3/42789508#42789508
# https://gist.github.com/EricDuminil/8faabc2f3de82b24e5a371b6dc0fd1e0
# I added comments, improved variable names, and made it more 'Python'.

import re

# Add a single string (term) to a trie dictionary.
def _add(trie, term):
    ref = trie
    for char in term:
        if char not in ref:
            # Create a new sub-trie for the character.
            ref[char] = {}
        else:
            # There is already a sub-trie for the character.
            pass
        # Recurse into the sub-trie.
        ref = ref[char]

    # A char of '' indicates that a term completes here.
    # Note that other terms may continue from the same ref point.
    ref[''] = None

# Remove a single string (term) from a trie dictionary.
# This assumes that the term is present in the trie.  If not, it will crash.
def _remove(trie, term):
    if term:
        # Recurse into the trie until we reach the trie position corresponding
        # to the of the term.
        char = term[0]
        _remove(trie[char], term[1:])

        # If trie[char] is now empty, it's because the deleted term was the
        # only way to reach it.  In that case, delete it.
        if not trie[char]:
            del trie[char]
    else:
        del trie['']

# Create a regex-type string that matches the trie (or sub-trie) argument.
def _pattern(trie):
    if '' in trie and len(trie.keys()) == 1:
        # No term continues past this point.
        return None

    smpl = [] # simple cases in which a single character ends the term
    cplx = [] # complex cases in which the term continues for > 1 character
    for char in sorted(trie.keys()):
        if char != '': # ignore terminator
            recurse = _pattern(trie[char])
            if recurse is None:
                smpl.append(re.escape(char))
            else:
                cplx.append(re.escape(char) + recurse)
    smpl_only = (len(cplx) == 0)

    # Add a single character or a character set to the end of the
    # complex pattern.  (The order doesn't matter since the characters
    # in the simple pattern are different than those that start the
    # complex patterns.)
    if len(smpl) == 1:
        cplx.append(smpl[0])
    elif len(smpl) > 1:
        cplx.append('[' + ''.join(smpl) + ']')

    if len(cplx) == 1:
        result = cplx[0]
    else:
        result = "(?:" + "|".join(cplx) + ")"

    if '' in trie:
        # A term is allowed to end here.
        # Append a ? to the set of alternative, longer endings
        # to signify "or none of the preceding endings".
        # Note that greedy matching will prefer the longer endings,
        # which is what we want.
        if smpl_only or len(cplx) > 1:
            # This works correctly for the following cases:
            #   the pattern is a single character, e.g. 'c'
            #   the pattern is a range of characters, e.g. '[ach]'
            #   the pattern is a union of patterns, e.g. '(?:es?|[ach])'
            result += "?"
        else:
            # A single complex pattern is by default not surrounded
            # by parentheses, so the '?' would match the wrong amount.
            result = f'(?:{result})?'
    return result

class Trie:
    def __init__(self, term_set=None):
        self.trie = {}
        if term_set:
            self.add(term_set)

    # Add one or more terms to the trie object.
    def add(self, term_set):
        for term in term_set:
            _add(self.trie, term)

    # Remove one or more terms to the trie object.
    # * This function isn't used in the current code, but I hesitate to remove
    # it since it's been tested.
    def remove(self, term_set):
        for term in term_set:
            _remove(self.trie, term)

    # Create a regex pattern from the trie.  (a string, not an actual regex.)
    def get_pattern(self):
        return _pattern(self.trie)
