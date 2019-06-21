is_hidden = true;
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

function fn_search(enter) {
  v = e_search_input.value;

  if (v == '') {
    hide_ac();
    return;
  }
  p = 0;
  vx = v.toUpperCase().replace(/[^A-Z]/g, '')
  for (i = 0; i < page.length; i++) {
    l = page[i]
    for (j = 0; j < l.length; j++) {
      c = l[j];
      cx = c.toUpperCase().replace(/[^A-Z]/g, '')
      if ((p < 4) && (cx == vx)) {
        p = 4;
        m = l[0]
      }
      if ((p < 3) && (cx.startsWith(vx))) {
        p = 3;
        m = l[0];
      }
      if ((p < 2) && (cx.includes(vx))) {
        p = 2;
        m = l[0];
      }
    }
  }
  if (p) {
    e_autocomplete_box.innerHTML = '<a href="' + path + m + '.html"><div>' + m + '</div></a>';
    e_autocomplete_box.style.visibility = 'visible';
    is_hidden = false;
  } else {
    hide_ac();
  }
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
