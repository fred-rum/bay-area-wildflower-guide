import json
import requests
import time
import datetime

# My files
from error import *
from files import *
from find_page import *
from page import *

inat_dict = {} # iNaturalist (taxon ID) or (rank sci) -> iNat data or None

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

file_set = get_file_set('inat', 'json')

def read_inat_files():
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

    if 'ancestors' in data:
        anc_list =  data['ancestors']
    else:
        anc_list = []
    num_anc = len(anc_list)

    Inat(data, f'{name}.json', name, num_anc)
    for anc_data in anc_list:
        Inat(anc_data, f'ancestor of {name}.json', name, num_anc)

# Create a Linnaean link from each page to its iNat parent's page.
# If we have taxon_id's, we accumulate as many as we can before making
# a mass query.  Otherwise, we query each name.
def link_inat(page_set):
    tid_set = set()

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

    for filename in sorted(file_set):
        #info(f'inat/{filename}.json')
        delete_file(f'inat/{filename}.json')


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
                warn(f'missing iNata data for {child.full()}')

            # On the other hand, if the page has no scientific name
            # and no taxon ID from any source, then skip it.  Note that
            # a page could derive a taxon ID from its common name in
            # observations.csv, in which case we can process its taxonomic
            # chain even without a scientific name.
            continue

        inat_child = get_inat(child.taxon_id, used=True)
        if not inat_child:
            warn(f'missing iNat data for {child.full()} with taxon_id {child.taxon_id}')
            continue

        if not inat_child.parent_id:
            # We expect the top taxon to not have a parent ID.
            #warn(f'iNat linking failed due to missing parent ID from iNat data for child {child.full()}')
            continue

        inat_parent = get_inat(inat_child.parent_id, used=True)
        if not inat_parent:
            warn(f'iNat linking failed due to missing iNat data for parent ID {inat_child.parent_id} from child {child.full()}')
            continue

        parent = inat_parent.page

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
        for anc_tid in inat.anc_tid_list:
            # For some reason, the 'life' taxon (48460) is never returned as
            # as an ancestor, so we don't treat it as if it will.
            if anc_tid != '48460':
                tid_set.discard(anc_tid)

        # Then add only the direct parent ID.
        tid_set.add(inat.parent_id)


# Get an iNaturalist record or None.
def get_inat(name, used=False):
    if not name in inat_dict:
        return None

    inat = inat_dict[name]

    if used:
        if inat:
            # When a valid record gets used, removed the associated
            # filename as a candidate for deletion.
            file_set.discard(inat.filename)

            if inat.num_anc:
                # This iNat record was part of a chain of ancestors from a
                # single result.  Remove the filename info from all its
                # ancestors, since even if they are used they won't
                # require any additional files.
                #
                # For some reason, the 'life' taxon (48460) is never returned
                # as an ancestor, so we don't treat it as if it will.
                inat_anc = inat
                while inat_anc and inat_anc.taxon_id != '48460':
                    inat_anc.filename = None
                    inat_anc = get_inat(inat_anc.parent_id)
        else:
            return used_fail(name)

    return inat


# If there's any kind of failure when trying to use iNat data,
# remove the corresponding file as a candidate for deletion.
def used_fail(name):
    file_set.discard(name)
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
    if not page.sci:
        return None

    if page.elab_inaturalist:
        elab = page.elab_inaturalist
        sci = strip_sci(elab)
    else:
        elab = page.elab
        sci = page.sci

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

    data_list = fetch(url)

    if len(data_list) != 1:
        write_inat_data({}, name, url)
        return used_fail(name)

    write_inat_data(data_list[0], name, url)
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

    data_list = fetch(url)

    # If a taxon_id is bogus or inactive, the results will be missing
    # that result.  So we can't assume that the order of the results
    # matches the order of the query.
    for data in data_list:
        tid = str(data['id'])
        write_inat_data(data, tid, url)
        tid_set.remove(tid)

    # No result returned for these.
    for tid in tid_set:
        write_inat_data({}, tid, url)

    for data in data_list:
        tid = str(data['id'])
        parse_inat_data(data, tid)


def fetch(url):
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

    info(url)
    r = requests.get(url, headers=req_headers)
    json_data = r.text
    try:
        data = json.loads(json_data)
    except:
        fatal(f'Malformed JSON data from fetch:\n{r.text}')
    if 'results' not in data:
        fatal(f'No result from fetch:\n{r.text}')

    return data['results']


def write_inat_data(data, filename, url):
    # Make the file a candidate for deletion.
    # E.g. it could get included by someone else's taxonomic chain
    # (because two related pages don't have a real link between them,
    # so they're both allowed to initiate queries).
    #
    # Note that if the file contains invalid data, we'd expect it to
    # be removed again from file_set later when link_inat() tries to
    # use it.
    file_set.add(filename)

    json_data = json.dumps(data, indent=2)
    with open(f'{root_path}/inat/{filename}.json', 'w', encoding='utf-8') as w:
        today = datetime.date.today().isoformat()
        w.write('{\n')
        w.write(f'"date": "{today}",\n')
        w.write(f'"url": "{url}",\n')
        w.write('"data":\n')
        w.write(f'{json_data}\n')
        w.write('}\n')


def apply_inat_names():
    for inat in inat_dict.values():
        if inat:
            inat.apply_names()


class Inat:
    pass

    def __init__(self, data, src, filename, num_anc):
        # A taxon_id is circulated internally as a string, not an integer.
        self.taxon_id = str(data['id'])

        # If there's already a record for this taxon_id, don't make a
        # duplicate.  (Since we don't record this object anywhere, it
        # gets discarded as soon as we return.)
        dup_inat = get_inat(self.taxon_id)
        if dup_inat:
            # When two records come from different queries, the query with
            # ancestors takes priority for being retained permanently.
            if not dup_inat.num_anc:
                dup_inat.update_file_info(filename, num_anc)
            return

        self.update_file_info(filename, num_anc)

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

        self.anc_tid_list = []
        if 'ancestor_ids' in data:
            for anc_tid in data['ancestor_ids']:
                self.anc_tid_list.append(str(anc_tid))

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

        # If iNat data is loaded from a file or is an ancestor thereof,
        # it might no longer be needed.  If the iNat data creates a shadow
        # page, but no real page is ever found to be a descendent, then
        # the iNat data is a candidate for deletion.
        #
        # Once all (shadow) taxonomy is prepared, 'used' is changed to True
        # for each real page and each (shadow) ancestor of a real page.
        self.used = False

        inat_dict[self.taxon_id] = self

        # Find or create a page corresponding to the iNat data.
        # If a page already exists, set (or check) its taxon_id.
        page = find_page2(self.com, self.elab, from_inat=True,
                          taxon_id=self.taxon_id)
        if page:
            #info(f'iNat data matched to {page.full()}')
            pass
        else:
            page = Page(self.com, self.elab, shadow=True, from_inat=True,
                        src=src)
            page.set_taxon_id(self.taxon_id)
            #info(f'iNat data created {page.full()}')

        if self.origin:
            page.set_origin(self.origin)

        self.page = page


    def update_file_info(self, filename, num_anc):
        self.filename = filename
        self.num_anc = num_anc


    # Associate common names with scientific names.  (Previously we didn't
    # have the properties in place to know what to do with common names.)
    def apply_names(self):
        page = find_page2(self.com, self.elab, from_inat=True,
                          taxon_id=self.taxon_id)
        if page:
            #info(f'applied iNat names to {page.full()}')
            pass
        else:
            info(f'no names match for iNat data: {self.com} ({self.elab}), tid={self.taxon_id}')
