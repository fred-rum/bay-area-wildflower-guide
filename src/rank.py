from enum import Enum, auto

internal_ranks = (
    'below',
    'species',
    'complex',
    'subsection', 'section',
    'subgenus', 'genus',
    'subtribe', 'tribe', 'supertribe',
    'subfamily', 'family', 'epifamily', 'superfamily',
    'zoosubsection', 'zoosection',
    'parvorder', 'infraorder', 'suborder', 'order', 'superorder',
    'subterclass', 'infraclass', 'subclass', 'class', 'superclass',
    'subphylum', 'phylum',
    'kingdom')

rank_set = set()
for rank in internal_ranks:
    rank_set.add(rank)

# OrderedEnum allows <, > comparisons without the drawbacks of IntEnum.
# (E.g. IntEnum might unexpectedly use an integer value instead of a name.)
# Copied from https://docs.python.org/3/library/enum.html#orderedenum
class _OrderedEnum(Enum):
    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented
    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented
    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

# The Rank enum cannot be declared in the traditional manner because
# 'class = auto()' triggers a syntax error on 'class'.  Instead we
# use the Functional API to supply the Rank names as strings.
Rank = _OrderedEnum('Rank', internal_ranks)
