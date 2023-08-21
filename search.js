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
function get_url(page_info, anchor) {
  if (page_info.x == 'j') {
    var url = 'https://ucjeps.berkeley.edu/eflora/glossary.html';
  } else {
    var url = path + page_info.p + '.html';
    url = url.replace(/ /g, '-');
  }
  if (anchor) {
    url += '#' + anchor;
  }
  return encodeURI(url);
}
function get_class(page_info) {
  if (page_info.x == 'f') {
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
function check(search_str, match_str, pri_adj) {
  const s = search_str;
  const upper_str = match_str.toUpperCase()
  const m = upper_str.replace(/\W/g, '');
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
    if (((page_info.x == 'g') || (page_info.x == 'j')) &&
        !name.endsWith(' glossary')){
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
function text_search(search_str, type, text) {
  var match_info = check(search_str, text, 0);
  if (match_info) {
    var fit_info = {
      pri: match_info.pri,
      type: type,
      text: text,
      match_info: match_info
    };
    insert_match(fit_info);
  }
}
function page_search(search_str, page_info) {
  if (adv_search && ((page_info.x == 's') || (page_info.x == 'g') || (page_info.x == 'j'))) {
    return;
  }
  if ('c' in page_info) {
    var com_match_info = check_list(search_str, page_info.c, page_info);
  } else {
    var com_match_info = null;
  }
  if ('s' in page_info) {
    var sci_match_info = check_list(search_str, page_info.s, page_info);
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
      type: 'taxon',
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
      if ('c' in page_info) {
        var match_info = glossary_check_list(search_str, glossary,
                                             page_info.c, page_info);
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
          type: 'taxon',
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
function gen_ac_taxon_text(fit_info) {
  var page_info = fit_info.page_info;
  if ('c' in page_info) {
    const com = page_info.c[0];
    var com_highlight = highlight_match(fit_info.com_match_info,
                                        com, false);
    if ((page_info.x != 'g') && (page_info.x != 'j') &&
        fit_info.com_match_info &&
        (fit_info.com_match_info.match_str != com)) {
      com_highlight = (com +
                       ' <span class="altname">[' +
                       com_highlight +
                       ']</span>');
    }
  } else {
    var com_highlight = null;
  }
  if ('s' in page_info) {
    const sci = page_info.s[0];
    var sci_highlight = highlight_match(fit_info.sci_match_info,
                                        sci, true);
    if (fit_info.sci_match_info &&
        (fit_info.sci_match_info.match_str != sci)) {
      var sci_ital = highlight_match(null, sci, true);
      sci_highlight = (sci_ital +
                       ' <span class="altname">[' +
                       sci_highlight +
                       ']</span>');
    }
    sci_highlight = sci_highlight.replace(/:/, '&times; ');
  } else {
    var sci_highlight = null;
  }
  return compose_full_name(com_highlight, sci_highlight)
}
function fn_search(default_ac_selected) {
  var search_str = e_search_input.value.toUpperCase();
  ac_list = [];
  if (/\w/.test(search_str)) {
    if (adv_search) {
      for (var i = 0; i < traits.length; i++) {
        text_search(search_str, 'trait', traits[i]);
      }
    }
    for (var i = 0; i < pages.length; i++) {
      var page_info = pages[i];
      page_search(search_str, pages[i]);
    }
  } else if (adv_search && (term_id < term_list.length)) {
    var fit_info = {
      pri: 0,
      type: 'clear',
      text: 'remove this search term'
    };
    insert_match(fit_info);
  } else {
    hide_ac();
    return;
  }
  for (var i = 0; i < ac_list.length; i++) {
    var fit_info = ac_list[i];
    if (fit_info.type == 'taxon') {
      var text = gen_ac_taxon_text(fit_info);
      var c = get_class(fit_info.page_info);
    } else {
      if ('match_info' in fit_info) {
        var text = highlight_match(fit_info.match_info, fit_info.text, false);
      } else {
        var text = fit_info.text;
      }
      var c = 'unobs';
    }
    const p = '<p class="nogap">' + text + '</p>'
    if (adv_search) {
      fit_info.html = '<span class="autocomplete-entry" class="' + c + '" onclick="return fn_ac_click(' + i + ');">' + p + '</span>';
    } else {
      const url = get_url(page_info, fit_info.anchor);
      fit_info.html = '<a class="enclosed ' + c + '" href="' + url + '" onclick="return fn_ac_click();">' + p + '</a>';
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
function fn_ac_click(i) {
  if (adv_search) {
    confirm_adv_search(i);
    return false;
  } else {
    clear_search();
    return true;
  }
}
function fn_change() {
  fn_search(0);
}
function confirm_reg_search(event) {
  var fit_info = ac_list[ac_selected];
  var url = get_url(fit_info.page_info, fit_info.anchor);
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
var term_list = [];
var term_id = 0;
var zstr_len = 1;
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
  const num_zcodes = traits.length;
  while (num_zcodes > 93**zstr_len) {
    zstr_len++;
  }
  const zstr_to_trait = {}
  for (var i = 0; i < traits.length; i++) {
    zstr_to_trait[convert_zint_to_zstr(i)] = traits[i];
  }
  for (const page_info of pages) {
    page_info.trait_set = new Set();
    page_info.child_set = new Set();
    page_info.parent_set = new Set();
  }
  for (const page_info of pages) {
    if ('z' in page_info) {
      for (var i = 0; i < page_info.z.length; i += zstr_len) {
        const zstr = page_info.z.slice(i, i + zstr_len);
        page_info.trait_set.add(zstr_to_trait[zstr]);
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
  var fit_info = ac_list[i];
  if (fit_info.type == 'clear') {
    term_list.splice(term_id, 1);
  } else {
    const term_info = {
      search_str: e_search_input.value,
      ac_selected: i,
      type: fit_info.type
    };
    if (fit_info.type == 'trait') {
      term_info.trait = fit_info.text;
    } else {
      term_info.page_info = fit_info.page_info;
    }
    term_list.splice(term_id, 1, term_info);
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
  const term_info = term_list[term_id];
  const e_term = document.createElement('button');
  term_info.e_term = e_term;
  e_term.className = 'term';
  e_term.addEventListener('click', fn_term_click);
  if (term_info.type == 'trait') {
    var c = 'unobs';
    var full_name = term_info.trait;
    var prefix = 'with';
  } else {
    const page_info = term_info.page_info;
    var c = get_class(page_info);
    var full_name = compose_page_name(page_info, 1);
    var prefix = 'within';
  }
  const span = '<span class="' + c + '">' + full_name + '</span>';
  e_term.innerHTML = '<p>' + prefix + ' <b>' + span + '</b></p>';
  term_info.e_term = e_term;
  e_search_container.replaceWith(e_term);
}
function check_trait_term(trait, result_set) {
  for (const page_info of result_set) {
    if (!page_info.trait_set.has(trait)) {
      result_set.delete(page_info);
    }
  }
}
function add_descendents(term_result_set, page_info) {
  term_result_set.add(page_info);
  if ('d' in page_info) {
    for (const child_id of page_info.d) {
      const child_page_info = pages[child_id];
      add_descendents(term_result_set, child_page_info);
    }
  }
}
function within_taxon(page_info, target_info, in_tgt_map) {
  if (in_tgt_map.has(page_info)) {
    return in_tgt_map.get(page_info);
  } else if (page_info == target_info) {
    in_tgt_map.set(page_info, true);
    return true;
  } else {
    for (const parent_info of page_info.parent_set) {
      if (within_taxon(parent_info, target_info, in_tgt_map)) {
        in_tgt_map.set(page_info, true);
        return true;
      }
    }
    in_tgt_map.set(page_info, false);
    return false;
  }
}
function check_taxon_term(target_info, result_set) {
  var in_tgt_map = new Map();
  for (const page_info of result_set) {
    if (!within_taxon(page_info, target_info, in_tgt_map)) {
      result_set.delete(page_info);
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
  const result_set = new Set(pages);
  for (const term_info of term_list) {
    if (term_info.type == 'trait') {
      check_trait_term(term_info.trait, result_set);
    } else {
      check_taxon_term(term_info.page_info, result_set);
    }
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
