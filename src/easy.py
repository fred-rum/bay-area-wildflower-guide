# Make easy substitutions in the text, such as "+-" and smart quotes.
# Do this before glossary substitutions because the HTML added for
# glossary links confuses the heuristic for smart-quote direction.

import re

_repl_easy_dict = {
    # Replace common Jepson codes.
    '+-' : '&plusmn;',
    '--' : '&ndash;',
    '<=' : '&le;',
    '>=' : '&ge;',
    '<<' : '&#8810',
    '>>' : '&#8811',

    "'"  : '&rsquo;',
    '"'  : '&rdquo;',

    # '<' and '>' should be escaped, but for now I'll leave them alone
    # because the browser seems to figure them out correctly, and it's
    # probably smarter about it than I would be.
}

_ex = '|'.join(map(re.escape, list(_repl_easy_dict.keys())))
_repl_easy_regex = re.compile(f'({_ex})')

def repl_easy(matchobj):
    return _repl_easy_dict[matchobj.group(1)]

# Make the easy substitutions without worrying about HTML tags or
# special txt syntax.  I.e. this should only be called on a text
# snippet which is already guaranteed to be safe.
def easy_sub_safe(txt):
    # I assume that I only use double-quotes to quote a passage
    # of text.  If I try to do something similar for single-quotes,
    # I could use the wrong smart quote for something like the '80s.
    txt = re.sub(r'(?<![\w.,])"|\A"', r'&ldquo;', txt)
    txt = _repl_easy_regex.sub(repl_easy, txt)
    return txt

# Perform easy substitutions in group 1, but leave group 2 unchanged.
def _repl_easy_pair(matchobj):
    allowed = matchobj.group(1)
    disallowed = matchobj.group(2)
    return easy_sub_safe(allowed) + disallowed

# Make the easy substitutions while carefully *not* changing anything
# within an HTML tag <...> or special txt syntax {...}.
def easy_sub(txt):
    # Note that a tag is assumed to start with a word character, e.g. "<a".
    # Thus, we won't get thrown off by a non-tag angle bracket such as "< "
    # or "<=".
    sub_re = r'(.*?)(\Z|<\w.*?>|{.*?})'

    # Perform the easy substitution for each non-tag/tag
    # pair throughout the entire multi-line txt string.
    return re.sub(sub_re, _repl_easy_pair, txt,
                  flags=re.DOTALL)
