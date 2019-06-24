"use strict";

var is_hidden = true;
function expose_ac() {
  e_autocomplete_box.style.visibility = 'visible';
  is_hidden = false;
}

function hide_ac() {
  e_autocomplete_box.style.visibility = 'hidden';
  is_hidden = true;
}

function is_focused() {
  var e_active = document.activeElement;
  return e_search_box.contains(e_active);
}

function fn_focusin() {
  if (is_hidden) {
    /* e_search_input.select(); */ /* Not as smooth on Android as desired. */
    fn_search();
  }
}

function fn_focusout() {
  if (!is_hidden) {
    hide_ac();
  }
}

function compress(name) {
  return name.toUpperCase().replace(/[^A-Z]/g, '');
}

function check(vx, name, d, best) {
  var cx = compress(name);
  if ((best.pri < 4) && (cx == vx)) {
    best.pri = 4;
    best.d = d;
  }
  if ((best.pri < 3) && (cx.startsWith(vx))) {
    best.pri = 3;
    best.d = d;
  }
  if ((best.pri < 2) && (cx.includes(vx))) {
    best.pri = 2;
    best.d = d;
  }
}

function startsUpper(name) {
  return (name.search(/^[A-Z]/) >= 0);
}

function bold(vx, name) {
  var has_ssp = false;
  var test_name = name;

  var nx = compress(name);
  var start = nx.indexOf(vx);
  if ((start == -1) && startsUpper(name)) {
    /* There wasn't a match, but since it's a scientific name, maybe there
       will be a match when we take the subtype specifier out. */
    var name_split = name.split(' ');
    if (name_split.length == 4) {
      has_ssp = true;
      var ssp = name_split[2];
      var ssp_pos = name_split[0].length + 1 + name_split[1].length;
      test_name = name_split[0] + ' ' + name_split[1] + ' ' + name_split[3]
      nx = compress(test_name);
      start = nx.indexOf(vx);
    }
  }
  if (start == -1) {
    return name;
  }

  var regex = RegExp('[a-zA-Z][^a-zA-Z]*', 'y');
  for (var i = 0; i < start; i++) {
    regex.test(test_name);
  }
  var b = regex.lastIndex;

  for (var i = 0; i < vx.length; i++) {
    regex.test(test_name);
  }
  var e = regex.lastIndex;

  if (has_ssp) {
    if (b > ssp_pos) {
      b += ssp.length + 1;
    }
    if (e > ssp_pos) {
      e += ssp.length + 1;
    }
  }

  var s = name.substring(0, b);
  s += '<span class="match">' + name.substring(b, e) + '</span>';
  s += name.substring(e);

  return s;
}

function fn_search(enter) {
  var v = e_search_input.value;

  if (v == '') {
    hide_ac();
    return;
  }

  var vx = compress(v);
  var best_list = [];

  for (var i = 0; i < pages.length; i++) {
    var d = pages[i];
    var best = {
      pri: 0
    }

    check(vx, d.page, d, best)
    if ('com' in d) {
      check(vx, d.com, d, best)
    }
    if ('sci' in d) {
      check(vx, d.sci, d, best)
    }
    if ('elab' in d) {
      check(vx, d.elab, d, best)
    }

    if (best.pri &&
        ((best_list.length < 10) || (best.pri > best_list[9].pri))) {
      /* We found the best match for the page.
         Insert its information into the best_list. */
      for (var j = 0; j < best_list.length; j++) {
        if (best.pri > best_list[j].pri) break;
      }
      best_list.splice(j, 0, best);
      if (best_list.length > 10) {
        best_list.splice(-1, 1);
      }
    }
  }

  if (best_list.length) {
    var ac_list = [];
    for (var i = 0; i < best_list.length; i++) {
      var best = best_list[i];
      var d = best.d;
      if ('key' in d) {
        var c = 'parent';
      } else {
        var c = 'leaf';
      }
      if ('com' in d) {
        var com = d.com;
      } else {
        var com = d.page;
      }
      if (('sci' in d) || ('elab' in d) || startsUpper(d.page)) {
        if ('elab' in d) {
          var elab = d.elab;
        } else if ('sci' in d) {
          var elab = d.sci;
        } else {
          var elab = d.page;
        }
        if (('sci' in d) && (d.sci != com)) {
          var name = bold(vx, com) + ' (<i>' + bold(vx, elab) + '</i>)';
        } else {
          var name = '<i>' + bold(vx, elab) + '</i>';
        }
      } else {
        name = bold(vx, com)
      }
      var entry = '<a class="enclosed ' + c + '" href="' + path + d.page + '.html"><div>' + name + '</div></a>';
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
    window.location.href = path + best_list[0].d.page + '.html';
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
