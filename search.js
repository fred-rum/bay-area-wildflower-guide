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

function check(vx, name, d, best) {
  cx = name.toUpperCase().replace(/[^A-Z]/g, '')
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

function bold(vx, name) {
  nx = name.toUpperCase().replace(/[^A-Z]/g, '');
  start = nx.indexOf(vx);

  if (start == -1) {
    return name;
  }

  regex = RegExp('[a-zA-Z][^a-zA-Z]*', 'y');
  for (i = 0; i < start; i++) {
    regex.test(name);
  }
  b = regex.lastIndex;

  for (i = 0; i < vx.length; i++) {
    regex.test(name);
  }

  s = name.substring(0, b);
  s += '<span class="match">' + name.substring(b, regex.lastIndex) + '</span>';
  s += name.substring(regex.lastIndex);

  return s;
}

function fn_search(enter) {
  v = e_search_input.value;

  if (v == '') {
    hide_ac();
    return;
  }
  best = {
    pri: 0
  }
  vx = v.toUpperCase().replace(/[^A-Z]/g, '')
  for (i = 0; i < pages.length; i++) {
    d = pages[i]
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
  }
  if (best.pri) {
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
    if (('sci' in d) || ('elab' in d)) {
      if ('elab' in d) {
        elab = d.elab;
      } else {
        elab = d.sci;
      }
      if (('sci' in d) && (d.sci != com)) {
        name = bold(vx, com) + ' (<i>' + bold(vx, elab) + '</i>)';
      } else {
        name = '<i>' + bold(vx, elab) + '</i>';
      }
    } else {
      name = bold(vx, com)
    }
    e_autocomplete_box.innerHTML = '<a class="enclosed ' + c + '" href="' + path + d.page + '.html"><div>' + name + '</div></a>';
  } else {
    e_autocomplete_box.innerHTML = 'No matches found.';
  }
  expose_ac();
  if (enter && p) {
    window.location.href = path + m + '.html';
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
