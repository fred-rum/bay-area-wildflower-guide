# Read and process the observations.csv file

import csv

# My files
from page import *
from core import *


# Map the names used in iNaturalist observation locations
# to consistent park names for use in the HTML.
park_map = {}
park_loc = {}

# master set of trips; each as (date string, park name)
trips = set()

def read_parks(f):
    yaml_data = yaml.safe_load(f)

    for loc in yaml_data:
        for x in yaml_data[loc]:
            if isinstance(x, str):
                semi1 = x.find(';')
                if semi1 == -1:
                    name = x
                    exp = x
                else:
                    semi2 = x.find(';', semi1+1)
                    if semi2 == -1:
                        name = x[:semi1] + x[semi1+1:]
                        exp = x[:semi1]
                    else:
                        name = x[:semi1] + x[semi1+1:semi2] + x[semi2+1:]
                        exp = x[semi1+1:semi2]
                x = {name: exp}

            assert isinstance(x, dict)

            # x should typically be a dict with a single key/value pair,
            # but we also accept multiple key/value pairs.
            for name, exp in x.items():
                if isinstance(exp, str):
                    park_map[exp] = name
                    park_loc[exp] = loc
                else:
                    # the expression is actually a list
                    assert isinstance(exp, list)
                    exp_list = exp
                    for exp in exp_list:
                        park_map[exp] = name
                        park_loc[exp] = loc

sci_ignore = {}

def read_ignore_species(f):
    global sci_ignore
    sci_ignore = yaml.safe_load(f)

    for sci in sci_ignore:
        # Keep only the first character ('+' or '-') and ignore the comment.
        sci_ignore[sci] = sci_ignore[sci][0]

        if sci in isci_page:
            page = isci_page[sci]
        else:
            page = find_page1(sci)

        if page and not page.shadow:
            error(f'{sci} is ignored, but there is a real page for it: {page.full()}')


# Read the taxonomic chains from the observations file (exported from
# iNaturalist).  There is more data in there that we'll read later, but
# first we want to complete the Linnaean tree so that properties can be
# properly applied.
def read_obs_chains(f):
    def get_field(fieldname):
        if fieldname in row:
            return row[fieldname]
        else:
            return None

    csv_reader = csv.DictReader(f)

    for row in csv_reader:
        sci = get_field('scientific_name')
        taxon_id = get_field('taxon_id')
        gall_code = get_field('field:gallformers code')

        # In the highly unusual case of no scientific name for an
        # observation, just throw it out.  And if there is a scientific
        # name, I'd expect that there should be a taxon_id as well.
        if (not sci or not taxon_id) and not gall_code:
            continue

        orig_sci = sci

        # Remove the special 'x' sign used by hybrids since I
        # can't (yet) support it cleanly.  Note that I *don't* use
        # the r'' string format here because I want the \N to be
        # parsed during string parsing, not during RE parsing.
        sci = re.sub(' \N{MULTIPLICATION SIGN} ', r' X', sci)

        com = get_field('common_name')

        # The common name is forced to all lower case to match my
        # convention.
        if com:
            com = com.lower()
        else:
            com = None

        if gall_code:
            if gall_code in gsci_page:
                page = gsci_page[gall_code]
                found_lowest_level = True
            else:
                print(f'observed {gall_code} matches no page')
                continue # !@# temporary

        with Progress(f'Read taxonomy chain from observations.csv, line {csv_reader.line_num} for {com} ({sci})'):
            # Get an unambiguous rank from the core data if possible.
            # A hybrid will always fail because the core data doesn't
            # expect its 'X', but a hybrid is unambiguous anyway.
            core_rank = get_core_rank(sci, taxon_id)

            # Read the taxonomic chain from observations.csv and create
            # Linnaean links accordingly.
            page = None
            found_lowest_level = False
            for rank in Rank:
                group = get_field(f'taxon_{rank.name}_name')

                # ignore an empty group string
                if not group:
                    continue

                # The first non-empty group that is found usually tells us
                # the rank of the observed taxon.  Find or create a page
                # with the appropriate rank.
                if not found_lowest_level:
                    sci_words = sci.split(' ')
                    if (get_field('taxon_subspecies_name') or
                        core_rank == 'subspecies'):
                        sci = ' '.join((sci_words[0], sci_words[1],
                                        'ssp.', sci_words[2]))
                    elif (get_field('taxon_variety_name') or
                          core_rank == 'variety'):
                        sci = ' '.join((sci_words[0], sci_words[1],
                                        'var.', sci_words[2]))
                    elif ' X' in sci:
                        pass
                    elif ' ' in sci and (rank is Rank.species or
                                         core_rank == 'species'):
                        # If the scientific name has at least one space,
                        # then it is a species, subspecies, or variety that
                        # should have already been elaborated as necessary.
                        # ... unless it's a complex, which is a higher rank
                        # than species, so the first matching rank won't
                        # be 'species'
                        pass
                    elif core_rank:
                        sci = f'{core_rank} {sci}'
                    elif group == orig_sci:
                        # If the first name in the taxonomic chain matches
                        # the observed taxon name, then it directly tells
                        # us the taxon rank.
                        # ... unless its a subgenus whose name matches the
                        # genus name.  In which case we either need the
                        # core data to supply a rank (above) or the txt
                        # to supply a taxon_id so that the elab look-up is
                        # skipped.
                        sci = f'{rank.name} {sci}'
                    else:
                        # If the first name in the taxonomic chain doesn't
                        # match the observed taxon name, then the observed
                        # taxon must be an unrecognized rank.  Try to find
                        # a matching page of any rank.
                        pass

                    # Check whether a page already exists for the taxon.
                    # If find_page2() finds a match, it automatically sets the
                    # taxon_id for the page if it didn't have it already.
                    page = find_page2(com, sci, from_inat=True,
                                      taxon_id=taxon_id,
                                      src='observations.csv', date=now())

                    # if find_page2() didn't find a match, create a shadow
                    # page for the taxon.
                    if not page:
                        if (group != orig_sci and
                            not ' ssp. ' in sci and
                            not ' var. ' in sci and
                            not sci.startswith('complex ') and
                            not core_rank):
                            # We have to create a page for a taxon of unknown
                            # rank.  On the assumption that the observation
                            # will get promoted to a higher-level taxon, we
                            # fudge it here by pretending it's the lowest rank.
                            # set_sci() recognizes this as a guess that can
                            # be updated later.
                            sci = f'below {sci}'

                        page = Page(com, sci, shadow=True, from_inat=True,
                                    src='observations.csv')
                        page.set_taxon_id(taxon_id, from_obs=True,
                                          src='observations.csv', date=now())

                    if group != orig_sci:
                        # This is the lowest-level group we found, but
                        # since the taxon name doesn't match, the observed
                        # taxon must be at a lower level that isn't included
                        # in the observations.csv ranks.
                        #
                        # Note: this test isn't mixed in with the above
                        # 'group == orig_sci' tests because we don't want
                        # to exclude species/subspecies/varieties here.
                        found_lowest_level = True

                if found_lowest_level:
                    # add_linn_parent() adds the page for the parent
                    # (if necessary) and the link from parent to child.
                    page = page.add_linn_parent(rank, group,
                                                from_inat='observations.csv')

                found_lowest_level = True


# Read my observations file (exported from iNaturalist) and use it as follows
# for each observed taxon:
#   Associate common names with scientific names.  (Previously we didn't have
#     the properties in place to know what to do with common names.)
#   Get a count of observations (total and research grade).
#   Get an iNaturalist taxon ID.
def read_observation_data(f):
    def get_field(fieldname):
        if fieldname in row:
            return row[fieldname]
        else:
            return None

    set_any_observations()

    csv_reader = csv.DictReader(f)

    if 'quality_grade' in csv_reader.fieldnames:
        set_rg_supported()

    for row in csv_reader:
        sci = get_field('scientific_name')
        taxon_id = get_field('taxon_id')

        # In the highly unusual case of no scientific name for an
        # observation, just throw it out.  And if there is a scientific
        # name, I'd expect that there should be a taxon_id as well.
        if not sci or not taxon_id: continue

        # Modify the special 'x' sign used by hybrids to the BAWG format.
        # Note that I *don't* use the r'' string format here because I want
        # the \N to be parsed during string parsing, not during RE parsing.
        sci = re.sub(' \N{MULTIPLICATION SIGN} ', r' X', sci)

        com = get_field('common_name')

        # The common name is forced to all lower case to match my
        # convention.
        if com:
            com = com.lower()

        rg = get_field('quality_grade')

        park = get_field('private_place_guess')
        if not park:
            park = get_field('place_guess')

        with Progress('Park not recognized:'):
            for x in park_map:
                if re.search(x, park):
                    short_park = park_map[x]
                    loc = park_loc[x]
                    break
            else:
                error(park)
                short_park = park
                loc = 'unknown'

        date = get_field('observed_on')
        month = int(date.split('-')[1], 10) - 1 # January = month 0

        gall_code = get_field('field:gallformers code')

        page = None

        if gall_code:
            if gall_code in gsci_page:
                page = gsci_page[gall_code]
                found_lowest_level = True
            else:
                continue # !@# temporary

        if not page:
            # This call to find_page2() should always match a taxon_id
            # from the first pass through observations.csv.  However, that
            # first pass didn't yet have the property information to know
            # whether to add an alternative name from iNaturalist.  So we
            # supply the names again for that purpose.
            page = find_page2(com, sci, from_inat=True, taxon_id=taxon_id,
                              src='observations.csv', date=now())

        # A Linnaean page should have been created during the first path
        # through observations.csv, so it'd be weird if we can't find it.
        assert page

        page_below = page.equiv_page_below()
        if page_below:
            page = page_below

        # If we haven't matched the observation to a real page, advance
        # up the Linnaean hierarchy until we find a real page.  We'll
        # check later whether this promotion is allowed.
        orig_sci = sci
        orig_page = page
        ignore = False
        disable_promotion_checks = True # may change to False in loop below
        while page.shadow:
            if sci in sci_ignore:
                if sci_ignore[sci] == '+':
                    ignore = True
                else: # '-'
                    # The obesrvations should be entirely ignored.
                    # Stop promoting on the ignored page.
                    break
            else:
                msg = f'{orig_page.full()} observation can create page {page.full()}'
                if (loc == 'bay area' and
                    not page.has_real_linnaean_descendants() and
                    (page.rp_do('obs_create', shadow=True, msg=msg) or
                     (page.com and
                      page.rp_do('obs_create_com', shadow=True, msg=msg)))):
                    page.promote_to_real()
                    break

            # If any rank that we promote through fails to disable promotion
            # checks, then promotion checks aren't disabled.
            if not page.rp_do('disable_obs_promotion_checks_from',
                              shadow=True):
                disable_promotion_checks = False

            page = page.linn_parent
            if not page:
                break
            sci = page.sci
            if ignore:
                # Update orig_page to match the new promoted page,
                # thus pretending that there was no promotion.
                orig_page = page

        if not page or (sci in sci_ignore and sci_ignore[sci] == '-'):
            # the observation is not contained by *any* page, or
            # the observation'so taxon (or some taxon it was promoted through)
            # should be completely ignored.
            continue

        if (loc != 'bay area' and
            not page.rp_do('outside_obs')):
            continue

        if (rg == 'casual' and
            not page.rp_do('casual_obs')):
            continue

        if page != orig_page:
            # The page got promoted.

            # The following code mostly decides whether to complain about the
            # promotion.  Any code path that results in a "pass" statement
            # means that no complaint should be issued.
            if loc != 'bay area':
                # We never complain if an observation outside the bay area
                # isn't in the guide.
                pass
            elif orig_page.rank_unknown:
                # If an observation has an unknown rank, then we always
                # promote it without complaint.
                pass
            elif orig_page.has_real_linnaean_descendants():
                # If the observation's original (shadow) page has real Linnaean
                # descendants, then we don't know what it is, but it could
                # be something we've documented, so it's always OK.
                #print(f'{orig_page.full()} has real descendents')
                pass
            elif disable_promotion_checks:
                # Ignore observations that aren't at a desired level of
                # specificity and weren't promoted through a desired level.
                #print('disable_obs_promotion_checks_from')
                pass
            elif (rg == 'needs_id' and
                  orig_page.rp_do('disable_obs_promotion_checks_from_needs_id',
                                  shadow=True)):
                # Ignore observations without agreement.
                #print('needs_id')
                pass
            elif page.taxon_uncat():
                # Ignore observations that are promoted to a taxon that
                # doesn't care about lower levels.  The function call checks
                # disable_obs_promotion_to_incomplete when appropriate.
                #print(f'{orig_page.full()} is uncat')
                pass
            else:
                page.rp_check('obs_promotion',
                              f'{orig_page.full()} observation promoted to {page.full()}')

            # Now check whether the observation should be counted.
            if not page.rp_action('obs_promotion', 'do'):
                continue
            if (loc != 'bay area'
                and (not page.rp_do('outside_obs_promotion') or page.child)):
                    continue
            if (rg == 'casual'
                and (not page.rp_do('casual_obs_promotion') or page.child)):
                    continue


        page.obs_n += 1
        if rg == 'research':
            page.obs_rg += 1
        if short_park not in page.parks:
            page.parks[short_park] = 0
        page.parks[short_park] += 1
        page.month[month] += 1

        page.trips.add((date, short_park))
        trips.add((date, short_park))

def write_trips_to_pages_js(w):
    w.write('const trips=[\n')
    for trip in sorted(trips):
        assign_zcode(trip)
        w.write(f'["{trip[0]}","{trip[1]}"],\n')
    w.write('];\n')
