import zipfile
import io
import csv
import datetime

# My files
from args import *
from error import *
from files import *
from find_page import *
from rank import *
from page import *


zip_name = 'inaturalist-taxonomy.dwca.zip'
core_pickle_name = 'core.pickle'
mini_pickle_name = 'core_mini.pickle'
db_version = '2.5.0'

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
core_dict = {}
mini_dict = {}
read_mini = False

def getmtime(filename):
    try:
        return os.path.getmtime(f'{root_path}/data/{filename}')
    except:
        return 0

def read_core():
    global core_dict, read_mini

    zip_mtime = getmtime(zip_name)
    core_mtime = getmtime(core_pickle_name)
    mini_mtime = getmtime(mini_pickle_name)

    if mini_mtime > core_mtime and mini_mtime > zip_mtime and not arg('-core'):
        read_core_pickle(mini_pickle_name)
        if core_dict:
            read_mini = True

    if not core_dict and core_mtime > zip_mtime:
        read_core_pickle(core_pickle_name)

    if not core_dict:
        read_file('data/' + zip_name, read_core_zip,
                  raw=True, msg='taxon hierarchy')


def read_core_pickle(pickle_name):
    global core_dict, core_date
    try:
        with open(f'{root_path}/data/{pickle_name}', mode='rb') as f:
            core_db = pickle.load(f)
            if core_db['version'] == db_version:
                core_dict = core_db['core_dict']
                core_date = core_db['core_date']
    except:
        pass


def dump_core_db(core_dict, name):
    core_db = {'version': db_version,
               'core_date': core_date,
               'core_dict': core_dict}

    with open(f'{root_path}/data/{name}', mode='wb') as w:
        pickle.dump(core_db, w)


def read_core_zip(zip_fd):
    def get_field(fieldname):
        if fieldname in row:
            return row[fieldname]
        else:
            return None

    zip_read = zipfile.ZipFile(zip_fd)
    binary_fd = zip_read.open('taxa.csv')
    csv_fd = io.TextIOWrapper(binary_fd, encoding='utf-8')
    csv_reader = csv.DictReader(csv_fd)

    zip_info = zip_read.getinfo('taxa.csv')
    date_time = zip_info.date_time
    # I have no way to know for sure, but my best guess is that the
    # ZIP file uses the UTC timezone.  Thus, the 7 am time in the ZIP file
    # corresponds to late night on the US west coast, which I know is when
    # iNaturalist prefers to perform its heavy calculations.
    global core_date
    core_date = datetime.datetime(date_time[0],
                                  date_time[1],
                                  date_time[2],
                                  hour=date_time[3],
                                  minute=date_time[4],
                                  second=date_time[5],
                                  tzinfo=datetime.timezone.utc)

    for row in csv_reader:
        rank_str = get_field('taxonRank')
        sci = get_field('scientificName')

        # iNaturalist uses the hybrid's special 'x' symbol in the
        # otherwise unelaborated scientific name, so we strip that out
        # when doing the comparison.  In this context, this character
        # may or may not have a space after it.
        sci = re.sub(' \N{MULTIPLICATION SIGN} ?', r' ', sci)

        # We convert the taxon ID to an integer as a trivial way
        # to save a lot of space in the binary pickle.
        taxon_id = int(get_field('id'))

        if rank_str in ('infrahybrid', 'form', 'variety', 'subspecies'):
            parent_rank_str = 'species'
            parent_sci = get_field('genus') + ' ' + get_field('specificEpithet')
        else:
            for r in ('genus',
                      'family',
                      'order',
                      'class',
                      'phylum',
                      'kingdom'):
                if get_field(r) and r != rank_str:
                    parent_rank_str = r
                    parent_sci = get_field(r)
                    break
            else:
                parent_rank_str = None
                parent_sci = None

        # A name may occasionally be used for multiple taxons.
        # My research leads me to expect that this will only happen
        # within a kingdom at different ranks, or
        # at the same rank in different kingdoms.
        # So we record the kingdom and rank as disambiguators.
        kingdom = get_field('kingdom')

        data = (rank_str, kingdom, taxon_id, parent_sci, parent_rank_str)

        if sci not in core_dict:
            core_dict[sci] = []
        core_dict[sci].append(data)

    dump_core_db(core_dict, core_pickle_name)


# Add useful entries to mini_dict.
#
def use_data(sci, data):
    if not sci in mini_dict:
        mini_dict[sci] = []
    if data not in mini_dict[sci]:
        mini_dict[sci].append(data)
        #print(f'{sci}: {data}')


def get_core_rank(sci, taxon_id):
    if sci not in core_dict:
        return None

    tid = int(taxon_id)

    data_list = core_dict[sci]

    for data in data_list:
        if tid == data[2]: # does TID match?
            use_data(sci, data)
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
    elif rank_str == 'form':
        return ' '.join((sci_words[0], sci_words[1],
                         'f.', sci_words[2]))
    elif rank_str == 'hybrid':
        return sci_words[0] + ' X' + sci_words[1]
    elif rank_str == 'species':
        return sci
    else:
        return rank_str + ' ' + sci


def find_data(page, sci, rank_str, kingdom, tid):
    if (page.taxon_id and
        ((page.taxon_id_src == 'iNaturalist API'
          and page.taxon_id_date > core_date)
         or page.taxon_id_src.endswith('.txt'))):
        # If the page has a taxon_id from the iNaturalist API, and that
        # data is more recent than the DarwinCore archive, then don't
        # complain about the missing or conflicting data in the DarwinCore
        # archive.  It's possible that iNaturalist hasn't updated the
        # DarwinCore archive yet, and we don't want to be stuck with
        # warnings until that happens.
        #
        # Note, however, that if the DarwinCore database is newer than
        # the cached iNaturalist API data, we process the DarwinCore data
        # as usual and complain about any problems.
        return None

    if sci not in core_dict:
        if arg('-core'):
            warn(f"The DarwinCore archive doesn't include a scientific name that matches {page.full()}")
        else:
            warn(f"The cached DarwinCore archive doesn't include a scientific name that matches {page.full()}.  Try again with '-core'?")
        return None

    data_list = core_dict[sci]

    good_type = None

    for data in data_list:
        # rank and/or TID may be None, in which case that won't match,
        # but maybe something else will.  Even if neither rank nor TID
        # match, we can still assume a match if there's only one taxon
        # with this scientific name.
        if rank_str == data[0] or not rank_str:
            # We found a matching rank, but we have to keep looking
            # in case there is another TID with the same rank!
            # (E.g. genus Pieris is both a plant and an animal.)
            good_data = data
            if kingdom == data[1] or (not kingdom and tid == data[2]):
                # A TID match beats any number of conflicting ranks.
                # Take the data and immediately go home.
                # (If the rank turns out to be wrong, that should show
                # up in later checks.)
                break
            elif good_type:
                good_type = 'rank conflict'
            else:
                good_type = 'rank match'
    else:
        if good_type == 'rank conflict':
            error(f'The DarwinCore archive has multiple taxons that could match {page.full()}')
            return None
        elif not good_type:
            warn(f'The DarwinCore archive has no rank or taxon_id that matches {page.full()}')
            return None
        # else good_type == 'rank match', so good_data gets processed

    use_data(sci, good_data)
    return good_data


def parse_core_chains():
    for page in page_array:
        if page.linn_child:
            # only initiate a chain from the lowest level
            # in part because species names are unique,
            # and knowing the kingdom helps disambiguate their ancestors
            continue

        if page.no_names:
            elab = page.name
        elif page.elab_inaturalist:
            elab = page.elab_inaturalist
            if elab == 'n/a':
                continue
        elif page.elab:
            elab = page.elab
        else:
            # If the page only has a common name, don't touch it.
            # Maybe we could look it up by TID, but there's little benefit
            # to it.
            continue

        sci = strip_sci(elab)

        if page.rank:
            if ' ssp. ' in elab:
                rank_str = 'subspecies'
            elif ' var. ' in elab:
                rank_str = 'variety'
            elif ' f. ' in elab:
                rank_str = 'form'
            elif not elab[0].islower() and ' X' in elab:
                rank_str = 'hybrid'
            else:
                rank_str = page.rank.name
        else:
            rank_str = None

        kingdom = None
        anc = page
        while anc:
            if anc.rank is Rank.kingdom:
                kingdom = anc.sci
                break
            anc = anc.linn_parent

        if page.taxon_id:
            tid = int(page.taxon_id)
        else:
            tid = None

        data = find_data(page, sci, rank_str, kingdom, tid)

        if not data:
            continue

        use_data(sci, data)

        rank_str = data[0]
        kingdom = data[1]
        tid = str(data[2])
        parent_sci = data[3]
        parent_rank_str = data[4]

        elab = convert_rank_str_to_elab(rank_str, sci)

        # Update the page with a full elaborated scientific name and taxon_id
        # if it doesn't already have both.
        find_page2(None, elab, from_inat=True, taxon_id=str(tid),
                   src='DarwinCore archive', date=core_date)

        # traverse the taxonomic chain
        while parent_rank_str and parent_sci:
            #print(f'{rank_str} {sci} -> {parent_rank_str} {parent_sci}')
            data = find_data(page, parent_sci, parent_rank_str, kingdom, None)

            if not data:
                break

            use_data(parent_sci, data)

            sci = parent_sci
            rank_str = data[0]
            tid = str(data[2])
            parent_sci = data[3]
            parent_rank_str = data[4]

            elab = convert_rank_str_to_elab(rank_str, sci)

            parent = find_page2(None, elab, from_inat=True, taxon_id=str(tid),
                                src='DarwinCore archive', date=core_date)

            if not parent:
                break

            parent.link_linn_child(page)

            page = parent

    if mini_dict and not read_mini:
        dump_core_db(mini_dict, mini_pickle_name)
