"use strict";

var ac_is_hidden = true;
function expose_ac() {
  e_autocomplete_box.style.display = 'block';
  ac_is_hidden = false;
}

function hide_ac() {
  e_autocomplete_box.style.display = 'none';
  ac_is_hidden = true;
}

function fn_focusin() {
  if (ac_is_hidden) {
    /* e_search_input.select(); */ /* Not as smooth on Android as desired. */
    fn_search();
  }
}

function fn_focusout() {
  if (!ac_is_hidden) {
    hide_ac();
  }
}

function fn_search_box_focusout(event) {
  if (event.target == this) {
    fn_focusout()
  }
}

/* Global variable so that it can be used by independent events. */
var ac_list;
var ac_selected;

function clear_search() {
  e_search_input.value = '';
  ac_list = [];
  ac_selected = 0;
  fn_focusout();
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
function fn_url(page_info) {
  if (page_info.x == 'j') {
    return 'https://ucjeps.berkeley.edu/eflora/glossary.html#' + page_info.anchor;
  } else if (page_info.x == 'g') {
    return path + page_info.page + '.html#' + page_info.anchor;
  } else {
    return path + page_info.page + '.html';
  }
}

/* Construct all the contents of a link to a page. */
function fn_link(page_info) {
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
  var url = fn_url(page_info);

  /* I tried this and didn't like it.  If I ever choose to use it, I also
     have to change the behavior of the return key (where fn_url is used). */
  /*if (page_info.x == 'j') {
    target = ' target="_blank"';
  }*/

  return 'class="enclosed ' + c + '"' + target + ' href="' + url + '" onclick="return fn_click();"'
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
    var j = start_j + (i - start_i);
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

/* Call check() on a list of potential matches and return the best match. */
function check_list(search_str, match_list, page_info) {
  var best_match_info = null;
  var pri_adj = 0.0;
  for (var i = 0; i < match_list.length; i++) {
    var match_info = check(search_str, match_list[i], pri_adj);
    if (match_info && (!best_match_info ||
                       (match_info.pri > best_match_info.pri))) {
      best_match_info = match_info;
    }

    /* Secondary names have slightly reduced priority.  E.g. a species
       that used to share a name with another species can be found with
       that old name, but the species that currently uses the name
       is always the better match.  So we adjust the priority slightly
       for all names in the match_list after the first. */
    if (page_info.x == 'f') {
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
  if (match_info) {
    var m = match_info.match_str;
    var match_ranges = match_info.match_ranges;
  } else {
    /* Rather than writing special code to handle italicization of the
     * scientific name for this default case, we can simply fall through the
     * regular highlighting code with no highlighted ranges. */
    var m = default_name;
    var match_ranges = [];
  }

  /* h is the highlighed string to be returned. */
  var h = '';

  /* is_delayed_sci indicates whether <i> still needs to be inserted. */
  var is_delayed_sci = is_sci;

  if (is_delayed_sci && startsUpper(m)) {
    h += '<i>';
    is_delayed_sci = false;
  }

  var m_highlight_start;
  var m_highlight_stop = 0;
  /* We iterate through match_ranges to handle each unhighlighed range
     followed by a highlighed range.  Then we perform one more half step
     in order to pick up the final unhighlighted range. */
  for (var i = 0; i <= match_ranges.length; i++) {
    if (i == match_ranges.length) {
      /* We're in the last half step.  Pick up the final unhighlighed range.
         Don't try to look up match_ranges[i] ! */
      m_highlight_start = m.length;
    } else if (match_ranges[i][0] == 0) {
      /* In the unusual case that the match starts with the first letter
         and the name starts with punctuation before that letter, include
         the punctuation in the highlight. */
      m_highlight_start = 0;
    } else {
      m_highlight_start = find_letter_pos(m, match_ranges[i][0]);
    }

    var s = m.substring(m_highlight_stop, m_highlight_start);

    if (is_delayed_sci && s.includes(' ')) {
      var space_pos = s.indexOf(' ');
      s = s.substring(0, space_pos) + ' <i>' + s.substring(space_pos+1)
      is_delayed_sci = false;
    }

    h += s;

    if (i == match_ranges.length) {
      break; /* We're done after that last half step. */
    }

    /* Stop highlighting just after letter N-1.  I.e. don't include
       the punctuation between letter N-1 and letter N, which is the
       first letter outside the match range. */
    m_highlight_stop = find_letter_pos(m, match_ranges[i][1] - 1) + 1;

    if (/!\w/.test(m.substring(m_highlight_stop))) {
      /* In the unusual case that only punctuation follows the highlight,
         include the punctuation in the highlight. */
      m_highlight_stop = m.length;
    }

    var s = m.substring(m_highlight_start, m_highlight_stop);

    if (is_delayed_sci && s.includes(' ')) {
      var space_pos = s.indexOf(' ');
      s = s.substring(0, space_pos) + ' <i>' + s.substring(space_pos+1)
      is_delayed_sci = false;
    }

    h += ('<span class="match">' + s + '</span>');
  }

  if (is_sci && !is_delayed_sci) {
    /* We added <i> at some point, so now close it off with </i>. */
    h += '</i>';
  }

  return h;
}

/* Update the autocomplete list. */
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

    if (!com_match_info && !sci_match_info) {
      continue; /* no match */
    } else if (com_match_info && (!sci_match_info ||
                                  (com_match_info.pri > sci_match_info.pri))) {
      var pri = com_match_info.pri;
    } else {
      var pri = sci_match_info.pri;
    }

    /* Reduce the priority of an autogenerated page to below all others. */
    if ((page_info.x == 'f') || (page_info.x == 'u')) {
      pri -= 2.0;
    }

    var fit_info = {
      pri: pri,
      page_info: page_info,
      com_match_info: com_match_info,
      sci_match_info: sci_match_info
    };

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
    } else {
      var sci_highlight = null;
    }

    if (com_highlight && sci_highlight) {
      var full = com_highlight + ' (' + sci_highlight + ')';
    } else if (sci_highlight) {
      var full = sci_highlight;
    } else {
      var full = com_highlight;
    }
    full = full.replace(/'/g, '&rsquo;')

    fit_info.html = ('<p class="nogap"><a ' + fn_link(page_info) + '>' +
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

/* Handle all changes to the search value.  This includes changes that
   are not accompanied by a keyup event, such as a mouse-based paste event. */
function fn_change() {
  fn_search();
}

/* Handle when the user presses various special keys in the search box. */
function fn_keyup() {
  if ((event.key == 'Enter') && ac_list.length) {
    var page_info = ac_list[ac_selected].page_info;
    var url = fn_url(page_info);
    if (event.shiftKey || event.ctrlKey) {
      /* Shift or control was held along with the enter key.  We'd like to
         open a new window or new tab, respectively, but JavaScript doesn't
         really give that option.  So we just call window.open() and let the
         browser make the choise.  E.g. Firefox will only open a new tab
         (after first requiring the user to allow pop-ups), while Chrome will
         open a new tab if ctrl is held or a new window otherwise.  Nice! */
      window.open(url)
    } else {
      /* The enter key was pressed *without* the shift or control key held.
         Navigate to the new URL within the existing page. */
      window.location.href = fn_url(page_info);
    }
    /* Opening a new window doesn't affect the current page.  Also, a
       search of the glossary from a glossary page might result in no
       page change.  In either case, the search will remain active,
       which is not what we want.  In either case, clear the search. */
    clear_search();
  } else if (event.key == 'Escape') {
    clear_search();
  }
}

/* The default behavior for the arrow keys triggers on keydown, so at the
   very least we need to capture and suppress that behavior.  And it makes
   sense to also have my behavior trigger on keydown for consistency. */
function fn_keydown() {
  if ((event.key == 'Down') || (event.key == 'ArrowDown') ||
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

/* normalize the data in the pages array. */
for (var i = 0; i < pages.length; i++) {
  var page_info = pages[i]
  if ((page_info.x == 'g') || (page_info.x == 'j')) {
    if (page_info.x == 'j') {
      page_info.page = 'Jepson eFlora glossary';
    } else {
      page_info.page = glossaries[page_info.idx];
    }
    if (!('anchor' in page_info)) {
      page_info.anchor = page_info.com[0]
    }
    for (var j = 0; j < page_info.com.length; j++) {
      page_info.com[j] = page_info.com[j] + ' (' + page_info.page + ')'
    }
  } else {
    if (!('com' in page_info)) {
      if (!hasUpper(page_info.page)) {
        page_info.com = [page_info.page]
      }
    }
    if (!('sci' in page_info)) {
      if (hasUpper(page_info.page)) {
        page_info.sci = [page_info.page]
      }
    }
  }
}

/* Determine whether to add 'html/' to the URL when navigating to a page. */
if (window.location.pathname.includes('/html/')) {
  var path = '';
} else {
  var path = 'html/';
}

/* The 'body' div is everything on the page not associated with the search bar.
   Thus, clicking somewhere other than the search bar or autocomplete box
   causes the autocomplete box to be hidden. */
var e_body = document.getElementById('body');

e_body.insertAdjacentHTML('beforebegin', `
<div id="search-bg"></div>
<div id="search-container">
<input type="text" id="search" autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" placeholder="search for a flower or glossary term...">
<div id="autocomplete-box"></div>
</div>
`);

var e_search_input = document.getElementById('search');
e_search_input.addEventListener('input', fn_change);
e_search_input.addEventListener('keyup', fn_keyup);
e_search_input.addEventListener('keydown', fn_keydown);
e_search_input.addEventListener('focusin', fn_focusin);

var e_search_box = document.getElementById('search-container');
e_search_box.addEventListener('mousedown', fn_search_box_focusout, true);

e_body.addEventListener('mousedown', fn_focusout);

var e_autocomplete_box = document.getElementById('autocomplete-box');

/* On Android Firefox, if the user clicks an autocomplete link to navigate
   away, then hits the back button to return to the page, the search field
   is cleared (good), but the autocomplete box remains visible and populated
   (bad).  This code fixes that. */
window.onbeforeunload = fn_focusout;

/* When entering the page or when changing anchors within a page,
   set the window title to "anchor (page title)". */
function fn_hashchange(event) {
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

/* Set the window title when entering the page (possibly with an anchor)... */
fn_hashchange();

/* ... or when changing anchors within a page. */
window.onhashchange = fn_hashchange;

/*****************************************************************************/
/* non-search functions also used by the BAWG HTML */

function fn_details(e) {
  if (e.textContent == '[show details]') {
    e.textContent = '[hide details]';
    document.getElementById('details').style.display = 'block';
  } else {
    e.textContent = '[show details]';
    document.getElementById('details').style.display = 'none';
  }
}
