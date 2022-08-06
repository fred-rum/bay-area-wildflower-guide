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
