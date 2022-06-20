/* Copyright Chris Nelson - All rights reserved. */

'use strict';

/*****************************************************************************/
/* code related to the photo gallery */

/* fresh is 'true' only for the first call to gallery_main() */
var fresh = true;

/* obj_photos is an array of Photo objects, one for each photo associated
   with this page */
var obj_photos = [];

/* obj_photo is the Photo object currently being displayed in the gallery,
   or null if the gallery isn't open */
var obj_photo = null;

/* e_bg is the gray background for the photo gallery.  It covers the normal
   page contents. It is created once and then added or removed from the page as
   desired. */
var e_bg = null;

/* e_spin is the canvas where the spinning 'loading' icon is drawn.
   The canvas is created once and then drawn or cleared as desired. */
var e_spin;

/* spin_req represents the request for the next animation frame when the
   spinner is spinning.  It can be used to cancel the request and stop the
   spinner. */
var spin_req = null;

/* spin_timestamp indicates the time of the last spinner update.  This helps
   determine how far the spinner should rotate the next time it is drawn. */
var spin_timestamp;

/* The touches array keeps track of active pointers, i.e. a mouse with the
   left button pressed and any finger or stylus touching the screen. */
var touches = [];

/* one_unmoved_touch tracks whether there is a current touch in progress
   that should count as a 'click' if released */
var one_unmoved_touch = true;

/* orig_pinch remembers data about how the current multi-touch started.
   Movements of the touch points can be compared against this original. */
var orig_pinch;

/* win_x and win_y keep track of the current viewport dimentions.  These are
   updated on a resize event.  These values can be queried at any time, but
   I need them in so many parts of the code that it's easier to just maintain
   them as global values. */
var win_x, win_y;


/* Ideally, we want gallery_main() to be called after the thumbnails are
   loaded into the DOM, but before the user can click on them.  But the
   only way to perfectly guarantee this is to write potentially a lot of
   JavaScript directly into the HTML file.  Parts of the JavaScript could
   potentially be in a separate script file, but that file would have to
   be loaded synchronously, thus slowing down the page display.

   Instead, we allow the JavaScript to load separately and asynchronously,
   then try to annotate the HTML as quickly as possible.  This ends up
   calling gallery_main() twice:

   1. We call gallery_main() as soon as the JavaScript is loaded.  Since the
   HTML is small and the script is large, most likely the HTML has already
   loaded and populated the DOM, so this is as fast as we can go.
   This call is at the end of the photogallery section.

   2. In case the DOM was *not* full populated the first time, we call
   gallery_main() again once the DOM is complete.  The second call to
   gallery_main() only annotates any HTML that was missed by the first call.
   This call is in main().

   Note that if the DOM is complete before the script finishes loading,
   both calls may be made consecutively once the script has loaded.
*/
function gallery_main() {
  /* Initialize each potential gallery photo, in particular adding
     Javascript to intercept a click on any of the page's thumbnails. */
  var e_thumbnail_list = document.getElementsByClassName('leaf-thumb')

  /* If we already annotated some thumbnails, only annotate ones that
     we didn't see before. */
  var first_photo = obj_photos.length;

  console.log('e_thumbnail_list:', e_thumbnail_list);

  for (var i = first_photo; i < e_thumbnail_list.length; i++) {
    console.log('annotating thumbnail', i);
    var obj = new Photo(i, e_thumbnail_list[i])
    obj_photos.push(obj);
  }

  /* maintain the window dimensions for quick access */
  win_x = window.innerWidth;
  win_y = window.innerHeight;
  window.addEventListener('resize', fn_resize);

  /* We attach 'history.state' to the document when entering the gallery.
     The browser then informs us on any forward/back navigation whether
     the current 'history'state' has changed, which means that we need to
     either close or re-open the gallery. */
  window.addEventListener('popstate', fn_popstate);

  /* The gallery doesn't have an input field that can have key focus,
     so we look for keypresses in the entire window.  fn_gallery_keydown()
     ignores keys if the gallery isn't open. */
  window.addEventListener('keydown', fn_gallery_keydown);

  /* Handle any history.state that may be present.  Typically we do this only
     on the first call to gallery_main(), but if we don't have the necessary
     obj_photo info on the first call, do it on the second call. */
  if (fresh) {
    /* first call */
    if (!history.state ||
        (history.state.i < obj_photos.length)) {
      fn_popstate(null);
    }
    fresh = false;
  } else {
    /* second call */
    /* At this point, we shouldn't normally have to worry about history.state.i
       indexing outside the range of obj_photos, but it's possible that the
       HTML changed since the history was recorded and now has fewer thumbnails.
       Unlikely, but I might as well test for it and not crash. */
    if (history.state &&
        (history.state.i >= first_photo) &&
        (history.state.i < obj_photos.length)) {
      fn_popstate(null);
    }
  }

}

/* Move the photo gallery from a 'closed' to an 'open' state.

   If this is the first time the gallery is opened, the necessary DOM elements
   are created.  On the other hand, if the gallery was previously opened and
   then closed, then the DOM elements still exist, and we only have to undo the
   changes that were made when the gallery was closed. */
function open_gallery() {
  console.log('open_gallery');

  if (!orig_title) {
    orig_title = document.title;
  }
  document.title = 'gallery - ' + orig_title;

  /* prevent the 'enter' key from following the photo link that was
     just clicked and focused.  Alternatively, the browser may have
     "restored" focus to the link after reloading or returning to the
     page, which is why we have to remove focus here and not only after
     a direct click. */
  document.activeElement.blur();

  /* prevent scrollbars from appearing based on the hidden page content */
  document.documentElement.style.overflow = 'hidden';

  /* Only create the gallery elements the first time the gallery is opened. */
  if (!e_bg) {
    e_bg = document.createElement('div');
    e_bg.id = 'gallery-background';
    e_bg.addEventListener('pointerdown', fn_pointerdown);
    e_bg.addEventListener('pointerleave', fn_pointercancel);
    e_bg.addEventListener('pointercancel', fn_pointercancel);
    e_bg.addEventListener('pointerup', fn_pointerup);
    e_bg.addEventListener('pointermove', fn_pointermove);
    e_bg.addEventListener('wheel', fn_wheel);

    e_spin = document.createElement('canvas');
    e_spin.id = 'photo-loading';
    e_spin.width = 100;
    e_spin.height = 100;
    e_bg.appendChild(e_spin);
  }

  document.body.appendChild(e_bg);

  /* We always start the 'loading' spinner when we open the gallery,
     but later code will immediately stop it if the full-sized photo
     is already loaded. */
  if (!spin_req) {
    spin_req = window.requestAnimationFrame(draw_spinner);
    spin_timestamp = performance.now();
  }
}

function close_gallery() {
  document.documentElement.style.overflow = 'auto';
  obj_photo.remove_images();
  obj_photo = null;
  e_bg.remove();
  clear_spinner();
  touches = [];
}

var orig_title = null;

/* fn_popstate() gets a callback when the user navigates from the photo gallery
   back to the main page or from the main page forward to the photo gallery.
   The latter is equally useful when a gallery page is reloaded, so we also
   manually call fn_popstate() as soon as the page is loaded. */
function fn_popstate(event) {
  console.log('popstate');

  if (obj_photo) {
    console.log('closing gallery');
    close_gallery();
  }

  if (history.state) {
    console.log('restoring gallery');
    obj_photo = obj_photos[history.state.i];
    obj_photo.fit = history.state.fit;
    obj_photo.history_width = history.state.width;
    obj_photo.cx = history.state.cx;
    obj_photo.cy = history.state.cy;
    obj_photo.gallery_init();
  } else if (orig_title) {
    document.title = orig_title;
  }
}

var offset = 0;
function draw_spinner(timestamp) {
  var ctx = e_spin.getContext('2d');
  ctx.clearRect(0, 0, 100, 100);
  var r_ring = 40;
  var r_circle = 10;
  var n = 7;
  var hz = 1.0;
  for (var i = 0; i < n; i++) {
    var c = Math.floor(i * 255 / (n-1));
    ctx.fillStyle = 'rgb(' + c + ',' + c + ',' + c + ')';
    var a = 2 * Math.PI * ((i / n) + offset);
    var x = 50 + Math.sin(a) * (r_ring - r_circle);
    var y = 50 - Math.cos(a) * (r_ring - r_circle);
    ctx.beginPath();
    ctx.arc(x, y, r_circle, 0, 2 * Math.PI);
    ctx.fill();
  }

  var elapsed = timestamp - spin_timestamp;
  spin_timestamp = timestamp;

  var inc = elapsed / 1000 * hz;
  inc = Math.min(inc, 1 / n);
  offset = (offset + inc) % n;

  spin_req = window.requestAnimationFrame(draw_spinner);

  /* activate_images() polls the photo loading status and may stop the
     spinner if there was a problem. */
  obj_photo.activate_images();
}

function clear_spinner() {
  console.log('clear spin');

  /* We could remove the spinner's canvas element, but then we'd have to
     restore it if we switch to another photo.  So instead we leave the canvas
     in place, but clear its contents. */
  var ctx = e_spin.getContext('2d');
  ctx.clearRect(0, 0, 100, 100);

  end_spinner();
}

function end_spinner() {
  if (spin_req) {
    console.log('end spin');
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
  console.log(event);

  if ((event.pointerType == 'mouse') && (event.buttons != 1)) {
    /* ignore any mouse click that is not solely the the primary (left)
       mouse button */
    return;
  }

  /* Capture the pointer so that drag tracking can continue
     outside the normal gallery region.  (E.g. the mouse can leave the
     window while the button is held down.) */
  e_bg.setPointerCapture(event.pointerId);

  var touch = copy_touch(event);

  /* remember the touch location */
  touches.push(touch);
  console.log('pointer down:', touches.length);

  one_unmoved_touch = (touches.length == 1);

  /* reset the starting pinch/drag location */
  orig_pinch = undefined;

  /* We don't care if the pointerdown event propagates, but if I return false
     here, Firefox on Android suddenly can't generate pointermove events for
     two moving touches at the same time. */
}

function touch_index(touch) {
  for (var i = 0; i < touches.length; i++) {
    if (touches[i].id == touch.id) {
      return i;
    }
  }
  return -1;
}

/* Remove and element from the touches array (because the touch has been
   removed).  Returns 'true' if the touch was in the array, 'false' if not. */
function discard_touch(touch) {
  /* Discard the cached touch location */
  var i = touch_index(touch);
  if (i != -1) { /* should never be -1, but we check to be sure */
    touches.splice(i, 1);
    return true;
  }

  return false;
}

function fn_pointercancel(event) {
  var touch = copy_touch(event);
  discard_touch(touch);
  console.log('pointer cancel:', touches.length);

  /* reset the starting pinch/drag location */
  orig_pinch = undefined;
}

function fn_pointerup(event) {
  var touch = copy_touch(event);

  /* reset the starting pinch/drag location */
  orig_pinch = undefined;

  /* For some reason the browser doesn't do proper click handling when there
     are event handlers for the various pointer events.  In Chrome on the
     desktop, click-drag-release causes the browser to pause for about a second
     before triggering a 'click' event.  But it shouldn't trigger a 'click' if
     the mouse moved, and the second-long pause is a UX nightmare.

     So we handle the click ourselves as a degenerate case of pointer up
     followed by pointer down with no pointermove in between. */
  if (discard_touch(touch) && one_unmoved_touch) {
    /* There was a single click with no drag. */

    /* Let the photo object handle it if appropriate. */
    if (obj_photo && !obj_photo.click.call(obj_photo, touch)) {
      /* The click was outside the photo, so we return to the normal page view.
         We could close the gallery directly, but since opening the gallery
         pushed an entry to the browser's history, we want to pop back up the
         history.  Since there is already code to restore the proper state when
         the user navigates back through the history, the rest is automatic. */
      history.back();
    }

    return;
  }

  console.log('pointer up:', touches.length);
}

/* Measure the pinch distance by calculating the bounding box around all
   touch events, then calculating the diagonal distance across the box. */
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
    /* e.g. the mouse was moved without a button down. */
    return;
  }

  if ((event.pointerType == 'mouse') && (event.buttons != 1)) {
    /* discard mouse actions if any extra buttons are pressed at any point */
    fn_pointercancel(event);
    return;
  }

  console.log('pointermove ID:', event.pointerId);

  var touch = copy_touch(event);

  var i = touch_index(touch);
  if (i == -1) {
    /* e.g. the mouse was moved while separately
       a finger was touching the screen */
    return;
  }

  if ((touches[i].x == touch.x) &&
      (touches[i].y == touch.y)) {
    /* Android likes to activate pointermove even when no movement occurred.
       Don't waste time processing it, and particularly don't let it
       disrupt click detection. */
    return;
  }

  /* A touching pointer moved. */
  one_unmoved_touch = false;

  var old_pinch = measure_pinch();

  /* Update the touch cache even if there is no photo to manipulate. */
  touches[i] = touch;

  /* We shouldn't get events if the gallery isn't open, but we check
     to be safe before calling the current photo's pinch function. */
  if (obj_photo) {
    var new_pinch = measure_pinch();
    obj_photo.pinch.call(obj_photo, old_pinch, new_pinch);
  }
}

function fn_wheel(event) {
  orig_pinch = undefined;

  var touch = copy_touch(event);

  if (event.deltaY < 0) {
    obj_photo.zoom_to(obj_photo, obj_photo.zoom * 1.30, touch, touch);
  }
  if (event.deltaY > 0) {
    obj_photo.zoom_to(obj_photo, obj_photo.zoom / 1.30, touch, touch);
  }
}

function Photo(i, e_thumbnail) {
  this.i = i;
  this.e_thumbnail = e_thumbnail;

  /* The HTML has a link from the thumbnail to the full-size photo file.
     We hijack a click on the thumbnail to instead start the photo gallery.
     However, we leave the original alone:
     - open link in new window and save link still work
     - navigating through the link via the keyboard bypasses the photo gallery
       (since this is no worse and may be better than the photo gallery without
       a keyboard) */
  this.e_thumbnail.addEventListener('click', this.fn_gallery_start.bind(this));

  /* The image elements for the thumbnail (for fast loading) and full-sized
     photo (for detail when available).
  this.e_thumb = null;
  this.e_full = null;

  /* The thumbnail can be displayed as soon as we have dimensions for it.
     Although it may still be loading, at least the user can see as much of
     the image has loaded and can start interacting with it.

     Similarly, the full-sized photo can be displayed as soon as we have
     dimensions for it.  Although it may still be loading, it provides
     extra detail over what the thumbnail can display, and its greater
     dimensions allow it to be displayed larger.

     We keep track of whether each photo is "active" on the screen with
     the variables below. */
  this.active_thumb = false;
  this.active_full = false;
  this.done_full = false;
}

Photo.prototype.fn_gallery_start = function(event) {
  console.log('click: start gallery');

  this.fit = true;
  this.history_width = null; /* doesn't matter when fit = true */
  this.cx = null;
  this.cy = null;

  this.gallery_init();

  /* Push the gallery state to the browser's history. */
  var state = this.get_state();
  history.pushState(state, '');

  /* This function was called for a click on a thumbnail.  The thumbnail has a
     link to the full-sized image file that is needed if JavaScript is
     disabled.  But if JavaScript is enabled and this code is run to start the
     photo gallery, we use preventDefault() to prevent the browser from 
    following the link. */
  event.preventDefault();
}

Photo.prototype.gallery_init = function() {
  open_gallery();

  obj_photo = this;

  /* e_thumb and e_full are always create together, so we only need to check
     whether either one is present.  If the photos have already been created,
     we don't need to create them again. */
  if (!this.e_thumb) {
    /* This photo has never been opened in the gallery before.  We create the
       necessary DOM elements here, but we'll have to wait for the thumbnail
       and full-sized photo to load. */

    this.e_thumb = document.createElement('img');
    this.e_thumb.className = 'gallery-photo';
    this.e_thumb.setAttribute('draggable', 'false');

    /* The thumb-sized photo is the same as e_thumbnail.  Unfortunately,
       there's no way to simply re-use the thumbnail from the original page.
       We can only hope that the browser has cached the JPG file and can
       re-create the image quickly. */
    this.e_thumb.src = this.e_thumbnail.src;

    this.e_full = document.createElement('img');
    this.e_full.className = 'gallery-photo';
    this.e_full.setAttribute('draggable', 'false');

    /* By setting the load event handler before setting the img src value,
       we guarantee that the img isn't loaded yet. */
    this.e_full.addEventListener('load', this.fn_full_onload.bind(this));

    /* 'onloadend' isn't well supported yet, so there's no callback if
       the photo fails to load.  Instead, we poll for that condition in
       the spinner. */

    /* The full-sized photo is the target of the original link.  BTW, this
       event handler ultimately suppresses further handling of the click, so
       when the photo galleyr is opened, the original link doesn't get
       activated. */
    this.e_full.src = this.e_thumbnail.parentElement.href;

    /* Note that although the image elements have been created, they have not
       yet been inserted into the document.  We don't do that until the image
       dimensions have been loaded, as polled by the spinner. */
  }

  this.activate_images();
}

Photo.prototype.activate_images = function() {
  /* If we add a new photo to the display, we set new_active to 'true',
     which eventually triggers a call to redraw_photo(). */
  var new_active = false;

  if (!this.active_full && this.e_full.naturalWidth) {
    /* We now have dimensions for the full-sized photo. */
    new_active = true;

    console.log('activate full');

    this.active_full = true;
    this.photo_x = this.e_full.naturalWidth;
    this.photo_y = this.e_full.naturalHeight;

    if (this.active_thumb) {
      /* The zoom factor was previously based on the thumb dimensions, so
         adjust it now so that the full-sized dimensions retain the same
         effective image size on the screen. */
      var zoom_adjust = this.e_full.naturalWidth / this.e_thumb.naturalWidth;
      this.zoom /= zoom_adjust;
      if (orig_pinch) {
        orig_pinch /= zoom_adjust;
      }
    }

    /* Insert the full-sized image just before the spinner,
       and after the thumbnail (if present). */
    e_spin.insertAdjacentElement('beforebegin', this.e_full);
  }

  if (!this.active_thumb && this.e_thumb.naturalWidth && !this.done_full) {
    /* We now have dimensions for the thumbnail photo, but we only bother
       to display it if the full-size photo is not done. */
    new_active = true;

    console.log('activate thumb');

    this.active_thumb = true;

    /* Only set the photo dimensions if we don't already have them from
       the full-sized photo. */
    if (!this.active_full) {
      this.photo_x = this.e_thumb.naturalWidth;
      this.photo_y = this.e_thumb.naturalHeight;
    }

    /* Insert the thumbnail image at the beginning of e_bg,
       before the full-sized photo (if present) and the spinner. */
    e_bg.insertAdjacentElement('afterbegin', this.e_thumb);
  }

  if (this.done_full) {
    /* The full-sized photo has loaded completely. */
    clear_spinner();

    if (this.active_thumb) {
      /* The thumbnail photo is no longer useful, so we remove it. */
      this.e_thumb.remove();
      this.active_thumb = false;
    }
  } else if (this.e_thumb.complete && this.e_full.complete) {
    /* Both photos have stopped loading, but we the full-sized photo didn't
       load completely ('done_full').  That means that the load of the
       full-sized photo failed or was aborted by the user.  We stop the spinner
       but leave it on-screen to indicate that loading has stopped.  If the
       browser decides later that the photo *is* completely loaded, it'll call
       the 'onload' callback, which clears the spinner. */
    end_spinner();
  }

  if (new_active) {
    /* If history_width has a value, we need to restore the zoom to match
       that width. */
    if (this.history_width) {
      this.zoom = this.history_width / this.photo_x;
      this.history_width = null;
    }

    this.redraw_photo();
  }
}

Photo.prototype.fn_full_onload = function(event) {
  console.log('full-size photo loaded');

  this.done_full = true;

  /* It's possible that a photo finishes loading while the gallery is closed
     or has switched to another photo.  In that case, do *not* respond in
     any way.  If the user switches back to this photo later, we'll rebuild
     the gallery and notice that the image is ready. */
  if (this != obj_photo) {
    return;
  }

  /* The image might have loaded in less than a frame, so it hasn't been
     activated yet.  Since the spinner's polling loop can no longer activate
     it, do it manually here. */
  this.activate_images();
}

Photo.prototype.remove_images = function() {
  /* The gallery is being closed and might be re-opened with any photo,
     so we go ahead and remove this one from its position in e_bg. */
  if (this.active_thumb) {
    this.e_thumb.remove();
    this.active_thumb = false;
  }
  if (this.active_full) {
    this.e_full.remove();
    this.active_full = false;
  }
}

/* Check whether a touch position is inside or outside the photo image. */
Photo.prototype.in_image = function(touch) {
  /* calculate image bounds */
  var img_x = this.photo_x * this.zoom;
  var img_y = this.photo_y * this.zoom;

  var img_x0 = (win_x / 2) - (img_x * this.cx);
  var img_y0 = (win_y / 2) - (img_y * this.cy);

  var img_x1 = img_x0 + img_x;
  var img_y1 = img_y0 + img_y;

  if ((touch.x >= img_x0) &&
      (touch.x < img_x1) &&
      (touch.y >= img_y0) &&
      (touch.y < img_y1)) {
    /* the click was outside the image, so continue processing the click
       on the gallery background. */
    return true;
  }
}

Photo.prototype.click = function(touch) {
  if (!this.in_image(touch)) {
    return false; /* the click hasn't been handled */
  }

  console.log('click in image');

  /* calculate image bounds */
  var img_x = this.photo_x * this.zoom;
  var img_y = this.photo_y * this.zoom;

  /* either zoom to full size, or zoom to fit */
  if (((img_x == win_x) && (img_y <= win_y)) ||
      ((img_x <= win_x) && (img_y == win_y))) {
    /* If the image already fits the screen, zoom the image to full size.
       Do this even if the user dragged the "fit" image, as long as it
       wasn't resized.

       Note that we aim for 1 image pixel = 1 screen pixel.  However, because
       mobile pixels are so tiny, a device may pretend that a measured screen
       pixel is actually multiple physical pixels across.  This works in our
       favor; if it requires multiple physical pixels to display something
       large enough for the user to see, then that's how big we want an image
       pixel to be. */
    this.zoom_to(this, 1.0, touch, touch);
  } else {
    /* For all other zoom levels, zoom to fit.
       the image is larger than full size and can't fit on the screen.
       In these cases, zoom the image to fit the screen.

       Note that a full-size image may be smaller than the screen.
       In this case, the user will see the image as "small", and expect
       a click to zoom to fit.
    */
    this.fit = true;
    /* Once this.fit is true, redraw_photo() does the work for us. */
  }
  this.redraw_photo();
  return true; /* the click has been handled */
}

Photo.prototype.constrain_zoom = function() {
  /* Don't let the image get larger than a maximum size
     unless the screen is even larger. */
  var max_zoom = Math.max(3, this.window_zoom());
  if (this.zoom > max_zoom) {
    this.zoom = max_zoom;
  }

  /* Don't let the image get smaller than a minimum size
     unless the screen is even smaller. */
  /* min_zoom is 100 pixels across the smaller image dimension */
  var min_zoom = Math.max(100 / this.photo_x, 100 / this.photo_y);
  if (this.zoom < min_zoom) {
    console.log('min_zoom =', min_zoom);
    this.zoom = Math.min(min_zoom, this.window_zoom());
  }
}

/* Constrain each edge so that the image remains reasonably visible:
   - if the image is less than half the screen extent, keep the entire
     image visible;
   - otherwise, keep the image on at least half the screen.
*/
Photo.prototype.constrain_pos = function() {
  var img_x = this.photo_x * this.zoom;
  var img_y = this.photo_y * this.zoom;

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

/* Update the image zoom and position while keeping the same part of the
   image under a particular screen location (e.g. where the user is
   pointing).  The input parameters are flexible about the kind of object
   they get, as long as the appropriate parameters are in each object:
   - orig_img can be a photo object or a copy of the photo zoom & position.
   - old_pos and new_pos can be a touch object or pinch distance object.
*/
Photo.prototype.zoom_to = function(orig, new_zoom, old_pos, new_pos) {
  this.fit = false;

  /* Find the part of the image under old_pos, as a fraction of the image
     dimensions.  Typically this would be between 0-1, but is outside that
     range if old_pos is outside the image. */
  var img_x = this.photo_x * orig.zoom;
  var img_y = this.photo_y * orig.zoom;

  var img_x0 = (win_x / 2) - (img_x * orig.cx);
  var img_y0 = (win_y / 2) - (img_y * orig.cy);

  var img_x1 = img_x0 + img_x;
  var img_y1 = img_y0 + img_y;

  /* If the old position is outside the image, zoom relative to a point
     at the image's edge, while maintaining the pixel offset to that edge. */
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

  this.zoom = new_zoom;

  this.constrain_zoom();

  /* Move the image so that the part that was under old_pos (with offset)
     is now under new_pos (with offset). */
  img_x = this.photo_x * this.zoom;
  img_y = this.photo_y * this.zoom;

  img_x0 = (new_pos.x - ox) - (cpx * img_x);
  img_y0 = (new_pos.y - oy) - (cpy * img_y);

  this.cx = ((win_x / 2) - img_x0) / img_x;
  this.cy = ((win_y / 2) - img_y0) / img_y;

  this.constrain_pos();

  this.redraw_photo();
}

/* The code for 2+ touches (pinch) also handles 1 touch (drag)
   as a degenerate case (with no change in zoom). */
Photo.prototype.pinch = function(old_pinch, new_pinch) {
  if (!this.active_thumb && !this.active_full) {
    /* Nothing to pinch/drag yet. */
    return;
  }

  if (!orig_pinch) {
    /* If this is the first pinch movement after an interruption, record
       the pinch parameters in orig_pinch.

       Pinch movements are relative to orig_pinch until interrupted (e.g. by
       pointerup).  The main benefit occurs when the image zoom or position
       hits a limit.  E.g. if the image is dragged to the edge, it stays there
       until the touch returns.  I.e. it doesn't start moving away from the
       edge as soon as the touch starts to return. */
    orig_pinch = old_pinch;

    /* Also remember the image zoom & position.  Thus, pimch changes
       are compared to orig_pinch, and image changes are also applied
       relative to orig_pinch. */
    orig_pinch.zoom = this.zoom;
    orig_pinch.cx = this.cx;
    orig_pinch.cy = this.cy;
  }

  var zoom = orig_pinch.zoom;
  if (orig_pinch.distance != 0) {
    zoom *= new_pinch.distance / orig_pinch.distance;

/*
    console.log('pinch move (' + (new_pinch.x - orig_pinch.x) + ',' + (new_pinch.y - orig_pinch.y), ') with zoom ' + (new_pinch.distance / orig_pinch.distance * 100) + '%');
  } else {
    console.log('drag move (' + (new_pinch.x - orig_pinch.x) + ',' + (new_pinch.y - orig_pinch.y) + ')');
*/
  }

  this.zoom_to(orig_pinch, zoom, orig_pinch, new_pinch);
}

/* Get the zoom level that expands the image as much as possible while
   still fitting in the window dimensions. */
Photo.prototype.window_zoom = function() {
  return Math.min(win_x / this.photo_x, win_y / this.photo_y);
}

Photo.prototype.get_state = function() {
  /* Note that the state records the actual image width rather than the zoom
     factor.  This makes it resiliant if the state gets used across a
     thumbnail/full-size transition.  E.g. the state might record the width
     of the full-sized photo, but a reload causes the thumbnail to be loaded
     first, in which case the 'width' works better for us than the 'zoom'. */
  return {
    'gallery': true,
    'i': this.i,
    'fit': this.fit,
    'width': this.zoom * this.photo_x,
    'cx': this.cx,
    'cy': this.cy
  };
}

var state_timer = null;

Photo.prototype.fn_save_state = function() {
  state_timer = null;
  var state = this.get_state();
  history.replaceState(state, '');
}

Photo.prototype.redraw_photo = function() {
  if (!this.active_thumb && !this.active_full) {
    /* Nothing to redraw. */
    return;
  }

  /* Chrome has a limit of 8 state updates per second to prevent overloading
     the browser.  Redraws can be super fast when the user is dragging the
     photo or dragging the window resize controls, so if we don't throttle
     ourselves, we could lose the last few state changes.  (I'm not sure of
     Chrome's exact algorithm, but it seems like we can perhaps lose up to a
     second worth of data.)

     We throttle ourselves by performing a state update no more often than
     5 times per second.  When we want to update the state, we wait 200 ms
     for any additional state to accumulate, then record the current state
     at that time.  Hopefully the user won't leave or reload the page within
     that 200 ms, but if she does, at least she'll lose less than 200 ms of
     interaction. */
  if (!state_timer) {
    state_timer = setTimeout(this.fn_save_state.bind(this), 200, this);
  }

  if (this.fit) {
    this.zoom = this.window_zoom();

    /* cx,cy determine which part of the photo is centered on the window.
       The units of cx,cy are the fraction of the photo/image dimensions. */
    this.cx = 0.5;
    this.cy = 0.5;
  }

  var img_x = this.photo_x * this.zoom;
  var img_y = this.photo_y * this.zoom;

  var img_x0 = (win_x / 2) - (img_x * this.cx);
  var img_y0 = (win_y / 2) - (img_y * this.cy);

  /* We don't have to set the height since the browser can compute it
     automatically from the width and the image's intrinsic aspect ratio. */
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
  if (obj_photo) {
    console.log(event);
    if (event.key == 'Escape') {
      history.back();
    }
  }
}

/* This call has to be after all gallery-related function definitions.
   It may be slightly helpful to have it prior to all the search-related
   code in case the browser can execute it while the rest of the script
   is downloaded. */
gallery_main();


/*****************************************************************************/
/* code related to the search bar */

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
    /* e_search_input.select(); */ // Not as smooth on Android as desired.
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

/* Global variable so that it can be used by independent events. */
var ac_list;
var ac_selected;

function clear_search() {
  e_search_input.value = '';
  ac_list = [];
  ac_selected = 0;
  hide_ac();
}

/* When comparing names, ignore all non-letter characters and ignore case. */
function compress(name) {
  return name.toUpperCase().replace(/\W/g, '');
}

/* Find the position of the Nth letter in string 'str'.
   I.e. search for N+1 letters, then back up one. */
function find_letter_pos(str, n) {
  var regex = /\w/g;

  for (var i = 0; i <= n; i++) {
    /* We use test() to advance regex.lastIndex.
       We don't bother to check the test() return value because we always
       expect it to match.  (E.g. when finding the last letter of match,
       we really are looking for the last letter, which always exists.) */
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

/* These functions are run only on scientific names, so they only need
   to handle ASCII and not weird Unicode. */
function startsUpper(name) {
  return (name.search(/^[A-Z]/) >= 0);
}

function hasUpper(name) {
  return (name.search(/[A-Z]/) >= 0);
}

/* Get the relative path to a page. */
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

/* Construct all the contents of a link to a page. */
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

  /* I tried this and didn't like it.  If I ever choose to use it, I also
     have to change the behavior of the return key (where fn_url is used). */
  /*if (page_info.x == 'j') {
    target = ' target="_blank" rel="noopener noreferrer"';
  }*/

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

/* Look for a fuzzy match of the user-entered search_str against a value from
   the pages array, match_str.  The "fuzzy" part of the match is that
   punctuation/whitespace is mostly ignored (e.g. "hedgenettle" matches "hedge
   nettle").  In addition, wherever punctuation/whitespace appears in
   search_str, it can skip any number of letters in match_str.  If there is
   a match, return an object with information about the match including its
   priority (higher is better).  If there is no match, return null. */
function check(search_str, match_str, pri_adj) {
  /* search_str has already been converted to upper case, and we keep its
     punctuation intact.  I just copy it to a shorter variable name here for
     convenience. */
  var s = search_str;

  /* m is the string we're trying to match against, converted to uppercase
     and with punctuation removed. */
  var upper_str = match_str.toUpperCase()
  var m = upper_str.replace(/\W/g, '');

  /* If match_str is of the format "<rank> <Name>", get the starting index of
     Name within m.  This assumes that <rank> is all normal letters, so the
     index of Name within m is the same as the index of the ' ' within
     match_str.  If the first word is uppercase (not a rank) or the second word
     is not uppercase (not a scientific name), then the name_pos is set to 0
     instead. */
  var name_pos = match_str.indexOf(' ');
  if ((name_pos < 0) ||
      (match_str.substr(0, 1) == upper_str.substr(0, 1)) ||
      (match_str.substr(name_pos+1, 1) != upper_str.substr(name_pos+1, 1))) {
    name_pos = 0;
  }
  

  /* match_ranges consists of [start, end] pairs that indicate regions in m for
     which a match was made */
  var match_ranges = [];

  /* i and j are the current position indexes into s and m, respectively */
  var i = 0;
  var j = 0;

  while (true) {
    /* find the first letter character in s */
    while ((/\W/.test(s.substr(i, 1))) && (i < s.length)) {
      i++;
    }
    var start_i = i;

    if (i == s.length) {
      break; // match complete
    }

    /* find end of letter characters */
    while ((/\w/.test(s.substr(i, 1))) && (i < s.length)) {
      i++;
    }

    var s_word = s.substring(start_i, i);
    var start_j = m.indexOf(s_word, j);
    if (start_j == -1) {
      return null; // no match
    }
    j = start_j + (i - start_i);
    if (match_ranges.length &&
        (match_ranges[match_ranges.length-1][1] == start_j)) {
      /* The next match follows directly from the previous match without
         skipping any letters.  (It might skip punctuation.)  Instead of
         adding a new match range, simply extend the previous one. */
      match_ranges[match_ranges.length-1][1] = j;
    } else {
      match_ranges.push([start_j, j]);
    }
  }

  /* Start with a priority high enough that the various decrements probably
     won't reduce it below 0.  (Although I'm not sure if that matters. */
  var pri = 100.0;

  pri += pri_adj;

  /* Decrease the priority a bit depending on how many different ranges are
     required to complete the match. */
  pri -= (match_ranges.length / 10);

  /* Increase the priority a bit if the first match range is at the start
     of the string.  The bump means that a match that starts at the
     beginning and has two match ranges is slightly better than one that
     starts later and has only one match range.  E.g. "gland glossary"
     matches "gland (plant glossary)" better than "England (glossary)".

     If the match starts after the rank but at the beginning of actual
     name, that's prioritized the same as a match at the beginning of
     the string. */
  if ((match_ranges[0][0] == 0) ||
      (match_ranges[0][0] == name_pos)) {
    pri += 0.15;
  }

  /* Construct an object with the necessary information about the match. */
  var match_info = {
    pri: pri,
    match_str: match_str,
    match_ranges: match_ranges
  }

  return match_info;
}

/* Check whether match_info one has greater priority than two.
   Either value can be null, which is considered lowest priority. */
function better_match(one, two) {
  return (one && (!two || (one.pri > two.pri)));
}

/* For a list of names for a page, call check() on each name and each
   combination of glossary term and page name.  Return the best match. */
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
      /* Allow a genus to match using the older 'spp.' style. */
      match_info = check(search_str, name.substr(6) + ' spp.');
    }
    if (better_match(match_info, best_match_info)) {
      best_match_info = match_info;
    }

    /* Secondary names have slightly reduced priority.  E.g. a species
       that used to share a name with another species can be found with
       that old name, but the species that currently uses the name
       is always the better match.  So we adjust the priority slightly
       for all names in the match_list after the first. */
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

/* Using the match_info constructed in check(), highlight the matched
   ranges within the matched string.  Or if match_info is null (because
   the other com/sci name of a page was matched), return default_name
   without highlighting.

   In either case, if it's a scientific name, italicize the Greek/Latin
   words (either the whole string or everything after the first word). */
function highlight_match(match_info, default_name, is_sci) {
  var tag_info = [];

  /* h is the highlighed string to be returned. */
  var h = '';

  if (match_info) {
    var m = match_info.match_str;
    var match_ranges = match_info.match_ranges;

    /* Convert match_ranges (which ignores punctuation) into string positions
       (which includes punctuation). */
    var ranges = [];
    for (var i = 0; i < match_ranges.length; i++) {
      var begin = find_letter_pos(m, match_ranges[i][0]);

      /* Stop highlighting just after letter N-1.  I.e. don't include
         the punctuation between letter N-1 and letter N, which is the
         first letter outside the match range. */
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
    /* Rather than writing special code to handle italicization of the
     * scientific name for this default case, we can simply fall through the
     * regular highlighting code with no highlighted ranges. */
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

  /* Keep track of tag nesting, because interleaved tags fail in some browsers.
     E.g. <i>x<span>y</i>z</span> on Chrome moves </span> to before </i>. */
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
      h += info.tag[0]; // open tag
      nest.push(info); // record its nesting level
    } else {
      /* close the tags that are nested within the tag we want to close */
      for (i = nest.length-1; nest[i] != info; i--) {
        h += nest[i].tag[1];
      }

      /* close the tag that we wanted to close */
      h += nest[i].tag[1];

      /* remove the closed tag from the nesting list */
      nest.splice(i, 1);

      /* re-open the previously nested tags */
      for (i = i; i < nest.length; i++) {
        h += nest[i].tag[0];
      }
    }

    info.half++;
    if (info.half == 2) {
      info.half = 0;
      info.i++;
      if (info.i == info.ranges.length) {
        /* remove entry from tag_info */
        tag_info.splice(info_idx, 1);
      }
    }
  }

  h += m.substring(pos);

  return h;
}

function insert_match(fit_info) {
  /* If there's a match, and
     - we don't already have 10 matches or
     - the new match is better than the last match on the list
     then remember the new match. */
  if ((ac_list.length < 10) || (fit_info.pri > ac_list[9].pri)) {
    /* Insert the new match into the list in priority order.  In case of
       a tie, the new match goes lower on the list. */
    for (var j = 0; j < ac_list.length; j++) {
      if (fit_info.pri > ac_list[j].pri) break;
    }
    ac_list.splice(j, 0, fit_info);
    /* If the list was already the maximum length, it is now longer than the
       maximum length.  Cut off the last entry. */
    if (ac_list.length > 10) {
      ac_list.splice(-1, 1);
    }
  }
}

/* Check for search matches in one page:
   - in its common name
   - in its scientific name
   - in its glossary terms */
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

    /* If there was a match on a page name, don't clutter up the auto-complete
       list with matches on its glossary terms. */
    return;
  }

  if ('glossary' in page_info) {
    /* We're willing to add one auto-complete entry for each separate anchor.
       We use the best fit among all terms associated with that anchor in
       combination with all page names. */
    var best_match_info = null;
    for (var j = 0; j < page_info.glossary.length; j++) {
      var glossary = page_info.glossary[j];

      /* Find the best match associated with glossary.anchor. */
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

/* Search all pages for a fuzzy match with the value in the search field, and
   create an autocomplete list from the matches. */
function fn_search() {
  /* We compare uppercase to uppercase to avoid having to deal with case
     differences anywhere else in the code.  Note that this could fail for
     funky unicode such as the German Eszett, which converts to uppercase 'SS'.
     I'll deal with it if and when I ever use such characters in a name. */
  var search_str = e_search_input.value.toUpperCase();

  /* We need at least one letter to do proper matching. */
  if (!/\w/.test(search_str)) {
    hide_ac();
    return;
  }

  /* Iterate over all pages and accumulate a list of the best matches
     against the search value. */
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
    /* escape the quote mark in the regex to avoid confusing strip.py */
    full = full.replace(/\'/g, '&rsquo;');

    /* The link is applied to the entire paragraph so that padding above
       and below and the white space to the right are also clickable. */
    fit_info.html = ('<a ' + link + '><p class="nogap">' +
                     full + '</p></a>');
  }

  /* Highlight the first entry in bold.  This entry is selected if the
     user presses 'enter'. */
  ac_selected = 0;
  generate_ac_html();
  expose_ac();
}

/* A link to an anchor might go somewhere on the current page rather than
   going to a new page.  If the page doesn't change, the search will
   remain active.  That's not what we want, so we clear the search before
   continuing with the handling of the clicked link.  Note that the event
   is already known to be interacting with the link, so removing the
   autocomplete box with the link in it will still allow the click to
   activate the link as desired. */
function fn_click() {
  clear_search();
  return true; // continue normal handling of the clicked link
}

/* Handle all changes to the search value.  This includes changes that are
   not accompanied by a keyboard event, such as a mouse-based paste event. */
function fn_change() {
  fn_search();
}

/* Handle when the user presses various special keys in the search box.
   The default behavior for the arrow keys triggers on keydown, so at the
   very least we need to capture and suppress that behavior.  I also notice
   that the browser performs normal actions for all other keys on keydown.
   So it makes sense to also have my behavior trigger on keydown for
   consistency. */
function fn_keydown() {
  if ((event.key == 'Enter') && !ac_is_hidden && ac_list.length) {
    var fit_info = ac_list[ac_selected];
    var url = fn_url(fit_info);
    if (event.shiftKey || event.ctrlKey) {
      /* Shift or control was held along with the enter key.  We'd like to
         open a new window or new tab, respectively, but JavaScript doesn't
         really give that option.  So we just call window.open() and let the
         browser make the choise.  E.g. Firefox will only open a new tab
         (after first requiring the user to allow pop-ups), while Chrome will
         open a new tab if ctrl is held or a new window otherwise.  Nice! */
      window.open(url);
    } else {
      /* The enter key was pressed *without* the shift or control key held.
         Navigate to the new URL within the existing page. */
      window.location.href = url;
    }
    /* Opening a new window doesn't affect the current page.  Also, a
       search of the glossary from a glossary page might result in no
       page change.  In either case, the search will remain active,
       which is not what we want.  In either case, clear the search. */
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

/* We want to trigger hide_ac whenever the user clicks somewhere that
   **isn't** the search field or autocomplete box.  I used to create a
   div containing everything except the search stuff, but the extra div
   is inelegant, and it still leaves places to click around the edges of
   the window that cause focus to be lost, but the div event isn't triggered.

   So now I trigger an event for the entire document, then exclude the
   search field and autocomplete box within the event handler.

   'mousedown' triggers an event on the scrollbar, but it doesn't remove
   focus from the search field.  That's awkward because I can't quickly
   find a way to ignore that event.  But 'click' doesn't trigger on the
   scrollbar, so that's what I use. */
document.addEventListener('click', fn_doc_click);

/* On Android Firefox, if the user clicks an autocomplete link to navigate
   away, then hits the back button to return to the page, the search field
   is cleared (good), but the autocomplete box remains visible and populated
   (bad).  This code fixes that. */
window.addEventListener('beforeunload', fn_focusout);

/* When entering the page or when changing anchors within a page,
   set the window title to "anchor (page title)". */
function fn_hashchange(event) {
  hide_ac();

  /* If the current title already has an anchor in it, throw away
     the anchor and keep just the last part, the original page title. */
  var title_list = document.title.split(' - ');
  var title = title_list[title_list.length - 1];

  /* If the URL has a hash, get the anchor portion of it and put it before
     the original page title.
     There is an exception for 'offline', which is not a typical anchor. */
  var hash = location.hash;
  if (hash && (hash != '#offline')) {
    document.title = decodeURIComponent(hash).substring(1) + ' - ' + title;
  }
}

/* Determine whether to add 'html/' to the URL when navigating to a page. */
if (window.location.pathname.includes('/html/')) {
  var path = '';
} else {
  var path = 'html/';
}

/* main() kicks off search-related activity once it is safe to do so.
   See further below for how main() is activated. */
function main() {
  console.info('main')

  /* Make sure the page elements are ready. */
  if (document.readyState === 'loading') {
    console.info('...main too early')
    document.addEventListener('DOMContentLoaded', main);
    return
  }

  /* normalize the data in the pages array. */
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

  /* Set the window title when entering the page (possibly with an anchor)... */
  fn_hashchange();

  /* ... or when changing anchors within a page. */
  window.addEventListener('hashchange', fn_hashchange);

  /* In case the user already started typing before the script loaded,
     perform the search right away on whatever is in the search field,
     but only if the focus is still in the search field.

     If the search field is (still) empty, fn_search() does nothing. */
  if (Document.activeElement == e_search_input) {
    fn_search();
  }

  /* Also initialize the photo gallery. */
  gallery_main();
}

/* main() is called when either of these two events occurs:
   we reach this part of search.js and the pages array exists, or
   we reach the end of pages.js and the main function exists.
*/
if (typeof pages !== 'undefined') {
  main();
}


/*****************************************************************************/
/* Show/hide observation details. */

function fn_details(event) {
  console.log(event);
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

/* Pressing 'enter' when the toggle is focused does the same as a mouse click
   in order to support accessibility requirements. */
function fn_details_keydown(event) {
  console.log(event);
  if ((event.key == 'Enter') ||
      (event.key == ' ') ||
      (event.key == 'Spacebar')) {
    fn_details(event);
    event.preventDefault();
  }
}
