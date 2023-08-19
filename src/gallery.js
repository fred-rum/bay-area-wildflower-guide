/* Copyright Chris Nelson - All rights reserved. */

'use strict';

/*****************************************************************************/
/* code related to the photo gallery */

/* fresh is 'true' only for the first call to main() */
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
var e_bg = document.getElementById('gallery-background');

/* e_ui_l and e_ui_r are the left/right UI arrows for switching among photos */
var e_ui_l = document.getElementById('gallery-ui-left');
var e_ui_r = document.getElementById('gallery-ui-right');

/* e_spin is the canvas where the spinning 'loading' icon is drawn.
   The canvas is created once and then drawn or cleared as desired. */
var e_spin = document.getElementById('gallery-spinner');

/* spin_req represents the request for the next animation frame when the
   spinner is spinning.  It can be used to cancel the request and stop the
   spinner. */
var spin_req = null;

/* spin_timestamp indicates the time of the last spinner update.  This helps
   determine how far the spinner should rotate the next time it is drawn. */
var spin_timestamp = performance.now();

/* spin_offset indicates the current spin position, as the fraction (0.0-1.0)
   of a 360-degree clockwise rotation from the default orientation. */
var spin_offset = 0;

/* The touches array keeps track of active pointers, i.e. a mouse with the
   left button pressed and any finger or stylus touching the screen. */
var touches = [];

/* click_target tracks the initial target of a pointerdown until a
   corresponding pointerup occurs.  Because the gallery background (e_bg)
   captures the pointer during the click duration, the pointerup event always
   lists e_bg as the target, which is why we record the original target here.
   If anything interrupts the click (e.g. pointer movement or extra touches),
   we reset click_target to null. */
var click_target;
var click_x;
var click_y;
var click_time;

/* orig_pinch remembers data about how the current multi-touch started.
   Movements of the touch points can be compared against this original. */
var orig_pinch;

/* win_x and win_y keep track of the current viewport dimentions.  These are
   updated on a resize event.  These values can be queried at any time, but
   I need them in so many parts of the code that it's easier to just maintain
   them as global values. */
var win_x, win_y;


/* This script is loaded with the 'defer' property, so the DOM is guaranteed
   to be ready when the script executes. */
function main() {
  /* Extract the encoded photo path from the 'search' portion of the URL
     (after the '?'), then find the page with a matching path.
     Note that the encoded path has a few character substitutions to avoid
     percent encoding.  I.e. '/' and ' ' are encoded as '-', and ',' is
     encoded as '.' */
  var first_photo_name = window.location.search;
  if (first_photo_name) {
    first_photo_name = decodeURIComponent(first_photo_name.substring(1))
  } else {
    first_photo_name = 'invalid'
  }

  for (var i = 0; i < pages.length; i++) {
    /* Each entry in pages[] is a list.

       The first list entry is the name of the page that includes
       one or more photos.

       The remainder of the list has the relative path to each file
       associated with the page.  But if the photo is in the 'photos'
       subdirectory, then the following optimizations reduce the size of
       the string to save bandwidth:
       - 'photos/' at the beginning of the file path is removed.
       - if the base name of the file is the same as the previous base name,
         it is omitted, along with the following comma.  The initial base name
         is taken to be the page name.
      - '.jpg' at the end of the file path is removed.
      The best optimized relative path is reduced down to just the photo
      suffix.  If this suffix is just a decimal number, it is encoded as
      a Javascript number instead of a string to avoid spending bandwidth on
      qutation marks.
    */
    var list = pages[i];

    var page_name = list[0];
    var base_name = page_name;

    /* Build up the list of photo URLs (relative photo paths) for all photos
       associated with a page; if any of them match the first_photo_name,
       the gallery will include all of these. */
    var photo_urls = [];

    var match_idx = 0;
    for (var j = 1; j < list.length; j++) {
      var photo_name = String(list[j]);

      if (!photo_name.includes('/')) {
        var comma_pos = photo_name.search(',');
        if (comma_pos == -1) {
          /* Expand the photo name from the existing base name. */
          photo_name = base_name + ',' + photo_name;
        } else {
          /* The photo name is complete and includes a new base name. */
          base_name = photo_name.substring(0, comma_pos);
        }
        photo_name = 'photos/' + photo_name + '.jpg';
      }

      photo_urls.push(photo_name);

      /* The photo path from the list is re-encoded in the same way as the
         one extracted from the URL before checking for a match. */
      var photo_name = munge_photo_for_url(photo_name);

      if (first_photo_name == photo_name) {
        /* Remember which photo on the page had the match, then continue
           through the page's list to finish populating photo_urls. */
        match_idx = j;
      }
    }

    if (match_idx) {
      break;
    }
  }

  if (i == pages.length) {
    /* no match, so just make something up that will probably fail to display */
    page_name = first_photo_name;
    photo_urls = [first_photo_name];
    match_idx = 1;
  }

  document.title = 'gallery - ' + page_name;

  for (var i = 0; i < photo_urls.length; i++) {
    var obj = new Photo(i, photo_urls[i])
    obj_photos.push(obj);
  }

  /* maintain the window dimensions for quick access */
  win_x = window.innerWidth;
  win_y = window.innerHeight;
  window.addEventListener('resize', fn_resize);

  /* The gallery doesn't have an input field that can have key focus,
     so we look for keypresses in the entire window. */
  window.addEventListener('keydown', fn_gallery_keydown);

  i = match_idx - 1;
  if (history.state) {
    console.log('restoring photo state');
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
  /* After any change in the image display, record its state so that it can
     be restored after browser navigation.

     Chrome has a limit of 8 state updates per second to prevent overloading
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
    state_timer = setTimeout(fn_save_state, 200);
  }
}

function fn_save_state() {
  state_timer = null;

  obj_photo.save_state();
}

function fn_spin(timestamp) {
  /* We won't get another fn_spin() call unless we request another. */
  spin_req = null;

  /* activate_images() polls the photo loading status and runs or stops the
     spinner as appropriate.  We don't bother to pass in the timestamp
     because activate_images() can be called from places that don't have one,
     so it has to call performance.now() anyway. */
  obj_photo.activate_images();
}

function draw_spinner(stopped) {
  var hz = 1.0; /* revolutions per second */
  var n = 7; /* number of circles in the spinner */
  var r_ring = 40; /* outer radius of the spinner as a whole */
  var r_circle = 10; /* radius of each circle within the spinner */

  /* calculate how much to spin the spinner */
  var timestamp = performance.now();
  var elapsed = timestamp - spin_timestamp;
  spin_timestamp = timestamp;

  var inc = elapsed / 1000 * hz;
  inc = Math.min(inc, 1 / n); /* don't spin by more than one circle position */
  spin_offset = (spin_offset + inc) % n;

  /* draw the spinner */
  var ctx = e_spin.getContext('2d');
  ctx.clearRect(0, 0, 100, 100);
  for (var i = 0; i < n; i++) {
    var c = Math.floor(i * 255 / (n-1));
    if (stopped) {
      /* red through deep red, patially transparent */
      ctx.fillStyle = 'rgb(' + (c / 255 * 155 + 100) + ',0,0,0.70)';
    } else {
      /* white through black, fully opaque */
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
  console.log('clear spin');

  /* We could remove the spinner's canvas element, but then we'd have to
     restore it if we switch to another photo.  So instead we leave the canvas
     in place, but clear its contents. */
  var ctx = e_spin.getContext('2d');
  ctx.clearRect(0, 0, 100, 100);
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
  console.log(event.target, event.target == e_ui_l);

  if (touches.length == 1) {
    click_target = event.target;
    click_x = touches[0].x;
    click_y = touches[0].y;
    click_time = performance.now();
  } else {
    click_target = null;
  }

  /* reset the starting pinch/drag location */
  orig_pinch = undefined;

  /* We don't care if the pointerdown event propagates, but if I return false
     here, Firefox on Android suddenly can't generate pointermove events for
     two touches that are moving at the same time. */
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
     followed by pointer down with minimal time and movement in between. */
  const max_click_time = 300; // ms
  if (obj_photo && click_target && discard_touch(touch) &&
      (performance.now() - click_time <= max_click_time)) {
    /* There was a single click with no drag while the gallery is open. */
    console.log('click on', click_target);

    /* Apply the appropriate action based on the target of the click.
       Note that if the user is fast and the browser is slow, the target
       may be out of date, particularly for the left and right arrows. */
    if (click_target == e_ui_l) {
      obj_photo.go_left();
    } else if (click_target == e_ui_r) {
      obj_photo.go_right();
    } else if ((click_target == obj_photo.e_thumb) ||
               (click_target == obj_photo.e_full)){
      obj_photo.click.call(obj_photo, touch);
    } else {
      /* The click was in the background or on the 'X', so we return to the
         normal page view.  We could close the gallery directly, but since
         opening the gallery pushed an entry to the browser's history, we want
         to pop back up the history.  Since there is already code to restore
         the proper state when the user navigates back through the history, the
         rest is automatic. */
      /* Unfortunately, Firefox on Android has a bug that if we go back while
         the click is still being processed, any link that appears under the
         user's finger gets followed.  This is true even with preventDefault(),
         stopPropagation(), stopImmediatePropagation(), and return false.  It
         also occurs even with a 0ms timeout, which is ridiculous.  A delay of
         50ms seems to solve the problem for me.  Who knows if it will work
         for everyone.  I can't find any reference to this bug on the
         internet. */
      setTimeout(go_back, 50);
    }
    return true;
  }

  console.log('pointer up:', touches.length);
}

/* If the browser is slow to go back (e.g. because loading the previous page is
   slow), the user can tap to go back more than once.  Chrome on Android has a
   bug that if history.back() is called more than once, it doesn't go back one
   page *relative to the current page*, but instead goes back two pages.  So we
   have to suppress additional calls after the first one. */
var go_back_in_progress = false;
function go_back() {
  console.log('go back:', go_back_in_progress);
  if (!go_back_in_progress) {
    go_back_in_progress = true;
    history.back();
  }
}

/* If the user comes back to this page (e.g. with the forward button), we
   need to re-enable go_back() again. */
addEventListener('pageshow', fn_return);
function fn_return() {
  go_back_in_progress = false;
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

  var touch = copy_touch(event);

  var i = touch_index(touch);
  if (i == -1) {
    /* e.g. the mouse was moved while separately
       a finger was touching the screen */
    return;
  }

  if ((touches[i].x == touch.x) &&
      (touches[i].y == touch.y)) {
    /* Android likes to activate pointermove even when no measurable
       movement occurred.  Don't waste time processing it. */
    return;
  }

  /* A touching pointer moved. */
  const diff_x = touches[i].x - click_x;
  const diff_y = touches[i].y - click_y;
  const max_click_move = 10;
  if (diff_x * diff_x + diff_y * diff_y > max_click_move * max_click_move) {
    click_target = null;
  }

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

/* This function must exactly match what is in search.js. */
function munge_photo_for_url(path) {
  /* Remove directory name, e.g. 'photos/'. */
  var slash_pos = path.indexOf('/')
  if (slash_pos != -1) {
    path = path.substring(slash_pos+1);
  }

  /* Remove extension, e.g. '.jpg'. */
  var dot_pos = path.indexOf('.')
  if (dot_pos != -1) {
    path = path.substring(0, dot_pos);
  }

  /* Convert common characters that must be percent-encoded to characters
     that are allowed after the '?' in the URL. */
  path = path.replace(/[/ ,/]/g, function (c) {
    return {
      '/': '-',
      ' ': '-',
      ',': '.'
    }[c];
  });

  /* Remove characters that must be percent-encoded. */
  path = path.replace(/[^A-Za-z0-9-.]/g, '');

  return path;
}

function Photo(i, url_full) {
  console.log('initializing photo', url_full);

  this.i = i;
  this.url_full = url_full;
  console.log(this.url_full);

  /* svg files don't have thumbnails (yet) */
  this.is_svg = /\.svg$/.test(url_full);
  if (!this.is_svg) {
    this.url_thumb = url_full.replace(/^photos\/|^figures\//, 'thumbs/')
    console.log(this.url_thumb);
  }

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
  this.done_thumb = null;
  this.done_full = null;
}

Photo.prototype.init_photo = function() {
  /* fit indicates whether the image size matches the window size */
  this.fit = true;

  /* img_x indicates the pixel width of the image.
     img_y is implied by img_x and the image's native aspect ratio. */
  this.img_x = null; /* doesn't matter when fit = true */

  /* cx,cy indicates which part of the photo is centered on the window.
     The units of cx,cy are the fraction of the photo/image dimensions.
     The user can change these values by dragging the image while 'fit'
     remains 'true'.  I judge this to be slightly preferable from a UX
     perspective, but it also means that a bit of accidental drag while
     clicking doesn't change the click-to-zoom behavior. */
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

  /* e_thumb and e_full are always create together, so we only need to check
     whether either one is present.  If the photos have already been created,
     we don't need to create them again. */
  if (!this.e_thumb) {
    /* This photo has never been opened in the gallery before.  We create the
       necessary DOM elements here, but we'll have to wait for the thumbnail
       and full-sized photo to load. */

    if (!this.is_svg) {
      this.e_thumb = document.createElement('img');
      this.e_thumb.className = 'gallery-photo';
      this.e_thumb.setAttribute('draggable', 'false');

      /* By setting the event handlers before setting the img src value,
         we guarantee that the img isn't loaded yet. */
      this.e_thumb.addEventListener('load', this.fn_img_result.bind(this));
      this.e_thumb.addEventListener('error', this.fn_img_result.bind(this));

      /* The thumb-sized photo is the same as e_thumbnail.  Unfortunately,
         there's no way to simply copy the thumbnail image from the original
         page.  We can only hope that the browser has cached the JPG file and
         can re-create the image quickly. */
      this.e_thumb.src = encodeURI(this.url_thumb);
    }

    this.e_full = document.createElement('img');
    this.e_full.className = 'gallery-photo';
    this.e_full.setAttribute('draggable', 'false');

    /* By setting the event handlers before setting the img src value,
       we guarantee that the img isn't loaded yet. */
    this.e_full.addEventListener('load', this.fn_img_result.bind(this));
    this.e_full.addEventListener('error', this.fn_img_result.bind(this));

    /* 'onloadend' isn't well supported yet, so there's no callback if
       the photo fails to load.  Instead, we poll for that condition in
       the spinner. */

    /* The full-sized photo is the target of the original link.  BTW, this
       event handler ultimately suppresses further handling of the click, so
       when the photo galleyr is opened, the original link doesn't get
       activated. */
    this.e_full.src = encodeURI(this.url_full);

    if (this.is_svg) {
      /* Firefox doesn't populate naturalWidth and naturalHeight for an SVG,
         so we have to display it first, then query its dimensions. */
      e_spin.insertAdjacentElement('beforebegin', this.e_full);
    }

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

  console.log('done:', this.done_full, 'active:', this.active_full, 'width:', this.e_full.width);

  if (!this.active_full && (this.e_full.naturalWidth ||
                            (this.is_svg && this.e_full.width))) {
    /* We now have dimensions for the full-sized photo. */
    new_active = true;

    console.log('activate full');

    this.active_full = true;

    if (this.is_svg) {
      /* An SVG doesn't have real pixel dimensions, so instead we allow it
         to scale as if it has a long axis of 2048 pixels. */
      console.log('dim:', this.e_full.width, this.e_full.height);
      var ar = this.e_full.width / this.e_full.height;
      this.photo_x = Math.min(2048, 2048 * ar);
      this.photo_y = Math.min(2048, 2048 / ar);
      this.e_full.style.backgroundColor = 'white';
      /* In the case of an SVG, the image element is already added to the
         DOM. */
    } else {
      this.photo_x = this.e_full.naturalWidth;
      this.photo_y = this.e_full.naturalHeight;
      if (!this.active_thumb) {
        this.e_full.style.backgroundColor = '#808080';
      }

      /* Insert the full-sized image just before the spinner,
         and after the thumbnail (if present). */
      e_spin.insertAdjacentElement('beforebegin', this.e_full);
    }
  }

  if (!this.is_svg && !this.active_thumb && this.e_thumb.naturalWidth &&
      (this.done_full != 'load')) {
    /* We now have dimensions for the thumbnail photo, but we only bother
       to display it if the full-size photo is not done. */
    new_active = true;

    console.log('activate thumb');

    this.active_thumb = true;

    /* Only set the photo dimensions if we don't already have them from
       the full-sized photo. */
    if (this.active_full) {
      this.e_full.style.backgroundColor = 'transparent';
    } else {
      this.photo_x = this.e_thumb.naturalWidth;
      this.photo_y = this.e_thumb.naturalHeight;
    }
    this.e_thumb.style.backgroundColor = '#808080';

    /* Insert the thumbnail image at the beginning of e_bg,
       before the full-sized photo (if present) and the spinner. */
    e_bg.insertAdjacentElement('afterbegin', this.e_thumb);
  }

  if (new_active) {
    this.redraw_photo();
  }

  /* If done_full is 'load', then then a JPG image necessarily has a
     naturalWidth, so active_full is true.  However, an SVG image may still be
     rendering, so it doesn't yet have a width.  In that case, keep spinning
     until we can get its width and height.  (Maybe I got confused and that
     didn't really happen, but in any case the extra check shouldn't hurt.) */
  if ((this.done_full == 'load') && this.active_full) {
    /* The full-sized photo has loaded completely. */
    clear_spinner();
    end_spinner();

    if (this.active_thumb) {
      /* The thumbnail photo is no longer useful, so we remove it. */
      this.e_thumb.remove();
      this.active_thumb = false;
    } else if (!this.is_svg){
      this.e_full.style.backgroundColor = 'transparent';
    }
  } else if ((this.done_full == 'error') && (this.done_thumb != null)) {
    /* The full-sized photo has an error and the thumbnail is complete. 
       Turn the spinner red and end its spinning. */
    draw_spinner(true);
    end_spinner();
  } else {
    /* The spinner continues spinning, either gray or red. */
    draw_spinner(this.done_full == 'error');

    /* Run the spinner (or continue running it). */
    if (!spin_req) {
      spin_req = window.requestAnimationFrame(fn_spin);
    }
  }
}

Photo.prototype.fn_img_result = function(event) {
  console.log('img load result:', event.type, event.target);

  if (event.target == this.e_full) {
    this.done_full = event.type;
  } else {
    this.done_thumb = event.type;
  }
    

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

Photo.prototype.close_photo = function() {
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

/* Calculate the image height from its width and aspect ratio. */
Photo.prototype.img_y = function() {
  return this.img_x / this.photo_x * this.photo_y;
}

Photo.prototype.click = function(touch) {
  console.log('click in image');

  /* either zoom to full size, or zoom to fit */
  if (this.fit) {
    /* If the image already fits the screen, zoom the image to full size.
       Note that a full-size image may be smaller a fitted image.

       Note that we aim for 1 image pixel = 1 screen pixel.  However, because
       mobile pixels are so tiny, a device may pretend that a measured screen
       pixel is actually multiple physical pixels across.  This works in our
       favor; if it requires multiple physical pixels to display something
       large enough for the user to see, then that's how big we want an image
       pixel to be. */
    this.zoom_to(this, this.photo_x, touch, touch);
  } else {
    /* For all other zoom levels, zoom to fit. */
    this.fit = true;
    this.cx = 0.5;
    this.cy = 0.5;
    this.redraw_photo();
  }
  return true; /* the click has been handled */
}

Photo.prototype.constrain_zoom = function() {
  /* Don't let the image get larger than a maximum size
     unless the screen is even larger. */
  var max_width = Math.max(this.photo_x * 3, this.fit_width());
  if (this.img_x > max_width) {
    this.img_x = max_width;
  }

  /* min_width is 100 pixels or
     the width that causes the height to be 100 pixels */
  var min_width = Math.max(100, 100 * this.photo_x / this.photo_y);
  if (this.img_x < min_width) {
    /* Don't let the image get smaller than a minimum size
       unless the screen is even smaller. */
    this.img_x = Math.min(min_width, this.fit_width());
  }
}

/* Constrain each edge so that the image remains reasonably visible:
   - if the image is less than half the screen extent, keep the entire
     image visible;
   - otherwise, keep the image on at least half the screen.
*/
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

/* Update the image zoom and position while keeping the same part of the
   image under a particular screen location (e.g. where the user is
   pointing).  The input parameters are flexible about the kind of object
   they get, as long as the appropriate parameters are in each object:
   - orig_img can be a photo object or a copy of the photo zoom & position.
   - old_pos and new_pos can be a touch object or pinch distance object.
*/
Photo.prototype.zoom_to = function(orig, new_width, old_pos, new_pos) {
  if (new_width != this.img_x) {
    this.fit = false;
  }

  /* Find the part of the image under old_pos, as a fraction of the image
     dimensions.  Typically this would be between 0-1, but is outside that
     range if old_pos is outside the image. */
  var img_x = this.img_x;
  var img_y = this.img_y();

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

  this.img_x = new_width;

  this.constrain_zoom();

  /* Move the image so that the part that was under old_pos (with offset)
     is now under new_pos (with offset). */
  img_x = this.img_x;
  img_y = this.img_y();

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

/* Get the zoom level that expands the image as much as possible while
   still fitting in the window dimensions. */
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
  const munged_url = munge_photo_for_url(this.url_full);
  const url = window.location.pathname + '?' + munged_url;

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
    /* Nothing to redraw. */
    return;
  }

  save_state();

  console.log('redraw:', this.fit);

  if (this.fit) {
    this.img_x = this.fit_width();
  }

  var img_x = this.img_x;
  var img_y = this.img_y();

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
  console.log('resize')
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
  console.log(event);

  var center_touch = {
    x: win_x/2,
    y: win_y/2
  };

  if ((event.key == 'Escape') ||(event.key == 'Esc')) {
    history.back();
    /* In Chrome on Windows, the escape key potentially interrupts the
       Javascript and prevents history.back() from executing.  Calling
       event.preventDefault() seems to prevent this problem and allow
       the browser to go back reliably as expected. */
    event.preventDefault();
  } else if ((event.key == 'Enter') ||
             (event.key == ' ') || (event.key == 'Spacebar')) {
    /* On 'enter' or 'space', either zoom to fit or zoom to full scale.
       Note that zoom to full scale is always coming from a 'fit' image.
       We act as if the mouse was clicked in the center, so the zoom is
       always to the center of the photo. */
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

/* This call has to be after all gallery-related function definitions. */
main();
