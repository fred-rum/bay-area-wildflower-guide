/* Copyright Chris Nelson - All rights reserved. */
'use strict';
var fresh = true;
var obj_photos = [];
var obj_photo = null;
var e_bg = document.getElementById('gallery-background');
var e_ui_l = document.getElementById('gallery-ui-left');
var e_ui_r = document.getElementById('gallery-ui-right');
var e_spin = document.getElementById('gallery-spinner');
var spin_req = null;
var spin_timestamp = performance.now();
var spin_offset = 0;
var touches = [];
var click_target;
var click_x;
var click_y;
var click_time;
var orig_pinch;
var win_x, win_y;
function main() {
  var first_photo_name = window.location.search;
  if (first_photo_name) {
    first_photo_name = decodeURIComponent(first_photo_name.substring(1))
  } else {
    first_photo_name = 'invalid'
  }
  var is_in_photos = first_photo_name.startsWith('photos')
  for (var i = 0; i < pages.length; i++) {
    var list = pages[i];
    var page_name = list[0];
    var base_name = page_name;
    var photo_urls = [];
    var match_idx = 0;
    for (var j = 1; j < list.length; j++) {
      var photo_name = String(list[j]);
      if (is_in_photos) {
        var comma_pos = photo_name.search(',');
        if (comma_pos == -1) {
          photo_name = base_name + ',' + photo_name;
        } else {
          base_name = photo_name.substring(0, comma_pos);
        }
        photo_name = 'photos/' + photo_name;
        photo_name =  photo_name + '.jpg';
      }
      photo_urls.push(photo_name);
      var photo_name = munge_path(photo_name);
      if (first_photo_name == photo_name) {
        match_idx = j;
      }
    }
    if (match_idx) {
      break;
    }
  }
  if (i == pages.length) {
    page_name = first_photo_name;
    photo_urls = [first_photo_name];
    match_idx = 1;
  }
  document.title = 'gallery - ' + page_name;
  for (var i = 0; i < photo_urls.length; i++) {
    var obj = new Photo(i, photo_urls[i])
    obj_photos.push(obj);
  }
  win_x = window.innerWidth;
  win_y = window.innerHeight;
  window.addEventListener('resize', fn_resize);
  window.addEventListener('keydown', fn_gallery_keydown);
  i = match_idx - 1;
  if (history.state) {
    obj_photos[i].fit = history.state.fit;
    obj_photos[i].img_x = history.state.img_x;
    obj_photos[i].cx = history.state.cx;
    obj_photos[i].cy = history.state.cy;
    obj_photos[i].open_photo();
  } else {
    obj_photos[i].init_photo();
  }
  e_bg.addEventListener('pointerdown', fn_pointerdown);
  e_bg.addEventListener('pointerleave', fn_pointercancel);
  e_bg.addEventListener('pointercancel', fn_pointercancel);
  e_bg.addEventListener('pointerup', fn_pointerup);
  e_bg.addEventListener('pointermove', fn_pointermove);
  e_bg.addEventListener('wheel', fn_wheel);
}
var state_timer = null;
function save_state() {
  if (!state_timer) {
    state_timer = setTimeout(fn_save_state, 200);
  }
}
function fn_save_state() {
  state_timer = null;
  obj_photo.save_state();
}
function fn_spin(timestamp) {
  spin_req = null;
  obj_photo.activate_images();
}
function draw_spinner(stopped) {
  var hz = 1.0;
  var n = 7;
  var r_ring = 40;
  var r_circle = 10;
  var timestamp = performance.now();
  var elapsed = timestamp - spin_timestamp;
  spin_timestamp = timestamp;
  var inc = elapsed / 1000 * hz;
  inc = Math.min(inc, 1 / n);
  spin_offset = (spin_offset + inc) % n;
  var ctx = e_spin.getContext('2d');
  ctx.clearRect(0, 0, 100, 100);
  for (var i = 0; i < n; i++) {
    var c = Math.floor(i * 255 / (n-1));
    if (stopped) {
      ctx.fillStyle = 'rgb(' + (c / 255 * 155 + 100) + ',0,0,0.70)';
    } else {
      ctx.fillStyle = 'rgb(' + c + ',' + c + ',' + c + ')';
    }
    var a = 2 * Math.PI * ((i / n) + spin_offset);
    var x = 50 + Math.sin(a) * (r_ring - r_circle);
    var y = 50 - Math.cos(a) * (r_ring - r_circle);
    ctx.beginPath();
    ctx.arc(x, y, r_circle, 0, 2 * Math.PI);
    ctx.fill();
  }
}
function clear_spinner() {
  var ctx = e_spin.getContext('2d');
  ctx.clearRect(0, 0, 100, 100);
}
function end_spinner() {
  if (spin_req) {
    window.cancelAnimationFrame(spin_req);
    spin_req = null;
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
    return;
  }
  e_bg.setPointerCapture(event.pointerId);
  var touch = copy_touch(event);
  touches.push(touch);
  if (touches.length == 1) {
    click_target = event.target;
    click_x = touches[0].x;
    click_y = touches[0].y;
    click_time = performance.now();
  } else {
    click_target = null;
  }
  orig_pinch = undefined;
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
  orig_pinch = undefined;
}
function fn_pointerup(event) {
  var touch = copy_touch(event);
  orig_pinch = undefined;
  const max_click_time = 300;
  if (obj_photo && click_target && discard_touch(touch) &&
      (performance.now() - click_time <= max_click_time)) {
    if (click_target == e_ui_l) {
      obj_photo.go_left();
    } else if (click_target == e_ui_r) {
      obj_photo.go_right();
    } else if ((click_target == obj_photo.e_thumb) ||
               (click_target == obj_photo.e_full)){
      obj_photo.click.call(obj_photo, touch);
    } else {
      setTimeout(go_back, 50);
    }
    return true;
  }
}
var go_back_in_progress = false;
function go_back() {
  if (!go_back_in_progress) {
    go_back_in_progress = true;
    history.back();
  }
}
addEventListener('pageshow', fn_return);
function fn_return() {
  go_back_in_progress = false;
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
    return;
  }
  if ((event.pointerType == 'mouse') && (event.buttons != 1)) {
    fn_pointercancel(event);
    return;
  }
  var touch = copy_touch(event);
  var i = touch_index(touch);
  if (i == -1) {
    return;
  }
  if ((touches[i].x == touch.x) &&
      (touches[i].y == touch.y)) {
    return;
  }
  const diff_x = touches[i].x - click_x;
  const diff_y = touches[i].y - click_y;
  const max_click_move = 10;
  if (diff_x * diff_x + diff_y * diff_y > max_click_move * max_click_move) {
    click_target = null;
  }
  var old_pinch = measure_pinch();
  touches[i] = touch;
  if (obj_photo) {
    var new_pinch = measure_pinch();
    obj_photo.pinch.call(obj_photo, old_pinch, new_pinch);
  }
}
function fn_wheel(event) {
  orig_pinch = undefined;
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
    return;
  }
  var touch = copy_touch(event);
  if (event.deltaY < 0) {
    obj_photo.zoom_in(touch);
  } else if (event.deltaY > 0) {
    obj_photo.zoom_out(touch);
  } else if (event.deltaX < 0) {
    obj_photo.go_left();
  } else if (event.deltaX > 0) {
    obj_photo.go_right();
  }
}
function munge_path(path) {
  return path.replace(/[/ ,/]/g, function (c) {
    return {
      '/': '-',
      ' ': '-',
      ',': '.'
    }[c];
  });
}
function Photo(i, url_full) {
  this.i = i;
  this.url_full = url_full;
  this.is_svg = /\.svg$/.test(url_full);
  if (!this.is_svg) {
    this.url_thumb = url_full.replace(/^photos\/|^figures\//, 'thumbs/')
  }
  this.active_thumb = false;
  this.active_full = false;
  this.done_thumb = null;
  this.done_full = null;
}
Photo.prototype.init_photo = function() {
  this.fit = true;
  this.img_x = null;
  this.cx = 0.5;
  this.cy = 0.5;
  this.open_photo();
  save_state();
}
Photo.prototype.open_photo = function() {
  obj_photo = this;
  if (this.i > 0) {
    e_ui_l.style.display = 'block';
  } else {
    e_ui_l.style.display = 'none';
  }
  if (this.i < (obj_photos.length-1)) {
    e_ui_r.style.display = 'block';
  } else {
    e_ui_r.style.display = 'none';
  }
  if (!this.e_thumb) {
    if (!this.is_svg) {
      this.e_thumb = document.createElement('img');
      this.e_thumb.className = 'gallery-photo';
      this.e_thumb.setAttribute('draggable', 'false');
      this.e_thumb.addEventListener('load', this.fn_img_result.bind(this));
      this.e_thumb.addEventListener('error', this.fn_img_result.bind(this));
      this.e_thumb.src = encodeURI(this.url_thumb);
    }
    this.e_full = document.createElement('img');
    this.e_full.className = 'gallery-photo';
    this.e_full.setAttribute('draggable', 'false');
    this.e_full.addEventListener('load', this.fn_img_result.bind(this));
    this.e_full.addEventListener('error', this.fn_img_result.bind(this));
    this.e_full.src = encodeURI(this.url_full);
    if (this.is_svg) {
      e_spin.insertAdjacentElement('beforebegin', this.e_full);
    }
  }
  this.activate_images();
}
Photo.prototype.activate_images = function() {
  var new_active = false;
  if (!this.active_full && (this.e_full.naturalWidth ||
                            (this.is_svg && this.e_full.width))) {
    new_active = true;
    this.active_full = true;
    if (this.is_svg) {
      var ar = this.e_full.width / this.e_full.height;
      this.photo_x = Math.min(2048, 2048 * ar);
      this.photo_y = Math.min(2048, 2048 / ar);
      this.e_full.style.backgroundColor = 'white';
    } else {
      this.photo_x = this.e_full.naturalWidth;
      this.photo_y = this.e_full.naturalHeight;
      if (!this.active_thumb) {
        this.e_full.style.backgroundColor = '#808080';
      }
      e_spin.insertAdjacentElement('beforebegin', this.e_full);
    }
  }
  if (!this.is_svg && !this.active_thumb && this.e_thumb.naturalWidth &&
      (this.done_full != 'load')) {
    new_active = true;
    this.active_thumb = true;
    if (this.active_full) {
      this.e_full.style.backgroundColor = 'transparent';
    } else {
      this.photo_x = this.e_thumb.naturalWidth;
      this.photo_y = this.e_thumb.naturalHeight;
    }
    this.e_thumb.style.backgroundColor = '#808080';
    e_bg.insertAdjacentElement('afterbegin', this.e_thumb);
  }
  if (new_active) {
    this.redraw_photo();
  }
  if ((this.done_full == 'load') && this.active_full) {
    clear_spinner();
    end_spinner();
    if (this.active_thumb) {
      this.e_thumb.remove();
      this.active_thumb = false;
    } else if (!this.is_svg){
      this.e_full.style.backgroundColor = 'transparent';
    }
  } else if ((this.done_full == 'error') && (this.done_thumb != null)) {
    draw_spinner(true);
    end_spinner();
  } else {
    draw_spinner(this.done_full == 'error');
    if (!spin_req) {
      spin_req = window.requestAnimationFrame(fn_spin);
    }
  }
}
Photo.prototype.fn_img_result = function(event) {
  if (event.target == this.e_full) {
    this.done_full = event.type;
  } else {
    this.done_thumb = event.type;
  }
  if (this != obj_photo) {
    return;
  }
  this.activate_images();
}
Photo.prototype.close_photo = function() {
  if (this.active_thumb) {
    this.e_thumb.remove();
    this.active_thumb = false;
  }
  if (this.active_full) {
    this.e_full.remove();
    this.active_full = false;
  }
}
Photo.prototype.img_y = function() {
  return this.img_x / this.photo_x * this.photo_y;
}
Photo.prototype.click = function(touch) {
  if (this.fit) {
    this.zoom_to(this, this.photo_x, touch, touch);
  } else {
    this.fit = true;
    this.cx = 0.5;
    this.cy = 0.5;
    this.redraw_photo();
  }
  return true;
}
Photo.prototype.constrain_zoom = function() {
  var max_width = Math.max(this.photo_x * 3, this.fit_width());
  if (this.img_x > max_width) {
    this.img_x = max_width;
  }
  var min_width = Math.max(100, 100 * this.photo_x / this.photo_y);
  if (this.img_x < min_width) {
    this.img_x = Math.min(min_width, this.fit_width());
  }
}
Photo.prototype.constrain_pos = function() {
  var img_x = this.img_x;
  var img_y = this.img_y();
  var cx_bound0 = Math.min(0, 1-(win_x/2) / img_x);
  var cx_bound1 = Math.max(1, (win_x/2) / img_x);
  if (this.cx < cx_bound0) {
    this.cx = cx_bound0;
  } else if (this.cx > cx_bound1) {
    this.cx = cx_bound1;
  }
  var cy_bound0 = Math.min(0, 1-(win_y/2) / img_y);
  var cy_bound1 = Math.max(1, (win_y/2) / img_y);
  if (this.cy < cy_bound0) {
    this.cy = cy_bound0;
  } else if (this.cy > cy_bound1) {
    this.cy = cy_bound1;
  }
}
Photo.prototype.zoom_to = function(orig, new_width, old_pos, new_pos) {
  if (new_width != this.img_x) {
    this.fit = false;
  }
  var img_x = this.img_x;
  var img_y = this.img_y();
  var img_x0 = (win_x / 2) - (img_x * orig.cx);
  var img_y0 = (win_y / 2) - (img_y * orig.cy);
  var img_x1 = img_x0 + img_x;
  var img_y1 = img_y0 + img_y;
  var cpx, cpy, ox, oy;
  if (old_pos.x < img_x0) {
    ox = old_pos.x - img_x0;
    cpx = 0;
  } else if (old_pos.x > img_x1) {
    ox = old_pos.x - img_x1;
    cpx = 1;
  } else {
    ox = 0;
    cpx = (old_pos.x - img_x0) / img_x;
  }
  if (old_pos.y < img_y0) {
    oy = old_pos.y - img_y0;
    cpy = 0;
  } else if (old_pos.y > img_y1) {
    oy = old_pos.y - img_y1;
    cpy = 1;
  } else {
    oy = 0;
    cpy = (old_pos.y - img_y0) / img_y;
  }
  this.img_x = new_width;
  this.constrain_zoom();
  img_x = this.img_x;
  img_y = this.img_y();
  img_x0 = (new_pos.x - ox) - (cpx * img_x);
  img_y0 = (new_pos.y - oy) - (cpy * img_y);
  this.cx = ((win_x / 2) - img_x0) / img_x;
  this.cy = ((win_y / 2) - img_y0) / img_y;
  this.constrain_pos();
  this.redraw_photo();
}
Photo.prototype.pinch = function(old_pinch, new_pinch) {
  if (!this.active_thumb && !this.active_full) {
    return;
  }
  if (!orig_pinch) {
    orig_pinch = old_pinch;
    orig_pinch.img_x = this.img_x;
    orig_pinch.cx = this.cx;
    orig_pinch.cy = this.cy;
  }
  var width = orig_pinch.img_x;
  if (orig_pinch.distance != 0) {
    width *= new_pinch.distance / orig_pinch.distance;
  }
  this.zoom_to(orig_pinch, width, orig_pinch, new_pinch);
}
Photo.prototype.fit_width = function() {
  return Math.min(win_x, this.photo_x / this.photo_y * win_y);
}
Photo.prototype.zoom_in = function(touch) {
  this.zoom_to(this, this.img_x * 1.30, touch, touch);
}
Photo.prototype.zoom_out = function(touch) {
  this.zoom_to(this, this.img_x / 1.30, touch, touch);
}
Photo.prototype.go_left = function() {
  if (this.i > 0) {
    this.close_photo();
    var i = this.i - 1;
    obj_photo = obj_photos[i];
    obj_photo.init_photo();
  }
}
Photo.prototype.go_right = function() {
  if (this.i < (obj_photos.length-1)) {
    this.close_photo();
    var i = this.i + 1;
    obj_photo = obj_photos[i];
    obj_photo.init_photo();
  }
}
Photo.prototype.save_state = function() {
  const munged_url = munge_path(this.url_full);
  const url = window.location.pathname + '?' + encodeURIComponent(munged_url);
  const state = {
    'fit': this.fit,
    'img_x': this.img_x,
    'cx': this.cx,
    'cy': this.cy
  };
  history.replaceState(state, '', url);
}
Photo.prototype.redraw_photo = function() {
  if (!this.active_thumb && !this.active_full) {
    return;
  }
  save_state();
  if (this.fit) {
    this.img_x = this.fit_width();
  }
  var img_x = this.img_x;
  var img_y = this.img_y();
  var img_x0 = (win_x / 2) - (img_x * this.cx);
  var img_y0 = (win_y / 2) - (img_y * this.cy);
  if (this.active_thumb) {
    this.e_thumb.style.width = img_x + 'px';
    this.e_thumb.style.left = img_x0 + 'px';
    this.e_thumb.style.top = img_y0 + 'px';
  }
  if (this.active_full) {
    this.e_full.style.width = img_x + 'px';
    this.e_full.style.left = img_x0 + 'px';
    this.e_full.style.top = img_y0 + 'px';
  }
}
Photo.prototype.resize = function() {
  this.constrain_zoom();
  this.constrain_pos();
  this.redraw_photo();
}
function fn_resize() {
  win_x = window.innerWidth;
  win_y = window.innerHeight;
  if (obj_photo) {
    obj_photo.resize();
  }
}
function fn_gallery_keydown(event) {
  var center_touch = {
    x: win_x/2,
    y: win_y/2
  };
  if ((event.key == 'Escape') ||(event.key == 'Esc')) {
    history.back();
    event.preventDefault();
  } else if ((event.key == 'Enter') ||
             (event.key == ' ') || (event.key == 'Spacebar')) {
    obj_photo.click.call(obj_photo, center_touch);
  } else if ((event.key == 'ArrowLeft') || (event.key == 'Left')) {
    obj_photo.go_left();
  } else if ((event.key == 'ArrowRight') || (event.key == 'Right')) {
    obj_photo.go_right();
  } else if (event.key == 'PageUp') {
    obj_photo.zoom_in(center_touch);
  } else if (event.key == 'PageDown') {
    obj_photo.zoom_out(center_touch);
  }
}
main();
