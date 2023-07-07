/* Copyright Chris Nelson - All rights reserved. */

'use strict';

/*****************************************************************************/
/* code related to the photo gallery */

/* Ideally, we want gallery_main() to be called after the thumbnails are
   loaded into the DOM, but before the user can click on them.  But the
   only way to perfectly guarantee this is to write potentially a lot of
   JavaScript directly into the HTML file.  Parts of the JavaScript could
   potentially be in a separate script file, but that file would have to
   be loaded synchronously, thus slowing down the page display.

   Instead, we allow the JavaScript to load separately and asynchronously,
   then try to annotate the HTML as quickly as possible.  This ends up
   calling gallery_main() twice:

   1. We call gallery_main() as soon as the JavaScript is loaded.  Since the
   HTML is small and the script is large, most likely the HTML has already
   loaded and populated the DOM, so this is as fast as we can go.
   This call is at the end of the photogallery section.

   2. In case the DOM was *not* fullly populated the first time, we call
   gallery_main() again once the DOM is complete.  The second call shouldn't
   re-annotate any photos that were already annotated, but it would be fine
   even if it did.

   Note that if the DOM is complete before the script finishes loading,
   both calls may be made consecutively once the script has loaded.
*/
var annotated_href_list = [];
function gallery_main() {
  /* Decode the current page's URL.
     It is expected to start with any string,
     followed by an optional 'html/',
     followed by the page name (encoded as needed),
     followed by '.html'. */
  const html_url = window.location.pathname;
  const matches = /(?:html\/)?[^\/]*\.html$/.exec(html_url);
  if (matches) {
    /* The page name in the pathname has different encoding requirements when
       moved to the search component of the URL. */
    var prefix = window.location.origin + html_url.substr(0, matches.index);
  } else {
    /* If the URL doesn't end with '*.html', then we assume it ends in '/',
       which implicitly maps to 'index.html'. */
    var prefix = window.location.origin + html_url
    if (!prefix.endsWith('/')) {
      prefix += '/';
    }
  }

  /* Change each link to a BAWG photo or figure to instead link via the
     gallery page. */
  const e_link_list = document.links

  for (var i = 0; i < e_link_list.length; i++) {
    /* Look for any href that starts with the same start of the URL as the
       current page, followed by 'photos/' or 'figures/'.  We assume that all
       hrefs are in the same canonical form, so we don't need to figure out all
       the ways that different hrefs could map to the same URL. */
    const href = e_link_list[i].href;
    if (href.startsWith(prefix + 'photos/') ||
        href.startsWith(prefix + 'figures/')) {
      var suffix = decodeURI(href.substr(prefix.length));
      console.log('annotating link to', suffix);

      /* Simplify the URL in case the user looks at it. */
      suffix = munge_photo_for_url(suffix);

      /* The path to the photo has different encoding requirements when
         moved to the search component of the URL. */
      const suffix_query = encodeURIComponent(suffix);

      /* Replace the href to point to the gallery. */
      e_link_list[i].href = prefix + 'gallery.html?' + suffix;
    } else {
      console.log('not annotating link to', href);
    }
  }
}

/* This function must exactly match what is in gallery.js. */
function munge_photo_for_url(path) {
  /* Remove directory name, e.g. 'photos/'. */
  var slash_pos = path.indexOf('/')
  if (slash_pos != -1) {
    path = path.substring(slash_pos+1);
  }

  /* Remove extension, e.g. '.jpg'. */
  var dot_pos = path.indexOf('.')
  if (dot_pos != -1) {
    path = path.substring(0, dot_pos);
  }

  /* Convert common characters that must be percent-encoded to characters
     that are allowed after the '?' in the URL. */
  path = path.replace(/[/ ,/]/g, function (c) {
    return {
      '/': '-',
      ' ': '-',
      ',': '.'
    }[c];
  });

  /* Remove characters that must be percent-encoded. */
  path = path.replace(/[^A-Za-z0-9-.]/g, '');

  return path;
}

/* This call has to be after all gallery-related function definitions.
   It may be slightly helpful to have it prior to all the search-related
   code in case the browser can execute it while the rest of the script
   is still downloading. */
gallery_main();


/*****************************************************************************/
/* code related to the search bar */

var ac_is_hidden = true;
function expose_ac() {
  e_autocomplete_box.style.display = 'block';
  ac_is_hidden = false;
  e_home_icon.className = 'with-autocomplete';
}

function hide_ac() {
  if (!ac_is_hidden) {
    e_autocomplete_box.style.display = 'none';
    ac_is_hidden = true;
    e_home_icon.className = '';
  }
}

function fn_focusin() {
  if (ac_is_hidden) {
    /* e_search_input.select(); */ // Not as smooth on Android as desired.
    fn_search();
  }
}

function fn_pageshow() {
  hide_ac();
}

function fn_doc_click(event) {
  var search_element = event.target.closest('#search-container');
  if (!search_element) {
    hide_ac();
  }
}

/* Global variable so that it can be used by independent events. */
var ac_list;
var ac_selected;

function clear_search() {
  e_search_input.value = '';
  ac_list = [];
  ac_selected = 0;
  hide_ac();
}

/* When comparing names, ignore all non-letter characters and ignore case. */
function compress(name) {
  return name.toUpperCase().replace(/\W/g, '');
}

/* Find the position of the Nth letter in string 'str'.
   I.e. search for N+1 letters, then back up one. */
function find_letter_pos(str, n) {
  var regex = /\w/g;

  for (var i = 0; i <= n; i++) {
    /* We use test() to advance regex.lastIndex.
       We don't bother to check the test() return value because we always
       expect it to match.  (E.g. when finding the last letter of match,
       we really are looking for the last letter, which always exists.) */
    regex.test(str);
  }

  return regex.lastIndex - 1;
}

function index_of_letter(str, letter_num) {
  var letter_cnt = 0;
  for (var i = 0; letter_cnt < letter_num; i++) {
    if (str.substring(i).search(/^\w/) >= 0) {
      letter_cnt++;
    }
  }

  return i;
}

/* These functions are run only on scientific names, so they only need
   to handle ASCII and not weird Unicode. */
function startsUpper(name) {
  return (name.search(/^[A-Z]/) >= 0);
}

function hasUpper(name) {
  return (name.search(/[A-Z]/) >= 0);
}

/* Get the relative path to a page. */
function fn_url(fit_info) {
  var page_info = fit_info.page_info;

  if (page_info.x == 'j') {
    var url = 'https://ucjeps.berkeley.edu/eflora/glossary.html';
  } else {
    var url = path + page_info.page + '.html';
    url = url.replace(/ /g, '-')
  }

  if ('anchor' in fit_info) {
    url += '#' + fit_info.anchor;
  }

  return encodeURI(url);
}

/* Construct all the contents of a link to a page. */
function fn_link(fit_info) {
  var page_info = fit_info.page_info;

  if (page_info.x == 'f') {
    var c = 'family';
  } else if (page_info.x == 'k') {
    var c = 'parent';
  } else if (page_info.x == 'o') {
    var c = 'leaf';
  } else if (page_info.x == 'g') {
    var c = 'glossary';
  } else if (page_info.x == 'j') {
    var c = 'jepson';
  } else {
    var c = 'unobs';
  }

  var target = '';
  var url = fn_url(fit_info);

  /* I tried this and didn't like it.  If I ever choose to use it, I also
     have to change the behavior of the return key (where fn_url is used). */
  /*if (page_info.x == 'j') {
    target = ' target="_blank" rel="noopener noreferrer"';
  }*/

  return 'class="enclosed ' + c + '"' + target + ' href="' + url + '" onclick="return fn_click();"';
}

function generate_ac_html() {
  if (ac_list.length) {
    var html = '';
    for (var i = 0; i < ac_list.length; i++) {
      if (i == ac_selected) {
        html += '<b>' + ac_list[i].html + '</b>';
      } else {
        html += ac_list[i].html;
      }
    }
    e_autocomplete_box.innerHTML = html;
  } else {
    e_autocomplete_box.innerHTML = 'No matches found.';
  }
}

/* Look for a fuzzy match of the user-entered search_str against a value from
   the pages array, match_str.  The "fuzzy" part of the match is that
   punctuation/whitespace is mostly ignored (e.g. "hedgenettle" matches "hedge
   nettle").  In addition, wherever punctuation/whitespace appears in
   search_str, it can skip any number of letters in match_str.  If there is
   a match, return an object with information about the match including its
   priority (higher is better).  If there is no match, return null. */
function check(search_str, match_str, pri_adj) {
  /* search_str has already been converted to upper case, and we keep its
     punctuation intact.  I just copy it to a shorter variable name here for
     convenience. */
  var s = search_str;

  /* m is the string we're trying to match against, converted to uppercase
     and with punctuation removed. */
  var upper_str = match_str.toUpperCase()
  var m = upper_str.replace(/\W/g, '');

  /* If match_str is of the format "<rank> <Name>", get the starting index of
     Name within m.  This assumes that <rank> is all normal letters, so the
     index of Name within m is the same as the index of the ' ' within
     match_str.  If the first word is uppercase (not a rank) or the second word
     is not uppercase (not a scientific name), then name_pos is set to 0
     instead. */
  var name_pos = match_str.indexOf(' ');
  if ((name_pos < 0) ||
      (match_str.substr(0, 1) == upper_str.substr(0, 1)) ||
      (match_str.substr(name_pos+1, 1) != upper_str.substr(name_pos+1, 1))) {
    name_pos = 0;
  }

  /* match_ranges consists of [start, end] pairs that indicate regions in m for
     which a match was made */
  var match_ranges = [];

  /* i and j are the current position indexes into s and m, respectively */
  var i = 0;
  var j = 0;

  while (true) {
    /* find the first letter character in s */
    while ((/\W/.test(s.substr(i, 1))) && (i < s.length)) {
      i++;
    }
    var start_i = i;

    if (i == s.length) {
      break; // match complete
    }

    /* find end of letter characters */
    while ((/\w/.test(s.substr(i, 1))) && (i < s.length)) {
      i++;
    }

    var s_word = s.substring(start_i, i);
    var start_j = m.indexOf(s_word, j);
    if (start_j == -1) {
      return null; // no match
    }
    j = start_j + (i - start_i);
    if (match_ranges.length &&
        (match_ranges[match_ranges.length-1][1] == start_j)) {
      /* The next match follows directly from the previous match without
         skipping any letters.  (It might skip punctuation.)  Instead of
         adding a new match range, simply extend the previous one. */
      match_ranges[match_ranges.length-1][1] = j;
    } else {
      match_ranges.push([start_j, j]);
    }
  }

  /* Start with a priority high enough that the various decrements probably
     won't reduce it below 0.  (Although I'm not sure if that matters. */
  var pri = 100.0;

  pri += pri_adj;

  /* Decrease the priority a bit depending on how many different ranges are
     required to complete the match. */
  pri -= (match_ranges.length / 10);

  /* Increase the priority a bit if the first match range is at the start
     of the string.  The bump means that a match that starts at the
     beginning and has two match ranges is slightly better than one that
     starts later and has only one match range.  E.g. "gland glossary"
     matches "gland (plant glossary)" better than "England (glossary)".

     If the match starts after the rank but at the beginning of actual
     name, that's prioritized the same as a match at the beginning of
     the string. */
  if ((match_ranges[0][0] == 0) ||
      (match_ranges[0][0] == name_pos)) {
    pri += 0.15;
  }

  /* Construct an object with the necessary information about the match. */
  var match_info = {
    pri: pri,
    match_str: match_str,
    match_ranges: match_ranges
  }

  return match_info;
}

/* Check whether match_info one has greater priority than two.
   Either value can be null, which is considered lowest priority. */
function better_match(one, two) {
  return (one && (!two || (one.pri > two.pri)));
}

/* For a list of names for a page, call check() on each name and each
   combination of glossary term and page name.  Return the best match. */
function check_list(search_str, match_list, page_info) {
  var best_match_info = null;
  var pri_adj = 0.0;
  for (var i = 0; i < match_list.length; i++) {
    var name = match_list[i];
    if ((page_info.x == 'g') || (page_info.x == 'j')) {
      name = 'glossary: ' + name;
    }
    var match_info = check(search_str, name, pri_adj);
    if (!match_info && name.startsWith('genus ')) {
      /* Allow a genus to match using the older 'spp.' style. */
      match_info = check(search_str, name.substr(6) + ' spp.');
    }
    if (better_match(match_info, best_match_info)) {
      best_match_info = match_info;
    }

    /* Secondary names have slightly reduced priority.  E.g. a species
       that used to share a name with another species can be found with
       that old name, but the species that currently uses the name
       is always the better match.  So we adjust the priority slightly
       for all names in the match_list after the first. */
    pri_adj = -0.01;
  }

  return best_match_info;
}

function glossary_check_list(search_str, glossary, name_list, page_info) {
  var best_match_info = null;
  var pri_adj = 0.0; /* alternative terms are all the same priority */
  for (var i = 0; i < name_list.length; i++) {
    for (var k = 0; k < glossary.terms.length; k++) {
      var term_str = glossary.terms[k] + ' (glossary: ' + name_list[i] + ')';
      var match_info = check(search_str, term_str, pri_adj);
      if (better_match(match_info, best_match_info)) {
        best_match_info = match_info;
      }
    }
  }

  return best_match_info;
}

/* Using the match_info constructed in check(), highlight the matched
   ranges within the matched string.  Or if match_info is null (because
   the other com/sci name of a page was matched), return default_name
   without highlighting.

   In either case, if it's a scientific name, italicize the Greek/Latin
   words (either the whole string or everything after the first word). */
function highlight_match(match_info, default_name, is_sci) {
  var tag_info = [];

  /* h is the highlighed string to be returned. */
  var h = '';

  if (match_info) {
    var m = match_info.match_str;
    var match_ranges = match_info.match_ranges;

    /* Convert match_ranges (which ignores punctuation) into string positions
       (which includes punctuation). */
    var ranges = [];
    for (var i = 0; i < match_ranges.length; i++) {
      var begin = find_letter_pos(m, match_ranges[i][0]);

      /* Stop highlighting just after letter N-1.  I.e. don't include
         the punctuation between letter N-1 and letter N, which is the
         first letter outside the match range. */
      var end = find_letter_pos(m, match_ranges[i][1] - 1) + 1;

      ranges.push([begin, end]);
    }

    var highlight_info = {
      ranges: ranges,
      i: 0,
      half: 0,
      tag: ['<span class="match">', '</span>']
    };
    tag_info.push(highlight_info);
  } else {
    /* Rather than writing special code to handle italicization of the
     * scientific name for this default case, we can simply fall through the
     * regular highlighting code with no highlighted ranges. */
    var m = default_name;
  }

  if (is_sci) {
    var ranges = [[0, m.length]];

    if (m.endsWith(' spp.')) {
      ranges[0][1] -= 5;
    }
    var pos = m.indexOf(' ssp. ');
    if (pos == -1) {
      var pos = m.indexOf(' var. ');
    }
    if (pos != -1) {
      ranges.push([pos + 6, ranges[0][1]]);
      ranges[0][1] = pos;
    }

    if (!startsUpper(m)) {
      ranges[0][0] = m.indexOf(' ');
    }

    var italic_info = {
      ranges: ranges,
      i: 0,
      half: 0,
      tag: ['<i>', '</i>']
    };
    tag_info.push(italic_info);
  }

  /* Keep track of tag nesting, because interleaved tags fail in some browsers.
     E.g. <i>x<span>y</i>z</span> on Chrome moves </span> to before </i>. */
  var nest = [];

  var pos = 0;
  while (tag_info.length) {
    var info_idx = 0;
    var info = tag_info[0];
    for (var j = 1; j < tag_info.length; j++) {
      var infoj = tag_info[j];
      if (infoj.ranges[infoj.i][infoj.half] < info.ranges[info.i][info.half]) {
        info_idx = j;
        info = infoj;
      }
    }
    var next_pos = info.ranges[info.i][info.half];
    var s = m.substring(pos, next_pos);
    h += s;
    pos = next_pos;

    if (info.half == 0) {
      h += info.tag[0]; // open tag
      nest.push(info); // record its nesting level
    } else {
      /* close the tags that are nested within the tag we want to close */
      for (i = nest.length-1; nest[i] != info; i--) {
        h += nest[i].tag[1];
      }

      /* close the tag that we wanted to close */
      h += nest[i].tag[1];

      /* remove the closed tag from the nesting list */
      nest.splice(i, 1);

      /* re-open the previously nested tags */
      for (i = i; i < nest.length; i++) {
        h += nest[i].tag[0];
      }
    }

    info.half++;
    if (info.half == 2) {
      info.half = 0;
      info.i++;
      if (info.i == info.ranges.length) {
        /* remove entry from tag_info */
        tag_info.splice(info_idx, 1);
      }
    }
  }

  h += m.substring(pos);

  return h;
}

function insert_match(fit_info) {
  /* If there's a match, and
     - we don't already have 10 matches or
     - the new match is better than the last match on the list
     then remember the new match. */
  if ((ac_list.length < 10) || (fit_info.pri > ac_list[9].pri)) {
    /* Insert the new match into the list in priority order.  In case of
       a tie, the new match goes lower on the list. */
    for (var j = 0; j < ac_list.length; j++) {
      if (fit_info.pri > ac_list[j].pri) break;
    }
    ac_list.splice(j, 0, fit_info);
    /* If the list was already the maximum length, it is now longer than the
       maximum length.  Cut off the last entry. */
    if (ac_list.length > 10) {
      ac_list.splice(-1, 1);
    }
  }
}

/* Check for search matches in one page:
   - in its common name
   - in its scientific name
   - in its glossary terms */
function page_search(search_str, page_info) {
  if ('com' in page_info) {
    var com_match_info = check_list(search_str, page_info.com, page_info);
  } else {
    var com_match_info = null;
  }

  if ('sci' in page_info) {
    var sci_match_info = check_list(search_str, page_info.sci, page_info);
  } else {
    var sci_match_info = null;
  }

  if (com_match_info || sci_match_info) {
    if (better_match(com_match_info, sci_match_info)) {
      var pri = com_match_info.pri;
    } else {
      var pri = sci_match_info.pri;
    }

    var fit_info = {
      pri: pri,
      page_info: page_info,
      com_match_info: com_match_info,
      sci_match_info: sci_match_info
    };

    insert_match(fit_info);

    /* If there was a match on a page name, don't clutter up the auto-complete
       list with matches on its glossary terms. */
    return;
  }

  if ('glossary' in page_info) {
    /* We're willing to add one auto-complete entry for each separate anchor.
       We use the best fit among all terms associated with that anchor in
       combination with all page names. */
    var best_match_info = null;
    for (var j = 0; j < page_info.glossary.length; j++) {
      var glossary = page_info.glossary[j];

      /* Find the best match associated with glossary.anchor. */
      if ('com' in page_info) {
        var match_info = glossary_check_list(search_str, glossary,
                                             page_info.com, page_info);
      } else {
        var match_info = null;
      }

      if (match_info) {
        if ('anchor' in glossary) {
          var anchor = glossary.anchor;
        } else {
          var anchor = glossary.terms[0];
        }

        var fit_info = {
          pri: match_info.pri,
          page_info: page_info,
          com_match_info: match_info,
          sci_match_info: null,
          anchor: anchor
        };

        insert_match(fit_info);
      }
    }
  }
}

/* Search all pages for a fuzzy match with the value in the search field, and
   create an autocomplete list from the matches. */
function fn_search() {
  /* We compare uppercase to uppercase to avoid having to deal with case
     differences anywhere else in the code.  Note that this could fail for
     funky unicode such as the German Eszett, which converts to uppercase 'SS'.
     I'll deal with it if and when I ever use such characters in a name. */
  var search_str = e_search_input.value.toUpperCase();

  /* We need at least one letter to do proper matching. */
  if (!/\w/.test(search_str)) {
    hide_ac();
    return;
  }

  /* Iterate over all pages and accumulate a list of the best matches
     against the search value. */
  ac_list = [];
  for (var i = 0; i < pages.length; i++) {
    var page_info = pages[i];
    page_search(search_str, pages[i]);
  }

  for (var i = 0; i < ac_list.length; i++) {
    var fit_info = ac_list[i];
    var page_info = fit_info.page_info;

    if ('com' in page_info) {
      /* If there is a match in a common name, highlight it.
         If there is no match, use the default common name without highlighting.
         If there are alternative common names but no default common name,
         then com_highlight could end up as an empty string.  Conveniently,
         this gets treated the same as com_highlight == null when deciding
         whether to combine it with the scientific name. */
      const com = page_info['com'][0];
      var com_highlight = highlight_match(fit_info.com_match_info,
                                          com, false);

      /* If the match is not on the default common name,
         write the common name first followed by the matching name in brackets.
         If there is no default common name, an extra space gets added before
         the matching name in brackets, but the browser nicely suppresses the
         extra space. */
      if ((page_info.x != 'g') && (page_info.x != 'j') &&
          fit_info.com_match_info &&
          (fit_info.com_match_info.match_str != com)) {
        com_highlight = (com +
                         ' <span class="altname">[' +
                         com_highlight +
                         ']</span>');
      }
    } else {
      var com_highlight = null;
    }

    if ('sci' in page_info) {
      const sci = page_info['sci'][0];
      var sci_highlight = highlight_match(fit_info.sci_match_info,
                                          sci, true);
      if (fit_info.sci_match_info &&
          (fit_info.sci_match_info.match_str != sci)) {
        var sci_ital = highlight_match(null, sci, true);
        sci_highlight = (sci_ital +
                         ' <span class="altname">[' +
                         sci_highlight +
                         ']</span>');
      }
      sci_highlight = sci_highlight.replace(/:/, '&times; ');
    } else {
      var sci_highlight = null;
    }

    var link = fn_link(fit_info);

    if (com_highlight && sci_highlight) {
      var full = com_highlight + ' (' + sci_highlight + ')';
    } else if (sci_highlight) {
      var full = sci_highlight;
    } else {
      var full = com_highlight;
    }
    /* escape the quote mark in the regex to avoid confusing strip.py */
    full = full.replace(/\'/g, '&rsquo;');

    /* The link is applied to the entire paragraph so that padding above
       and below and the white space to the right are also clickable. */
    fit_info.html = ('<a ' + link + '><p class="nogap">' +
                     full + '</p></a>');
  }

  /* Highlight the first entry in bold.  This entry is selected if the
     user presses 'enter'. */
  ac_selected = 0;
  generate_ac_html();
  expose_ac();
}

/* A link to an anchor might go somewhere on the current page rather than
   going to a new page.  If the page doesn't change, the search will
   remain active.  That's not what we want, so we clear the search before
   continuing with the handling of the clicked link.  Note that the event
   is already known to be interacting with the link, so removing the
   autocomplete box with the link in it will still allow the click to
   activate the link as desired. */
function fn_click() {
  clear_search();
  return true; // continue normal handling of the clicked link
}

/* Handle all changes to the search value.  This includes changes that are
   not accompanied by a keyboard event, such as a mouse-based paste event. */
function fn_change() {
  fn_search();
}

/* Handle when the user presses various special keys in the search box.
   The default behavior for the arrow keys triggers on keydown, so at the
   very least we need to capture and suppress that behavior.  I also notice
   that the browser performs normal actions for all other keys on keydown.
   So it makes sense to also have my behavior trigger on keydown for
   consistency. */
function fn_keydown() {
  if ((event.key == 'Enter') && !ac_is_hidden && ac_list.length) {
    var fit_info = ac_list[ac_selected];
    var url = fn_url(fit_info);
    if (event.shiftKey || event.ctrlKey) {
      /* Shift or control was held along with the enter key.  We'd like to
         open a new window or new tab, respectively, but JavaScript doesn't
         really give that option.  So we just call window.open() and let the
         browser make the choise.  E.g. Firefox will only open a new tab
         (after first requiring the user to allow pop-ups), while Chrome will
         open a new tab if ctrl is held or a new window otherwise.  Nice! */
      window.open(url);
    } else {
      /* The enter key was pressed *without* the shift or control key held.
         Navigate to the new URL within the existing page. */
      window.location.href = url;
    }
    /* Opening a new window doesn't affect the current page.  Also, a
       search of the glossary from a glossary page might result in no
       page change.  In either case, the search will remain active,
       which is not what we want.  In either case, clear the search. */
    clear_search();
  } else if (event.key == 'Escape') {
    clear_search();
    event.preventDefault();
  } else if (!ac_is_hidden &&
             ((event.key == 'Down') || (event.key == 'ArrowDown') ||
              ((event.key == 'Tab') && !event.shiftKey))) {
    ac_selected++;
    if (ac_selected >= ac_list.length) {
      ac_selected = 0;
    }
    generate_ac_html();
    event.preventDefault();
  } else if (!ac_is_hidden &&
             ((event.key == 'Up') || (event.key == 'ArrowUp') ||
              ((event.key == 'Tab') && event.shiftKey))) {
    ac_selected--;
    if (ac_selected < 0) {
      ac_selected = ac_list.length - 1;
    }
    generate_ac_html();
    event.preventDefault();
  }
}

var e_search_input;
var e_autocomplete_box;
var e_home_icon;

/* We want hide the autocomplete box whenever the user clicks somewhere that
   **isn't** the search field or autocomplete box.  I could potentially add an
   event listener to 'focusout', but that fires on a click in the autocomplete
   box.  I could maybe figure out a workaround that still uses the 'focusout'
   event, but the below method seens easier.

   We add an event listener for a 'click' anywhere in the window.  The event
   handler explicitly ignores a click event if the target is the search field
   or autocomplete box.  If it's outside those elements, the event handler
   close the autocomplete box.

   Special cases:

   A click in the window chrome (outside the HTML area) doesn't trigger the
   event, nor does a click outside the window, although both of these remove
   focus from the search bar.  I prefer that these don't remove the
   autocomplete box, so that's fine.

   A click in the scroll bar also doesn't trigger the event, which is good
   because the browser doesn't change the focus in this case.

   The browser removes focus from the search bar as soon as the mouse button
   is pressed or the touch begins, whereas the click event isn't triggered
   until the mouse button is released or the touch ends.  This isn't ideal,
   but it's not bad.  I tried a few workarounds, with the following results:

      An event handler on 'pointerdown' has better timing, but I find that it
      also triggers on the scroll bar, which would be bad as mentioned above.

      An 'pointerdown' event handler on document.body ignores the scroll bar
      as desired, but it also ignores clicks below the last HTML element.
*/
window.addEventListener('click', fn_doc_click);

/* On Android Firefox, if the user clicks an autocomplete link to navigate
   away, then hits the back button to return to the page, the search field
   is cleared (good), but the autocomplete box remains visible and populated
   (bad).  This code fixes that. */
window.addEventListener('pageshow', fn_pageshow);

/* When entering the page or when changing anchors within a page,
   set the window title to "anchor (page title)". */
function fn_hashchange(event) {
  hide_ac();

  /* If the current title already has an anchor in it, throw away
     the anchor and keep just the last part, the original page title. */
  var title_list = document.title.split(' - ');
  var title = title_list[title_list.length - 1];

  /* If the URL has a hash, get the anchor portion of it and put it before
     the original page title.
     There is an exception for 'offline', which is not a typical anchor. */
  var hash = location.hash;
  if (hash && (hash != '#offline')) {
    document.title = decodeURIComponent(hash).substring(1) + ' - ' + title;
  }
}

/* Determine whether to add 'html/' to the URL when navigating to a page. */
if (/\/html\/[^\/]*$/.test(window.location.pathname)) {
  var path = '';
} else {
  var path = 'html/';
}

/* main() kicks off search-related activity once it is safe to do so.
   See further below for how main() is activated. */
function main() {
  console.info('main')

  /* Make sure the page elements are ready. */
  if (document.readyState === 'loading') {
    console.info('...main too early')
    document.addEventListener('DOMContentLoaded', main);
    return
  }

  e_search_input = document.getElementById('search');
  e_autocomplete_box = document.getElementById('autocomplete-box');
  e_home_icon = document.getElementById('home-icon');

  /* normalize the data in the pages array. */
  for (var i = 0; i < pages.length; i++) {
    var page_info = pages[i];
    if (('page' in page_info) &&
        !('com' in page_info) &&
        (!hasUpper(page_info.page) || (page_info.x == 'j'))) {
      page_info.com = [page_info.page];
    }
    if (('page' in page_info) &&
        !('sci' in page_info) &&
        hasUpper(page_info.page) && (page_info.x != 'j')) {
      page_info.sci = [page_info.page];
    }
  }

  e_search_input.addEventListener('input', fn_change);
  e_search_input.addEventListener('keydown', fn_keydown);
  e_search_input.addEventListener('focusin', fn_focusin);

  /* Set the window title when entering the page (possibly with an anchor)... */
  fn_hashchange();

  /* ... or when changing anchors within a page. */
  window.addEventListener('hashchange', fn_hashchange);

  /* In case the user already started typing before the script loaded,
     perform the search right away on whatever is in the search field,
     but only if the focus is still in the search field.

     If the search field is (still) empty, fn_search() does nothing. */
  if (Document.activeElement == e_search_input) {
    fn_search();
  }

  /* Also initialize the photo gallery. */
  gallery_main();
}

/* main() is called when either of these two events occurs:
   we reach this part of search.js and the pages array exists, or
   we reach the end of pages.js and the main function exists.
*/
if (typeof pages !== 'undefined') {
  main();
}


/*****************************************************************************/
/* Show/hide observation details. */

function fn_details(event) {
  console.log(event);
  if (event.target.textContent == '[show details]') {
    event.target.textContent = '[hide details]';
    document.getElementById('details').style.display = 'block';
    event.target.setAttribute('aria-expanded', 'true');
  } else {
    event.target.textContent = '[show details]';
    document.getElementById('details').style.display = 'none';
    event.target.setAttribute('aria-expanded', 'false');
  }
}

/* Pressing 'enter' when the toggle is focused does the same as a mouse click
   in order to support accessibility requirements. */
function fn_details_keydown(event) {
  console.log(event);
  if ((event.key == 'Enter') ||
      (event.key == ' ') ||
      (event.key == 'Spacebar')) {
    fn_details(event);
    event.preventDefault();
  }
}
