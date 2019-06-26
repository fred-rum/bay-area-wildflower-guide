"use strict";

var ac_is_hidden = true;
function expose_ac() {
  e_autocomplete_box.style.visibility = 'visible';
  ac_is_hidden = false;
}

function hide_ac() {
  e_autocomplete_box.style.visibility = 'hidden';
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

/* When comparing names, ignore all non-letter characters and ignore case. */
function compress(name) {
  return name.toUpperCase().replace(/[^A-Z]/g, '');
}

/* check() is called multiple times, once for each name associated with a page.
   Throughout this process, it accumulates the best fit in the best_fit_info
   structure.  An exact match is given highest priority.  A match at the start
   of the name has medium priority, and a match somewhere later in the name
   has the lowest priority. */
function check(search_str_cmp, match_str, page_info, best_fit_info) {
  var cx = compress(match_str);
  if ((best_fit_info.pri < 4) && (cx == search_str_cmp)) {
    best_fit_info.pri = 4;
    best_fit_info.page_info = page_info;
  }
  if ((best_fit_info.pri < 3) && (cx.startsWith(search_str_cmp))) {
    best_fit_info.pri = 3;
    best_fit_info.page_info = page_info;
  }
  if ((best_fit_info.pri < 2) && (cx.includes(search_str_cmp))) {
    best_fit_info.pri = 2;
    best_fit_info.page_info = page_info;
  }
}

function startsUpper(name) {
  return (name.search(/^[A-Z]/) >= 0);
}

function bold(search_str_cmp, name) {
  var has_ssp = false;
  var test_name = name;

  var name_cmp = compress(name);
  var cmp_match_pos = name_cmp.indexOf(search_str_cmp);
  if ((cmp_match_pos == -1) && startsUpper(name)) {
    /* There wasn't a match, but since it's a scientific name, maybe there
       will be a match when we take the subtype specifier out. */
    var name_split = name.split(' ');
    if (name_split.length == 4) {
      has_ssp = true;
      var ssp = name_split[2];
      var ssp_pos = name_split[0].length + 1 + name_split[1].length;
      test_name = name_split[0] + ' ' + name_split[1] + ' ' + name_split[3]
      name_cmp = compress(test_name);
      cmp_match_pos = name_cmp.indexOf(search_str_cmp);
    }
  }
  if (cmp_match_pos == -1) {
    return name;
  }

  /* Based on the number of letters in the compressed name prior to the match,
     skip the same number of letters in the uncompressed name (also skipping
     any number of non-letters). */
  var regex = RegExp('[a-zA-Z]', 'g');
  for (var i = 0; i <= cmp_match_pos; i++) {
    regex.test(test_name);
  }
  var uncmp_match_begin = regex.lastIndex - 1;

  for (var i = 1; i < search_str_cmp.length; i++) {
    regex.test(test_name);
  }
  var uncmp_match_end = regex.lastIndex;

  if (has_ssp) {
    if (uncmp_match_begin > ssp_pos) {
      uncmp_match_begin += ssp.length + 1;
    }
    if (uncmp_match_end > ssp_pos) {
      uncmp_match_end += ssp.length + 1;
    }
  }

  var highlighted_name = name.substring(0, uncmp_match_begin);
  highlighted_name += ('<span class="match">' +
                       name.substring(uncmp_match_begin, uncmp_match_end) +
                       '</span>');
  highlighted_name += name.substring(uncmp_match_end);

  return highlighted_name;
}

/* Update the autocomplete list.
   If 'enter' is true, then navigate to the top autocompletion's page. */
function fn_search(enter) {
  var search_str_cmp = compress(e_search_input.value);

  if (search_str_cmp == '') {
    hide_ac();
    return;
  }

  /* Iterate over all pages and accumulate a list of the best matches
     against the search value. */
  var best_list = [];
  for (var i = 0; i < pages.length; i++) {
    var page_info = pages[i];
    var best_fit_info = {
      pri: 0 /* 0 means no match */
    }

    check(search_str_cmp, page_info.page, page_info, best_fit_info)
    if ('com' in page_info) {
      check(search_str_cmp, page_info.com, page_info, best_fit_info)
    }
    if ('sci' in page_info) {
      check(search_str_cmp, page_info.sci, page_info, best_fit_info)
    }
    if ('elab' in page_info) {
      check(search_str_cmp, page_info.elab, page_info, best_fit_info)
    }

    /* If there's a match, and
       - we don't already have 10 matches or
       - the new match is better than the last match on the list
       then remember the new match. */
    if (best_fit_info.pri &&
        ((best_list.length < 10) || (best_fit_info.pri > best_list[9].pri))) {
      /* Insert the new match into the list in priority order.  In case of
         a tie, the new match goes lower on the list. */
      for (var j = 0; j < best_list.length; j++) {
        if (best_fit_info.pri > best_list[j].pri) break;
      }
      best_list.splice(j, 0, best_fit_info);
      /* If the list was already the maximum length, it is now longer than the
         maximum length.  Cut off the last entry. */
      if (best_list.length > 10) {
        best_list.splice(-1, 1);
      }
    }
  }

  if (best_list.length) {
    var ac_list = [];
    for (var i = 0; i < best_list.length; i++) {
      var page_info = best_list[i].page_info;
      if ('key' in page_info) {
        var c = 'parent';
      } else {
        var c = 'leaf';
      }
      if ('com' in page_info) {
        var com = page_info.com;
      } else {
        var com = page_info.page;
      }
      if (('sci' in page_info) ||
          ('elab' in page_info) ||
          startsUpper(page_info.page)) {
        if ('elab' in page_info) {
          var elab = page_info.elab;
        } else if ('sci' in page_info) {
          var elab = page_info.sci;
        } else {
          var elab = page_info.page;
        }
        var elab_bold = bold(search_str_cmp, elab);
        if (startsUpper(elab)) {
          var elab_bold_ital = '<i>' + elab_bold + '</i>';
        } else {
          /* Don't italicize the group type (e.g. "family"). */
          /* elab_bold might include a <span ...> tag for highlighting, and
             we don't want to accidentially trigger on that space.  So we
             have to carefully check whether the highlighted span starts
             before or after the space. */
          var space_pos = elab.indexOf(' ');
          if (!elab_bold.startsWith(elab.substring(0, space_pos+1))) {
            /* The highlighted span starts before the space, so search
               backward to find the space instead.  (If the highlighed span
               spans the space, we'll end up with <i> inside the span and
               </i> outside the span, but that's OK. */
            var space_pos = elab_bold.lastIndexOf(' ');
          }
          var elab_bold_ital = (elab_bold.substring(0, space_pos) + ' <i>' +
                                elab_bold.substring(space_pos+1) + '</i>');
        }
        if (('sci' in page_info) && (page_info.sci != com)) {
          var full = bold(search_str_cmp, com) + ' (' + elab_bold_ital + ')';
        } else {
          var full = elab_bold_ital;
        }
      } else {
        var full = bold(search_str_cmp, com)
      }
      var entry = ('<a class="enclosed ' + c + '" href="' +
                   path + page_info.page + '.html"><div>' +
                   full + '</div></a>');

      /* Highlight the first entry in bold.  This entry is selected if the
         user presses 'enter'. */
      if (i == 0) {
        entry = '<b>' + entry + '</b>';
      }
      ac_list.push(entry);
    }
    e_autocomplete_box.innerHTML = ac_list.join('');
  } else {
    e_autocomplete_box.innerHTML = 'No matches found.';
  }
  expose_ac();
  if (enter && best_list) {
    window.location.href = path + best_list[0].page_info.page + '.html';
  }
}

/* Handle all changes to the search value.  This includes changes that
   are not accompanied by a keyup event, such as a mouse-based paste event. */
function fn_change() {
  fn_search(false);
}

/* Handle when the user presses the 'enter' key. */
function fn_keyup() {
  if (event.keyCode == 13) {
    fn_search(true);
  }
}

/* Determine whether to add 'html/' to the URL when navigating to a page. */
if (window.location.pathname.includes('/html/')) {
  var path = '';
} else {
  var path = 'html/';
}

var e_search_input = document.getElementById('search');
e_search_input.addEventListener('input', fn_change);
e_search_input.addEventListener('keyup', fn_keyup);
e_search_input.addEventListener('focusin', fn_focusin);

var e_search_box = document.getElementById('search-container');

/* The 'body' div is everything on the page not associated with the search bar.
   Thus, clicking somewhere other than the search bar or autocomplete box
   causes the autocomplete box to be hidden. */
var e_body = document.getElementById('body');
e_body.addEventListener('mousedown', fn_focusout);

var e_autocomplete_box = document.getElementById('autocomplete-box');

/*****************************************************************************/

function fn_details(e) {
  if (e.textContent == '[show details]') {
    e.textContent = '[hide details]';
    document.getElementById('details').style.display = 'block';
  } else {
    e.textContent = '[show details]';
    document.getElementById('details').style.display = 'none';
  }
}
