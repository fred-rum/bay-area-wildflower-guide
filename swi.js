/* This script implements the service worker interface (swi).  It runs in the
   context of each browser tab and connects to the (single) service worker
   instance.  It performs 3 main duties:
   - It registers the service worker.
   - It sends user directives to the service worker.
   - It polls the service worker status and displays it for the user.

   Because the status worker can be communicating with multiple copies of
   swi.js at the same time, I put as little logic in swi.js as possible.
   It blindly sends requests to sw.js (even if it looks like the request
   should get ignored), and it reports whatever status comes from sw.js
   without interpretation.

   swi.js has two types of pages that it interacts with:
   - the home page, with an 'update' button and a 'delete' button and lots
     of progress information.
   - all other pages, with a potential 'hazard' icon that links back to
     the home page when an update is available.
*/

'use strict';

var e_update;
var e_progress;
var e_status;
var e_err_status;

var e_clear;
var e_usage;
var e_extra;

var e_top_msg = {};
var e_red_missing;

var e_body;
var e_icon;

var pollID;

// old_msg is initialized to a dict, so when receive_status() looks for
// changes, every old value appears to be undefined.
var old_msg = {};

var old_icon;

var wakelock;

const POLL_INTERVAL_MS = 500; // poll interval in milliseconds
var polls_since_response;
var timed_out = false;

var root_path;

/* If the readyState is 'interactive', then the user can (supposedly)
   interact with the page, but it may still be loading HTML, images,
   or the stylesheet.  In fact, the page may not even be rendered yet.
*/
async function swi_oninteractive() {
  if (document.readyState !== 'complete') {
    window.addEventListener('load', swi_oninteractive);
    return
  }
  console.info('swi_oninteractive()');

  e_update = document.getElementById('update');
  if (e_update) {
    e_progress = document.getElementById('progress');
    e_status = document.getElementById('status');
    e_err_status = document.getElementById('err-status');

    e_clear = document.getElementById('clear');
    e_usage = document.getElementById('usage');
    e_extra = document.getElementById('extra');

    e_top_msg['green'] = document.getElementById('cache-green');
    e_top_msg['yellow'] = document.getElementById('cache-yellow');
    e_top_msg['online'] = document.getElementById('cache-online');

    e_red_missing = document.getElementById('red-missing');

    e_status.innerHTML = 'Waiting for the service worker to load';
  } else {
    e_body = document.getElementById('body');
  }

  if (window.location.pathname.includes('/html/')) {
    root_path = '../';
  } else {
    root_path = '';
  }

  if (navigator.serviceWorker) {
    navigator.serviceWorker.addEventListener('controllerchange', fn_controllerchange);

    if (e_update) {
      e_update.addEventListener('click', fn_update);
      e_clear.addEventListener('click', fn_clear);

      e_update.addEventListener('keydown', fn_update_keydown);
      e_clear.addEventListener('keydown', fn_clear_keydown);

      navigator.serviceWorker.addEventListener('message', fn_receive_status);
    } else if (e_body) {
      navigator.serviceWorker.addEventListener('message', fn_receive_icon);
    }

    if (navigator.serviceWorker.controller) {
      start_polling();
    } else {
      register_sw();
    }
  } else if (e_update) {
    console.warn('no service worker support in browser');
    e_status.innerHTML = 'Sorry, but your browser doesn&rsquo;t support this feature.';
  }
}
swi_oninteractive();

function fn_controllerchange() {
  console.info('controllerchange: ' + navigator.serviceWorker.controller);

  // If we change from one controller to another, we could conceivably keep
  // the same interval timer.  But I prefer to poll the new controller
  // immediately and restart regular polling with the proper relative delay.

  if (pollID) {
    clearInterval(pollID);
  }

  if (navigator.serviceWorker.controller) {
    start_polling();
  } else {
    // The user must have cleared the site data or otherwise unregistered
    // the controller.  Presumably they knew what they were doing, so don't
    // bother with any information messages; just disable the interface
    // cleanly.
    if (e_update) {
      e_update.className = 'update-disable';
      e_clear.className = 'clear-disable';
      e_progress.innerHTML = '';
      e_status.innerHTML = '&nbsp;';
      e_err_status.innerHTML = '';
      e_usage.innerHTML = '';
      e_extra.innerHTML = '';
      e_top_msg['green'].style.display = 'none';
      e_top_msg['yellow'].style.display = 'none';
      e_top_msg['online'].style.display = 'none';
      e_red_missing.style.display = 'none';

      old_msg = {}

      update_wakelock();
    } else if (e_icon) {
      e_icon.style.display = 'none';
    }
  }
}

function start_polling() {
  console.info('start_polling()');

  polls_since_response = 0;
  post_msg('poll');
  pollID = setInterval(fn_poll_cache, POLL_INTERVAL_MS);
}

function fn_poll_cache(event) {
  // If we don't get a response from the service worker for too long,
  // let the user know that something went wrong.
  let secs = Math.floor((polls_since_response * POLL_INTERVAL_MS) / 1000);
  if (secs >= 3) {
    timed_out = true;
    if (e_err_status) {
      e_err_status.innerHTML = 'No response from the service worker for ' + secs + ' seconds.<br>It might recover eventually, or you might need to clear the site data from the browser.';
    }
  }

  post_msg('poll')
}

function post_msg(msg) {
  navigator.serviceWorker.controller.postMessage(msg);

  polls_since_response++;
}

/* This function receives service worker messages only on the home page. */
function fn_receive_status(event) {
  polls_since_response = 0;

  try {
    let msg = event.data;

    // Update DOM elements only if they've changed.
    // This might improve performance, but the main advantage is to stop
    // the scrollbar from flickering in Android Chrome emulation.
    // (I'd guess that the browser can detect unchanged values for
    // textContent and className, but not for innerHTML).

    if (msg.update_button !== old_msg.update_button) {
      e_update.textContent = msg.update_button;
    }

    if (msg.update_class !== old_msg.update_class) {
      e_update.className = msg.update_class;
    }

    if (msg.progress !== old_msg.progress) {
      e_progress.innerHTML = msg.progress;
    }

    // Since e_status and e_err_status depend on each other occasionally,
    // update both if either updates.
    if ((msg.msg !== old_msg.msg) ||
        (msg.err_status !== old_msg.err_status) ||
        timed_out) {
      if (msg.msg || msg.err_status) {
        e_status.innerHTML = msg.msg;
      } else {
        // To avoid elements jumping unnecessarily, always allocate at least
        // one line to the status (or err_status).
        e_status.innerHTML = '&nbsp;'
      }

      // If we previously had a 'time out' message, always replace it
      // (or clear it) when we get a new poll response.
      e_err_status.innerHTML = msg.err_status;
    }

    if (msg.usage !== old_msg.usage) {
      e_usage.innerHTML = msg.usage;
    }

    if (msg.extra !== old_msg.extra) {
      e_extra.innerHTML = msg.extra;
    }

    if (msg.top_msg !== old_msg.top_msg) {
      if (old_msg.top_msg in e_top_msg) {
        e_top_msg[old_msg.top_msg].style.display = 'none';
      }
      if (msg.top_msg in e_top_msg) {
        e_top_msg[msg.top_msg].style.display = 'block';
      }
    }

    if (msg.red_missing !== old_msg.red_missing) {
      if (msg.red_missing) {
        e_red_missing.style.display = 'block';
      } else {
        e_red_missing.style.display = 'none';
      }
    }

    if (msg.clear_class !== old_msg.clear_class) {
      e_clear.className = msg.clear_class;
    }

    old_msg = msg;

    update_wakelock();
  } catch (e) {
    console.error('polling msg error:', e);
    // If sw.js and swi.js update unequally, communication could break down.
    // If so, we want to make clear what steps might lead to recovery.
    e_update.className = 'update-update';
    e_progress.innerHTML = '';
    e_clear.className = '';
    e_status.innerHTML = '';
    e_err_status.innerHTML = 'Interface not in sync; try clearing the site data and then refreshing the page.';
    e_usage.innerHTML = '';
    e_extra.innerHTML = '';
    e_top_msg['green'].style.display = 'none';
    e_top_msg['yellow'].style.display = 'none';
    e_top_msg['online'].style.display = 'none';
    e_red_missing.style.display = 'none';
  }
}

function fn_update(event) {
  localStorage.removeItem('click_time_yellow');
  localStorage.removeItem('click_time_missing');

  init_permissions();

  if (navigator.serviceWorker.controller) {
    // If sw.js and swi.js update unequally, communication could break down.
    // So regardless of what we *think* the status is, always send the 'update'
    // message and let the service worker sort it out.
    post_msg('update');
  }
}

async function init_permissions() {
  if (navigator.storage) {
    let persistent = await navigator.storage.persist();
    console.info('persistent =', persistent);
  }
}

async function register_sw() {
  console.info('register_sw()');

  try {
    var sw_path = root_path + 'sw.js';
    await navigator.serviceWorker.register(sw_path);

    // When register() resolves, we're not guaranteed to have an active
    // service worker.  In fact, the service worker might not even be
    // 'installing' yet!  We can await navigator.serviceWorker.ready, but
    // (at least in Chrome), navigator.serviceWorker.controller hasn't been
    // updated yet when that resolves!  In any case, I already listen for
    // the 'controllerchange' event anyway, and it seems to reliably fire
    // after navigator.serviceWorker.controller has updated.
    //
    // So the only reason I 'await' the results of register() is in to
    // catch a failure if one is signaled.
  } catch (e) {
    console.warn('service worker registration failed', e);
    if (e_status) {
      e_status.innerHTML = '';
      e_err_status.innerHTML = 'Service worker failed to load.  Manually clearing all site data might help.';
    }
  }
}

function fn_clear(event) {
  if (navigator.serviceWorker.controller) {
    // If sw.js and swi.js update unequally, communication could break down.
    // So regardless of what we *think* the status is, always send the 'clear'
    // message and let the service worker sort it out.
    post_msg('clear');
    localStorage.clear();
  }
}

/* Pressing 'enter' when a button is focused does the same as a mouse click
   in order to support accessibility requirements. */
function fn_update_keydown(event) {
  if ((event.key == 'Enter') ||
      (event.key == ' ') ||
      (event.key == 'Spacebar')) {
    fn_update(event);
    event.preventDefault();
  }
}

function fn_clear_keydown(event) {
  if ((event.key == 'Enter') ||
      (event.key == ' ') ||
      (event.key == 'Spacebar')) {
    fn_clear(event);
    event.preventDefault();
  }
}

/* This function receives service worker messages on all pages except
   the home page.  It's only purpose is to update the icon in the upper
   right corner if the cache is imperfect. */
function fn_receive_icon(event) {
  let msg = event.data;

  let click_time_yellow = get_click_time('yellow');
  let click_time_missing = get_click_time('missing');

  let ms_in_12hrs = 1000*60*60*12;
  let ms_in_10days = 1000*60*60*24*10;

  if (msg.red_missing &&
      (Date.now() > click_time_missing + ms_in_12hrs) &&
      (msg.update_class === 'update-update')) {
    var icon = 'missing';
  } else if ((msg.top_msg === 'yellow') &&
             (Date.now() > click_time_yellow + ms_in_10days) &&
             (msg.update_class === 'update-update')) {
    var icon = 'yellow';
  } else {
    var icon = undefined;
  }

  if (icon !== old_icon) {
    console.info('changing to icon:', icon);
    if (!e_icon) {
      console.info('inserting hazard icon');
      e_body.insertAdjacentHTML('afterbegin', '<a href="' + root_path + 'index.html#offline" tabindex="0" id="icon"><img src="' + root_path + 'icons/hazard.svg" class="hazard-img" alt="offline file warning"></a>');
      e_icon = document.getElementById('icon');
      e_icon.addEventListener('click', fn_icon_click);
    }
    if (icon === 'missing') {
      e_icon.className = 'icon-red';
      e_icon.style.display = 'block';
    } else if (icon === 'yellow') {
      e_icon.className = 'icon-yellow';
      e_icon.style.display = 'block';
    } else {
      e_icon.style.display = 'none';
    }
  }

  old_icon = icon;
}

/* We get the last click time from local storage every time we need it
   instead of keeping a local variable.  This ensures that multiple
   windows stay in sync. */
function get_click_time(name) {
  let time_str = localStorage.getItem('click_time_' + name);
  if (time_str) {
    return parseFloat(time_str);
  } else {
    return 0.0;
  }
}

function fn_icon_click(event) {
  if (old_icon === 'missing') {
    localStorage.setItem('click_time_missing', String(Date.now()));
    localStorage.setItem('click_time_yellow', String(Date.now()));
  } else if (old_icon === 'yellow') {
    localStorage.setItem('click_time_yellow', String(Date.now()));
  }

  // The icon has a link to the 'offline' section of the home page.
  // So we don't call event.preventDefault(), and we allow the browser
  // to navigate there.
}

/* If the browser supports it, keep the screen awake whenever the 'update'
   button is in the 'update-stop' state (meaning that an update is in
   progress).  Wakelock is currently only supported in Chrome. */
async function update_wakelock() {
  let update_class = e_update.className;

  if (update_class == 'update-stop' && !wakelock && navigator.wakeLock) {
    try {
      console.info('Requesting wakelock');
      wakelock = await navigator.wakeLock.request('screen');
      console.info('wakelock = ', wakelock);
      wakelock.addEventListener('release', fn_wakelock_released);
    } catch (e) {
      // Documentation is lacking as to why the request might fail.
      // Perhaps a low battery.
      // In any case, fine, no wakelock.
      console.warn('wakelock request failed:', e);
      wakelock = undefined;
    }
  } else if (update_class != 'update-stop' && wakelock) {
    try {
      console.info('releasing wakelock');
      wakelock.release();
      wakelock = undefined;
    } catch (e) {
      // Maybe this will never happen, but I wouldn't be surprised, e.g.
      // if the system kills our wakelock just before we try to release it.
      console.warn('wakelock release failed:', e);
    }
  }
}

function fn_wakelock_released() {
  console.info('fn_wakelock_released()');
}
