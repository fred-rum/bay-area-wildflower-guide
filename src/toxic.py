import yaml

# My files
from error import *
from find_page import *
from rank import *
from files import *


toxic_table = {
    '0': "Non-toxic.",
    '0b': "These plants are not a problem to humans, but are known to be dangerous to animals (dogs and cats). Because dogs, especially, will eat large amounts, it is important to keep pets and these plants apart.",
    '1': "Skin contact with these plants can cause symptoms ranging from redness, itching, and rash to painful blisters like skin burns.",
    '2a': "The juice or sap of these plants contains tiny oxalate crystals that are shaped like tiny needles. Chewing on these plants can cause immediate pain and irritation to the lips, mouth and tongue. In severe cases, they may cause breathing problems by causing swelling in the throat.",
    '2b': "These plants contain oxalate crystals but they do not cause immediate problems. These plants have tiny crystals that lodge in the kidneys and can cause kidney damage as well as nausea, vomiting and diarrhea.",
    '3': "Ingestion of these plants is expected to cause nausea, vomiting, diarrhea and other symptoms that may cause illness but is not life-threatening.",
    '4': "Ingestion of these plants, especially in large amounts, is expected to cause serious effects to the heart, liver, kidneys or brain. If ingested in any amount, call the poison center immediately.",
}


class ToxicDetail:
    def __init__(self, src_page, ratings):
        self.src_page = src_page
        self.ratings = ratings

toxic_alias_dict = {}
def read_toxic_alias(f):
    for c in f:
        c = c.strip()

        # remove comments
        c = re.sub(r'\s*#.*$', '', c)

        if not c: # ignore blank lines (and comment-only lines)
            continue

        m1 = re.match(r'\s*"([^\"]*)"\s*:\s*"([^\"]*)"\s*$', c)
        m2 = re.match(r'\s*"([^\"]*)"\s*,\s*"([^\"]*)"\s*:\s*"([^\"]*)"\s*,\s*"([^\"]*)"\s*$', c)
        if m1:
            toxic_alias_dict[m1.group(1)] = m1.group(2)
        elif m2:
            toxic_alias_dict[(m2.group(1), m2.group(2))] = (m2.group(3),
                                                            m2.group(4))
        else:
            error(f'Unknown line in toxic_alias.txt: {c}')

read_data_file('toxic_alias.txt', read_toxic_alias)


def read_toxicity():
    read_data_file('semitoxic.scrape', read_semitoxic_plants,
                   msg='list of plants that are only toxic to animals')

    read_data_file('nontoxic.scrape', read_nontoxic_plants,
                   msg='list of non-toxic plants')

    read_data_file('toxic.scrape', read_toxic_plants,
                   msg='plant toxicity ratings')


def read_semitoxic_plants(f):
    read_toxic_scrape(f, '0b')

def read_nontoxic_plants(f):
    read_toxic_scrape(f, '0')

def read_toxic_plants(f):
    read_toxic_scrape(f, False)


def read_toxic_line(f):
    while True:
        s = next(f).strip()
        if s:
            return s


def read_toxic_scrape(f, default_rating):
    def repl_detail(matchobj):
        nonlocal detail
        detail = matchobj.group(1)
        return ''

    while True:
        # read the scientific and common name
        while True:
            try:
                elab = read_toxic_line(f)
            except StopIteration: # EOF is allowed here
                return

            if not re.match(r'[A-Z]$', elab):
                # only exit the loop when we *don't* have
                # a single capital letter
                break

        com = read_toxic_line(f)

        # check for double or single aliases
        if (elab, com) in toxic_alias_dict:
            (elab, com) = toxic_alias_dict[(elab, com)]
        else:
            if elab in toxic_alias_dict:
                elab = toxic_alias_dict[elab]
            if com in toxic_alias_dict:
                com = toxic_alias_dict[com]


        # parse the scientific name

        if elab.endswith(' spp'):
            elab += '.'
        elab = fix_elab(elab)

        elab_list = or_list(elab)


        # parse the common name

        com = com.lower()

        com = re.sub(r'\s*.(?:do not confuse with|not to be confused with).*$',
                     '', com)

        # extract added toxicity detail that is included in the common name,
        # e.g. "cherry (chewed pits)".
        detail = ''
        com = re.sub(r'\s*\((.*)\)', repl_detail, com)

        # Rearrange names that are listed as "last name, first name",
        # e.g. "cherry, bitter".
        com = re.sub(r'([^,]*), (.*)', r'\2 \1', com)

        com_list = or_list(com)


        # read and parse the rating
        if default_rating:
            rating = default_rating
        else:
            rating = read_toxic_line(f)
            if rating in toxic_alias_dict:
                rating = toxic_alias_dict[rating]

        raw_rating_list = rating.split(',')
        rating_list = []
        for rating in raw_rating_list:
            rating = rating.strip()
            if rating in toxic_table:
                rating_list.append(rating)
            else:
                error(f'Unknown toxicity rating {rating} for {com} ({elab})')

        for elab in elab_list:
            for com in com_list:
                assign_toxicity(elab, com, rating_list, detail)


def or_list(s):
    matchobj = re.match(r'(.* )?(\S*) or (\S*)( .*)?$', s)
    if matchobj:
        pfx1  = matchobj.group(1)
        word1 = matchobj.group(2)
        word2 = matchobj.group(3)
        sfx2  = matchobj.group(4)

        if pfx1 and sfx2:
            return (pfx1 + word1, word2 + sfx2)
        elif pfx1:
            return (pfx1 + word1, pfx1 + word2)
        elif sfx2:
            return (word1 + sfx2, word2 + sfx2)
        else:
            return (word1, word2)
    else:
        return (s,)


def assign_toxicity(elab, com, rating_list, detail):
    # find the page
    page = None

    sci = strip_sci(elab)
    if sci in cpsci_page:
        page = cpsci_page[sci]

    # Search for the scientific and common names separately
    # to avoid creating an association that may not be wanted.
    if not page:
        page = find_page2(None, elab)
    if not page:
        page = find_page2(com, None)
        if page and not page.shadow:
            if page.elab_calpoison == 'n/a' or page.toxicity_dict:
                return # ignore it
            else:
                warn(f'Toxicity rating specified for scientific name "{elab}", but the common name matched {page.full()}')
    if not page or page.elab_calpoison == 'n/a':
        return

    page.set_toxicity(detail, page, tuple(rating_list))
