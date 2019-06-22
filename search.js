is_hidden = true;
function expose_ac() {
  e_autocomplete_box.style.visibility = 'visible';
  is_hidden = false;
}

function hide_ac() {
  e_autocomplete_box.style.visibility = 'hidden';
  is_hidden = true;
}

function is_focused() {
  e_active = document.activeElement;
  return e_search_box.contains(e_active);
}

function fn_focusin() {
  if (is_hidden) {
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
  cx = compress(name);
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
  has_ssp = false;
  test_name = name;

  nx = compress(name);
  start = nx.indexOf(vx);
  if ((start == -1) && startsUpper(name)) {
    /* There wasn't a match, but since it's a scientific name, maybe there
       will be a match when we take the subtype specifier out. */
    name_split = name.split(' ');
    if (name_split.length == 4) {
      has_ssp = true;
      ssp = name_split[2];
      ssp_pos = name_split[0].length + 1 + name_split[1].length;
      test_name = name_split[0] + ' ' + name_split[1] + ' ' + name_split[3]
      nx = compress(test_name);
      start = nx.indexOf(vx);
    }
  }
  if (start == -1) {
    return name;
  }

  regex = RegExp('[a-zA-Z][^a-zA-Z]*', 'y');
  for (var i = 0; i < start; i++) {
    regex.test(test_name);
  }
  b = regex.lastIndex;

  for (var i = 0; i < vx.length; i++) {
    regex.test(test_name);
  }
  e = regex.lastIndex;

  if (has_ssp) {
    if (b > ssp_pos) {
      b += ssp.length + 1;
    }
    if (e > ssp_pos) {
      e += ssp.length + 1;
    }
  }

  s = name.substring(0, b);
  s += '<span class="match">' + name.substring(b, e) + '</span>';
  s += name.substring(e);

  return s;
}

function fn_search(enter) {
  v = e_search_input.value;

  if (v == '') {
    hide_ac();
    return;
  }

  vx = compress(v);
  best_list = [];

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

  if (best_list) {
    ac_list = [];
    for (var i = 0; i < best_list.length; i++) {
      best = best_list[i];
      d = best.d;
      if ('key' in d) {
        c = 'parent';
      } else {
        c = 'leaf';
      }
      if ('com' in d) {
        com = d.com;
      } else {
        com = d.page;
      }
      if (('sci' in d) || ('elab' in d) || startsUpper(d.page)) {
        if ('elab' in d) {
          elab = d.elab;
        } else if ('sci' in d) {
          elab = d.sci;
        } else {
          elab = d.page;
        }
        if (('sci' in d) && (d.sci != com)) {
          name = bold(vx, com) + ' (<i>' + bold(vx, elab) + '</i>)';
        } else {
          name = '<i>' + bold(vx, elab) + '</i>';
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

if (window.location.href.endsWith('/index.html')) {
  path = 'html/';
} else {
  path = '';
}

e_search_input = document.getElementById('search');
e_search_input.addEventListener('input', fn_change);
e_search_input.addEventListener('keyup', fn_keyup);
e_search_input.addEventListener('focusin', fn_focusin);

e_search_box = document.getElementById('search-container');

/* The 'body' div is everything on the page not associated with the search bar.
   Thus, clicking somewhere other than the search bar or autocomplete box
   causes the autocomplete box to be hidden. */
e_body = document.getElementById('body');
e_body.addEventListener('mousedown', fn_focusout);

e_autocomplete_box = document.getElementById('autocomplete-box');
