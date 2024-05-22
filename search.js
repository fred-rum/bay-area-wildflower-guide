/* Copyright Chris Nelson - All rights reserved. */
'use strict';
const html_url = window.location.pathname;
var root_path = window.location.origin;
if (root_path == 'null') {
  root_path = 'file://';
}
const match_pos = html_url.search(/(?:html\/)?[^\/]*\.html$/);
if (match_pos != -1) {
  root_path += html_url.substring(0, match_pos);
} else {
  root_path += html_url
  if (!root_path.endsWith('/')) {
    root_path += '/';
  }
}
var annotated_href_list = [];
function gallery_main() {
  const e_link_list = document.links
  for (var i = 0; i < e_link_list.length; i++) {
    const href = e_link_list[i].href;
    if (href.startsWith(root_path + 'photos/') ||
        href.startsWith(root_path + 'figures/')) {
      var suffix = decodeURI(href.substr(root_path.length));
      suffix = munge_photo_for_url(suffix);
      const suffix_query = encodeURIComponent(suffix);
      e_link_list[i].href = root_path + 'gallery.html?' + suffix;
    }
  }
}
function munge_photo_for_url(path) {
  var slash_pos = path.indexOf('/')
  if (slash_pos != -1) {
    path = path.substring(slash_pos+1);
  }
  var dot_pos = path.lastIndexOf('.')
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
function term_changed(care_ac, ac_selected) {
  return ((term_id == term_list.length) ||
          (e_search_input.value != term_list[term_id].search_str) ||
          (care_ac && (ac_selected != term_list[term_id].ac_selected)));
}
function fn_doc_click(event) {
  var search_element = event.target.closest('#search-container');
  if (!search_element) {
    if (adv_search && !term_changed(false, 0)) {
      confirm_adv_search_term(term_list[term_id].ac_selected);
      prepare_new_adv_input();
    } else {
      hide_ac();
    }
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
function canonical_case(name) {
  name = name.normalize('NFD');
  name = name.replace(/[\u0300-\u036f]/g, '');
  return name.toUpperCase();
}
function find_letter_start(str, n) {
  const regex = /[a-zA-Z0-9@#]/g;
  for (var i = 0; i <= n; i++) {
    regex.test(str);
    if (regex.lastIndex == 0) {
      return str.length;
    }
}
  return regex.lastIndex - 1;
}
function find_letter_end(str, n) {
  const pos = find_letter_start(str, n) + 1;
  const regex = /^[\u0300-\u036f]*/;
  regex.test(str.substring(pos));
  return pos + regex.lastIndex;
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
function check(search_str, prefix, match_str, pri_adj = 0, def_num_list = []) {
  const s = search_str;
  const upper_no_pfx = canonical_case(match_str);
  var name_pos = match_str.indexOf(' ');
  if ((name_pos < 0) ||
      (match_str.substr(0, 1) == upper_no_pfx.substr(0, 1)) ||
      (match_str.substr(name_pos+1, 1) != upper_no_pfx.substr(name_pos+1, 1))) {
    name_pos = 0;
  }
  const orig_match_str = match_str;
  if (prefix) {
    match_str = prefix + ' ' + match_str;
    var prefix_len = prefix.replace(/[^A-Za-z]/g, '').length;
  }
  const upper_str = canonical_case(match_str);
  const m = upper_str.replace(/[^A-Z@#]/g, '');
  const num_list = [];
  const num_start = [];
  const num_missing_digits = [];
  const re = /@#*/g;
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
        const digits_replaced = def_num.slice(-s_word.length);
        var digits_padding = def_num.slice(0, -s_word.length);
        const padding_len = digits_padding.length;
        if (padding_len && (s_word > digits_replaced)) {
          digits_padding = String(Number(digits_padding) - 1);
          digits_padding = digits_padding.padStart(padding_len, '0');
        }
        var num = digits_padding + s_word;
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
  if (prefix && (match_ranges[0][0] >= prefix_len)) {
    match_str = orig_match_str;
    for (const range_pair of match_ranges) {
      range_pair[0] -= prefix_len;
      range_pair[1] -= prefix_len;
    }
    for (var i = 0; i < num_start.length; i++) {
      num_start[i] -= prefix_len;
    }
    var allow_name_match = true;
  } else {
    var allow_name_match = !prefix;
  }
  if ((match_ranges[0][0] == 0) ||
      ((match_ranges[0][0] == name_pos) && allow_name_match)) {
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
class Tag {
  tag_text;
  ranges = [];
  i = 0;
  half = 0;
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
function highlight_match(match_info, default_name, is_sci, tag_list = []) {
  var h = '';
  if (match_info && match_info.match_ranges.length) {
    var m = match_info.match_str.normalize('NFD');
    var match_ranges = match_info.match_ranges;
    var tag = new Tag('<span class="match">', '</span>');
    for (const range of match_ranges) {
      var begin = find_letter_start(m, range[0]);
      var end = find_letter_end(m, range[1] - 1);
      tag.add_range(begin, end);
    }
    tag_list.push(tag);
    if (match_info.num_list.length) {
      var tag = new Tag('<span class="de-emph">', '</span>');
      for (var i = 0; i < match_info.num_list.length; i++) {
        m = m.replace(/@#*/, match_info.num_list[i]);
        if (match_info.num_missing_digits[i]) {
          const mbegin = match_info.num_start[i];
          const mend = (match_info.num_start[i] +
                        match_info.num_missing_digits[i] - 1);
          const begin = find_letter_start(m, mbegin);
          const end = find_letter_end(m, mend);
          tag.add_range(begin, end);
        }
      }
      if (!tag.is_done()) {
        tag_list.push(tag);
      }
    }
  } else {
    var m = default_name;
  }
  const paren_pos = m.search(/\([^\)]*\)$/);
  if (paren_pos != -1) {
    const c = match_info.num_list.length ? 'de-emph' : 'altname';
    var tag = new Tag('<span class="' + c + '">', '</span>');
    tag.add_range(paren_pos, m.length);
    tag_list.push(tag);
  }
  if (is_sci) {
    var tag = new Tag('<i>', '</i>');
    var range = [0, m.length];
    if (m.endsWith(' spp.')) {
      range[1] -= 5;
    }
    var pos = m.search(/ ssp\. | var\. /);
    if (pos != -1) {
      range[1] = pos;
      tag.add_range(range[0], range[1]);
      range = [pos + 6, m.length];
    }
    if (!startsUpper(m)) {
      range[0] = m.indexOf(' ');
    }
    tag.add_range(range[0], range[1]);
    tag_list.push(tag);
  }
  var nest = [];
  var pos = 0;
  while (tag_list.length) {
    var tag_idx = 0;
    var tag = tag_list[0];
    for (var j = 1; j < tag_list.length; j++) {
      var tagj = tag_list[j];
      if ((tagj.get_next_pos() < tag.get_next_pos()) ||
                   ((tagj.get_next_pos() == tag.get_next_pos()) &&
                    (tagj.is_open() ?
                     (!tag.is_open() ||
                      (tagj.get_open_pos() >= tag.get_open_pos())) :
                     (!tag.is_open() &&
                      (tagj.get_close_pos() > tag.get_close_pos()))))) {
        tag_idx = j;
        tag = tagj;
      }
    }
    var next_pos = tag.get_next_pos();
    var s = m.substring(pos, next_pos);
    h += s;
    pos = next_pos;
    if (!tag.is_open()) {
      h += tag.open();
      nest.push(tag);
    } else {
      for (i = nest.length-1; nest[i] != tag; i--) {
        h += nest[i].close();
      }
      h += nest[i].close();
      nest.splice(i, 1);
      for (i = i; i < nest.length; i++) {
        h += nest[i].open();
      }
    }
    tag.advance();
    if (tag.is_done()) {
      tag_list.splice(tag_idx, 1);
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
  group;
  e_term;
  constructor(group) {
    this.group = group;
  }
  get_url() {
    const query = cvt_name_to_query(this.get_canonical_name());
    return root_path + 'advanced-search.html?' + query;
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
        break;
      }
    }
    term_list.splice(id, 0, this);
    if (id == 0) {
      e_terms.insertAdjacentElement('afterbegin', this.e_term);
    } else {
      const prev_e_term = term_list[id-1].e_term;
      prev_e_term.insertAdjacentElement('afterend', this.e_term);
    }
  }
}
function better_match(one, two) {
  return (one && (!two || (one.pri > two.pri)));
}
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
  check_list(match_list) {
    const page_info = this.page_info;
    var best_match_info = null;
    var pri_adj = 0.0;
    for (var name of match_list) {
      var match_info = check(this.search_str, this.prefix(), name, pri_adj);
      if (!match_info && name.startsWith('genus ')) {
        const spp_name = name.substr(6) + ' spp.';
        match_info = check(this.search_str, this.prefix(), spp_name, pri_adj);
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
    if (adv_search && ('sgj'.includes(page_info.x))) {
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
        const term = new AnchorTerm(this.group, search_str,
                                    page_info, anchor_info);
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
    const prefix = this.prefix();
    if (prefix) {
      var prefix_len = prefix_len = (prefix.replace(/[^A-Za-z]/g, '')).length;
    } else {
      prefix_len = 0;
    }
    let com_prefixed = (this.com_match_info &&
                        this.com_match_info.match_str.startsWith(prefix));
    let sci_prefixed = (this.sci_match_info &&
                        this.sci_match_info.match_str.startsWith(prefix));
    let prefix_differs = (com_prefixed != sci_prefixed);
    if (com_prefixed && sci_prefixed) {
      for (let i = 0; i < this.com_match_info.match_ranges.length; i++) {
        if ((this.com_match_info.match_ranges[i][0] >= prefix_len) &&
            (this.sci_match_info.match_ranges[i][0] >= prefix_len)) {
          break;
        }
        if (this.com_match_info.match_ranges[i][0] !=
            this.sci_match_info.match_ranges[i][0]) {
          prefix_differs = true;
          break;
        }
        if ((this.com_match_info.match_ranges[i][1] >= prefix_len) &&
            (this.sci_match_info.match_ranges[i][1] >= prefix_len)) {
          break;
        }
        if ((this.com_match_info.match_ranges[i][1] >= prefix_len) ||
            (this.sci_match_info.match_ranges[i][1] >= prefix_len)) {
          prefix_differs = true;
          break;
        }
      }
    }
    if (this.com_match_info && (this.com_match_info.pri == this.pri) &&
        prefix_differs) {
      this.sci_match_info = null;
      sci_prefixed = false;
    } else if (this.sci_match_info && (this.sci_match_info.pri == this.pri) &&
               prefix_differs) {
      this.com_match_info = null;
      com_prefixed = false;
    }
    this.prefixed = com_prefixed || sci_prefixed;
    function separate_prefix_info(prefix, match_info) {
      const pfx_ranges = [];
      const pfx_len_w_punct = prefix.length + 1;
      match_info.match_str = match_info.match_str.substring(pfx_len_w_punct);
      var match_ranges = match_info.match_ranges;
      for (var i = 0; i < match_ranges.length; i++) {
        if (match_ranges[i][0] < prefix_len) {
          if (match_ranges[i][1] <= prefix_len) {
            pfx_ranges.push(match_ranges[i]);
          } else {
            pfx_ranges.push([match_ranges[i][0], prefix_len]);
            break;
          }
        } else {
          break;
        }
      }
      match_ranges = match_ranges.slice(i);
      for (const range_pair of match_ranges) {
        if (range_pair[0] < prefix_len) {
          range_pair[0] = 0;
        } else {
          range_pair[0] -= prefix_len;
        }
        range_pair[1] -= prefix_len;
      }
      match_info.match_ranges = match_ranges;
      for (var i = 0; i < match_info.num_start.length; i++) {
        match_info.num_start[i] -= prefix_len;
      }
      return {
        match_str: prefix,
        match_ranges: pfx_ranges,
        num_list: [],
        num_start: [],
        num_missing_digits: []
      };
    }
    var pfx_info = null;
    if (com_prefixed) {
      pfx_info = separate_prefix_info(this.prefix(), this.com_match_info);
    }
    if (sci_prefixed) {
      pfx_info = separate_prefix_info(this.prefix(), this.sci_match_info);
    }
    var pfx_highlight = '';
    if (pfx_info) {
      pfx_highlight = highlight_match(pfx_info, null, false);
      const last_pfx_range_idx = pfx_info.match_ranges.length - 1;
      const last_pfx_range = pfx_info.match_ranges[last_pfx_range_idx];
      const incl_com = (('c' in page_info) &&
                        (this.com_match_info || page_info.c[0]));
      if ((last_pfx_range[1] == prefix_len) &&
          (incl_com ?
           (this.com_match_info &&
            (this.com_match_info.match_str == page_info.c[0]) &&
            this.com_match_info.match_ranges.length &&
            this.com_match_info.match_ranges[0][0] == 0) :
           (this.sci_match_info &&
            (this.sci_match_info.match_str == page_info.s[0]) &&
            this.sci_match_info.match_ranges.length &&
            this.sci_match_info.match_ranges[0][0] == 0))) {
        const pos = pfx_highlight.length - '</span>'.length;
        pfx_highlight = pfx_highlight.substring(0, pos) + ' </span>';
      } else {
        pfx_highlight += ' ';
      }
      pfx_highlight = '<span class="unobs altname">' + pfx_highlight + '</span>';
    }
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
    var h = pfx_highlight + compose_full_name(com_highlight, sci_highlight);
    return h.replace(/%/, '&times; ');
  }
  get_class() {
    return get_class(this.page_info);
  }
  get_url() {
    if (this.prefixed) {
      return super.get_url();
    } else {
      return get_url(this.page_info);
    }
  }
  prefix() {
    if ('gj'.includes(this.page_info.x)) {
      return null;
    } else if (this.page_info.x == 's') {
      const trait = this.page_info.c[0];
      return trait_info.get(trait).prefix;
    } else {
      return 'within';
    }
  }
  get_text() {
    const page_info = this.page_info;
    return compose_page_name(page_info, 1);
  }
  get_canonical_name() {
    const page_info = this.page_info;;
    if ('s' in page_info) {
      return page_info.s[0];
    } else {
      return page_info.c[0];
    }
  }
  get_human_name() {
    const page_info = this.page_info;;
    if ('c' in page_info) {
      return page_info.c[0];
    } else {
      return page_info.s[0];
    }
  }
  within_taxon(page_info) {
    if (this.in_tgt_map.has(page_info)) {
      return this.in_tgt_map.get(page_info);
    } else if (page_info == this.page_info) {
      this.in_tgt_map.set(page_info, true);
      return true;
    } else {
      for (const parent_info of page_info.parent_set) {
        if (this.within_taxon(parent_info, this.in_tgt_map)) {
          this.in_tgt_map.set(page_info, true);
          return true;
        }
      }
      this.in_tgt_map.set(page_info, false);
      return false;
    }
  }
  result_init() {
    this.in_tgt_map = new Map();
  }
  result_match(page_info, past_trip_set, current_trip_set) {
    if (this.within_taxon(page_info)) {
      for (const trip of past_trip_set) {
        past_trip_set.delete(trip);
        current_trip_set.add(trip);
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
    const pri_adj = 0.0;
    for (const page_name of this.page_info.c) {
      for (const glossary_term of this.anchor_info.terms) {
        const term_str = glossary_term + ' (' + page_name + ')';
        const match_info = check(this.search_str, null, term_str, pri_adj);
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
  var search_str = canonical_case(e_search_input.value);
  ac_list = [];
  if (/\w/.test(search_str)) {
    add_adv_terms(search_str);
    for (const page_info of pages) {
      const term = new PageTerm(0, search_str, page_info);
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
      term.html = '<span class="autocomplete-entry ' + c + '" onclick="return fn_adv_ac_click(' + i + ');">' + p + '</span>';
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
  let changed = term_changed(true, i);
  confirm_adv_search_term(i);
  prepare_new_adv_input();
  if (changed) {
    save_state();
    gen_adv_search_results();
  }
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
      let changed = term_changed(true, ac_selected);
      confirm_adv_search_term(ac_selected);
      prepare_new_adv_input();
      if (changed) {
        save_state();
        gen_adv_search_results();
      }
    } else {
      confirm_reg_search(event);
    }
  } else if (event.key == 'Escape') {
    if (adv_search && (term_id < term_list.length)){
      revert_adv_search_term();
      term_id = term_list.length;
      prepare_new_adv_input();
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
var cnt_list;
const term_list = [];
var term_id = 0;
var zstr_len = 1;
const trait_info = new Map();
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
function init_traits() {
  for (const [i, trait_group] of traits.entries()) {
    for (const trait_name of trait_group[1]) {
      const info = {
        group: i + 1,
        prefix: trait_group[0],
        is_subset: false,
      };
      trait_info.set(trait_name, info);
    }
  }
  if (!adv_search) {
    for (const page_info of pages) {
      if (page_info.c) {
        const name = page_info.c[0];
        if (trait_info.has(name)) {
          const info = trait_info.get(name);
          info.is_subset = true;
        }
      }
    }
  }
}
function init_parks() {
  for (const trip of trips) {
    parks.add(trip[1]);
  }
}
function init_adv_search() {
  const num_zcodes = trait_info.size + trips.length;
  while (num_zcodes > 93**zstr_len) {
    zstr_len++;
  }
  var i = 0;
  const zstr_to_trait = {}
  for (const trait_name of trait_info.keys()) {
    const zstr = convert_zint_to_zstr(i);
    zstr_to_trait[zstr] = trait_name;
    i++;
  }
  const zstr_to_trip = {}
  for (const trip of trips) {
    const zstr = convert_zint_to_zstr(i);
    zstr_to_trip[zstr] = trip;
    i++;
  }
  for (const page_info of pages) {
    page_info.trait_set = new Set();
    page_info.trip_set = new Set();
    page_info.child_set = new Set();
    page_info.parent_set = new Set();
  }
  for (const page_info of pages) {
    if ('z' in page_info) {
      for (i = 0; i < page_info.z.length; i += zstr_len) {
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
  window.addEventListener("popstate", restore_state);
}
function digits(num, len) {
  return String(num).padStart(len, '0');
}
function add_adv_terms(search_str) {
  var group = 1;
  for (const [name, info] of trait_info) {
    if (adv_search || !info.is_subset) {
      const term = new TraitTerm(info.group, search_str, name);
      term.search();
      group = Math.max(group, info.group);
    }
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
function fn_term_click(event) {
  if (term_id < term_list.length) {
    revert_adv_search_term();
  }
  const tgt = event.currentTarget;
  for (term_id = 0; term_list[term_id].e_term != tgt; term_id++) {}
  const term = term_list[term_id];
  term.e_term.replaceWith(e_search_container);
  restore_term(term_list[term_id].search_str, term_list[term_id].ac_selected);
  e_search_input.focus();
  e_search_input.select();
  generate_ac_html();
  event.stopPropagation();
}
function cvt_name_to_query(name) {
  name = name.replace(/[^A-Za-z0-9]*(\([^\)]*\))?$/, '');
  name = name.replace(/[^A-Za-z0-9]+/g, '-');
  return name;
}
function set_title() {
  if (term_list.length) {
    var term_names = [];
    for (const term of term_list) {
      const name = term.get_human_name();
      const q = name.replace(/[^A-Za-z0-9]*(\([^\)]*\))?$/, '');
      term_names.push(q);
    }
    document.title = '? ' + term_names.join(', ');
  } else {
    document.title = 'Advanced Search'
  }
}
function save_state() {
  var term_names = [];
  for (const term of term_list) {
    const name = term.get_canonical_name();
    const q = cvt_name_to_query(name);
    term_names.push(q);
  }
  const query = term_names.join('.');
  const url = window.location.pathname + '?' + query;
  history.pushState(null, '', url);
  set_title();
}
function restore_state(query) {
  for (var i = 0; i < term_list.length; i++) {
    term_list[i].e_term.remove();
  }
  term_list.length = 0;
  term_id = 0;
  var query = window.location.search;
  if (!query) return;
  query = query.substring(1);
  for (var name of query.split('.')) {
    name = name.replace(/(?<!\d)-|-(?!\d)/g, ' ');
    restore_term(name, 0);
    if (ac_list.length != 0) {
      confirm_adv_search_term(0);
    }
  }
  clear_search();
  gen_adv_search_results();
}
function restore_term(search_str, ac_selected) {
  e_search_input.value = search_str;
  fn_search(ac_selected);
}
function confirm_adv_search_term(ac_selected) {
  const term = ac_list[ac_selected];
  term.search_str = e_search_input.value;
  term.ac_selected = ac_selected;
  term.gen_html_element();
  if ((term_id < term_list.length) &&
      (term.group == term_list[term_id].group)) {
    term_list[term_id] = term;
    revert_adv_search_term();
  } else {
    term_list.splice(term_id, 1);
    term.insert_html_element();
  }
  term_id = term_list.length;
}
function revert_adv_search_term() {
  const term = term_list[term_id];
  e_search_container.insertAdjacentElement('beforeBegin', term.e_term);
}
function prepare_new_adv_input() {
  clear_search();
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
    super(null);
    this.pri = 0.0;
    insert_match(this);
  }
  get_ac_text() {
    return 'remove this search term';
  }
  get_class() {
    return 'unobs';
  }
  gen_html_element() {
  }
  insert_html_element() {
  }
}
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
    const match_info = check(this.search_str, this.prefix(), this.match_str, 0,
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
    if (this.match_info.match_str.startsWith(this.prefix())) {
      const tag = new Tag('<span class="altname">', '</span>');
      tag.add_range(0, this.prefix().length);
      return highlight_match(this.match_info, null, false, [tag]);
    } else {
      return highlight_match(this.match_info, null, false);
    }
  }
  get_class() {
    return 'unobs';
  }
  get_text() {
    var term_name = this.match_info.match_str;
    for (const num of this.match_info.num_list) {
      term_name = term_name.replace(/@#*/, num);
    }
    if (term_name.startsWith(this.prefix())) {
      term_name = term_name.substring(this.prefix().length + 1);
    }
    return term_name;
  }
  get_canonical_name() {
    return this.get_text();
  }
  get_human_name() {
    return this.get_text();
  }
}
class TraitTerm extends TextTerm {
  result_init() {
  }
  result_match(page_info, past_trip_set, current_trip_set) {
    const trait = this.match_str;
    if (page_info.trait_set.has(trait)) {
      for (const trip of past_trip_set) {
        past_trip_set.delete(trip);
        current_trip_set.add(trip);
      }
    }
  }
  prefix() {
    const trait = this.match_str;
    return trait_info.get(trait).prefix;
  }
}
class TripTerm extends TextTerm {
  result_match(page_info, past_trip_set, current_trip_set) {
    for (const trip of past_trip_set) {
      if (this.matching_trips.has(trip)) {
        past_trip_set.delete(trip);
        current_trip_set.add(trip);
      }
    }
  }
}
class ParkTerm extends TripTerm {
  result_init() {
    this.matching_trips = new Set();
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
  prefix() {
    return 'observed';
  }
  result_init() {
    this.matching_trips = new Set();
    this.init_matching_trips();
  }
}
class InYTerm extends DateTerm {
  constructor(group, search_str, dy) {
    super(group, search_str, 'in @###', [dy]);
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
    super(group, search_str, 'in @###-@#', [dy, dm]);
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
    super(group, search_str, prefix + '@###-@#-@#' + postfix, [dy, dm, dd]);
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
    super(group, search_str, 'between @#-@# and @#-@# (inclusive)',
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
    super(group, search_str, 'between @###-@#-@# and @###-@#-@# (inclusive)',
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
class ParkCnt {
  total = 0;
  date_to_cnt = new Map();
  add(date, cnt) {
    this.total += cnt;
    if (this.date_to_cnt.has(date)) {
      cnt += this.date_to_cnt.get(date);
    }
    this.date_to_cnt.set(date, cnt);
  }
  add_parkcnt(parkcnt) {
    for (const [date, cnt] of parkcnt.date_to_cnt) {
      this.add(date, cnt);
    }
  }
}
function sort_parkcnt_map(a, b) {
  return b[1].total - a[1].total;
}
function sort_datecnt_map(a, b) {
  return (a[0] > b[0]) ? -1 : (a[0] < b[0]) ? 1 : 0;
}
function sort_trip_to_cnt(a, b) {
  if ((a[0][0] > b[0][0]) ||
      ((a[0][0] == b[0][0]) && (a[0][1] < b[0][1]))) {
    return -1;
  } else if ((a[0][0] < b[0][0]) ||
             ((a[0][0] == b[0][0]) && (a[0][1] > b[0][1]))) {
    return 1;
  } else {
    return 0;
  }
}
function sorted_map(m, sort_fn) {
  const entries = Array.from(m.entries());
  return entries.sort(sort_fn);
}
function by_cnt(a, b) {
  return b.total - a.total;
}
function get_cnt(page_to_trips, page_to_cnt, page_info) {
  if (!page_to_cnt.has(page_info)) {
    page_to_cnt.set(page_info, new Cnt(page_to_trips, page_to_cnt, page_info));
  }
  return page_to_cnt.get(page_info);
}
class Cnt {
  total = 0;
  trip_to_cnt = new Map();
  included_set;
  has_self_cnt = false;
  child_cnt_list = [];
  constructor(page_to_trips, page_to_cnt,
              page_info = null, included_set = null) {
    this.page_to_trips = page_to_trips;
    this.page_to_cnt = page_to_cnt;
    if (!included_set) {
      this.included_set = new Set();
      if (page_info) {
        page_to_cnt.set(page_info, this);
      }
    } else {
      this.included_set = included_set;
      if (included_set.has(page_info)) {
        return this;
      }
    }
    if (page_info) {
      this.add_page(page_info);
    }
  }
  add_page(page_info) {
    this.page_info = page_info;
    this.included_set.add(page_info);
    if (this.page_to_trips.has(page_info)) {
      this.has_self_cnt = true;
      const trips = this.page_to_trips.get(page_info);
      for (const trip of trips) {
        this.total++;
        var tripcnt = 1;
        if (this.trip_to_cnt.has(trip)) {
          tripcnt += this.trip_to_cnt.get(trip);
        }
        this.trip_to_cnt.set(trip, tripcnt);
      }
    }
    for (const child_info of page_info.child_set) {
      this.add_child(child_info);
    }
  }
  get_parkcnt(park) {
    if (this.park_to_parkcnt.has(park)) {
      return this.park_to_parkcnt.get(park);
    } else {
      const parkcnt = new ParkCnt();
      this.park_to_parkcnt.set(park, parkcnt);
      return parkcnt;
    }
  }
  add_child(child_info) {
    if (this.included_set.has(child_info)) {
      return;
    }
    const child_cnt = get_cnt(this.page_to_trips, this.page_to_cnt, child_info);
    if (child_cnt.total) {
      this.child_cnt_list.push(child_cnt);
      var no_overlap = true;
      for (const included_page of child_cnt.included_set) {
        if (this.included_set.has(included_page)) {
          no_overlap = false;
          break;
        }
      }
      if (no_overlap) {
        this.add_cnt(child_cnt);
        for (const included_page of child_cnt.included_set) {
          this.included_set.add(included_page);
        }
      } else {
        this.add_cnt(new Cnt(this.page_to_trips, this.page_to_cnt,
                             child_info, this.included_set));
      }
    }
  }
  add_cnt(cnt) {
    this.total += cnt.total;
    for (let [trip, tripcnt] of cnt.trip_to_cnt) {
      if (this.trip_to_cnt.has(trip)) {
        tripcnt += this.trip_to_cnt.get(trip);
      }
      this.trip_to_cnt.set(trip, tripcnt);
    }
  }
  html(indent) {
    var sub_indent = indent;
    const list = [];
    const page_info = this.page_info;
    const has_self_cnt = this.has_self_cnt;
    const child_cnt_list = this.child_cnt_list;
    const enclose = (page_info &&
                     (((child_cnt_list.length > 0) && has_self_cnt) ||
                      (child_cnt_list.length > 1)));
    if (enclose) {
      indent = false;
      sub_indent = true;
      if (indent) {
        list.push('<div class="box indent">');
      } else {
        list.push('<div class="box">');
      }
    }
    if (enclose || (page_info && has_self_cnt)) {
      const c = get_class(page_info);
      const url = get_url(page_info, null);
      if (indent) {
        list.push('<div class="list-box indent">');
      } else {
        list.push('<div class="list-box">');
      }
      if (('j' in page_info) && (child_cnt_list.length == 0)) {
        var jpg = String(page_info.j);
        const comma_pos = jpg.search(',');
        if (comma_pos == -1) {
          jpg = page_info.p + ',' + jpg;
        }
        var jpg_url = 'thumbs/' + jpg + '.jpg';
        var lazy = (cnt_list.length > 10) ? ' loading="lazy"' : '';
        list.push('<a href="' + url + '">');
        list.push('<div class="list-thumb">');
        list.push('<img class="boxed"' + lazy + ' src="' + jpg_url + '" alt="photo">');
        list.push('</div>');
        list.push('</a>');
      }
      list.push('<div>');
      list.push('<a class="' + c + '" href="' + url + '">');
      list.push(compose_page_name(page_info, 2));
      list.push('</a>');
      list.push('<br>');
      list.push(this.details('</div></div>'));
    }
    child_cnt_list.sort(by_cnt);
    for (const child_cnt of child_cnt_list) {
      list.push(child_cnt.html(sub_indent));
    }
    if (enclose) {
      list.push('</div>');
    }
    if (!page_info) {
      list.push('<hr>');
      list.push(this.details());
    }
    return list.join('');
  }
  details(sep = null) {
    const i = cnt_list.length;
    cnt_list.push(this);
    this.trips_open = false;
    this.months_open = false;
    this.parks_open = false;
    const list = [];
    if (this.total == 1) {
      list.push('1 observation');
    } else {
      list.push(this.total + ' observations');
    }
    list.push('<br><span class="summary" onclick="return fn_click_trips(' + i + ');">[trips]</span>');
    list.push(' <span class="summary" onclick="return fn_click_months(' + i + ');">[by&nbsp;month]</span>');
    list.push(' <span class="summary" onclick="return fn_click_parks(' + i + ');">[by&nbsp;location]</span>');
    if (sep) {
      list.push(sep);
    }
    list.push('<div class="details" id="details' + i + '"></div>');
    return list.join('');
  }
  details_trips(i) {
    const e_details = document.getElementById('details' + i);
    this.trips_open = !this.trips_open;
    this.months_open = false;
    this.parks_open = false;
    const list = [];
    if (this.trips_open) {
      list.push('<ul>');
      const trip_list = sorted_map(this.trip_to_cnt, sort_trip_to_cnt);
      for (const [trip, cnt] of trip_list) {
        if (cnt == 1) {
          list.push('<li>' + trip[0] + ' in ' + trip[1] + '</li>');
        } else {
          list.push('<li>' + trip[0] + ' in ' + trip[1] + ': ' + cnt + '</li>');
        }
      }
      list.push('</ul>');
    }
    e_details.innerHTML = list.join('');
  }
  details_months(i) {
    const e_details = document.getElementById('details' + i);
    this.trips_open = false;
    this.months_open = !this.months_open;
    this.parks_open = false;
    const list = [];
    const month_cnt = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    if (this.months_open) {
      for (const [trip, cnt] of this.trip_to_cnt) {
        const month = Number(trip[0].substring(5, 7)) - 1;
        month_cnt[month] += cnt;
      }
      var z_first = 0
      var z_length = 0
      for (var i = 0; i < 12; i++) {
        for (var j = 0; j < 12; j++) {
          if (month_cnt[(i+j) % 12]) {
            if ((j > z_length) ||
                ((j == z_length) && ((i == 0) || (i+j >= 12)))) {
              z_first = i
              z_length = j
            }
            break;
          }
        }
      }
      const month_name = ['Jan.', 'Feb.', 'Mar.', 'Apr.', 'May', 'Jun.',
                          'Jul.', 'Aug.', 'Sep.', 'Oct.', 'Nov.', 'Dec.']
      list.push('<ul>');
      for (var i = 0; i < 12 - z_length; i++) {
        var m = (i + z_first + z_length) % 12;
        list.push('<li>' + month_name[m] + ': ' + month_cnt[m] + '</li>')
      }
      list.push('</ul>\n');
    }
    e_details.innerHTML = list.join('');
  }
  details_parks(i) {
    const e_details = document.getElementById('details' + i);
    this.trips_open = false;
    this.months_open = false;
    this.parks_open = !this.parks_open;
    const list = [];
    if (this.parks_open) {
      const park_to_parkcnt = new Map();
      for (const [trip, cnt] of this.trip_to_cnt) {
        const date = trip[0];
        const park = trip[1];
        if (!park_to_parkcnt.has(park)) {
          park_to_parkcnt.set(park, new ParkCnt());
        }
        const parkcnt = park_to_parkcnt.get(park);
        parkcnt.add(date, cnt);
      }
      const sorted_parkcnt = sorted_map(park_to_parkcnt, sort_parkcnt_map);
      for (const [park, parkcnt] of sorted_parkcnt) {
        list.push('<p>' + park + ': ' + parkcnt.total + '</p>');
        list.push('<ul>');
        const sorted_datecnt = sorted_map(parkcnt.date_to_cnt, sort_datecnt_map);
        for (const [date, cnt] of sorted_datecnt) {
          if (cnt > 1) {
            list.push('<li>' + date + ': ' + cnt + ' taxons </li>');
          } else {
            list.push('<li>' + date + '</li>');
          }
        }
        list.push('</ul>');
      }
    }
    e_details.innerHTML = list.join('');
  }
}
function fn_click_trips(i) {
  cnt_list[i].details_trips(i);
}
function fn_click_months(i) {
  cnt_list[i].details_months(i);
}
function fn_click_parks(i) {
  cnt_list[i].details_parks(i);
}
function delete_ancestors(page_info, page_to_trips, checked_set) {
  for (const parent_info of page_info.parent_set) {
    if (checked_set.has(parent_info)) {
    } else {
      if (page_to_trips.has(parent_info)) {
        page_to_trips.delete(parent_info);
      }
      checked_set.add(parent_info);
      delete_ancestors(parent_info, page_to_trips, checked_set);
    }
  }
}
function gen_adv_search_results() {
  if (term_list.length == 0) {
    e_results.innerHTML = '<p>...</p>';
    return;
  }
  for (const term of term_list) {
    term.result_init();
  }
  const page_to_trips = new Map();
  for (const page_info of pages) {
    if (page_info.trip_set.size == 0) {
      continue;
    }
    let prev_group = -1;
    let current_trip_set = new Set(page_info.trip_set);
    let past_trip_set;
    for (const term of term_list) {
      if (term.group != prev_group) {
        if (current_trip_set.size == 0) {
          break;
        }
        past_trip_set = current_trip_set;
        current_trip_set = new Set();
        prev_group = term.group;
      }
      term.result_match(page_info, past_trip_set, current_trip_set);
    }
    if (current_trip_set.size) {
      page_to_trips.set(page_info, current_trip_set);
    }
  }
  const page_to_cnt = new Map();
  const top_cnt = new Cnt(page_to_trips, page_to_cnt);
  for (const page_info of pages) {
    if (page_info.parent_set.size == 0) {
      top_cnt.add_child(page_info);
    }
  }
  cnt_list = [];
  const html = top_cnt.html(false, 0);
  if (html) {
    e_results.innerHTML = html;
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
  init_traits();
  init_parks();
  if (adv_search) {
    init_adv_search();
  }
  e_search_input.addEventListener('input', fn_change);
  e_search_input.addEventListener('keydown', fn_keydown);
  e_search_input.addEventListener('focusin', fn_focusin);
  fn_hashchange();
  window.addEventListener('hashchange', fn_hashchange);
  if (adv_search) {
    restore_state();
    set_title();
  }
  gallery_main();
  if (Document.activeElement == e_search_input) {
    fn_search(0);
  }
}
if (typeof pages !== 'undefined') {
  main();
}
