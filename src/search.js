/* Copyright Chris Nelson - All rights reserved. */

"use strict";

var ac_is_hidden = true;
function expose_ac() {
  e_autocomplete_box.style.display = 'block';
  ac_is_hidden = false;
}

function hide_ac() {
  if (!ac_is_hidden) {
    e_autocomplete_box.style.display = 'none';
    ac_is_hidden = true;
  }
}

function fn_focusin() {
  if (ac_is_hidden) {
    /* e_search_input.select(); */ /* Not as smooth on Android as desired. */
    fn_search();
  }
}

function fn_focusout() {
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
    target = ' target="_blank"';
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
  var m = match_str.toUpperCase().replace(/\W/g, '');

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
      break; /* match complete */
    }

    /* find end of letter characters */
    while ((/\w/.test(s.substr(i, 1))) && (i < s.length)) {
      i++;
    }

    var s_word = s.substring(start_i, i);
    var start_j = m.indexOf(s_word, j);
    if (start_j == -1) {
      return null; /* no match */
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
     matches "gland (plant glossary)" better than "England (glossary)". */
  if (match_ranges[0][0] == 0) {
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
  var pri_adj = 0.0;
  for (var i = 0; i < name_list.length; i++) {
    for (var k = 0; k < glossary.terms.length; k++) {
      var term_str = glossary.terms[k] + ' (glossary: ' + name_list[i] + ')';
      var match_info = check(search_str, term_str, pri_adj);
      if (better_match(match_info, best_match_info)) {
        best_match_info = match_info;
      }
      pri_adj = -0.01;
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
      h += info.tag[0]; /* open tag */
      nest.push(info); /* record its nesting level */
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
      var com_highlight = highlight_match(fit_info.com_match_info,
                                          page_info['com'][0], false);
    } else {
      var com_highlight = null;
    }

    if ('sci' in page_info) {
      var sci_highlight = highlight_match(fit_info.sci_match_info,
                                          page_info['sci'][0], true);
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
    full = full.replace(/'/g, '&rsquo;');

    fit_info.html = ('<p class="nogap"><a ' + link + '>' +
                     full + '</a></p>');
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
  return true; /* continue normal handling of the clicked link */
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
  if ((event.key == 'Enter') && ac_list.length) {
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
      window.location.href = fn_url(fit_info);
    }
    /* Opening a new window doesn't affect the current page.  Also, a
       search of the glossary from a glossary page might result in no
       page change.  In either case, the search will remain active,
       which is not what we want.  In either case, clear the search. */
    clear_search();
  } else if (event.key == 'Escape') {
    clear_search();
  } else if ((event.key == 'Down') || (event.key == 'ArrowDown') ||
      ((event.key == 'Tab') && !event.shiftKey)) {
    ac_selected++;
    if (ac_selected >= ac_list.length) {
      ac_selected = 0;
    }
    generate_ac_html();
    event.preventDefault();
  } else if ((event.key == 'Up') || (event.key == 'ArrowUp') ||
      ((event.key == 'Tab') && event.shiftKey)) {
    ac_selected--;
    if (ac_selected < 0) {
      ac_selected = ac_list.length - 1;
    }
    generate_ac_html();
    event.preventDefault();
  }
}

/* Create the search-related HTML and insert it at the beginning of the
   document.  I can't find a function to insert HTML directly into the
   document, so we accomplish the same task a bit awkwardly by inserting
   the HTML before the 'body' div (which we know is present on every
   page). */
var e_body = document.getElementById('body');
e_body.insertAdjacentHTML('beforebegin', `
<div id="search-container">
<input type="text" id="search" autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" placeholder="search for a flower or glossary term...">
<div id="autocomplete-box"></div>
`);

var e_search_input = document.getElementById('search');
var e_autocomplete_box = document.getElementById('autocomplete-box');

/* We want to trigger hide_ac whenever the user clicks somewhere that
   **isn't** the search field or autocomplete box.  I used to create a
   div containing everything except the search stuff, but the extra div
   is inelegant, and it still leaves places to click around the edges of
   the window that cause focus to be lost, but the div event isn't triggered.

   So now I trigger an event for the entire document, then exclude the
   search field and autocomplete box within the event handler.

   'mousedown' triggers an event on the scrollbar, but it doesn't remove
   focus from the search field.  That's awkward because I can't quickly
   find a way to ignore that event.  But 'click' doesn't trigger on the
   scrollbar, so that's what I use. */
document.addEventListener('click', fn_doc_click);

/* On Android Firefox, if the user clicks an autocomplete link to navigate
   away, then hits the back button to return to the page, the search field
   is cleared (good), but the autocomplete box remains visible and populated
   (bad).  This code fixes that. */
window.onbeforeunload = fn_focusout;

/* When entering the page or when changing anchors within a page,
   set the window title to "anchor (page title)". */
function fn_hashchange(event) {
  hide_ac();

  /* If the current title already has an anchor in it, throw away
     the anchor and keep just the last part, the original page title. */
  var title_list = document.title.split(' - ');
  var title = title_list[title_list.length - 1];

  /* If the URL has a hash, get the anchor portion of it and put it before
     the original page title. */
  var hash = location.hash;
  if (hash) {
    document.title = decodeURIComponent(hash).substring(1) + ' - ' + title;
  }
}

/* Determine whether to add 'html/' to the URL when navigating to a page. */
if (window.location.pathname.includes('/html/')) {
  var path = '';
} else {
  var path = 'html/';
}

/* main() kicks off search-related activity once it is safe to do so.
   See further below for how main() is activated. */
function main() {
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
  window.addEventListener("hashchange", fn_hashchange);

  /* In case the user already started typing before the script loaded,
     perform the search right away on whatever is in the search field,
     but only if the focus is still in the search field.

     If the search field is (still) empty, fn_search() does nothing. */
  if (Document.activeElement == e_search_input) {
    fn_search();
  }
}

/* main() is called when either of these two events occurs:
   we reach this part of search.js and the pages array exists, or
   we reach the end of pages.js and the main function exists.

   Bug: Nothing waits for e_body or e_search to exist.
   https://stackoverflow.com/questions/16149431/make-function-wait-until-element-exists
*/
if (typeof pages !== 'undefined') {
  main();
}


/*****************************************************************************/
/* non-search functions also used by the BAWG HTML */

/* Show/hide observation details. */
function fn_details(e) {
  if (e.textContent == '[show details]') {
    e.textContent = '[hide details]';
    document.getElementById('details').style.display = 'block';
  } else {
    e.textContent = '[show details]';
    document.getElementById('details').style.display = 'none';
  }
}


/*****************************************************************************/
/* code to restore the scroll position after a history navigation.

   Caveat: this code saves and restores the amount of vertical scroll.  If the
   page is resized (or the mobile device is rotated), then a different amount
   of vertical scroll may be needed to restore any particular page element to
   be visible.  There doesn't seem to be anything I can do about that.

   For a big page like flowering plants, maybe that's not a big deal:
   - A wide desktop screen is unlikely to flow much differently.
   - A phone screen can only resize by changing orientation.
   It could be more of an issue for something like the plant glossary.

   Maybe maybe I could figure out which element is at the top of the screen,
   then set "overflow-anchor: none;" on all other elements.  That seems
   computationally expensive and hard to make work.
*/


/* We want to save the scroll position of the scrollable body div so that we
   can restore it when the user navigates back to this page.

   Note that calling save_scroll() when the page is unloaded is insufficient
   when the user clicks a link to an anchor within the same page.  Throw in the
   possibility that the user uses the forward or back buttons (or other method)
   to navigate through the history, and it is simply impossible to capture the
   scroll position in all cases before the state changes.

   Instead, we save the scroll position whenever the scroll position changes.

   Note: we don't start saving the scroll position until we've attempted to
   restore the scroll position.  Otherwise a navigation event might cause the
   browser to auto-scroll to the anchor, which could trigger save_scroll()
   before restore_scroll().
*/
function save_scroll() {
  var scrollPos = e_body.scrollTop;
  var stateObj = { data: scrollPos };
  history.replaceState(stateObj, '');
  console.info('save_scroll()')
  console.info(scrollPos)
}


/* Restore the scroll position when returning to the page.  The browser would
   do this automatically for the *window* scroll position, but it doesn't do it
   for the scrollable body div.

   We arrange events to call restore_scroll when the DOM content is loaded
   (navigation from another page) or when the hash changes (navigation within a
   page).
*/
function restore_scroll() {
  console.info('restore_scroll()');
  if (history.state) {
    e_body.scrollTop = history.state.data;
    console.info(e_body.scrollTop);
  }

  /* Now that we've restored the scroll position, we can start saving new
     position data. */
  e_body.addEventListener('scroll', save_scroll);
}
window.addEventListener("hashchange", restore_scroll);


/* If the readyState is 'interactive', then the user can (supposedly)
   interact with the page, but it may still be loading HTML, images,
   or the stylesheet.  In fact, the page may not even be rendered yet.
   We use a 0-length timeout to call restore_scroll() as soon as possible
   after pending rendering, if any.

   Hopefully the HTML and CSS is well designed so that the page isn't
   still adjusting its layout after the call to restore_scroll().
*/
function oninteractive() {
  console.info('oninteractive()');
  setTimeout(restore_scroll, 0);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', oninteractive);
} else {
  oninteractive();
}
