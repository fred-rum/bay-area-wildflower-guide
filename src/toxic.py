import yaml

# My files
from error import *
from find_page import *
from rank import *
from files import *


table = {
    '1': "Skin contact with these plants can cause symptoms ranging from redness, itching, and rash to painful blisters like skin burns.",
    '2a': "The juice or sap of these plants contains tiny oxalate crystals that are shaped like tiny needles. Chewing on these plants can cause immediate pain and irritation to the lips, mouth and tongue. In severe cases, they may cause breathing problems by causing swelling in the throat.",
    '2b': "These plants also contain oxalate crystals but they do not cause immediate problems. These plants have tiny crystals that lodge in the kidneys and can cause kidney damage as well as nausea, vomiting and diarrhea.",
    '3': "Ingestion of these plants is expected to cause nausea, vomiting, diarrhea and other symptoms that may cause illness but is not life-threatening.",
    '4': "Ingestion of these plants, especially in large amounts, is expected to cause serious effects to the heart, liver, kidneys or brain. If ingested in any amount, call the poison center immediately.",
}

def read_toxic_alias(f):
    global toxic_alias_dict
    toxic_alias_dict = yaml.safe_load(f)

read_data_file('toxic_alias.yaml', read_toxic_alias)


def read_toxic_plants(f):
    read_toxic_scrape(f, True)


def read_toxic_line(f):
    s = next(f).strip()

    if s in toxic_alias_dict:
        s = toxic_alias_dict[s]

    return s


def read_toxic_scrape(f, is_toxic):
    def repl_parens(matchobj):
        nonlocal detail
        detail = ' (' + matchobj.group(1) + ')'
        return ''

    while True:
        # read and parse the scientific name
        while True:
            try:
                elab = read_toxic_line(f)
            except StopIteration: # EOF is allowed here
                return

            if not re.match(r'[A-Z]?$', elab):
                # only exit the loop when we *don't* have
                # a blank line or a single capital letter
                break

        if elab.endswith(' spp'):
            elab += '.'
        elab = fix_elab(elab)

        elab_list = or_list(elab)


        # read and parse the common name
        while True:
            com = read_toxic_line(f)
            if com != '':
                # only exit the loop when we don't have a blank line
                break

        com = com.lower()

        com = re.sub(r'\s*.(?:do not confuse with|not to be confused with).*$',
                     '', com)

        # extract added toxicity detail that is included in the common name,
        # e.g. "cherry (chewed pits)".
        detail = ''
        com = re.sub(r'\s*\((.*)\)', repl_parens, com)

        # Rearrange names that are listed as "last name, first name",
        # e.g. "cherry, bitter".
        com = re.sub(r'([^,]*), (.*)', r'\2 \1', com)

        com_list = or_list(com)


        # read and parse the rating
        while True:
            rating = read_toxic_line(f)
            if rating != '':
                # only exit the loop when we don't have a blank line
                break

        raw_rating_list = rating.split(',')
        rating_list = []
        for rating in raw_rating_list:
            rating = rating.strip()
            if rating in table:
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
            print((pfx1 + word1, word2 + sfx2))
            return (pfx1 + word1, word2 + sfx2)
        elif pfx1:
            print((pfx1 + word1, pfx1 + word2))
            return (pfx1 + word1, pfx1 + word2)
        elif sfx2:
            print((word1 + sfx2, word2 + sfx2))
            return (word1 + sfx2, word2 + sfx2)
        else:
            print((word1, word2))
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
            if page.elab_calpoison == 'n/a' or page.toxicity_set:
                return # ignore it
            else:
                warn(f'Toxicity rating specified for scientific name "{elab}", but the common name matched {page.full()}')
    if not page or page.elab_calpoison == 'n/a':
        return

    page.set_toxicity(rating_list, detail)


def calpoison_html(rating_set, detail):
    if not rating_set:
        return ''

    clist = []
    for rating in sorted(rating_set):
        clist.append(f'{rating} &ndash; {table[rating]}')

    return (f'<p>\n<a href="https://calpoison.org/topics/plant#toxic" target="_blank" rel="noopener noreferrer">Toxicity</a>{detail}:\n<br>\n' + 
            '\n<br>\n'.join(clist) +
            '\n</p>\n')
