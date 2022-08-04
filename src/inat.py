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

def read_inat_files():
    filenames = sorted(get_file_set('inat', 'json'))
    for filename in filenames:
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
def parse_inat_data(data, name):
    # raw_data could have a single data item
    # or a 'results' item with a list of data items.
    if 'results' in data and data['results']:
        data = data['results'][0]

    if 'id' not in data:
        inat_dict[name] = None
        return

    id = str(data['id'])
    rank = data['rank']
    sci = data['name']

    # iNaturalist uses the hybrid's special 'x' symbol in the
    # otherwise unelaborated scientific name, so we strip that out
    # when doing the comparison.
    sci = re.sub(' \\u00d7 ', r' ', sci)

    if (name != id) and (name != rank + ' ' + sci):
        inat_dict[name] = None
        # The fetched data may be useful, but it's more likely to be
        # confusing, so we ignore it.
        return

    Inat(data, f'{name}.json')
    if 'ancestors' in data and data['ancestors']:
        #info('processing ancestors')
        for anc_data in data['ancestors']:
            Inat(anc_data, f'ancestors of {name}.json')

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

# link_inat() did the work of initiating page fetches by name or TID.
# link_inat2() actually links and traverses the pagse,
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
        if not child.rank:
            continue
        elif not child.taxon_id or child.taxon_id not in inat_dict:
            warn(f'missing iNat data for {child.full()}')
            continue

        inat_child = inat_dict[child.taxon_id]

        if not inat_child.parent_id:
            warn(f'iNat linking failed due to missing parent ID from iNat data for child {child.full()}')
            continue
        elif inat_child.parent_id not in inat_dict:
            warn(f'iNat linking failed due to missing iNat data for parent ID {inat_child.parent_id} from child {child.full()}')
            continue

        inat_parent = inat_dict[inat_child.parent_id]
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
    if page.taxon_id and page.taxon_id in inat_dict:
        inat_child = inat_dict[page.taxon_id]
        if inat_child.parent_id:
            tid_set.add(inat_child.parent_id)
        for anc in inat_child.anc_id_list:
            tid_set.add(anc)

# Get an iNaturalist record or None.
def get_inat(name):
    if name in inat_dict:
        return inat_dict[name]
    else:
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
    if page.taxon_id in inat_dict:
        return inat_dict[page.taxon_id]

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
        filename = f'{rank} {sci}'
    else:
        q = f'q={sci}'
        filename = sci

    url = f'https://api.inaturalist.org/v1/taxa/autocomplete?{q}&per_page=1&is_active=true&locale=en&preferred_place_id=14'

    # Make sure we don't repeatedly pound the same URL.
    if filename in inat_dict:
        return inat_dict[filename]

    if not arg('-api') or not page.sci:
        return None

    fetch(url, [filename])

    return get_inat(page.taxon_id)

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

    fetch(url, tid_list)

def fetch(url, filename_list):
    global api_called
    if api_called:
        if arg('-api_delay'):
            delay = int(arg('-api_delay'))
        else:
            delay = 10
        time.sleep(delay)
    api_called = True

    info(url)
    r = requests.get(url, headers=req_headers)
    json_data = r.text
    try:
        data = json.loads(json_data)
    except:
        return None
    if 'results' not in data:
        return None

    for i, name in enumerate(filename_list):
        if len(data['results']) > i:
            write_inat_data(data['results'][i], name, url)
        else:
            write_inat_data({}, name, url)

    for i, name in enumerate(filename_list):
        if len(data['results']) > i:
            parse_inat_data(data['results'][i], name)
        else:
            parse_inat_data({}, name)

def write_inat_data(data, filename, url):
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

    def __init__(self, data, src):
        # A taxon_id is circulated internally as a string, not an integer.
        self.taxon_id = str(data['id'])

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

        if 'preferred_establishment_means' in data:
            self.origin = data['preferred_establishment_means']
        else:
            self.origin = None

        self.anc_id_list = []
        if 'ancestor_ids' in data:
            for tid in data['ancestor_ids']:
                self.anc_id_list.append(str(tid))

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
