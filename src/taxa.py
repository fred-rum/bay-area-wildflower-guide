import zipfile
import io
import csv

# My files
from error import *
from files import *
from find_page import *
from rank import *
from page import *


inat_ranks = ('infrahybrid',
              'form',
              'variety',
              'subspecies',
              'hybrid',
              'genushybrid') + internal_ranks

rank_to_num = {}
num_to_rank = {}
for i, rank in enumerate(inat_ranks):
    rank_to_num[rank] = i
    num_to_rank[i] = rank


# It takes a long time to read the entire iNaturalist database(s),
# so we compress the data down into a reduced-sized data structure
# that we save as a pickle.  The structure is chosen to allow quick
# look ups by scientific name while saving efficiently in pickle
# format.
#
# Each dict entry maps a <sci> to a list of lists.  These are lists
# rather than keyed dictionaries to avoid repeatedly saving the same
# key names.
#
# The upper-level list contains a list for each rank that uses the
# same scientific name.
#
# The lower-level list contains the following strings:
#   rank
#   taxon_id
#   parent sci
#   parent rank
#
# If there is no parent (i.e. for a kingdom), the lower-level list is
# not stored.
#
taxa_dict = {}

zip_name = 'inaturalist-taxonomy.dwca.zip'
pickle_name = 'taxa.pickle'

def getmtime(filename):
    try:
        return os.path.getmtime(f'{root_path}/data/{filename}')
    except:
        return 0

def read_taxa():
    global taxa_dict

    zip_mtime = getmtime(zip_name)
    pickle_mtime = getmtime(pickle_name)

    if pickle_mtime > zip_mtime:
        try:
            with open(f'{root_path}/data/{pickle_name}', mode='rb') as f:
                taxa_dict = pickle.load(f)
        except:
            pass

    if not taxa_dict:
        read_data_file(zip_name, read_taxa_zip,
                       mode='rb', encoding=None,
                       msg='taxon hierarchy')

def read_taxa_zip(zip_fd):
    def get_field(fieldname):
        if fieldname in row:
            return row[fieldname]
        else:
            return None

    zip_read = zipfile.ZipFile(zip_fd)
    binary_fd = zip_read.open('taxa.csv')
    csv_fd = io.TextIOWrapper(binary_fd, encoding='utf-8')
    csv_reader = csv.DictReader(csv_fd)

    for row in csv_reader:
        rank = get_field('taxonRank')
        sci = get_field('scientificName')

        # iNaturalist uses the hybrid's special 'x' symbol in the
        # otherwise unelaborated scientific name, so we strip that out
        # when doing the comparison.  In this context, this character
        # may or may not have a space after it.
        sci = re.sub(' \N{MULTIPLICATION SIGN} ?', r' ', sci)

        # We convert the taxon ID to an integer as a trivial way
        # to save a lot of space in the binary pickle.
        taxon_id = int(get_field('id'))

        if rank in ('infrahybrid', 'form', 'variety', 'subspecies'):
            parent_rank = 'species'
            parent_sci = get_field('genus') + ' ' + get_field('specificEpithet')
        else:
            for r in ('genus',
                      'family',
                      'order',
                      'class',
                      'phylum',
                      'kingdom'):
                if get_field(r):
                    parent_rank = r
                    parent_sci = get_field(r)
                    break
            else:
                # No parent found, so bail out of this CSV row
                continue

        # rank_num = rank_to_num[rank]
        # parent_rank_num = rank_to_num[parent_rank]
        # data = (rank_num, taxon_id, parent_sci, parent_rank_num)

        data = (rank, taxon_id, parent_sci, parent_rank)

        if sci not in taxa_dict:
            taxa_dict[sci] = []
        taxa_dict[sci].append(data)

    # Compress out redundant info
    # for sci in taxa_dict:
    #     data_list = taxa_dict[sci]
    #     if len(data_list) == 1:
    #         data = data_list[0]
    #         rank = data[0]
    #         if rank in ('species', 'subspecies', 'variety', 'form'):
    #             # The rank is unambiguous, and the parent name is obvious,
    #             # so don't bother to record anything.
    #             taxa_dict.remove(sci)
    #         else:
    #             # Replace a list with a single tuple with the tuple itself.
    #             taxa_dict[sci] = data

    with open(f'{root_path}/data/taxa.pickle', mode='wb') as w:
        pickle.dump(taxa_dict, w)

def get_taxa_rank(sci, taxon_id):
    if not sci in taxa_dict:
        return None

    tid = int(taxon_id)

    data_list = taxa_dict[sci]

    for data in data_list:
        if tid == data[1]: # does TID match?
            return data[0] # return the matching rank
    else:
        return None

def convert_rank_str_to_elab(rank_str, sci):
    sci_words = sci.split(' ')
    if rank_str == 'subspecies':
        return ' '.join((sci_words[0], sci_words[1],
                         'ssp.', sci_words[2]))
    elif rank_str == 'variety':
        return ' '.join((sci_words[0], sci_words[1],
                         'var.', sci_words[2]))
    elif rank_str == 'hybrid':
        return sci_words[0] + ' X' + sci_words[1]
    elif rank_str == 'species':
        return sci
    else:
        return rank_str + ' ' + sci

def parse_taxa_chains():
    for page in page_array:
        if page.linn_child:
            # only initiate a chain from the lowest level
            # in part because species names are unique,
            # and knowing the kingdom helps disambiguate their ancestors
            continue

        sci = page.sci
        if not sci in taxa_dict:
            continue

        if page.rank:
            if ' ssp. ' in page.elab:
                rank_str = 'subspecies'
            elif ' var. ' in page.elab:
                rank_str = 'variety'
            elif not page.elab[0].islower() and ' X' in page.elab:
                rank_str = 'hybrid'
            else:
                rank_str = page.rank.name
        else:
            rank_str = None

        if page.taxon_id:
            tid = int(page.taxon_id)
        else:
            tid = None

        data_list = taxa_dict[sci]

        good_type = None

        for data in data_list:
            # rank and/or TID may be None, in which case that won't match,
            # but maybe something else will.  Even if neither rank nor TID
            # match, we can still assume a match if there's only one taxon
            # with this scientific name.
            if tid == data[1]:
                # A TID match beats any number of conflicting ranks.
                # Take the data and immediately go home.
                # (If the rank turns out to be wrong, that should show
                # up in later checks.)
                good_data = data
                break
            elif not rank_str and len(data_list) == 1:
                # A page with no rank finds a match as long as there is only
                # one option.
                good_data = data
                break
            elif rank_str == data[0]:
                # We found a matching rank, but we have to keep looking
                # in case there is another TID with the same rank!
                # (E.g. genus Pieris is both a plant and an animal.)
                good_data = data
                if good_type:
                    good_type = 'rank conflict'
                else:
                    good_type = 'rank match'
        else:
            if good_type == 'rank conflict' or not rank_str:
                error(f'The taxa file has multiple taxons that could match {page.full()}')
                continue
            elif not good_type:
                error(f'The taxa file has no rank or taxon_id that matches {page.full()} (rank: {rank_str}, tid: {tid})')
                continue
            # else good_type == 'rank match', so good_data gets processed

        taxa_rank_str = data[0]
        taxa_taxon_id = str(data[1])
        parent_sci = data[2]
        parent_rank_str = data[3]

        elab = convert_rank_str_to_elab(taxa_rank_str, sci)

        page = find_page2(None, elab, from_inat=True,
                          taxon_id=taxa_taxon_id)
