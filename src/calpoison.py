import csv

# My files
from error import *
from find_page import *
from rank import *
from page import *


table = {
    '1': "Skin contact with these plants can cause symptoms ranging from redness, itching, and rash to painful blisters like skin burns.",
    '2a': "The juice or sap of these plants contains tiny oxalate crystals that are shaped like tiny needles. Chewing on these plants can cause immediate pain and irritation to the lips, mouth and tongue. In severe cases, they may cause breathing problems by causing swelling in the throat.",
    '2b': "These plants also contain oxalate crystals but they do not cause immediate problems. These plants have tiny crystals that lodge in the kidneys and can cause kidney damage as well as nausea, vomiting and diarrhea.",
    '3': "Ingestion of these plants is expected to cause nausea, vomiting, diarrhea and other symptoms that may cause illness but is not life-threatening.",
    '4': "Ingestion of these plants, especially in large amounts, is expected to cause serious effects to the heart, liver, kidneys or brain. If ingested in any amount, call the poison center immediately.",
}


def read_toxic_plants(f):
    def get_field(fieldname):
        if fieldname in row:
            return row[fieldname]
        else:
            return None

    csv_reader = csv.DictReader(f)

    for row in csv_reader:
        def repl_parens(matchobj):
            nonlocal detail
            detail = ' (' + matchobj.group(1) + ')'
            return ''

        elab = get_field('elab')
        if elab.endswith(' spp'):
            elab += '.'
        elab = fix_elab(elab)

        com = get_field('com').lower()
        detail = ''
        com = re.sub(r'\s*\((.*)\)', repl_parens, com)

        rating_list = get_field('rating').split(',')

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
                if page.elab_calpoison == 'n/a' or page.toxic:
                    continue # ignore it
                else:
                    warn(f'Toxicity rating specified for scientific name "{elab}", but the common name matched {page.full()}')
        if not page or page.toxic or page.elab_calpoison == 'n/a':
            continue

        page.toxic = True

        page.txt += f'<p>\n<a href="https://calpoison.org/topics/plant#toxic" target="_blank" rel="noopener noreferrer">Toxicity</a>{detail}:\n'
        for rating in rating_list:
            if rating in table:
                page.txt += f'<br>\n{rating} &ndash; {table[rating]}\n'
            else:
                error(f'Unknown toxicity rating {rating} for {page.full()}')
        page.txt += '</p>\n'
