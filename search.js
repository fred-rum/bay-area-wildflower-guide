/* Copyright Chris Nelson - All rights reserved. */
'use strict';
var annotated_href_list = [];
function gallery_main() {
  const html_url = window.location.pathname;
  const matches = /(?:html\/)?[^\/]*\.html$/.exec(html_url);
  if (matches) {
    var prefix = window.location.origin + html_url.substr(0, matches.index);
  } else {
    var prefix = window.location.origin + html_url
    if (!prefix.endsWith('/')) {
      prefix += '/';
    }
  }
  const e_link_list = document.links
  for (var i = 0; i < e_link_list.length; i++) {
    const href = e_link_list[i].href;
    if (href.startsWith(prefix + 'photos/') ||
        href.startsWith(prefix + 'figures/')) {
      var suffix = decodeURI(href.substr(prefix.length));
      suffix = munge_photo_for_url(suffix);
      const suffix_query = encodeURIComponent(suffix);
      e_link_list[i].href = prefix + 'gallery.html?' + suffix;
    }
  }
}
function munge_photo_for_url(path) {
  var slash_pos = path.indexOf('/')
  if (slash_pos != -1) {
    path = path.substring(slash_pos+1);
  }
  var dot_pos = path.indexOf('.')
  if (dot_pos != -1) {
    path = path.substring(0, dot_pos);
  }
  path = path.replace(/[/ ,/]/g, function (c) {
    return {
      '/': '-',
      ' ': '-',
      ',': '.'
    }[c];
  });
  path = path.replace(/[^A-Za-z0-9-.]/g, '');
  return path;
}
gallery_main();
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
    fn_search(ac_selected);
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
var ac_list;
var ac_selected = 0;
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
  var regex = /[a-zA-Z0-9%#]/g;
  for (var i = 0; i <= n; i++) {
    regex.test(str);
  }
  if (regex.lastIndex == 0) {
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
function check(search_str, match_str, pri_adj = 0, def_num_list = []) {
  const s = search_str;
  const upper_str = match_str.toUpperCase()
  const m = upper_str.replace(/[^A-Z%#]/g, '');
  var name_pos = match_str.indexOf(' ');
  if ((name_pos < 0) ||
      (match_str.substr(0, 1) == upper_str.substr(0, 1)) ||
      (match_str.substr(name_pos+1, 1) != upper_str.substr(name_pos+1, 1))) {
    name_pos = 0;
  }
  const num_list = [];
  const num_start = [];
  const num_missing_digits = [];
  const re = /%#*/g;
  var idx = 0;
  while (true) {
    const match = re.exec(m);
    if (!match) break;
    num_list.push(def_num_list[idx]);
    num_start.push(match.index);
    num_missing_digits.push(match[0].length);
    idx++;
  }
  var match_ranges = [];
  var i = 0;
  var j = 0;
  while (true) {
    while (/[^A-Z0-9]/.test(s.substr(i, 1)) && (i < s.length)) {
      i++;
    }
    var start_i = i;
    if (i == s.length) {
      break;
    }
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
      var idx = 0;
      while (true) {
        if (idx == num_start.length) {
          return null;
        }
        if ((num_start[idx] >= j) &&
            (num_missing_digits[idx] >= s_word.length)) {
          break;
        }
        idx++;
      }
      j = num_start[idx] + num_missing_digits[idx];
      start_j = j - s_word.length;
      num_missing_digits[idx] -= s_word.length;
      const def_num = def_num_list[idx];
      if (def_num.length == 4) {
        var num = def_num.slice(0, -s_word.length) + s_word;
      } else {
        var num = s_word.padStart(2, '0');
      }
      num_list[idx] = num;
    } else {
      var start_j = m.indexOf(s_word, j);
      if (start_j == -1) {
        return null;
      }
      j = start_j + s_word.length;
    }
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
    match_ranges: match_ranges,
    num_list: num_list,
    num_start: num_start,
    num_missing_digits: num_missing_digits
  }
  return match_info;
}
function better_match(one, two) {
  return (one && (!two || (one.pri > two.pri)));
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
    var ranges = [];
    for (var i = 0; i < match_info.num_list.length; i++) {
      m = m.replace(/%#*/, match_info.num_list[i]);
      if (match_info.num_missing_digits[i]) {
        const mbegin = match_info.num_start[i];
        const mend = (match_info.num_start[i] +
                      match_info.num_missing_digits[i] - 1);
        const begin = find_letter_pos(m, mbegin);
        const end = find_letter_pos(m, mend) + 1;
        ranges.push([begin, end]);
      }
    }
    if (ranges.length) {
      const deemph_info = {
        ranges: ranges,
        i: 0,
        half: 0,
        tag: ['<span class="de-emph">', '</span>']
      };
      tag_info.push(deemph_info);
    }
  } else {
    var m = default_name;
  }
  const paren_pos = m.search(/\([^\)]*\)$/);
  if (paren_pos != -1) {
    const tag = match_info.num_list.length ? 'de-emph' : 'altname';
    const paren_info = {
      ranges: [[paren_pos, m.length]],
      i: 0,
      half: 0,
      tag: ['<span class="' + tag + '">', '</span>']
    };
    tag_info.push(paren_info);
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
      ranges[0][1] = pos;
      ranges.push([pos + 6, ranges[0][1]]);
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
function insert_match(term) {
  if ((ac_list.length < 10) || (term.pri > ac_list[9].pri)) {
    for (var j = 0; j < ac_list.length; j++) {
      if (term.pri > ac_list[j].pri) break;
    }
    ac_list.splice(j, 0, term);
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
class Term {
  is_clear = false;
  constructor() {
  }
}
class PageTerm extends Term {
  search_str;
  page_info;
  pri;
  com_match_info;
  sci_match_info;
  constructor(search_str, page_info) {
    super();
    this.search_str = search_str;
    this.page_info = page_info;
  }
  check_list(match_list) {
    const page_info = this.page_info;
    var best_match_info = null;
    var pri_adj = 0.0;
    for (var name of match_list) {
      var match_info = check(this.search_str, name, pri_adj);
      if (!match_info && name.startsWith('genus ')) {
        match_info = check(this.search_str, name.substr(6) + ' spp.', pri_adj);
      }
      if (better_match(match_info, best_match_info)) {
        best_match_info = match_info;
      }
      pri_adj = -0.01;
    }
    return best_match_info;
  }
  search() {
    const search_str = this.search_str;
    const page_info = this.page_info;
    if (adv_search && ((page_info.x == 's') || (page_info.x == 'g') || (page_info.x == 'j'))) {
      return;
    }
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
      if (better_match(com_match_info, sci_match_info)) {
        this.pri = com_match_info.pri;
      } else {
        this.pri = sci_match_info.pri;
      }
      this.com_match_info = com_match_info;
      this.sci_match_info = sci_match_info;
      insert_match(this);
    } else if ('glossary' in page_info) {
      for (const anchor_info of page_info.glossary) {
        const term = new AnchorTerm(search_str, page_info, anchor_info);
        term.search();
      }
    }
  }
  highlight_name(match_info, name, is_sci) {
    if (!match_info ||
        (match_info.match_str == name) ||
        'gj'.includes(this.page_info.x)) {
      return highlight_match(match_info, name, is_sci);
    } else {
      const name_highlight = highlight_match(null, name, is_sci);
      const match_highlight = highlight_match(match_info, null, is_sci);
      return (name_highlight +
              ' <span class="altname">[' + match_highlight + ']</span>');
    }
  }
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
  get_url() {
    return get_url(this.page_info);
  }
  prefix() {
    return 'within';
  }
  get_search_term_text() {
    const page_info = this.page_info;
    return compose_page_name(page_info, 1);
  }
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
        result_set.delete(this.page_info);
      }
    }
  }
}
class AnchorTerm extends PageTerm {
  anchor_info;
  match_info;
  constructor(search_str, page_info, anchor_info) {
    super(search_str, page_info);
    this.anchor_info = anchor_info;
  }
  check_list() {
    var best_match_info = null;
    const pri_adj = 0.0;
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
}
function fn_search(default_ac_selected) {
  var search_str = e_search_input.value.toUpperCase();
  ac_list = [];
  if (/\w/.test(search_str)) {
    if (adv_search) {
      for (const trait of traits) {
        const term = new TraitTerm(search_str, trait);
        term.search();
      }
      for (const park of parks) {
        const term = new ParkTerm(search_str, park);
        term.search();
      }
      var term = new BeforeYMDTerm(search_str);
      term.search();
      var term = new InYTerm(search_str);
      term.search();
    }
    for (const page_info of pages) {
      const term = new PageTerm(search_str, page_info);
      term.search();
    }
  } else if (adv_search && (term_id < term_list.length)) {
    new ClearTerm();
  } else {
    hide_ac();
    return;
  }
  for (var i = 0; i < ac_list.length; i++) {
    const term = ac_list[i];
    const text = term.get_ac_text();
    const c = term.get_class();
    const p = '<p class="nogap">' + text + '</p>'
    if (adv_search) {
      term.html = '<span class="autocomplete-entry" class="' + c + '" onclick="return fn_adv_ac_click(' + i + ');">' + p + '</span>';
    } else {
      const url = term.get_url();
      term.html = '<a class="enclosed ' + c + '" href="' + url + '" onclick="return fn_ac_click();">' + p + '</a>';
    }
  }
  if (default_ac_selected < ac_list.length) {
    ac_selected = default_ac_selected;
  } else {
    ac_selected = 0;
  }
  generate_ac_html();
  expose_ac();
}
function fn_ac_click() {
  clear_search();
  return true;
}
function fn_adv_ac_click(i) {
  confirm_adv_search(i);
  return false;
}
function fn_change() {
  fn_search(0);
}
function confirm_reg_search(event) {
  var term = ac_list[ac_selected];
  var url = term.get_url();
  if (event.shiftKey || event.ctrlKey) {
    window.open(url);
  } else {
    window.location.href = url;
  }
  clear_search();
}
function fn_keydown() {
  if ((event.key == 'Enter') && !ac_is_hidden && ac_list.length) {
    if (adv_search) {
      confirm_adv_search(ac_selected);
    } else {
      confirm_reg_search(event);
    }
  } else if (event.key == 'Escape') {
    if (adv_search && (term_id < term_list.length)){
      restore_term();
      confirm_adv_search(ac_selected);
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
window.addEventListener('click', fn_doc_click);
window.addEventListener('pageshow', fn_pageshow);
function fn_hashchange(event) {
  hide_ac();
  var title_list = document.title.split(' - ');
  var title = title_list[title_list.length - 1];
  var hash = location.hash;
  if (hash && (hash != '#offline')) {
    document.title = decodeURIComponent(hash).substring(1) + ' - ' + title;
  }
}
const term_list = [];
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
function init_adv_search() {
  const num_zcodes = traits.length + trips.length;
  while (num_zcodes > 93**zstr_len) {
    zstr_len++;
  }
  const zstr_to_trait = {}
  for (var i = 0; i < traits.length; i++) {
    const zstr = convert_zint_to_zstr(i);
    zstr_to_trait[zstr] = traits[i];
  }
  const zstr_to_trip = {}
  for (var i = 0; i < trips.length; i++) {
    const trip = trips[i];
    const zstr = convert_zint_to_zstr(traits.length + i);
    zstr_to_trip[zstr] = trip;
    parks.add(trip[1]);
  }
  for (const page_info of pages) {
    page_info.trait_set = new Set();
    page_info.trip_set = new Set();
    page_info.child_set = new Set();
    page_info.parent_set = new Set();
  }
  for (const page_info of pages) {
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
    if ('d' in page_info) {
      for (const child_id of page_info.d) {
        const child_info = pages[child_id];
        page_info.child_set.add(child_info);
        child_info.parent_set.add(page_info);
      }
    }
  }
  for (const trip of trips) {
    const date_str = trip[0];
    const date = new Date(date_str);
    trip.push(date);
  }
}
function fn_term_click(event) {
  apply_term();
  for (var i = 0; i < term_list.length; i++) {
    if (term_list[i].e_term == event.currentTarget) break;
  }
  term_id = i;
  var term_info = term_list[term_id];
  term_info.e_term.replaceWith(e_search_container);
  e_search_input.focus();
  restore_term();
  generate_ac_html();
  event.stopPropagation();
}
function restore_term() {
  const term_info = term_list[term_id];
  e_search_input.value = term_info.search_str;
  fn_search(term_info.ac_selected);
}
function confirm_adv_search(i) {
  var term = ac_list[i];
  term.search_str = e_search_input.value;
  if (term.is_clear) {
    term_list.splice(term_id, 1);
  } else {
    term.ac_selected = i;
    term_list.splice(term_id, 1, term);
    apply_term();
  }
  clear_search();
  term_id = term_list.length;
  if (term_id == 0) {
    e_terms.insertAdjacentElement('afterbegin', e_search_container);
  } else {
    const prev_e_term = term_list[term_id-1].e_term;
    prev_e_term.insertAdjacentElement('afterend', e_search_container);
  }
  e_search_input.focus();
  gen_adv_search_results();
}
function apply_term() {
  if (term_id == term_list.length) {
    return;
  }
  const term = term_list[term_id];
  const e_term = document.createElement('button');
  term.e_term = e_term;
  e_term.className = 'term';
  e_term.addEventListener('click', fn_term_click);
  const c = term.get_class();
  const prefix = term.prefix();
  const term_name = term.get_search_term_text();
  const span = '<span class="' + c + '">' + term_name + '</span>';
  e_term.innerHTML = '<p>' + prefix + ' <b>' + span + '</b></p>';
  term.e_term = e_term;
  e_search_container.replaceWith(e_term);
}
class ClearTerm extends Term {
  pri;
  is_clear = true;
  constructor() {
    super();
    this.pri = 0.0;
    insert_match(this);
  }
  get_ac_text() {
    return 'remove this search term';
  }
  get_class() {
    return 'unobs';
  }
}
class TextTerm extends Term {
  search_str;
  pri;
  match_info;
  constructor(search_str, match_str, def_num_list = []) {
    super();
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
  get_search_term_text() {
    var term_name = this.match_info.match_str;
    for (const num of this.match_info.num_list) {
      term_name = term_name.replace(/%#*/, num);
    }
    return term_name;
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
    this.init_matching_trips();
    for (const page_info of result_set) {
      if (!(page_to_trip.has(page_info))) {
        page_to_trip[page_info] = new Set(page_info.trip_set);
      }
      const trip_result_set = page_to_trip[page_info];
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
class DateTerm extends TripTerm {
  compare_dates(op, date1, date2) {
     if (op == '<') {
       return date1 < date2;
     } else if (op == '<=') {
       return date1 <= date2;
     } else if (op == '>=') {
       return date1 >= date2;
     } else if (op == '>') {
       return date1 > date2;
     } else {
       return date1 == date2;
     }
  }
  prefix() {
    return 'observed';
  }
}
function digits(num, len) {
  return String(num).padStart(len, '0');
}
class BeforeYMDTerm extends DateTerm {
  constructor(search_str) {
    const now = new Date();
    const year = digits(now.getFullYear(), 4);
    const month = digits(now.getMonth() + 1, 2);
    const day = digits(now.getDay(), 2);
    super(search_str, 'before %###-%#-%# (exclusive)', [year, month, day]);
  }
  init_matching_trips() {
    const tgt_year = Number(this.match_info.num_list[0]);
    const tgt_month = Number(this.match_info.num_list[1]);
    const tgt_day = Number(this.match_info.num_list[2]);
    const tgt_date = new Date(tgt_year + '-' + tgt_month + '-' + tgt_day);
    const tgt_time = tgt_date.getTime();
    for (const trip of trips) {
      const date = trip[2];
      const time = date.getTime();
      if (time < tgt_time) {
        this.matching_trips.add(trip);
      }
    }
  }
}
class InYTerm extends DateTerm {
  constructor(search_str) {
    const now = new Date();
    const year = digits(now.getFullYear(), 4);
    super(search_str, 'in %###', [year]);
  }
  init_matching_trips() {
    const tgt_year = Number(this.match_info.num_list[0]);
    for (const trip of trips) {
      const date = trip[2];
      const year = date.getUTCFullYear();
      if (year == tgt_year) {
        this.matching_trips.add(trip);
      }
    }
  }
}
function delete_ancestors(page_info, result_set, checked_set) {
  for (const parent_info of page_info.parent_set) {
    if (checked_set.has(parent_info)) {
    } else {
      if (result_set.has(parent_info)) {
        result_set.delete(parent_info);
      }
      checked_set.add(parent_info);
      delete_ancestors(parent_info, result_set, checked_set);
    }
  }
}
function gen_adv_search_results() {
  if (term_list.length == 0) {
    e_results.innerHTML = '<p>...</p>';
    return;
  }
  const result_set = new Set(pages.filter((x) => !'sgj'.includes(x.x)));
  const page_to_trip = new Map();
  for (const term of term_list) {
    term.match(result_set, page_to_trip);
  }
  const checked_set = new Set();
  for (const page_info of result_set) {
    delete_ancestors(page_info, result_set, checked_set);
  }
  const list = [];
  for (const page_info of result_set) {
    const c = get_class(page_info);
    const url = get_url(page_info, null);
    list.push('<div class="list-box">');
    if ('j' in page_info) {
      var jpg = String(page_info.j);
      const comma_pos = jpg.search(',');
      if (comma_pos == -1) {
        jpg = page_info.p + ',' + jpg;
      }
      var jpg_url = 'thumbs/' + jpg + '.jpg';
      list.push('<a href="' + url + '">');
      list.push('<div class="list-thumb">');
      list.push('<img class="boxed" src="' + jpg_url + '" alt="photo">');
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
if (/\/html\/[^\/]*$/.test(window.location.pathname)) {
  var path = '';
} else {
  var path = 'html/';
}
function main() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
    return
  }
  e_home_icon = document.getElementById('home-icon');
  e_terms = document.getElementById('terms');
  e_search_container = document.getElementById('search-container');
  e_search_input = document.getElementById('search');
  e_autocomplete_box = document.getElementById('autocomplete-box');
  e_results = document.getElementById('results');
  adv_search = Boolean(e_results)
  e_search_input.className = 'search';
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
  if (adv_search) {
    init_adv_search();
  }
  e_search_input.addEventListener('input', fn_change);
  e_search_input.addEventListener('keydown', fn_keydown);
  e_search_input.addEventListener('focusin', fn_focusin);
  fn_hashchange();
  window.addEventListener('hashchange', fn_hashchange);
  if (Document.activeElement == e_search_input) {
    fn_search(0);
  }
  gallery_main();
}
if (typeof pages !== 'undefined') {
  main();
}
