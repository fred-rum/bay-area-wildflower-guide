# Accumulate observation stats for one or more hierarchies of pages.
#
# A color is declared when the Obs object is created, and only pages
# that match that color are counted.  If color is None, then all pages
# are treated as matching.
#
# In some cases, the counted stats are never written out to HTML.
# Instead, only the 'n' count is used in order to sort pages.  This
# means that we've wasted time accumulating the other stats, but the
# time spent is negligible, and it's simpler to just always do it
# rather than try to be selective.
#
# This isn't the cleanest of modules.  Obs looks directly into the
# page objects, and users of Obs sometimes look inside it for 'n'.

rg_supported = False
def set_rg_supported():
    global rg_supported
    rg_supported = True

class Obs:
    pass

    def __init__(self, color):
        self.match_set = set() # pages already searched, to avoid doublecounting
        self.color = color # color being searched for

        self.n = 0 # accumulated number of observations from observations.csv
        self.rg = 0 # number of research-grade observations as above
        self.parks = {} # subcounts for each park with observations
        self.month = [0] * 12 # subcounts for each month with observations

        self.key = 0 # number of key pages found in the hierarchy
        self.leaf_obs = 0 # number of leaf pages found with photos
        self.leaf_unobs = 0 # number of leaf pages found without photos

    # Accumulate the observations for a page and all its children and add
    # these to the current counts.  Each page must match the declared color
    # in order to count.
    def count_matching_obs(self, page):
        if page in self.match_set: return

        old_leaf_obs = self.leaf_obs

        for child in page.child:
            self.count_matching_obs(child)

        # If a container page contains exactly one descendant with a matching
        # color, the container isn't listed on the color page, and the color
        # isn't listed in page_color for the page.  Therefore, we follow all
        # child links blindly and only compare the color when we reach a flower
        # with an observation count.
        if page.page_matches_color(self.color):
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
                if page.jpg_list and self.leaf_obs == old_leaf_obs:
                    # If a page is both a key and an observed flower and none
                    # of its descendents is observed, then treat it as if one
                    # of its descendents is observed instead.
                    # However, if any descendent is observed, then we can't
                    # guarantee that the photos for the key page are of a
                    # different species, so we ignore the key photos.
                    self.leaf_obs += 1
                    self.leaf_unobs -= 1
            elif page.jpg_list:
                self.leaf_obs += 1
            else:
                self.leaf_unobs += 1

    def write_page_counts(self, w):
        w.write(f'<span class="parent">{self.key} keys</span>')
        w.write(f' / <span class="leaf">{self.leaf_obs} observed flowers</span>')
        if self.color is None and self.leaf_unobs == 0:
            # Unobserved pages don't normally have an assigned color,
            # so it doesn't make sense to try to print out how many
            # match the current color.
            w.write(f' / <span class="unobs">{self.leaf_unobs} unobserved flowers</span>')
        w.write('\n')

    def write_obs(self, link, w):
        n = self.n
        rg = self.rg

        w.write('<p>\n')

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
<span class="toggle-details" onclick="fn_details(event)" onkeydown="fn_details_keydown(event)" tabindex="0" role="button" aria-expanded="false">[show details]</span>
</p>
<div id="details">
Locations:
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

            w.write('</ul>\nMonths:\n<ul>\n')

            # break_month = None
            # for i in range(12):
            #     weight = 0
            #     for j in range(12):
            #         factor = abs((i+5.5-j) % 12 - 6)
            #         weight += self.month[j] / factor
            #     if i == 0: # bias toward January unless there's a clear winner
            #         weight /= 1
            #     if break_month is None or weight < break_weight:
            #         break_month = i
            #         break_weight = weight

            # first = None
            # for i in range(12):
            #     m = (i + break_month) % 12
            #     if self.month[m]:
            #         if first is None:
            #             first = i
            #         last = i

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
            w.write('</ul>\n</div>\n')
        else:
            w.write('\n</p>\n')
