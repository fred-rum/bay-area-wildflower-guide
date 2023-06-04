import json
import requests
import time
import sys

# My files
from error import *
from files import *
from find_page import *
from page import *
from args import *

api_pickle_name = 'api.pickle'
db_version = '1'

# inat_dict contains different types of mappings:
# (taxon ID) -> (iNat data) ... taxon ID for a page
# (rank sci) -> tid         ... an alias from an old name to a current tid
# (rank sci) -> (None)      ... a name not found at iNaturalist
inat_dict = {}

 # used_dict is the same as inat_dict, but only for entries that have been used
used_dict = {}

anc_dict = {} # taxon ID -> list of ancestor taxon IDs

if arg('-api_taxon'):
    user_discard_set = set(arg('-api_taxon')) # set of taxons to be discarded
else:
    user_discard_set = set()

# accumulate a set of names to discard that includes all ancestors/descendents
# of discarded TIDs
discard_dict = {} # name to discard -> reason for discard

api_called = False # the first API call isn't delayed

req_headers = {'user-agent': 'Bay Area Wildflower Guide - fred-rum.github.io/bay-area-wildflower-guide/'}


###############################################################################

# Sequence of operation:
#
# read cached API data
#   store data in inat_dict by taxon_id
#   create shadow pages as needed
#   apply taxon_id to pages
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


def mark_discard(name, reason):
    if name not in discard_dict:
        discard_dict[name] = reason
        print(f'discarded from API cache: {name}{reason}')

def get_sci_from_ranked_elab(name):
    if name[0].islower():
        sci_words = name.split(' ')
        return ' '.join(sci_words[1:])
    else:
        return name

def read_inat_files():
    global inat_dict
    try:
        with open(f'{root_path}/data/{api_pickle_name}', mode='rb') as f:
            inat_db = pickle.load(f)
            if inat_db['version'] == db_version:
                inat_dict = inat_db['inat_dict']
    except:
        pass

    # If any taxons need to be discarded, also discard any taxons that depend
    # on them.
    if user_discard_set:
        for (name, value) in inat_dict.items():
            if isinstance(value, Inat):
                value.check_for_discard()
            else:
                sci = get_sci_from_ranked_elab(name)
                if name in user_discard_set or sci in user_discard_set:
                    if value:
                        mark_discard(name, f' (was aliased to {value})')
                    else:
                        mark_discard(name, f' (was unknown to iNaturalist)')
                elif value in user_discard_set:
                    mark_discard(name, f' (was aliased to {value})')
                elif not value and 'unknown' in user_discard_set:
                    mark_discard(name, f' (was unknown to iNaturalist)')

        for name in discard_dict:
            del inat_dict[name]

    # The loaded dictionary has the information stored by each Inat object,
    # but Inat() has not been called, so we need to perform a separate step
    # to apply the Inat data elsewhere.
    for inat in inat_dict.values():
        if isinstance(inat, Inat):
            inat.apply_info()


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

    # The record may be completely empty in the case of a query error.
    # But if any of the fields are valid, we assume the other fields are
    # valid as well.
    #
    # Every query should return only active results, but we double-check
    # is_active anyway.
    if 'is_active' not in data or not data['is_active']:
        inat_dict[name] = None
        return

    tid = str(data['id'])
    rank = data['rank']
    sci = data['name']

    # iNaturalist uses the hybrid's special 'x' symbol in the
    # otherwise unelaborated scientific name, so we strip that out
    # when doing the comparison.
    sci = re.sub(' \\u00d7 ', r' ', sci)

    # An older file may have a re-directed ID, or a name search may have
    # returned the record for a different name.  In either case, it's
    # counts as an invalid record.
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
    except:
        # If anything goes wrong, dump everything in the dictionary.
        # (We don't know the full extent of what's useful, so assume
        # it all is.)
        dump_inat_db(False)
        raise

    # We'll fetch more later, but dump what we've got so far in case
    # an error occurs.
    dump_inat_db(False)


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
                if arg('-api'):
                    warn(f"Unable to fetch data for {child.full()} from the iNaturalist API")
                else:
                    warn(f"The cached iNaturalist API data doesn't include {child.full()}.  Tray again with '-api'?")

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
                            taxon_id=inat_parent.taxon_id,
                            src='iNaturalist API', date=inat_parent.date)

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
    if isinstance(inat, Inat) and inat.parent_id:
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
        if isinstance(inat, Inat):
            used_dict[inat.taxon_id] = inat
        used_dict[name] = inat

    if isinstance(inat, Inat):
        return inat
    else:
        return None


# If there's any kind of failure when trying to use the iNat API data,
# mark the name in both dictionaries so that we don't try to fetch
# the API data again.
def used_fail(name):
    inat_dict[name] = None
    used_dict[name] = None
    return None


def get_rank(elab):
    elab_words = elab.split(' ')
    if elab_words[0].islower():
        rank = f'{elab_words[0]}'
    elif len(elab_words) == 2:
        if elab_words[1].startswith('X'):
            rank = 'hybrid'
            elab = f'{elab_words[0]} {elab_words[1][1:]}'
        else:
            rank = 'species'
    elif ' ssp. ' in elab:
        rank = 'subspecies'
    elif ' var. ' in elab:
        rank = 'variety'
    else:
        rank = ''

    return (rank, elab)


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

    (rank, elab) = get_rank(elab)

    if rank:
        q = f'q={sci}&rank={rank}'
        name = f'{rank} {sci}'
    else:
        q = f'q={sci}'
        name = sci

    # Make sure we don't repeatedly fail fetching the same URL.
    if name in inat_dict:
        return used_fail(name)

    if not arg('-api'):
        return used_fail(name)

    url = f'https://api.inaturalist.org/v1/taxa/autocomplete?{q}&per_page=1&is_active=true&locale=en&preferred_place_id=14'

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
def get_inat_for_tid_set(tid_set, local=True):
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
        if not arg('-api'):
            do_fetch = False
        elif local:
            # The first fetch request always specifies the local area.
            # We only make the fetch if we don't already have data.
            do_fetch = tid not in inat_dict
        else:
            # We may make a second fetch request without specifying the
            # local area, so the API returns the "global" common name.
            # This name is useful since it is the one used in the Seek app.
            # We only make this request if we have results from the first
            # fetch, but we don't have any information about its global
            # common name.  No extra checks are needed for this case
            # since all necessary checks have already been performed.
            do_fetch = True

        if do_fetch:
            tid_list.append(tid)
            tid_set.remove(tid)
            if len(tid_list) == 30:
                break
        else:
            tid_set.remove(tid)

    if not tid_list:
        return

    tid_str = ','.join(tid_list)

    # This API doesn't document any query string options,
    # but experimentation indicates that at least preferred_place_id
    # works.
    cnt = len(tid_list)
    query = f'?per_page={cnt}&is_active=true&locale=en'
    if local:
        query += '&preferred_place_id=14'

    url = f'https://api.inaturalist.org/v1/taxa/{tid_str}{query}'

    if local:
        name = tid_str
    else:
        name = '(for global common name) ' + tid_str

    data_list = fetch(url, name)

    # If a taxon_id is bogus or inactive, the results will be missing
    # that result.  So we can't assume that the order of the results
    # matches the order of the query.
    for data in data_list:
        if 'id' in data:
            tid = str(data['id'])
            if local:
                parse_inat_data(data, tid)
            else:
                if 'preferred_common_name' in data and data ['preferred_common_name']:
                    inat_dict[tid].global_com = data['preferred_common_name'].lower()
                else:
                    inat_dict[tid].global_com = None

                if 'ancestors' in data:
                    for anc_data in data['ancestors']:
                        anc_tid = str(anc_data['id'])
                        if 'preferred_common_name' in anc_data and anc_data['preferred_common_name']:
                            inat_dict[anc_tid].global_com = anc_data['preferred_common_name'].lower()
                        else:
                            inat_dict[anc_tid].global_com = None
                        Inat(anc_data)


def find_plant_match(data_list, name):
    matched_data = None
    for data in data_list:
        if ('matched_term' in data and
            data['matched_term'] == name and
            'iconic_taxon_name' in data and
            data['iconic_taxon_name'] == 'Plantae'):
            if matched_data:
                if data['name'] == name and matched_data['name'] != name:
                    # prefer a non-aliased match
                    matched_data = data
                elif matched_data['name'] == name and data['name'] != name:
                    # prefer a non-aliased match
                    pass
                elif matched_data['id'] in data['ancestor_ids']:
                    # prefer a higher-level match if it includes the lower level
                    matched_data = data
                elif data['id'] in matched_data['ancestor_ids']:
                    # prefer a higher-level match if it includes the lower level
                    pass
                else:
                    # no preference found, so bail out and warn the user
                    return 'multiple'
            else:
                matched_data = data
    return matched_data

# Return a page mapped by a scientific name or None.
#
# If we already know the page by name, then this function isn't called.
# It is only called if we don't have a page for it or if we have the page
# at a different scientific name.
def get_page_for_alias(orig, elab):
    sci = strip_sci(elab)
    (rank, elab) = get_rank(elab)

    # We record the rank we're aliasing *from* in our dictionary,
    # but if it's a species, subspecies, or variety, we allow it to match
    # any rank in case it is a synonym of a taxon a different level.  E.g.
    # Dracaena marginata maps to variety Dracaena reflexa angustifolia.
    # However, a genus is only allowed to map to a genus.  Otherwise we
    # get too many matches, e.g. for Anemone.
    if rank:
        name = f'{rank} {sci}'
        if rank == 'genus':
            q = f'q={sci}&rank={rank}'
        else:
            q = f'q={sci}'
    else:
        name = sci
        q = f'q={sci}'

    if orig != elab:
        orig = f'{orig} -> {elab}'

    if name in inat_dict:
        tid = inat_dict[name]
        if not tid and name not in used_dict:
            warn(f'Scientific name "{orig}" is given in the CalPoison data, but iNaturalist doesn\'t recognize it.')
            return used_fail(name)
        used_dict[name] = tid
    else:
        if not arg('-api'):
            warn(f'Scientific name "{orig}" is given in the CalPoison data, but we don\'t have cached API data for it.  Re-run with -api?')
            return used_fail(name)

        url = f'https://api.inaturalist.org/v1/taxa/autocomplete?{q}&per_page=1&is_active=true&locale=en&preferred_place_id=14'
        
        data_list = fetch(url, name)

        # Even though I asked for 1 result, iNaturalist returns all results
        # that exactly *start* with the given name.  It seems to return a full
        # match first (which is what we want), but if the same name is in
        # multiple kingdoms, I don't know for sure that the plant match is
        # returned first, so I search the data list for the first plant with
        # an exact match.
        #
        # iNaturalist may also return an exact-match common name first.
        # The common name may be upper or lowercase.  If a taxon has both
        # a lowercase common name and the same scientific name in uppercase,
        # only the common name may be returned.  So I first search for the
        # correct case for the scientific name, then if there is no match,
        # I search for a lowercase version of the name.
        data = find_plant_match(data_list, sci)
        if not data:
            data = find_plant_match(data_list, sci.lower())
        if not data:
            warn(f'Scientific name "{orig}" is given in the CalPoison data, but iNaturalist doesn\'t recognize it.')
            return used_fail(name)
        elif data == 'multiple':
            warn(f'Scientific name "{orig}" is given in the CalPoison data, but there are multiple iNaturalist matches for it.')
            return used_fail(name)

        tid = data['id']
        inat_dict[name] = tid
        used_dict[name] = tid

    return find_taxon_id(str(tid))


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
    # Before applying names, query the API as necessary for the global
    # common name of each taxon.
    tid_set = set()
    anc_set = set()
    for inat in used_dict.values():
        if (inat
            and inat.com
            and not hasattr(inat, 'global_com')):

            tid = inat.taxon_id
            tid_set.add(tid)

            # When we query a TID, we automatically get its ancestors' data,
            # so we exclude all such ancestors from the query list.
            if tid in anc_dict:
                anc_set.update(anc_dict[tid])

    tid_set.difference_update(anc_set)
    try:
        while (tid_set):
            get_inat_for_tid_set(tid_set, local=False)
    except:
        # If anything goes wrong, dump everything in the dictionary.
        # (We don't know the full extent of what's useful, so assume
        # it all is.)
        dump_inat_db(False)
        raise

    # Dump the DB again now that we've added the global common names.
    dump_inat_db(False)

    for inat in used_dict.values():
        if isinstance(inat, Inat):
            inat.apply_names()


def dump_inat_db(done):
    if done:
        # Dump the DB a final time with only those entries that we've used for
        # pages or that we looked up for the CalPoison toxicity data.
        dump_dict = used_dict
    else:
        # Either we encountered an error or we finished a section of code
        # and we want to dump the database before an error can trash our
        # fetched data.  We don't yet know which entries are needed, so
        # we dump them all.
        dump_dict = inat_dict

    # normally don't bother to dump the pickle if we never fetched anything,
    # but we also dump it if we discarded anything.
    if api_called or discard_dict:
        inat_db = {'version': db_version,
                   'inat_dict': dump_dict}
        with open(f'{root_path}/data/{api_pickle_name}', mode='wb') as w:
            pickle.dump(inat_db, w)


# Inat holds data fetched and parsed from iNaturalist's API.
# Because we cache copies of the iNat class in a pickle file,
# we make sure to not have any references from Inat to any other class
# that would cause the pickle size to explode.
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

        if 'preferred_common_name' in data and data['preferred_common_name']:
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
        # If this is new API data, give it the current date.
        # If the date was loaded from the pickle file, keep it.
        # If the pickle file didn't include a date, treat it as fresh data.
        if not hasattr(self, 'date'):
            self.date = now()

        # Find or create a page corresponding to the iNat data.
        # If a page already exists, set (or check) its taxon_id.
        page = find_page2(self.com, self.elab, from_inat=True,
                          taxon_id=self.taxon_id,
                          src='iNaturalist API', date=self.date)
        if not page:
            page = Page(self.com, self.elab, shadow=True, from_inat=True,
                        src='iNaturalist API')
            page.set_taxon_id(self.taxon_id,
                              src='iNaturalist API', date=self.date)

        if self.origin:
            page.set_origin(self.origin)


    # Associate common names with scientific names.  (Previously we didn't
    # have the properties in place to know what to do with common names.)
    def apply_names(self):
        page = find_page2(self.com, self.elab, from_inat=True,
                          taxon_id=self.taxon_id,
                          src='iNaturalist API', date=self.date)
        if not page:
            info(f'no names match for iNat data: {self.com} ({self.elab}), tid=se{lf.taxon_id}')
        elif hasattr(self, 'global_com') and self.global_com:
            page = find_page2(self.global_com.lower(), self.elab,
                              from_inat='global_com', taxon_id=self.taxon_id,
                              src='iNaturalist API', date=self.date)


    # A TID should be discarded if it has an ancestor TID that the
    # user says should be discarded.  Just in case, all of its
    # ancestors are also discarded, all the way to top of the chain.
    #
    # If ancestors should be discarded, an indicator is passed as a parameter
    # to recursion.  If descendents should be discarded, an indicator is
    # passed as a return value.
    #
    def check_for_discard(self, discarded_descendent=None):
        discarded_ancestor = None

        sci = get_sci_from_ranked_elab(self.elab)

        if self.taxon_id in user_discard_set:
            mark_discard(self.taxon_id, '')
            discarded_descendent = discarded_ancestor = str(self.taxon_id)
        elif self.elab in user_discard_set:
            mark_discard(self.taxon_id, f' ({self.elab})')
            discarded_descendent = discarded_ancestor = self.elab
        elif discarded_descendent:
            mark_discard(self.taxon_id, f' (ancestor of {discarded_descendent})')

        # recurse upwards
        # - check whether an ancestor is discarded
        # - inform an ancestor if a descendent is discarded
        # but don't recurse up to and discard the "life" taxon
        # since that would trigger an extra unnecessary API fetch.
        if self.parent_id in inat_dict and self.parent_id != '48460':
            ret_val = inat_dict[self.parent_id].check_for_discard(discarded_descendent)
            if ret_val and not discarded_ancestor:
                discarded_ancestor = ret_val
                mark_discard(self.taxon_id, f' (descendent of {discarded_ancestor})')

        return discarded_ancestor
