# Accumulate observation stats for one or more hierarchies of pages.
#
# A trait and value are declared when the Cnt object is created, and
# only pages that match that trait and value are counted.  If trait is
# None, then all pages are treated as matching.
#
# In some cases, the counted stats are never written out to HTML.
# Instead, only the 'n' count is used in order to sort pages.  This
# means that we've wasted time accumulating the other stats, but the
# time spent is negligible, and it's simpler to just always do it
# rather than try to be selective.
#
# This isn't the cleanest of modules.  Cnt looks directly into the
# page objects, and users of Cnt sometimes look inside it for 'n'.

rg_supported = False
def set_rg_supported():
    global rg_supported
    rg_supported = True

any_observations = False
def set_any_observations():
    global any_observations
    any_observations = True

class Cnt:
    pass

    def __init__(self, trait, value):
        self.match_set = set() # pages already searched, to avoid doublecounting
        self.trait = trait # trait being searched for; may be None
        self.value = value # trait value being searched for

        self.n = 0 # accumulated number of observations from observations.csv
        self.rg = 0 # number of research-grade observations as above
        self.parks = {} # subcounts for each park with observations
        self.month = [0] * 12 # subcounts for each month with observations

        self.key = 0 # number of key pages found in the hierarchy
        self.leaf_obs = 0 # number of leaf pages found with photos
        self.leaf_unobs = 0 # number of leaf pages found without photos

    # Accumulate the observations for a page and all its children and add
    # these to the current counts.  Each page must match the declared trait
    # value in order to count.
    def count_matching_obs(self, page):
        if page in self.match_set: return

        old_leaf_obs = self.leaf_obs

        for child in page.child:
            self.count_matching_obs(child)

        if page.page_matches_trait_value(self.trait, self.value):
            self.match_set.add(page)
            self.n += page.obs_n
            self.rg += page.obs_rg
            for park in page.parks:
                if park not in self.parks:
                    self.parks[park] = 0
                self.parks[park] += page.parks[park]
            for i in range(12):
                self.month[i] += page.month[i]

            if page.child:
                if page.has_child_key:
                    self.key += 1
                if page.photo_dict and self.leaf_obs == old_leaf_obs:
                    # If a page is both a key and an observed flower and none
                    # of its descendents is observed, then treat it as if one
                    # of its descendents is observed instead.
                    # However, if any descendent is observed, then we can't
                    # guarantee that the photos for the key page are of a
                    # different species, so we ignore the key photos.
                    self.leaf_obs += 1
                    self.leaf_unobs -= 1
            elif page.photo_dict:
                self.leaf_obs += 1
            else:
                self.leaf_unobs += 1

    def write_page_counts(self, w):
        node_strs = []
        if (self.leaf_obs > 1 or
            (self.leaf_obs == 1 and (self.leaf_unobs or self.key))):
            s = 's' if (self.leaf_obs > 1) else ''
            node_strs.append(f'<span class="leaf">{self.leaf_obs} observed taxon{s}</span>')
        if (self.leaf_unobs > 1 or
            (self.leaf_unobs == 1 and (self.leaf_obs or self.key))):
            s = 's' if (self.leaf_unobs > 1) else ''
            node_strs.append(f'<span class="unobs">{self.leaf_unobs} unobserved taxon{s}</span>')
        if self.key:
            s = 's' if (self.key > 1) else ''
            node_strs.append(f'<span class="parent">{self.key} key{s}</span>')

        if node_strs:
            node_str = ' / '.join(node_strs)
            w.write(f'<p>\n{node_str}\n</p>\n')

    def write_obs(self, w, link, adv_link):
        if not any_observations:
            return

        n = self.n
        rg = self.rg

        self.write_page_counts(w)

        w.write('<p>\n')

        if n:
            w.write('<details>\n<summary>\n')

        if link:
            w.write(f'<a href="{link}" target="_blank" rel="noopener noreferrer">Chris&rsquo;s observations</a>: ')
        else:
            w.write('Chris&rsquo;s observations: ')

        if n == 0:
            w.write('none')
        elif not rg_supported:
            w.write(f'{n}')
        elif rg == 0:
            w.write(f'{n} (none are research grade)')
        elif rg == n:
            if n == 1:
                w.write('1 (research grade)')
            else:
                w.write(f'{n} (all are research grade)')
        else:
            if rg == 1:
                w.write(f'{n} ({rg} is research grade)')
            else:
                w.write(f'{n} ({rg} are research grade)')

        if n:
            w.write('''
</summary>
<p>Locations:</p>
<ul>
''')
            park_list = sorted(self.parks)
            park_list = sorted(park_list,
                               key = lambda x: self.parks[x],
                               reverse=True)
            for park in park_list:
                count = self.parks[park]
                if count == 1:
                    w.write(f'<li>{park}</li>\n')
                else:
                    w.write(f'<li>{park}: {count}</li>\n')

            w.write('</ul>\n<p>Months:</p>\n<ul>\n')

            # Search for the longest run of zeros in the month data.
            z_first = 0
            z_length = 0
            for i in range(12):
                for j in range(12):
                    if self.month[(i+j) % 12]:
                        # break ties around January
                        if (j > z_length or
                            (j == z_length and (i == 0 or i+j >= 12))):
                            z_first = i
                            z_length = j
                        break

            month_name = ['Jan.', 'Feb.', 'Mar.', 'Apr.', 'May', 'Jun.',
                          'Jul.', 'Aug.', 'Sep.', 'Oct.', 'Nov.', 'Dec.']

            # Iterate through all months that are *not* part of the longest
            # run of zeros (even if some of those months are themselves zero).
            for i in range(12 - z_length):
                m = (i + z_first + z_length) % 12
                w.write(f'<li>{month_name[m]}: {self.month[m]}</li>\n')
            w.write('</ul>\n')

            w.write(f'<p>For more details, use <a href="{adv_link}">advanced search</a>.</p>')
            w.write('<hr>\n')
            w.write('</details>\n')
        else:
            w.write('\n</p>\n')
