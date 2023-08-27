/* Copyright Chris Nelson - All rights reserved. */

'use strict';

/*****************************************************************************/
/* code related to the photo gallery */

/* Decode the current page's URL.
   It is expected to start with any string,
   followed by an optional 'html/',
   followed by the page name (encoded as needed),
   followed by '.html'. */
const html_url = window.location.pathname;
const match_pos = html_url.search(/(?:html\/)?[^\/]*\.html$/);
if (match_pos != -1) {
  var root_path = window.location.origin + html_url.substring(0, match_pos);
} else {
  /* If the URL doesn't end with '*.html', then we assume it ends in '/',
     which implicitly maps to 'index.html'. */
  var root_path = window.location.origin + html_url
  if (!root_path.endsWith('/')) {
    root_path += '/';
  }
}

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
  /* Change each link to a BAWG photo or figure to instead link via the
     gallery page. */
  const e_link_list = document.links

  for (var i = 0; i < e_link_list.length; i++) {
    /* Look for any href that starts with the same start of the URL as the
       current page, followed by 'photos/' or 'figures/'.  We assume that all
       hrefs are in the same canonical form, so we don't need to figure out all
       the ways that different hrefs could map to the same URL. */
    const href = e_link_list[i].href;
    if (href.startsWith(root_path + 'photos/') ||
        href.startsWith(root_path + 'figures/')) {
      var suffix = decodeURI(href.substr(root_path.length));

      /* Simplify the URL in case the user looks at it. */
      suffix = munge_photo_for_url(suffix);

      /* The path to the photo has different encoding requirements when
         moved to the search component of the URL. */
      const suffix_query = encodeURIComponent(suffix);

      /* Replace the href to point to the gallery. */
      e_link_list[i].href = root_path + 'gallery.html?' + suffix;
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
/* Code related to the search bar and autocompletion.

   This includes code shared between regular and advanced search,
   but not functions used only for advanced search.  Any functions
   exclusive to regular search are here as well. */

var ac_is_hidden = true;

/* Show the autocomplete box. */
function expose_ac() {
  e_autocomplete_box.style.display = 'block';
  ac_is_hidden = false;
  e_home_icon.className = 'with-autocomplete';
}

/* Hide the autocomplete box. */
function hide_ac() {
  if (!ac_is_hidden) {
    e_autocomplete_box.style.display = 'none';
    ac_is_hidden = true;
    e_home_icon.className = '';
  }
}

/* React to focus entering the search bar. */
function fn_focusin() {
  if (ac_is_hidden) {
    /* e_search_input.select(); */ // Not as smooth on Android as desired.
    fn_search(ac_selected);
  }
}

/* React to the user returning to the page via the browser's history
   (e.g. the back button). */
function fn_pageshow() {
  hide_ac();
}

/* hide the autocomplete box if the user clicks somewhere else on the page. */
function fn_doc_click(event) {
  var search_element = event.target.closest('#search-container');
  if (!search_element) {
    hide_ac();
  }
}

/* Global variable so that it can be used by independent events. */
var ac_list;
var ac_selected = 0;

/* Clear the search bar. */
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
   I.e. search for N+1 letters, then back up one.
   We treat digits *and* %# as letters since we may be
   in the middle of convert one form to the other. */
function find_letter_pos(str, n) {
  var regex = /[a-zA-Z0-9%#]/g;

  for (var i = 0; i <= n; i++) {
    /* We use test() to advance regex.lastIndex.
       We don't bother to check the test() return value because we always
       expect it to match.  (E.g. when finding the last letter of match,
       we really are looking for the last letter, which always exists.) */
    regex.test(str);
  }

  if (regex.lastIndex == 0) {
    /* There aren't N+1 letters.  Presumably there are N letters, so the
       notional next letter position is the end of the string. */
    return str.length;
  } else {
    return regex.lastIndex - 1;
  }
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

function get_url(page_info) {
  if (page_info.x == 'j') {
    var url = 'https://ucjeps.berkeley.edu/eflora/glossary.html';
  } else {
    var url = path + page_info.p + '.html';
    url = url.replace(/ /g, '-');
  }

  return encodeURI(url);
}

function get_class(page_info) {
  if ((page_info.x == 'f') || (page_info.x == 's')) {
    return 'family';
  } else if (page_info.x == 'k') {
    return 'parent';
  } else if (page_info.x == 'o') {
    return 'leaf';
  } else if (page_info.x == 'g') {
    return 'glossary';
  } else if (page_info.x == 'j') {
    return 'jepson';
  } else {
    return 'unobs';
  }
}

/* Construct the contents of the autocomplete box,
   i.e. the list of autocomplete results. */
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
function check(search_str, match_str, pri_adj = 0, def_num_list = []) {
  /* search_str has already been converted to upper case, and we keep its
     punctuation intact.  I just copy it to a shorter variable name here for
     convenience. */
  const s = search_str;

  /* m is the string we're trying to match against, converted to uppercase
     and with punctuation removed (except '%' and '#', which represents a
     number group). */
  const upper_str = match_str.toUpperCase()
  const m = upper_str.replace(/[^A-Z%#]/g, '');

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

  /* Find the position and length of each % group in m.
     These are where we expect to find numbers.
     Note that num_missing_digits represents the number of digits that
     we haven't found.  If a full or partial match is found for a
     number group, num_missing_digits will be updated. */
  const num_list = [];
  const num_start = [];
  const num_missing_digits = [];
  const re = /%#*/g;
  var idx = 0;
  while (true) {
    /* Find the next % group in m. */
    const match = re.exec(m);
    if (!match) break;

    num_list.push(def_num_list[idx]);
    num_start.push(match.index);
    num_missing_digits.push(match[0].length);
    idx++;
  }

  /* match_ranges consists of [start, end] pairs that indicate regions in m for
     which a match was made */
  var match_ranges = [];

  /* i and j are the current position indexes into s and m, respectively */
  var i = 0;
  var j = 0;

  while (true) {
    /* find the first letter character or digit in s */
    while (/[^A-Z0-9]/.test(s.substr(i, 1)) && (i < s.length)) {
      i++;
    }
    var start_i = i;

    if (i == s.length) {
      break; // match complete
    }

    /* find the end of the letter characters or digits */
    var is_num = (/[0-9]/.test(s.substr(i, 1)));
    if (is_num) {
      var pattern = /[0-9]/;
    } else {
      var pattern = /[A-Z]/;
    }
    while (pattern.test(s.substr(i, 1)) && (i < s.length)) {
      i++;
    }

    var s_word = s.substring(start_i, i);

    if (is_num) {
      /* Figure out which number group is being matched. */
      var idx = 0;
      while (true) {
        if (idx == num_start.length) {
          return null; /* no match found */
        }

        if ((num_start[idx] >= j) &&
            (num_missing_digits[idx] >= s_word.length)) {
          /* the next group with the right number of digits has been found */
          break;
        }

        /* keep looking */
        idx++;
      }

      /* start the match at the % that makes the number right aligned */
      j = num_start[idx] + num_missing_digits[idx];
      start_j = j - s_word.length;

      /* adjust the number of missing digits */
      num_missing_digits[idx] -= s_word.length;

      /* The number is expected to be a certain length.  Otherwise it is
         left-filled using information from the next number in def_num_list. */
      const def_num = def_num_list[idx];
      if (def_num.length == 4) {
        /* For a four-digit number (year), the number is padded with the
           digits from the default year. if that causes the year to be
           after the default year, decrement the padded value (e.g. switch
           to the 1900's). */
        const digits_replaced = def_num.slice(-s_word.length);
        var digits_padding = def_num.slice(0, -s_word.length);
        const padding_len = digits_padding.length;
        if (padding_len && (s_word > digits_replaced)) {
          digits_padding = String(Number(digits_padding) - 1);
          digits_padding = digits_padding.padStart(padding_len, '0');
        }
        var num = digits_padding + s_word;
      } else {
        /* For a two-digit number (month or day), the number is padded with
           a 0. */
        var num = s_word.padStart(2, '0');
      }
      num_list[idx] = num;
    } else {
      /* look for the search word in match_str */
      var start_j = m.indexOf(s_word, j);
      if (start_j == -1) {
        return null; // no match
      }
      j = start_j + s_word.length;
    }

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
     won't reduce it below 0.  (Although I'm not sure if that matters.) */
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
    match_ranges: match_ranges,
    num_list: num_list,
    num_start: num_start,
    num_missing_digits: num_missing_digits
  }

  return match_info;
}


/* Track the ranges at which a tag should be applied.
   Once set up, retrieving each tag open or close advances the
   state to the next open/close position. */
class Tag {
  tag_text;
  ranges = []; /* each entry is a pair: [tag open pos, tag close pos] */
  i = 0; /* current index into ranges */
  half = 0; /* current index into ranges[i] */

  constructor(tag_open, tag_close) {
    this.tag_text = [tag_open, tag_close];
  }

  add_range(start, end) {
    this.ranges.push([start, end]);
  }

  get_next_pos() {
    return this.ranges[this.i][this.half];
  }

  is_open() {
    return this.half;
  }

  get_open_pos() {
    return this.ranges[this.i][0];
  }

  get_close_pos() {
    return this.ranges[this.i][1];
  }

  open() {
    return this.tag_text[0];
  }

  close() {
    return this.tag_text[1];
  }

  advance() {
    if (this.half) {
      this.half = 0;
      this.i++;
    } else {
      this.half = 1;
    }
  }

  is_done() {
    return (this.i == this.ranges.length);
  }
}


/* Using the match_info constructed in check(), highlight the matched
   ranges within the matched string.  Or if match_info is null (because
   the other com/sci name of a page was matched), return default_name
   without highlighting.

   In either case, if it's a scientific name, italicize the Greek/Latin
   words (either the whole string or everything after the first word). */
function highlight_match(match_info, default_name, is_sci) {
  var tag_list = [];

  /* h is the highlighed string to be returned. */
  var h = '';

  if (match_info) {
    var m = match_info.match_str;
    var match_ranges = match_info.match_ranges;

    /* Convert match_ranges (which ignores punctuation) into string ranges
       (which include punctuation). */
    var tag = new Tag('<span class="match">', '</span>');
    for (const range of match_ranges) {
      var begin = find_letter_pos(m, range[0]);

      /* Stop highlighting just after letter N-1.  I.e. don't include
         the punctuation between letter N-1 and letter N, which is the
         first letter outside the match range. */
      var end = find_letter_pos(m, range[1] - 1) + 1;

      tag.add_range(begin, end);
    }
    /* We assume that something matched, or we wouldn't have match info.
       Therefore, the Tag is always valid. */
    tag_list.push(tag);


    /* Replace %# groups in match_str with the parsed/default numbers,
       and de-emphasize digits that were not typed. */
    if (match_info.num_list.length) {
      var tag = new Tag('<span class="de-emph">', '</span>');
      for (var i = 0; i < match_info.num_list.length; i++) {
        m = m.replace(/%#*/, match_info.num_list[i]);

        if (match_info.num_missing_digits[i]) {
          const mbegin = match_info.num_start[i];
          const mend = (match_info.num_start[i] +
                        match_info.num_missing_digits[i] - 1);

          const begin = find_letter_pos(m, mbegin);
          const end = find_letter_pos(m, mend) + 1;

          tag.add_range(begin, end);
        }
      }
      /* If none of the numbers are missing digits, there are no
         de-emphasized ranges.  If we pushed this tag to the tag_list,
         the code would break. */
      if (!tag.is_done()) {
        tag_list.push(tag);
      }
    }
  } else {
    /* Rather than writing special code to handle italicization of the
     * scientific name for this default case, we can simply fall through the
     * regular highlighting code with no highlighted ranges. */
    var m = default_name;
  }

  /* De-emphasize a parenthesized term at the end of the match string.
     The amount of de-emphasis is different for a glossary vs. the
     inclusive/exclusive text after a date. */
  const paren_pos = m.search(/\([^\)]*\)$/);
  if (paren_pos != -1) {
    const c = match_info.num_list.length ? 'de-emph' : 'altname';
    var tag = new Tag('<span class="' + c + '">', '</span>');
    tag.add_range(paren_pos, m.length);
    tag_list.push(tag);
  }

  if (is_sci) {
    var tag = new Tag('<i>', '</i>');

    /* By default, italicize the entire scientific name. */
    var range = [0, m.length];

    /* Exclude spp. from italicization. */
    if (m.endsWith(' spp.')) {
      range[1] -= 5;
    }

    /* Exclude ssp. or var. from italicization. */
    var pos = m.search(/ ssp\. | var\. /);
    if (pos != -1) {
      /* End the first italics range before the ssp./var.,
         and add a new range to cover everything after it. */
      range[1] = pos;
      tag.add_range(range[0], range[1]);
      range = [pos + 6, m.length];
    }

    /* Don't italicize the rank. */
    if (!startsUpper(m)) {
      range[0] = m.indexOf(' ');
    }

    /* Since this is a scientific name, there's always something italicized. */
    tag.add_range(range[0], range[1]);
    tag_list.push(tag);
  }

  /* Keep track of tag nesting, because interleaved tags fail in some browsers.
     E.g. <i>x<span>y</i>z</span> on Chrome moves </span> to before </i>. */
  var nest = [];

  var pos = 0;
  while (tag_list.length) {
    /* Find the next tag change (open or close). */
    var tag_idx = 0;
    var tag = tag_list[0];
    for (var j = 1; j < tag_list.length; j++) {
      var tagj = tag_list[j];
      /* If multiple tags change at the same position, prefer to close a tag.

         If multiple tags open at once, prefer the one that closes earlier.
         If they both open and close at the same time, prefer the first one
         in tag_list order.

         If multiple tags close at once, prefer the that opened later
         (because it should have the least nesting).  If they both open
         and close at the same time, prefer the last one in tag_list order
         (because it should be nested inside the earlier one). */
      if ((tagj.get_next_pos() < tag.get_next_pos()) ||
          ((tagj.get_next_pos() == tag.get_next_pos()) &&
           (tagj.is_open() ?
            (!tag.is_open() || (tagj.get_close_pos() < tag.get_close_pos())) :
            (!tag.is_open() && (tagj.get_close_pos() <= tag.get_close_pos())))))
      {
        tag_idx = j;
        tag = tagj;
      }
    }

    var next_pos = tag.get_next_pos();

    /* append the text (if any) from the position of the last tag change */
    var s = m.substring(pos, next_pos);
    h += s;

    /* and update the position of the most recent tag change */
    pos = next_pos;

    if (!tag.is_open()) {
      h += tag.open(); // open tag
      nest.push(tag); // record its nesting level
    } else {
      /* close the tags that are nested within the tag we want to close */
      for (i = nest.length-1; nest[i] != tag; i--) {
        h += nest[i].close();
      }

      /* close the tag that we wanted to close */
      h += nest[i].close();

      /* remove the closed tag from the nesting list */
      nest.splice(i, 1);

      /* re-open the previously nested tags */
      for (i = i; i < nest.length; i++) {
        h += nest[i].open();
      }
    }

    tag.advance();
    if (tag.is_done()) {
      /* remove entry from tag_list */
      tag_list.splice(tag_idx, 1);
    }
  }

  /* append the remaining part of the string with no tags */
  h += m.substring(pos);

  return h;
}

function insert_match(term) {
  /* If there's a match, and
     - we don't already have 10 matches or
     - the new match is better than the last match on the list
     then remember the new match. */
  if ((ac_list.length < 10) || (term.pri > ac_list[9].pri)) {
    /* Insert the new match into the list in priority order.  In case of
       a tie, the new match goes lower on the list. */
    for (var j = 0; j < ac_list.length; j++) {
      if (term.pri > ac_list[j].pri) break;
    }
    ac_list.splice(j, 0, term);
    /* If the list was already the maximum length, it is now longer than the
       maximum length.  Cut off the last entry. */
    if (ac_list.length > 10) {
      ac_list.splice(-1, 1);
    }
  }
}

function compose_full_name(com, sci, lines=1) {
  if (com && sci) {
    if (lines == 2) {
      var full = com + '<br>(' + sci + ')';
    } else {
      var full = com + ' (' + sci + ')';
    }
  } else if (sci) {
    var full = sci;
  } else {
    var full = com;
  }

  full = full.replace(/\'/g, '&rsquo;');

  return full;
}

function compose_page_name(page_info, lines=1) {
  if ('c' in page_info) {
    var com = page_info.c[0];
  } else {
    var com = null;
  }

  if ('s' in page_info) {
    var sci = highlight_match(null, page_info.s[0], true);
  } else {
    var sci = null;
  }

  return compose_full_name(com, sci, lines);
}

/* This class handles everything related to a search term, from its beginnings
   as a potential search match, through its potential entry into the
   autocomplete list, to its potential status as a confirmed advanced search
   term.

   Note that creating a Term object immediately performs a search from its
   constructor.  If the search matches, the Term is added to the autocomplete
   list.  Thus, the return value from the constructor is never needed.

   class Term itself is never used directly and doesn't have all the methods
   needed for use.  It is extended by other classes to become fully functional.
*/
class Term {
  is_clear = false;
  group;
  e_term;

  constructor(group) {
    this.group = group;
  }

  gen_html_element() {
    const e_term = document.createElement('button');

    e_term.className = 'term';

    e_term.addEventListener('click', fn_term_click);

    const c = this.get_class();
    const prefix = this.prefix();
    const term_name = this.get_text();

    const span = '<span class="' + c + '">' + term_name + '</span>';
    e_term.innerHTML = '<p>' + prefix + ' <b>' + span + '</b></p>';

    this.e_term = e_term;
  }

  insert_html_element() {
    for (var id = 0; id < term_list.length; id++) {
      const term = term_list[id];
      if (this.group < term.group) {
        /* We should insert our term before this one
           (after the previous term). */
        break;
      }
    }

    console.log('inserting in position', id, 'of', term_list.length + 1);

    /* Insert this term into the term_list. */
    term_list.splice(id, 0, this);

    /* Insert this term's HTML element into the DOM. */
    if (id == 0) {
      e_terms.insertAdjacentElement('afterbegin', this.e_term);
    } else {
      const prev_e_term = term_list[id-1].e_term;
      prev_e_term.insertAdjacentElement('afterend', this.e_term);
    }
  }
}

/* Check whether match_info one has greater priority than two.
   Either value can be null, which is considered lowest priority. */
function better_match(one, two) {
  return (one && (!two || (one.pri > two.pri)));
}

/* Handle a search term associated with an HTML page.  This is usually a taxon,
   but it can also be a glossary page.

   Caution: creating a PageTerm object for a glossary page automatically
   creates additional AnchorTerm objects for each glossary anchor. */
class PageTerm extends Term {
  search_str;
  page_info;
  pri;
  com_match_info;
  sci_match_info;

  constructor(group, search_str, page_info) {
    super(group);

    this.search_str = search_str;
    this.page_info = page_info;
  }

  /* For a list of names for a page, call check().  Return the best match. */
  check_list(match_list) {
    const page_info = this.page_info;

    var best_match_info = null;
    var pri_adj = 0.0;
    for (var name of match_list) {
      var match_info = check(this.search_str, name, pri_adj);

      if (!match_info && name.startsWith('genus ')) {
        /* Allow a genus to match using the older 'spp.' style. */
        match_info = check(this.search_str, name.substr(6) + ' spp.', pri_adj);
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

  /* Check for search matches in this page:
     - in its common name
     - in its scientific name
     - in its glossary terms */
  search() {
    const search_str = this.search_str;
    const page_info = this.page_info;

    /* The advanced search never matches glossary pages or glossary terms. */
    if (adv_search && ((page_info.x == 's') || (page_info.x == 'g') || (page_info.x == 'j'))) {
      return;
    }

    /* We search for a match in the com names and the scientific names.
       If there's a match, we'll put both the com and sci name in the
       autocomplete list.  Typically there will be a match only in a com
       name or only in a sci name, but there could be a match in both types
       of name.  We therefore record the best match for each so that both
       can be highlighted as appropriate. */
    if ('c' in page_info) {
      var com_match_info = this.check_list(page_info.c);
    } else {
      var com_match_info = null;
    }

    if ('s' in page_info) {
      var sci_match_info = this.check_list(page_info.s);
    } else {
      var sci_match_info = null;
    }

    if (com_match_info || sci_match_info) {
      /* The priority of the term in the autocomplete list is the priority
         of the best match among the com and sci names. */
      if (better_match(com_match_info, sci_match_info)) {
        this.pri = com_match_info.pri;
      } else {
        this.pri = sci_match_info.pri;
      }

      this.com_match_info = com_match_info;
      this.sci_match_info = sci_match_info;

      insert_match(this);
    } else if ('glossary' in page_info) {
      /* If there was a match on a glossary page name, don't clutter up
         the auto-complete list with matches on its glossary terms. */

      /* Add an additional search term for each glossary anchor. */
      for (const anchor_info of page_info.glossary) {
        const term = new AnchorTerm(this.group, search_str,
                                    page_info, anchor_info);
        term.search();
      }
    }
  }

  /* match_info may or may not be valid.  If it's valid, it specifies
     the string that was matched.  If it may be invalid, name specifies
     a string to use instead. */
  highlight_name(match_info, name, is_sci) {
    if (!match_info ||
        (match_info.match_str == name) ||
        'gj'.includes(this.page_info.x)) {
      /* Format and highlight a single name:
         - if there was no match, format the default name
         - if the canonical name matched, format and highlight it
         - if any name of a glossary matched, format and highlight it
      */
      return highlight_match(match_info, name, is_sci);
    } else {
      /* The match is on an alternative name.  Write the unhighlighted
         canonical name first, followed by the highlighted matching name in
         brackets.  Don't do this for glossaries because we don't need the
         canonical name to clarify an alternative name.

         If there is no canonical name, an extra space gets added before
         the matching name in brackets, but the browser nicely suppresses
         the extra space. */
      const name_highlight = highlight_match(null, name, is_sci);
      const match_highlight = highlight_match(match_info, null, is_sci);
      return (name_highlight +
              ' <span class="altname">[' + match_highlight + ']</span>');
    }
  }

  /* Generate the autocomplete result text (HTML) for a taxon match. */
  get_ac_text() {
    const page_info = this.page_info;

    if ('c' in page_info) {
      var com_highlight = this.highlight_name(this.com_match_info,
                                              page_info.c[0],
                                              false);
    } else {
      var com_highlight = null;
    }

    if ('s' in page_info) {
      var sci_highlight = this.highlight_name(this.sci_match_info,
                                              page_info.s[0],
                                              true);
    } else {
      var sci_highlight = null;
    }

    return compose_full_name(com_highlight, sci_highlight);
  }

  get_class() {
    return get_class(this.page_info);
  }

  /* Get the relative path to the page. */
  get_url() {
    return get_url(this.page_info);
  }

  prefix() {
    return 'within';
  }

  /* Create the text for the confirmed search term. */
  get_text() {
    const page_info = this.page_info;
    return compose_page_name(page_info, 1);
  }

  /* Create a name that we expect to match the same term *first* if searched. */
  get_name() {
    const page_info = this.page_info;;

    if ('s' in page_info) {
      return page_info.s[0];
    } else {
      return page_info.c[0];
    }
  }

  /* Check whether page_info is within the target taxon.
     To avoid excessive re-checking, remember results in in_tgt_map. */
  within_taxon(page_info, in_tgt_map) {
    if (in_tgt_map.has(page_info)) {
      return in_tgt_map.get(page_info);
    } else if (page_info == this.page_info) {
      in_tgt_map.set(page_info, true);
      return true;
    } else {
      for (const parent_info of page_info.parent_set) {
        if (this.within_taxon(parent_info, in_tgt_map)) {
          in_tgt_map.set(page_info, true);
          return true;
        }
      }
      in_tgt_map.set(page_info, false);
      return false;
    }
  }

  match(result_set, page_to_trip) {
    const in_tgt_map = new Map();
    for (const page_info of result_set) {
      if (!this.within_taxon(page_info, in_tgt_map)) {
        result_set.delete(page_info);
      }
    }
  }
}


class AnchorTerm extends PageTerm {
  anchor_info;
  match_info;

  constructor(group, search_str, page_info, anchor_info) {
    super(group, search_str, page_info);

    this.anchor_info = anchor_info;
  }

  check_list() {
    var best_match_info = null;
    const pri_adj = 0.0; /* alternative terms are all the same priority */
    for (const page_name of this.page_info.c) {
      for (const glossary_term of this.anchor_info.terms) {
        const term_str = glossary_term + ' (' + page_name + ')';
        const match_info = check(this.search_str, term_str, pri_adj);
        if (better_match(match_info, best_match_info)) {
          best_match_info = match_info;
        }
      }
    }

    return best_match_info;
  }

  search() {
    /* Find the best match associated with the glossary.anchor. */
    const match_info = this.check_list();

    if (match_info) {
      this.pri = match_info.pri;
      this.match_info = match_info;

      insert_match(this);
    }
  }

  get_ac_text() {
    return this.highlight_name(this.match_info, null, false);
  }

  /* Get the relative path to the page with the appropriate anchor. */
  get_url() {
    const page_info = this.page_info;
    var url = super.get_url();

    if ('anchor' in this.anchor_info) {
      url += '#' + this.anchor_info.anchor;
    } else {
      url += '#' + this.anchor_info.terms[0];
    }

    return encodeURI(url);
  }

  /* Advanced search never matches a glossary, so we don't need to asjust
     the values and methods used only for advanced search. */
}

/* Search all pages for a fuzzy match with the value in the search field, and
   create an autocomplete list from the matches. */
function fn_search(default_ac_selected) {
  /* We compare uppercase to uppercase to avoid having to deal with case
     differences anywhere else in the code.  Note that this could fail for
     funky unicode such as the German Eszett, which converts to uppercase 'SS'.
     I'll deal with it if and when I ever use such characters in a name. */
  var search_str = e_search_input.value.toUpperCase();

    /* Iterate over all possible search terms and accumulate a list of the
       best matches in ac_list (the autocomplete list). */
  ac_list = [];

  if (/\w/.test(search_str)) { /* if there are alphanumerics to be searched */
    /* Search terms associated with advanced search can be found even during
       regular search, but they create a link to the advanced search page where
       the work is done. */
    add_adv_terms(search_str);

    /* Search all pages and all glossary terms within each page. */
    for (const page_info of pages) {
      const term = new PageTerm(0, search_str, page_info);
      term.search();
    }
  } else if (adv_search && (term_id < term_list.length)) {
    /* The search box is empty while editing an advanced search term.
       We add a special entry to the autocomplete list that removes the
       search term from the list. */
    new ClearTerm();
  } else {
    /* no search text and nothing to do */
    hide_ac();
    return;
  }

  for (var i = 0; i < ac_list.length; i++) {
    const term = ac_list[i];
    const text = term.get_ac_text();
    const c = term.get_class();

    /* The link is applied to the entire paragraph so that padding above
       and below and the white space to the right are also clickable. */
    const p = '<p class="nogap">' + text + '</p>'

    if (adv_search) {
      /* For advanced search, the autocomplete_list doesn't contain links,
         just colored spans. */
      term.html = '<span class="autocomplete-entry" class="' + c + '" onclick="return fn_adv_ac_click(' + i + ');">' + p + '</span>';
    } else {
      /* When performing a regular search, any type of match has an associated
         link (with URL), even if it's a link to the advanced search page. */
      const url = term.get_url();

      /* Add class 'enclosed' to avoid extra link decoration.
         Add class c to style the link according to the destination page type.
         Add onclick with the autocomplete entry number so that we know what
         to do when the link is clicked. */
      term.html = '<a class="enclosed ' + c + '" href="' + url + '" onclick="return fn_ac_click();">' + p + '</a>';
    }
  }

  /* Select the default entry (usually the first).
     This entry is selected if the user presses 'enter'. */
  if (default_ac_selected < ac_list.length) {
    ac_selected = default_ac_selected;
  } else {
    ac_selected = 0;
  }

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
function fn_ac_click() {
  clear_search();
  return true; // continue normal handling of the clicked link
}

function fn_adv_ac_click(i) {
  confirm_adv_search_term(i);
  prepare_new_adv_input();
  gen_adv_search_results();
  return false; // no more click handling is needed
}

/* Handle all changes to the search value.  This includes changes that are
   not accompanied by a keyboard event, such as a mouse-based paste event. */
function fn_change() {
  fn_search(0);
}

function confirm_reg_search(event) {
  var term = ac_list[ac_selected];
  var url = term.get_url();
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
}

/* Handle when the user presses various special keys in the search box.
   The default behavior for the arrow keys triggers on keydown, so at the
   very least we need to capture and suppress that behavior.  I also notice
   that the browser performs normal actions for all other keys on keydown.
   So it makes sense to also have my behavior trigger on keydown for
   consistency. */
function fn_keydown() {
  if ((event.key == 'Enter') && !ac_is_hidden && ac_list.length) {
    if (adv_search) {
      confirm_adv_search_term(ac_selected);
      prepare_new_adv_input();
      gen_adv_search_results();
    } else {
      confirm_reg_search(event);
    }
  } else if (event.key == 'Escape') {
    if (adv_search && (term_id < term_list.length)){
      revert_adv_search_term();
      term_id = term_list.length;
      prepare_new_adv_input();
      /* No need to recalculate the results because nothing has changed. */
    } else {
      clear_search();
    }
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

var e_home_icon;
var e_search_container;
var e_search_input;
var e_autocomplete_box;
var e_terms;
var e_results;
var adv_search;

/* We want hide the autocomplete box whenever the user clicks somewhere that
   **isn't** the search field or autocomplete box.  I could potentially add an
   event listener to 'focusout', but that fires on a click in the autocomplete
   box.  I could maybe figure out a workaround that still uses the 'focusout'
   event, but the below method seens easier.

   We add an event listener for a 'click' anywhere in the window.  The event
   handler explicitly ignores a click event if the target is the search field
   or autocomplete box.  If it's outside those elements, the event handler
   closes the autocomplete box.

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

      A 'pointerdown' event handler on document.body ignores the scroll bar
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


/*****************************************************************************/
/* Code used exclusively for advanced search (*).

   (*) Search terms associated with advanced search can be found even during
   regular search, but they create a link to the advanced search page where
   the work is done.
*/

/* Keep track of confirmed search terms. */
const term_list = [];

/* The ID of the search term currently being edited.  This equals the
   term_list length when the user is adding a new search term.  It is
   a smaller value when one of the existing terms is being edited. */
var term_id = 0;

var zstr_len = 1;

const parks = new Set();

function convert_zint_to_zstr(zint) {
  var zstr = "";
  for (var i = 0; i < zstr_len; i++) {
    var c = (zint % 93) + 32;
    zint = Math.floor(zint / 93);
    if (c >= 34) c++;
    if (c >= 92) c++;
    zstr = String.fromCharCode(c) + zstr;
  }
  return zstr;
}

/* Record the minimal set of parks.

   This needs to be done even for regular searches so that a regular search
   can recognize a park name and convert it to an advanced search. */
function init_parks() {
  for (const trip of trips) {
    parks.add(trip[1]);
  }
}

function init_adv_search() {
  const num_zcodes = traits.length + trips.length;
  while (num_zcodes > 93**zstr_len) {
    zstr_len++;
  }

  /* assign zcodes to traits */
  const zstr_to_trait = {}
  for (var i = 0; i < traits.length; i++) {
    const zstr = convert_zint_to_zstr(i);
    zstr_to_trait[zstr] = traits[i];
  }

  /* assign zcodes to trips */
  const zstr_to_trip = {}
  for (var i = 0; i < trips.length; i++) {
    const trip = trips[i];
    const zstr = convert_zint_to_zstr(traits.length + i);
    zstr_to_trip[zstr] = trip;
  }

  /* initialize the sets that will hold the advanced-search data */
  for (const page_info of pages) {
    page_info.trait_set = new Set();
    page_info.trip_set = new Set();
    page_info.child_set = new Set();
    page_info.parent_set = new Set();
  }

  /* normalize the advanced-search data in the pages array */
  for (const page_info of pages) {
    /* Compose set of traits */
    if ('z' in page_info) {
      for (var i = 0; i < page_info.z.length; i += zstr_len) {
        const zstr = page_info.z.slice(i, i + zstr_len);
        if (zstr in zstr_to_trait) {
          page_info.trait_set.add(zstr_to_trait[zstr]);
        } else {
          page_info.trip_set.add(zstr_to_trip[zstr]);
        }
      }
    }

    /* Compose sets for children and parents */
    if ('d' in page_info) {
      for (const child_id of page_info.d) {
        const child_info = pages[child_id];
        page_info.child_set.add(child_info);
        child_info.parent_set.add(page_info);
      }
    }
  }
}

function digits(num, len) {
  return String(num).padStart(len, '0');
}

function add_adv_terms(search_str) {
  var group = 1;

  for (const trait of traits) {
    const term = new TraitTerm(group, search_str, trait);
    term.search();
  }
  group++;

  for (const park of parks) {
    const term = new ParkTerm(group, search_str, park);
    term.search();
  }
  group++;

  const now = new Date();
  const year = digits(now.getFullYear(), 4);
  const month = digits(now.getMonth() + 1, 2);
  const day = digits(now.getDate(), 2);

  var term = new BtwnMDTerm(group, search_str);
  term.search();

  var term = new InYTerm(group, search_str, year);
  term.search();

  var term = new InYMTerm(group, search_str, year, month);
  term.search();

  var term = new CmpYMDTerm(group, search_str, (x,y) => (x == y),
                            'on ', '', year, month, day);
  term.search();

  var term = new CmpYMDTerm(group, search_str, (x,y) => (x >= y),
                            'since ', ' (inclusive)', year, '01', '01');
  term.search();

  var term = new CmpYMDTerm(group, search_str, (x,y) => (x <= y),
                            'until ', ' (inclusive)', year, '12', '31');
  term.search();

  var term = new CmpYMDTerm(group, search_str, (x,y) => (x > y),
                            'after ', ' (exclusive)', year, '12', '31');
  term.search();

  var term = new CmpYMDTerm(group, search_str, (x,y) => (x < y),
                            'before ', ' (exclusive)', year, '01', '01');
  term.search();

  var term = new BtwnYMDTerm(group, search_str, year);
  term.search();
}

/* When the user clicks (or presses enter on) an existing search term, we
   re-open it for editing.  Note that the existing info about the search term
   isn't discarded yet, since the user can abandon her edits (e.g. by
   pressing the Escape key). */
function fn_term_click(event) {
  /* Before moving the search bar, restore any term that was in the process
     of being edited. */
  if (term_id < term_list.length) {
    revert_adv_search_term();
  }

  /* Figure out which term was clicked. */
  const tgt = event.currentTarget;
  for (term_id = 0; term_list[term_id].e_term != tgt; term_id++) {/*empty*/}

  /* Remove the HTML for the term being edited,
     and replace it with the search bar. */
  const term = term_list[term_id];
  term.e_term.replaceWith(e_search_container);

  /* Restore the search bar and autocomplete list to a state where the
     existing term can be re-confirmed by simply pressing the Enter key. */
  e_search_input.focus();
  restore_term(term_list[term_id].search_str, term_list[term_id].ac_selected);
  generate_ac_html();

  /* Once the click or 'Enter' keypress activates this function, it normally
     propagates to the document level and triggers fn_doc_click(), which
     hides the autocomplete box because the click is (was) outside the 
     search container.  We want to keep the autocomplete box, so we prevent
     the event from propagating further. */
  event.stopPropagation();
}

function cvt_name_to_query(name) {
  /* Remove unnecessary text at the end of the name. */
  name = name.replace(/[^A-Za-z0-9]*(\([^\)]*\))?$/, '');

  /* The URI component can't accept most special characters, but since
     all punctuation is equivalent when searching anyway, we can freely
     transform them to '-', which is valid in the URI component. */
  name = name.replace(/[^A-Za-z0-9]+/g, '-');

  return name;
}

/* Save the state of the search terms so that the page doesn't start over
   from scratch if the user navigates away and then back to the page. */
function save_state() {
  console.log('saving advanced search state');
  if (term_list.length) {
    var term_names = [];
    for (const term of term_list) {
      const name = term.get_name();
      console.log('saving', name);
      const q = cvt_name_to_query(name);
      term_names.push(q);
    }
    const query = term_names.join('.');

    const url = window.location.pathname + '?' + query;
    history.replaceState(null, '', url);
  } else {
    /* The code above would be OK except that it leaves the trailing '?',
       which I'd prefer to get rid of. */
    history.replaceState(null, '', window.location.pathname);
  }
}

function restore_state(query) {
  console.log('restoring advanced search state');

  for (var name of query.split('.')) {
    name = name.replace(/-/g, ' ');
    
    console.log('restoring', name);
    restore_term(name, 0);

    /* Assuming that we saved the state correctly, then we should always find
       the desired term in the first autocomplete match.  However, if something
       went wrong (e.g. the user mangled the URL or the database has changed),
       there might be no match at all.  In that case, we simply avoid crashing.
    */
    if (ac_list.length != 0) {
      confirm_adv_search_term(0);
    }
  }
  /* Since all of the search terms were inserted before the search input
     container, it doesn't need to move to be in the correct position. */
  clear_search();
  gen_adv_search_results();
}

/* Re-create a search term by reperforming a prior search. */
function restore_term(search_str, ac_selected) {
  e_search_input.value = search_str;
  fn_search(ac_selected);
}

/* Handle a mouse click or Enter keypress on an autocomplete entry
   while on the advanced search page. */
function confirm_adv_search_term(ac_selected) {
  /* Most calls invoke the default behavior of getting the term from the
     appropriate entry of ac_list.  Only special cases provide a term
     from another source. */
  const term = ac_list[ac_selected];

  /* Remember the user input that led to this term.
     We restore this state if the user clicks the term to edit it.
     Because the data in fit_info depends on the search type, we
     just add data to it rather than making a new object and copying
     the data over. */
  term.search_str = e_search_input.value;
  term.ac_selected = ac_selected;

  /* Note that the ClearTerm has special code so that the following
     functions that supposed create HTML and insert it into the list
     actually leave the entry unfilled. */

  term.gen_html_element();

  if ((term_id < term_list.length) &&
      (term.group == term_list[term_id].group)) {
    /* We were editing an existing term, and the edited term is in the
       same group.  Instead of moving the term to the end of its group,
       replace the edited one in the same position. */
    console.log('retaining position', term_id);
    term_list[term_id] = term;
    revert_adv_search_term();
  } else {
    /* We're confirming a new search term, so we can discard the one that
       we were editing.  If term_id == term_list.length (meaning that a
       new term was being entered), nothing happens here. */
    term_list.splice(term_id, 1);
    term.insert_html_element();
  }

  /* We don't call prepare_new_adv_input() or gen_adv_search_results()
     here because restore_state() would prefer to batch up all confirmations
     before performing those actions.  I.e. those function calls are the
     responsibility of the caller.

     But we do reset term_id to the end of the term_list so that the code
     knows it is not editing an existing entry. */
  term_id = term_list.length;
}

function revert_adv_search_term() {
  /* Since the term already has everything it needs (such as e_term),
     we just need to re-insert it into the HTML.  We don't call
     insert_html_element() because that would insert it at the end of its
     group, whereas we want it to keep its position.  So we simply
     re-insert its e_term before the search container. */
  const term = term_list[term_id];
  e_search_container.insertAdjacentElement('beforeBegin', term.e_term);

  /* Depending on the caller, the search input could move to the end of the
     list or to a different position.  So we leave that up to the caller. */
}

function prepare_new_adv_input() {
  clear_search();

  /* Move the search container element to the bottom of the list.

     This is only needed if the user was editing a previous term,
     but there's no harm in an extraneous move.

     If the list is empty, the input container obviously doesn't need
     to move to be in the correct position. */
  if (term_id != 0) {
    const prev_e_term = term_list[term_id-1].e_term;
    prev_e_term.insertAdjacentElement('afterend', e_search_container);
  }

  e_search_input.focus();
}


class ClearTerm extends Term {
  pri;
  is_clear = true;

  constructor() {
    super(null); /* group is never used */

    /* insert_match() requires a priority(?), even if there's nothing else
       to compare it to. */
    this.pri = 0.0;

    insert_match(this);
  }

  get_ac_text() {
    /* This is not a matched term, so there is no highlight. */
    return 'remove this search term';
  }

  get_class() {
    return 'unobs';
  }

  gen_html_element() {
    /* do nothing because this is not a valid term */
  }

  insert_html_element() {
    /* do nothing because this is not a valid term */
  }
}


/* TextTerm is another superclass that is not intended to be used directly.
   In particular, it is missing any match() method. */
class TextTerm extends Term {
  search_str;
  pri;
  match_info;

  constructor(group, search_str, match_str, def_num_list = []) {
    super(group);

    this.search_str = search_str;
    this.match_str = match_str;
    this.def_num_list = def_num_list;
  }

  search() {
    const search_str = this.search_str;
    const match_info = check(this.search_str, this.match_str, 0,
                             this.def_num_list);

    if (match_info) {
      this.pri = match_info.pri;
      this.match_info = match_info;

      /* If the user hasn't entered all the numeric values, fill in values
         from the def_num_list.  This is useful when writing the potential
         search term in the autocomplete list and also later when confirming
         the search term. */
      for (const num of this.def_num_list.slice(match_info.valid_nums)) {
        match_info.num_list.push(num);
      }

      insert_match(this);
    }
  }

  get_ac_text() {
    return highlight_match(this.match_info, null, false);
  }

  get_class() {
    return 'unobs';
  }

  get_text() {
    var term_name = this.match_info.match_str;
    for (const num of this.match_info.num_list) {
      term_name = term_name.replace(/%#*/, num);
    }
    return term_name;
  }

  get_name() {
    return this.get_text();
  }

  get_url() {
    const query = cvt_name_to_query(this.get_name());
    return root_path + 'advanced-search.html?' + query;
  }
}


class TraitTerm extends TextTerm {
  match(result_set, page_to_trip) {
    const trait = this.match_info.match_str;

    for (const page_info of result_set) {
      if (!page_info.trait_set.has(trait)) {
        result_set.delete(page_info);
      }
    }
  }

  prefix() {
    return 'with';
  }
}


class TripTerm extends TextTerm {
  matching_trips = new Set();

  match(result_set, page_to_trip) {
    /* First, determine which trips meet the term requirement. */
    this.init_matching_trips();

    /* Then reduce the trip set of each taxon accordingly. */
    for (const page_info of result_set) {
      /* Initialize page_to_trip for this result page if necessary. */
      if (!(page_to_trip.has(page_info))) {
        page_to_trip.set(page_info, new Set(page_info.trip_set));
      }

      /* This is the constrained set of trips for this page. */
      const trip_result_set = page_to_trip.get(page_info);

      for (const trip of trip_result_set) {
        if (!this.matching_trips.has(trip)) {
          trip_result_set.delete(trip);
        }
      }

      if (trip_result_set.size == 0){
        result_set.delete(page_info);
      }
    }
  }
}


class ParkTerm extends TripTerm {
  init_matching_trips() {
    for (const trip of trips) {
      if (trip[1] == this.match_info.match_str) {
        this.matching_trips.add(trip);
      }
    }
  }

  prefix() {
    return 'observed in';
  }
}


/* Support structure for date-related terms. */
class DateTerm extends TripTerm {
  prefix() {
    return 'observed';
  }
}

class InYTerm extends DateTerm {
  constructor(group, search_str, dy) {
    super(group, search_str, 'in %###', [dy]);
  }

  init_matching_trips() {
    const tgt_year = this.match_info.num_list[0];

    for (const trip of trips) {
      const year = trip[0].substr(0, 4);
      if (year == tgt_year) {
        this.matching_trips.add(trip);
      }
    }
  }
}

class InYMTerm extends DateTerm {
  constructor(group, search_str, dy, dm) {
    super(group, search_str, 'in %###-%#', [dy, dm]);
  }

  init_matching_trips() {
    const tgt_year = this.match_info.num_list[0];
    const tgt_month = this.match_info.num_list[1];
    const tgt_date = tgt_year + '-' + tgt_month;

    for (const trip of trips) {
      const date = trip[0].substr(0, 7);
      if (date == tgt_date) {
        this.matching_trips.add(trip);
      }
    }
  }
}

class CmpYMDTerm extends DateTerm {
  fn_cmp;

  constructor(group, search_str, fn_cmp, prefix, postfix, dy, dm, dd) {
    super(group, search_str, prefix + '%###-%#-%#' + postfix, [dy, dm, dd]);
    this.fn_cmp = fn_cmp;
  }

  init_matching_trips() {
    const tgt_year = this.match_info.num_list[0];
    const tgt_month = this.match_info.num_list[1];
    const tgt_day = this.match_info.num_list[2];
    const tgt_date = tgt_year + '-' + tgt_month + '-' + tgt_day;

    for (const trip of trips) {
      if (this.fn_cmp(trip[0], tgt_date)) {
        this.matching_trips.add(trip);
      }
    }
  }
}

class BtwnMDTerm extends DateTerm {
  constructor(group, search_str) {
    super(group, search_str, 'between %#-%# and %#-%# (inclusive)',
          ['01', '01', '12', '31']);
  }

  init_matching_trips() {
    const tgt_m1 = this.match_info.num_list[0];
    const tgt_d1 = this.match_info.num_list[1];

    const tgt_m2 = this.match_info.num_list[2];
    const tgt_d2 = this.match_info.num_list[3];

    const tgt_date1 = tgt_m1 + '-' + tgt_d1;
    const tgt_date2 = tgt_m2 + '-' + tgt_d2;
    const nat_order = (tgt_date1 < tgt_date2);

    for (const trip of trips) {
      const date = trip[0].substr(5, 10);
      if (nat_order ? ((date >= tgt_date1) && (date <= tgt_date2))
                    : ((date >= tgt_date1) || (date <= tgt_date2))) {
        this.matching_trips.add(trip);
      }
    }
  }
}

class BtwnYMDTerm extends DateTerm {
  constructor(group, search_str, dy) {
    super(group, search_str, 'between %###-%#-%# and %###-%#-%# (inclusive)',
          [dy, '01', '01', dy, '12', '31']);
  }

  init_matching_trips() {
    const tgt_y1 = this.match_info.num_list[0];
    const tgt_m1 = this.match_info.num_list[1];
    const tgt_d1 = this.match_info.num_list[2];

    const tgt_y2 = this.match_info.num_list[3];
    const tgt_m2 = this.match_info.num_list[4];
    const tgt_d2 = this.match_info.num_list[5];

    const tgt_date1 = tgt_y1 + '-' + tgt_m1 + '-' + tgt_d1;
    const tgt_date2 = tgt_y2 + '-' + tgt_m2 + '-' + tgt_d2;

    for (const trip of trips) {
      if ((trip[0] >= tgt_date1) && (trip[0] <= tgt_date2)) {
        this.matching_trips.add(trip);
      }
    }
  }
}


function delete_ancestors(page_info, result_set, checked_set) {
  for (const parent_info of page_info.parent_set) {
    if (checked_set.has(parent_info)) {
      /* no need to recheck or recurse */
    } else {
      if (result_set.has(parent_info)) {
        result_set.delete(parent_info);
      }
      checked_set.add(parent_info);
      delete_ancestors(parent_info, result_set, checked_set);
    }
  }
}

/* Perform the advanced search and generate the HTML for the results. */
function gen_adv_search_results() {
  save_state();

  if (term_list.length == 0) {
    e_results.innerHTML = '<p>...</p>';
    return;
  }

  /* Perform the advanced search, combining the results from each term. */

  /* Start with all possible results (excluding subset pages and glosseries),
     then remove pages that fail to satisfy a term. */
  const result_set = new Set(pages.filter((x) => !'sgj'.includes(x.x)));

  /* Keep track of the constrained set of trips for each page. */
  const page_to_trip = new Map();

  /* For each search term, remvoe taxons from the result_set that don't
     match the term. */
  for (const term of term_list) {
    term.match(result_set, page_to_trip);
  }

  /* Show only results at the lowest level.  I.e. eliminate higher-level
     pages where a lower-level page is in the results. */
  const checked_set = new Set();
  for (const page_info of result_set) {
    delete_ancestors(page_info, result_set, checked_set);
  }

/* Helper function for sorting a list of taxons (page_info) by the number of
   trips that match the search terms.

   Note that reference to page_to_trip from the containing function.

   We prefer that if two taxons are observed the same number of times, we
   keep the order from pagse.js.  Array.sort() is only guaranteed to preserve
   this order since ~2019, but
   - it primary benefit is to order a parent before its child, but that doesn't
     matter here since the advanced search results either group the children
     hierarchically under the parent or delete the parent from the results, and
   - it's not really a burden if results get out of order.
*/
  function by_trip_cnt(a, b) {
    if (page_to_trip.has(a)) {
      var a_cnt = page_to_trip.get(a).size;
    } else {
      var a_cnt = a.trip_set.size;
    }

    if (page_to_trip.has(b)) {
      var b_cnt = page_to_trip.get(b).size;
    } else {
      var b_cnt = b.trip_set.size;
    }

    return (a < b) ? -1 : (a > b) ? 1 : 0;
  }

  const result_list = Array.from(result_set).sort(by_trip_cnt);

  const list = [];
  var cnt = 0;
  for (const page_info of result_list) {
    const c = get_class(page_info);
    const url = get_url(page_info, null);
    cnt++;

    list.push('<div class="list-box">');

    if ('j' in page_info) {
      var jpg = String(page_info.j);
      const comma_pos = jpg.search(',');
      if (comma_pos == -1) {
        /* Append the suffix the suffix to the page name. */
        jpg = page_info.p + ',' + jpg;
      }
      var jpg_url = 'thumbs/' + jpg + '.jpg';

      /* Enable lazy image loading after the first 10 entries (whether those
         entries include imagse or not).  This prevents a broad search from
         fetching every thumbnail in the library!  The first 10 entries are
         allowed to load immediately because there is some slight penalty to
         responsiveness if the browser waits to determine whether they are
         in/near the visible area. */
      var lazy = (cnt > 10) ? ' loading="lazy"' : '';

      list.push('<a href="' + url + '">');
      list.push('<div class="list-thumb">');
      list.push('<img class="boxed"' + lazy + ' src="' + jpg_url + '" alt="photo">');
      list.push('</div>');
      list.push('</a>');
    }

    list.push('<a class="' + c + '" href="' + url + '">');
    list.push(compose_page_name(page_info, 2));
    list.push('</a>');

    list.push('</div>');
  }

  if (list.length) {
    e_results.innerHTML = list.join('');
  } else {
    e_results.innerHTML = '<p>No taxons match the criteria.</p>';
  }
}


/*****************************************************************************/
/* main() */

/* Determine whether to add 'html/' to the URL when navigating to a page. */
if (/\/html\/[^\/]*$/.test(window.location.pathname)) {
  var path = '';
} else {
  var path = 'html/';
}

/* main() kicks off search-related activity once it is safe to do so.
   See further below for how main() is activated. */
function main() {
  console.info('search.js main()')

  /* Make sure the page elements are ready. */
  if (document.readyState === 'loading') {
    console.info('...main too early')
    document.addEventListener('DOMContentLoaded', main);
    return
  }

  e_home_icon = document.getElementById('home-icon');
  e_terms = document.getElementById('terms');
  e_search_container = document.getElementById('search-container');
  e_search_input = document.getElementById('search');
  e_autocomplete_box = document.getElementById('autocomplete-box');
  e_results = document.getElementById('results');

  adv_search = Boolean(e_results) /* only the adv. search page has e_results */

  /* Add the search class to the search box in order to enable styling
     that should only be applied when JavaScript is enabled. */
  e_search_input.className = 'search';

  /* normalize the data in the pages array. */
  for (var i = 0; i < pages.length; i++) {
    var page_info = pages[i];
    if (('p' in page_info) &&
        !('c' in page_info) &&
        (!hasUpper(page_info.p) || (page_info.x == 'j'))) {
      page_info.c = [page_info.p];
    }
    if (('p' in page_info) &&
        !('s' in page_info) &&
        hasUpper(page_info.p) && (page_info.x != 'j')) {
      page_info.s = [page_info.p];
    }
  }

  init_parks();
  if (adv_search) {
    init_adv_search();
  }

  e_search_input.addEventListener('input', fn_change);
  e_search_input.addEventListener('keydown', fn_keydown);
  e_search_input.addEventListener('focusin', fn_focusin);

  /* Set the window title when entering the page (possibly with an anchor)... */
  fn_hashchange();

  /* ... or when changing anchors within a page. */
  window.addEventListener('hashchange', fn_hashchange);

  if (adv_search) {
    const query = window.location.search;
    if (query) {
      restore_state(query.substring(1)); /* discard leading '?' */
    }
  }

  /* Also initialize the photo gallery. */
  gallery_main();

  /* In case the user already started typing before the script loaded,
     perform the search right away on whatever is in the search field,
     but only if the focus is still in the search field.

     If the search field is (still) empty, fn_search() does nothing. */
  if (Document.activeElement == e_search_input) {
    fn_search(0);
  }
}

/* main() is called when either of these two events occurs:
   we reach this part of search.js and the pages array exists, or
   we reach the end of pages.js and the main function exists.
*/
if (typeof pages !== 'undefined') {
  main();
}
