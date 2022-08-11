import json
import requests
import time
import datetime

# My files
from error import *
from files import *
from find_page import *
from page import *

api_pickle_name = 'api.pickle'
db_version = '1'

inat_dict = {} # iNaturalist (taxon ID) or (rank sci) -> iNat data or None
used_dict = {} # same as inat_dict, but only for entries that have been used

anc_dict = {} # taxon ID -> list of ancestor taxon IDs

api_called = False # the first API call isn't delayed

req_headers = {'user-agent': 'Bay Area Wildflower Guide - fred-rum.github.io/bay-area-wildflower-guide/'}


###############################################################################

# Sequence of operation:
#
# read inat files and prepare inat data by taxon_id
#   each file may prepare multiple taxon_ids if it includes ancestors' data
#
# match inat data to pages (and assign a taxon_id to each matched page)
#   this is easier than trying to match a page to inat data later
#   if any inat data refers to a parent ID that isn't already known,
#     fetch that data from iNaturalist
#   assign a Linnaean relationship between pages according to the iNat parent
#
# for each real leaf page that isn't already matched to inat data
#   fetch the data from iNaturalist
#     the fetched data may prepare multiple taxon_ids (as above)
#   for all new dta, match the inat data to pages (as above)


def read_inat_files():
    global inat_dict
    try:
        with open(f'{root_path}/data/{api_pickle_name}', mode='rb') as f:
            inat_db = pickle.load(f)
            if inat_db['version'] == db_version:
                inat_dict = inat_db['inat_dict']
    except:
        pass

    if inat_dict:
        for inat in inat_dict.values():
            if inat:
                inat.apply_info()
        return


    # Code to read old JSON files.  If there aren't any users who are still
    # using the old JSON files, this can be deleted.
    global api_called
    api_called = True
    file_set = get_file_set('inat', 'json')
    for filename in sorted(file_set):
        try:
            with open(f'{root_path}/inat/{filename}.json', 'r', encoding='utf-8') as r:
                json_data = r.read()
                data = json.loads(json_data)
                if arg('-api_expire'):
                    if 'date' in data:
                        age = datetime.date.today() - datetime.date.fromisoformat(data['date'])
                        if age.days >= int(arg('-api_expire')):
                            # discard expired data
                            return
                    else:
                        # discard undated data
                        continue
                data = data['data']
                parse_inat_data(data, filename)
        except:
            warn(f'reading json file "{filename}"')
            raise


# raw_data is one result from the JSON, parsed into a Python structure.
# name is the filename for the result, either its rank+sci or taxon_id.
#
# The initial query may have been made multiple queries, but we've broken
# it down to the result from one query here.  The result has one primary
# record, and it may contain multiple ancestor records.
#
# parse_inat_data() checks each record for validity and initializes an
# Inat object for each valid record.
#
def parse_inat_data(data, name):
    # Older data from a file may have the raw fetch data instead of
    # only a single record's data.
    if 'results' in data and data['results']:
        data = data['results'][0]

    # The record may be completely empty.  But if any of the fields
    # are valid, we assume the other fields are valid as well.
    #
    # Every query should return only active results, but we double-check
    # is_active anyway.
    if 'is_active' not in data or not data['is_active']:
        inat_dict[name] = None
        return

    # An older file may have a re-directed ID, or a name search may have
    # returned the record for a different name.  In either case, it's
    # counts as an invalid record.
    tid = str(data['id'])
    rank = data['rank']
    sci = data['name']

    # iNaturalist uses the hybrid's special 'x' symbol in the
    # otherwise unelaborated scientific name, so we strip that out
    # when doing the comparison.
    sci = re.sub(' \\u00d7 ', r' ', sci)

    if (name != tid) and (name != rank + ' ' + sci):
        inat_dict[name] = None
        # The fetched data may be useful, but it's more likely to be
        # confusing, so we ignore it.
        return

    Inat(data)

    if 'ancestors' in data:
        for anc_data in data['ancestors']:
            Inat(anc_data)


# Create a Linnaean link from each page to its iNat parent's page.
# If we have taxon_id's, we accumulate as many as we can before making
# a mass query.  Otherwise, we query each name.
def link_inat(page_set):
    tid_set = set()

    try:
        # Fetch inat data for each child as necessary.
        page_list = sort_pages(page_set, with_count=False, sci_only=True)
        for page in page_list:
            if page.taxon_id:
                tid_set.add(page.taxon_id)
            else:
                get_inat_for_page(page)

                # Fetching a taxon by name doesn't get its ancestors.
                # Therefore we add a query for the parent of each taxon.
                # Note that any duplicate taxons are discarded.
                add_parent_tid_to_set(page, tid_set)

        #info('initial tid_set')
        #info(tid_set)
        while (tid_set):
            get_inat_for_tid_set(tid_set)

        link_inat2(page_set)

        # We completed all necessary fetches.
        # Dump all useful entries.
        dump_inat_db(used_dict)
    except:
        # If anything goes wrong, dump everything in the dictionary.
        # (We don't know the full extent of what's useful, so assume
        # it all is.)
        dump_inat_db(inat_dict)
        raise


# link_inat() did the work of initiating page fetches by name or TID.
# link_inat2() actually links and traverses the pages,
# and it only has to worry about TIDs.
def link_inat2(page_set):
    # In case some ancestors (parents) were somehow missed, fetch them.
    tid_set = set()
    page_list = sort_pages(page_set, with_count=False, sci_only=True)
    for child in page_list:
        add_parent_tid_to_set(child, tid_set)
    while (tid_set):
        get_inat_for_tid_set(tid_set)

    parent_set = set()
    for child in page_list:
        if not child.taxon_id:
            if child.sci:
                # We have a scientific name, but no taxon_id.
                # That implies that we failed to fetch the taxon info
                # from the iNat API (or JSON files).
                warn(f'missing iNat data for {child.full()}')

            # On the other hand, if the page has no scientific name
            # and no taxon ID from any source, then skip it.  Note that
            # a page could derive a taxon ID from its common name in
            # observations.csv, in which case we can process its taxonomic
            # chain even without a scientific name.
            continue

        inat_child = get_inat(child.taxon_id, used=True)
        if not inat_child:
            warn(f'missing iNat data for {child.full()}')
            continue

        if not inat_child.parent_id:
            # We expect the top taxon to not have a parent ID.
            #warn(f'iNat linking failed due to missing parent ID from iNat data for child {child.full()}')
            continue

        inat_parent = get_inat(inat_child.parent_id, used=True)
        if not inat_parent:
            warn(f'iNat linking failed due to missing iNat data for parent ID {inat_child.parent_id} from child {child.full()}')
            continue

        parent = find_page2(inat_parent.com, inat_parent.elab, from_inat=True,
                            taxon_id=inat_parent.taxon_id)

        if not parent or not parent.rank:
            # We expect "stateofmatter Life" to fail.
            #warn(f'iNat linking failed because no page matched the iNat data ({inat_parent.elab}) of the parent of {child.full()}')
            continue

        #info(f'iNat linking child {child.full()} to parent {parent.full()}')
        parent.link_linn_child(child)

        parent_set.add(parent)

    # Recurse and link the parents to their parents.
    if parent_set:
        #info(f'iNat linking to the next level of hierarchy')
        link_inat2(parent_set)


# Add all ancestor taxon IDs to tid_set.
def add_parent_tid_to_set(page, tid_set):
    inat = get_inat(page.taxon_id)
    if inat and inat.parent_id:
        # Fetching the parent ID will also fetch all other ancestors,
        # so if any ancestors are already in the queue, remove them.
        if page.taxon_id in anc_dict:
            for anc_tid in anc_dict[page.taxon_id]:
                # For some reason, the 'life' taxon (48460) is never returned as
                # as an ancestor, so we don't treat it as if it will.
                if anc_tid != '48460':
                    tid_set.discard(anc_tid)

        # Then add only the direct parent ID.
        tid_set.add(inat.parent_id)


# Get an iNaturalist record or None.
def get_inat(name, used=False):
    if name not in inat_dict:
        return None

    inat = inat_dict[name]

    if used:
        used_dict[inat.taxon_id] = inat
        used_dict[name] = inat

    return inat


# If there's any kind of failure when trying to use iNat data,
# remove the corresponding file as a candidate for deletion.
def used_fail(name):
    used_dict[name] = None
    return None


# Return the iNaturalist data for a page or None.
#
# If the data is not already loaded and the iNaturalist API is enabled,
# we use the API to fetch the data from iNaturalist.
#
# Since loaded iNaturalist data has already set the taxon_id of any
# matching page(s), we know that a page without a taxon_id should always
# fetch new data.  This avoids the complication of trying to find
# iNaturalist data from a page's names.  A page with a taxon_id may or
# may not need to fetch new iNaturalist data.
#
def get_inat_for_page(page):
    if page.elab_inaturalist:
        elab = page.elab_inaturalist
        sci = strip_sci(elab)
    elif page.elab:
        elab = page.elab
        sci = page.sci
    else:
        return None

    elab_words = elab.split(' ')
    if elab_words[0].islower():
        rank = f'{elab_words[0]}'
    elif len(elab_words) == 2:
        if elab_words[1].startswith('X'):
            rank = 'hybrid'
        else:
            rank = 'species'
    elif ' ssp. ' in page.elab:
        rank = 'subspecies'
    elif ' var. ' in page.elab:
        rank = 'variety'
    else:
        rank = ''

    if rank:
        q = f'q={sci}&rank={rank}'
        name = f'{rank} {sci}'
    else:
        q = f'q={sci}'
        name = sci

    url = f'https://api.inaturalist.org/v1/taxa/autocomplete?{q}&per_page=1&is_active=true&locale=en&preferred_place_id=14'

    # Make sure we don't repeatedly fail fetching the same URL.
    if name in inat_dict:
        return used_fail(name)

    # If the fetch is performed and succeeds, this placeholder does nothing.
    # It's only needed to prevent repeated fetches of the same name.
    inat_dict[name] = None

    if not arg('-api'):
        return used_fail(name)

    data_list = fetch(url, name)

    if len(data_list) != 1:
        return used_fail(name)

    parse_inat_data(data_list[0], name)

    if page.taxon_id:
        return get_inat(page.taxon_id, used=True)
    else:
        return used_fail(name)


# Get iNaturalist data for all taxon IDs in tid_set.
#
# No data is returned; we just fetch the data into inat_dict
# if necessary and appropriate.
#
def get_inat_for_tid_set(tid_set):
    # if "taxa?taxon_id={taxon_id}" is used, the taxon and all its
    # descendents are returned, not necessarily with the requested
    # taxon first!  So I use "taxa/{taxon_id}" instead to exactly get
    # the desired taxon.

    # As requested by the API documentation, I combine many queries
    # into one.  The API docs don't recommend an exact number.  It
    # gives 200 as an example, but I find that that results in an error.
    # 50 is also too many.  30 works, and it happens to be the default
    # number of results, so it may be the maximum number supported.
    tid_list = []
    for tid in sorted(tid_set):
        if tid in inat_dict or not arg('-api'):
            tid_set.remove(tid)
        else:
            tid_list.append(tid)
            if len(tid_list) == 30:
                break

    if not tid_list:
        return

    tid_str = ','.join(tid_list)

    # This API doesn't document any query string options,
    # but experimentation indicates that at least preferred_place_id
    # works.
    cnt = len(tid_list)
    query = f'?per_page={cnt}&is_active=true&locale=en&preferred_place_id=14'

    url = f'https://api.inaturalist.org/v1/taxa/{tid_str}{query}'

    data_list = fetch(url, tid_str)

    # If a taxon_id is bogus or inactive, the results will be missing
    # that result.  So we can't assume that the order of the results
    # matches the order of the query.
    for data in data_list:
        tid = str(data['id'])
        parse_inat_data(data, tid)


def fetch(url, name):
    global api_called
    if api_called:
        if arg('-api_delay'):
            delay = int(arg('-api_delay'))
            if delay < 1:
                delay = 5
        else:
            delay = 5
        time.sleep(delay)
    api_called = True

    info(f'Fetching from iNaturalist API: {name}')
    r = requests.get(url, headers=req_headers)
    json_data = r.text
    try:
        data = json.loads(json_data)
    except:
        fatal(f'Malformed JSON data from fetch:\n{r.text}')
    if 'results' not in data:
        fatal(f'No result from fetch:\n{r.text}')

    return data['results']


def apply_inat_names():
    for inat in used_dict.values():
        if inat:
            inat.apply_names()


def dump_inat_db(inat_dict):
    if api_called:
        inat_db = {'version': db_version,
                   'inat_dict': inat_dict}
        with open(f'{root_path}/data/{api_pickle_name}', mode='wb') as w:
            pickle.dump(inat_db, w)


class Inat:
    pass

    def __init__(self, data):
        # A taxon_id is circulated internally as a string, not an integer.
        self.taxon_id = str(data['id'])

        # If there's already a record for this taxon_id, don't make a
        # duplicate.  (Since we don't record this object anywhere, it
        # gets discarded as soon as we return.)
        dup_inat = get_inat(self.taxon_id)
        if dup_inat:
            return

        inat_dict[self.taxon_id] = self

        sci = data['name']
        rank = data['rank']

        sci_words = sci.split(' ')
        if rank == 'subspecies':
            elab = ' '.join((sci_words[0], sci_words[1], 'ssp.', sci_words[2]))
        elif rank == 'variety':
            elab = ' '.join((sci_words[0], sci_words[1], 'var.', sci_words[2]))
        elif rank == 'hybrid':
            # Remove the special 'x' sign used by hybrids
            # and use my internal encoding instead.
            elab = sci_words[0] + ' X' + sci_words[2]
        elif rank == 'species':
            elab = sci
        else:
            elab = rank + ' ' + sci

        self.elab = elab

        if data['parent_id']:
            self.parent_id = str(data['parent_id'])
        else:
            self.parent_id = None

        if 'ancestor_ids' in data:
            anc_dict[self.taxon_id] = []
            for anc_tid in data['ancestor_ids']:
                anc_dict[self.taxon_id].append(str(anc_tid))

        if 'preferred_establishment_means' in data:
            self.origin = data['preferred_establishment_means']
        else:
            self.origin = None

        if 'preferred_common_name' in data:
            # The common name is forced to all lower case to match my
            # convention.
            self.com = data['preferred_common_name'].lower()
        else:
            self.com = None

        if 'preferred_establishment_means' in data:
            origin = data['preferred_establishment_means']
            if origin == 'introduced':
                origin = 'alien'
            self.origin = origin
        else:
            self.origin = None

        self.apply_info()


    def apply_info(self):
        # Find or create a page corresponding to the iNat data.
        # If a page already exists, set (or check) its taxon_id.
        page = find_page2(self.com, self.elab, from_inat=True,
                          taxon_id=self.taxon_id)
        if not page:
            page = Page(self.com, self.elab, shadow=True, from_inat=True,
                        src='iNaturalist API')
            page.set_taxon_id(self.taxon_id)

        if self.origin:
            page.set_origin(self.origin)


    # Associate common names with scientific names.  (Previously we didn't
    # have the properties in place to know what to do with common names.)
    def apply_names(self):
        page = find_page2(self.com, self.elab, from_inat=True,
                          taxon_id=self.taxon_id)
        if not page:
            info(f'no names match for iNat data: {self.com} ({self.elab}), tid={self.taxon_id}')
