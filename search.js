/* Copyright Chris Nelson - All rights reserved. */
'use strict';
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
var ac_list;
var ac_selected;
function clear_search() {
  e_search_input.value = '';
  ac_list = [];
  ac_selected = 0;
  hide_ac();
}
function compress(name) {
  return name.toUpperCase().replace(/\W/g, '');
}
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
function startsUpper(name) {
  return (name.search(/^[A-Z]/) >= 0);
}
function hasUpper(name) {
  return (name.search(/[A-Z]/) >= 0);
}
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
function check(search_str, match_str, pri_adj) {
  var s = search_str;
  var upper_str = match_str.toUpperCase()
  var m = upper_str.replace(/\W/g, '');
  var name_pos = match_str.indexOf(' ');
  if ((name_pos < 0) ||
      (match_str.substr(0, 1) == upper_str.substr(0, 1)) ||
      (match_str.substr(name_pos+1, 1) != upper_str.substr(name_pos+1, 1))) {
    name_pos = 0;
  }
  var match_ranges = [];
  var i = 0;
  var j = 0;
  while (true) {
    while ((/\W/.test(s.substr(i, 1))) && (i < s.length)) {
      i++;
    }
    var start_i = i;
    if (i == s.length) {
      break;
    }
    while ((/\w/.test(s.substr(i, 1))) && (i < s.length)) {
      i++;
    }
    var s_word = s.substring(start_i, i);
    var start_j = m.indexOf(s_word, j);
    if (start_j == -1) {
      return null;
    }
    j = start_j + (i - start_i);
    if (match_ranges.length &&
        (match_ranges[match_ranges.length-1][1] == start_j)) {
      match_ranges[match_ranges.length-1][1] = j;
    } else {
      match_ranges.push([start_j, j]);
    }
  }
  var pri = 100.0;
  pri += pri_adj;
  pri -= (match_ranges.length / 10);
  if ((match_ranges[0][0] == 0) ||
      (match_ranges[0][0] == name_pos)) {
    pri += 0.15;
  }
  var match_info = {
    pri: pri,
    match_str: match_str,
    match_ranges: match_ranges
  }
  return match_info;
}
function better_match(one, two) {
  return (one && (!two || (one.pri > two.pri)));
}
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
      match_info = check(search_str, name.substr(6) + ' spp.');
    }
    if (better_match(match_info, best_match_info)) {
      best_match_info = match_info;
    }
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
function highlight_match(match_info, default_name, is_sci) {
  var tag_info = [];
  var h = '';
  if (match_info) {
    var m = match_info.match_str;
    var match_ranges = match_info.match_ranges;
    var ranges = [];
    for (var i = 0; i < match_ranges.length; i++) {
      var begin = find_letter_pos(m, match_ranges[i][0]);
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
      h += info.tag[0];
      nest.push(info);
    } else {
      for (i = nest.length-1; nest[i] != info; i--) {
        h += nest[i].tag[1];
      }
      h += nest[i].tag[1];
      nest.splice(i, 1);
      for (i = i; i < nest.length; i++) {
        h += nest[i].tag[0];
      }
    }
    info.half++;
    if (info.half == 2) {
      info.half = 0;
      info.i++;
      if (info.i == info.ranges.length) {
        tag_info.splice(info_idx, 1);
      }
    }
  }
  h += m.substring(pos);
  return h;
}
function insert_match(fit_info) {
  if ((ac_list.length < 10) || (fit_info.pri > ac_list[9].pri)) {
    for (var j = 0; j < ac_list.length; j++) {
      if (fit_info.pri > ac_list[j].pri) break;
    }
    ac_list.splice(j, 0, fit_info);
    if (ac_list.length > 10) {
      ac_list.splice(-1, 1);
    }
  }
}
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
    return;
  }
  if ('glossary' in page_info) {
    var best_match_info = null;
    for (var j = 0; j < page_info.glossary.length; j++) {
      var glossary = page_info.glossary[j];
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
function fn_search() {
  var search_str = e_search_input.value.toUpperCase();
  if (!/\w/.test(search_str)) {
    hide_ac();
    return;
  }
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
    full = full.replace(/\'/g, '&rsquo;');
    fit_info.html = ('<a ' + link + '><p class="nogap">' +
                     full + '</p></a>');
  }
  ac_selected = 0;
  generate_ac_html();
  expose_ac();
}
function fn_click() {
  clear_search();
  return true;
}
function fn_change() {
  fn_search();
}
function fn_keydown() {
  if ((event.key == 'Enter') && !ac_is_hidden && ac_list.length) {
    var fit_info = ac_list[ac_selected];
    var url = fn_url(fit_info);
    if (event.shiftKey || event.ctrlKey) {
      window.open(url);
    } else {
      window.location.href = url;
    }
    clear_search();
  } else if (event.key == 'Escape') {
    clear_search();
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
var e_search_input = document.getElementById('search');
var e_autocomplete_box = document.getElementById('autocomplete-box');
var e_home_icon = document.getElementById('home-icon');
document.addEventListener('click', fn_doc_click);
window.onbeforeunload = fn_focusout;
function fn_hashchange(event) {
  hide_ac();
  var title_list = document.title.split(' - ');
  var title = title_list[title_list.length - 1];
  var hash = location.hash;
  if (hash && (hash != '#offline')) {
    document.title = decodeURIComponent(hash).substring(1) + ' - ' + title;
  }
}
if (window.location.pathname.includes('/html/')) {
  var path = '';
} else {
  var path = 'html/';
}
function main() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
    return
  }
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
  fn_hashchange();
  window.addEventListener("hashchange", fn_hashchange);
  if (Document.activeElement == e_search_input) {
    fn_search();
  }
}
if (typeof pages !== 'undefined') {
  main();
}
function fn_details(event) {
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
function fn_details_keydown(event) {
  if ((event.key == 'Enter') ||
      (event.key == ' ') ||
      (event.key == 'Spacebar')) {
    fn_details(event);
    event.preventDefault();
  }
}
var obj_photos = [];
var obj_photo = undefined;
var e_bg = undefined;
var touches = [];
var one_unmoved_touch = true;
function open_gallery() {
  e_bg = document.createElement('div');
  e_bg.id = 'gallery-background';
  document.body.appendChild(e_bg);
  e_bg.onpointerdown = fn_pointerdown;
  e_bg.onpointerleave = fn_pointercancel;
  e_bg.onpointercancel = fn_pointercancel;
  e_bg.onpointerup = fn_pointerup;
  e_bg.onpointermove = fn_pointermove;
  e_bg.onwheel = fn_wheel;
}
function close_gallery() {
  e_bg.remove();
  obj_photo = undefined;
  return false;
}
function fn_popstate(event) {
  if (obj_photo) {
    close_gallery();
  }
  if (history.state) {
    obj_photo = obj_photos[history.state.i];
    obj_photo.fit = history.state.fit;
    obj_photo.zoom = history.state.zoom;
    obj_photo.cx = history.state.cx;
    obj_photo.cy = history.state.cy;
    obj_photo.gallery_init();
  }
}
function copy_touch(event) {
  return {
    id: event.pointerId,
    x: event.clientX,
    y: event.clientY
  };
}
function fn_pointerdown(event) {
  if ((event.pointerType == 'mouse') && (event.buttons != 1)) {
    return true;
  }
  var touch = copy_touch(event);
  touches.push(touch);
  one_unmoved_touch = (touches.length == 1);
  return false;
}
function touch_index(touch) {
  for (var i = 0; i < touches.length; i++) {
    if (touches[i].id == touch.id) {
      return i;
    }
  }
  return -1;
}
function discard_touch(touch) {
  var i = touch_index(touch);
  if (i != -1) {
    touches.splice(i, 1);
    return true;
  }
  return false;
}
function fn_pointercancel(event) {
  var touch = copy_touch(event);
  discard_touch(touch);
  return false;
}
function fn_pointerup(event) {
  var touch = copy_touch(event);
  if (discard_touch(touch) && one_unmoved_touch) {
    if (obj_photo && obj_photo.click.call(obj_photo, touch)) {
      history.back();
    }
    return false;
  }
  return true;
}
function measure_pinch() {
  var x0 = touches[0].x;
  var x1 = x0;
  var y0 = touches[0].y;
  var y1 = y0;
  for (var i = 1; i < touches.length; i++) {
    if (touches[i].x < x0) x0 = touches[i].x;
    if (touches[i].x > x1) x1 = touches[i].x;
    if (touches[i].y < y0) y0 = touches[i].y;
    if (touches[i].y > y1) y1 = touches[i].y;
  }
  return {
    'distance': Math.sqrt((x1 - x0) * (x1 - x0) + (y1 - y0) * (y1 - y0)),
    'x': (x0 + x1) / 2,
    'y': (y0 + y1) / 2
  };
}
function fn_pointermove(event) {
  if (touches.length == 0) {
    return false;
  }
  if ((event.pointerType == 'mouse') && (event.buttons != 1)) {
    fn_pointercancel(event);
    return true;
  }
  var touch = copy_touch(event);
  var old_pinch = measure_pinch();
  var i = touch_index(touch);
  if (i == -1) {
    return false;
  }
  if ((touches[i].x == touch.x) &&
      (touches[i].y == touch.y)) {
    return false;
  }
  one_unmoved_touch = false;
  touches[i] = touch;
  if (obj_photo) {
    var new_pinch = measure_pinch();
    obj_photo.pinch.call(obj_photo, old_pinch, new_pinch);
  }
  return false;
}
function fn_wheel(event) {
  var touch = copy_touch(event);
  if (event.deltaY < 0) {
    obj_photo.zoom_to(obj_photo.zoom * 1.30, touch, touch);
  }
  if (event.deltaY > 0) {
    obj_photo.zoom_to(obj_photo.zoom / 1.30, touch, touch);
  }
}
function bind(scope, fn) {
   return function(event) {
      return fn.call(scope, event);
   }
}
function Photo(i, e_thumbnail) {
  this.i = i;
  this.e_thumbnail = e_thumbnail;
  this.e_thumbnail.onclick = bind(this, this.fn_gallery_start);
  this.e_photo = undefined;
}
Photo.prototype.fn_gallery_start = function (event) {
  this.fit = true;
  this.zoom = undefined;
  this.cx = undefined;
  this.cy = undefined;
  var state = this.get_state();
  history.pushState(state, '');
  this.gallery_init();
  return false;
}
Photo.prototype.gallery_init = function() {
  open_gallery();
  obj_photo = this;
  if (this.e_photo) {
    this.display_photo();
  } else {
    this.e_photo = document.createElement('img');
    this.e_photo.onload = bind(this, this.fn_photo_loaded);
    this.e_photo.src = this.e_thumbnail.parentElement.href;
  }
}
Photo.prototype.fn_photo_loaded = function (event) {
  this.photo_x = this.e_photo.naturalWidth;
  this.photo_y = this.e_photo.naturalHeight;
  this.display_photo();
}
Photo.prototype.display_photo = function () {
  e_bg.appendChild(this.e_photo);
  this.redraw_photo();
}
Photo.prototype.click = function(touch) {
  var win_x = window.innerWidth;
  var win_y = window.innerHeight;
  var img_x = this.photo_x * this.zoom;
  var img_y = this.photo_y * this.zoom;
  var img_x0 = (win_x / 2) - (img_x * this.cx);
  var img_y0 = (win_y / 2) - (img_y * this.cy);
  var img_x1 = img_x0 + img_x;
  var img_y1 = img_y0 + img_y;
  console.log('click at: (', touch.x, ',', touch.y , '); photo in (',
              img_x0, ',', img_y0, '), (', img_x1, ',', img_y1, ')');
  if ((touch.x < img_x0) ||
      (touch.x >= img_x1) ||
      (touch.y < img_y0) ||
      (touch.y >= img_y1)) {
    return true;
  }
  if (((img_x == win_x) && (img_y <= win_y)) ||
      ((img_x <= win_x) && (img_y == win_y))) {
    this.zoom_to(1.0, touch, touch);
  } else {
    this.fit = true;
  }
  this.redraw_photo();
  return false;
}
Photo.prototype.zoom_to = function(new_zoom, old_pos, new_pos) {
  var win_x = window.innerWidth;
  var win_y = window.innerHeight;
  this.fit = false;
  var img_x = this.photo_x * this.zoom;
  var img_y = this.photo_y * this.zoom;
  var img_x0 = (win_x / 2) - (img_x * this.cx);
  var img_y0 = (win_y / 2) - (img_y * this.cy);
  var cpx = (old_pos.x - img_x0) / img_x;
  var cpy = (old_pos.y - img_y0) / img_y;
  this.zoom = new_zoom;
  var max_zoom = 3;
  if (this.zoom > max_zoom) {
    this.zoom = Math.max(max_zoom, this.window_zoom());
  }
  var min_zoom = Math.max(100 / this.photo_x, 100 / this.photo_y);
  if (this.zoom < min_zoom) {
    this.zoom = Math.min(min_zoom, this.window_zoom());
  }
  img_x = this.photo_x * this.zoom;
  img_y = this.photo_y * this.zoom;
  img_x0 = new_pos.x - (cpx * img_x);
  img_y0 = new_pos.y - (cpy * img_y);
  this.cx = ((win_x / 2) - img_x0) / img_x;
  this.cy = ((win_y / 2) - img_y0) / img_y;
  this.redraw_photo();
}
Photo.prototype.pinch = function(old_pinch, new_pinch) {
  if (!this.e_photo.complete) {
    return;
  }
  var zoom = this.zoom;
  if (old_pinch.distance != 0) {
    zoom *= new_pinch.distance / old_pinch.distance;
  } else {
  }
  this.zoom_to(zoom, old_pinch, new_pinch);
}
Photo.prototype.window_zoom = function() {
  var win_x = window.innerWidth;
  var win_y = window.innerHeight;
  return Math.min(win_x / this.photo_x, win_y / this.photo_y);
}
Photo.prototype.get_state = function() {
  return {
    'gallery': true,
    'i': this.i,
    'fit': this.fit,
    'zoom': this.zoom,
    'cx': this.cx,
    'cy': this.cy
  };
}
Photo.prototype.redraw_photo = function() {
  if (!this.e_photo.complete) {
    return;
  }
  var state = this.get_state();
  history.replaceState(state, '');
  var win_x = window.innerWidth;
  var win_y = window.innerHeight;
  if (this.fit) {
    this.zoom = this.window_zoom();
    this.cx = 0.5;
    this.cy = 0.5;
  }
  var img_x = this.photo_x * this.zoom;
  var img_y = this.photo_y * this.zoom;
  var img_x0 = (win_x / 2) - (img_x * this.cx);
  var img_y0 = (win_y / 2) - (img_y * this.cy);
  this.e_photo.style.width = img_x + 'px';
  this.e_photo.style.height = img_y + 'px';
  this.e_photo.style.marginLeft = img_x0 + 'px';
  this.e_photo.style.marginTop = img_y0 + 'px';
}
function fn_resize() {
  if (obj_photo) {
    obj_photo.redraw_photo();
  }
}
function fn_gallery_keydown(event) {
  if (obj_photo) {
    if (event.key == 'Escape') {
      history.back();
      return false;
    }
  }
  return true;
}
var e_thumbnail_list = document.getElementsByClassName('leaf-thumb')
for (var i = 0; i < e_thumbnail_list.length; i++) {
  var obj = new Photo(i, e_thumbnail_list[i])
  obj_photos.push(obj);
}
window.onresize = fn_resize;
window.onpopstate = fn_popstate;
window.onkeydown = fn_gallery_keydown;
fn_popstate(null);
