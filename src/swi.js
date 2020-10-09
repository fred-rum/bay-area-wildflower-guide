// This script handles the document end of ServiceWorker interaction (swi).

var e_update;
var e_progress;
var e_status;
var e_err_status;

var e_clear;
var e_usage;

var e_top_msg = {};

var e_body;
var e_icon;

var temp_controller;

// old_msg is initialized to a dict, so when receive_status() looks for
// changes, every old value appears to be undefined.
var old_msg = {};

var old_icon;

var wakelock;

var poll_interval = 500; // in milliseconds
var polls_since_response = 0;
var timed_out = false;

/* If the readyState is 'interactive', then the user can (supposedly)
   interact with the page, but it may still be loading HTML, images,
   or the stylesheet.  In fact, the page may not even be rendered yet.
   We use a 0-length timeout to call restore_scroll() as soon as possible
   after pending rendering, if any.

   Hopefully the stylesheet has been loaded and the HTML and CSS are
   sufficiently well designed so that the page isn't still adjusting
   its layout after the call to restore_scroll().
*/
async function swi_oninteractive() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', swi_oninteractive);
    return
  }
  console.info('swi_oninteractive()');

  e_update = document.getElementById('update');
  if (e_update) {
    e_status = document.getElementById('status');
    e_progress = document.getElementById('progress');
    e_err_status = document.getElementById('err-status');

    e_clear = document.getElementById('clear');
    e_usage = document.getElementById('usage');

    let top_msg_array = ['green', 'yellow', 'online'];
    for (i = 0; i < top_msg_array.length; i++) {
      top_msg = top_msg_array[i];
      e_top_msg[top_msg] = document.getElementById('cache-' + top_msg);
      console.info(top_msg, e_top_msg[top_msg]);
    }

    e_status.innerHTML = 'Waiting for the service worker to load';

    var sw_path = 'sw.js';
  } else {
    e_body = document.getElementById('body');

    var sw_path = '../sw.js';
  }

  if ('serviceWorker' in navigator) {
    try {
      registration = await navigator.serviceWorker.register(sw_path);
    } catch (e) {
      console.warn('service worker registration failed', e);
      if (e_status) {
        e_status.innerHTML = 'Service worker failed to load.  Manually clearing all site data might help.';
      }
      return;
    }

    // When register() resolves, we're not guaranteed to have an active
    // service worker.  In fact, the service worker might not even be
    // 'installing' yet!  Theoretically, I could set up callbacks on
    // updatestate and statechange, but even easier, I can simply wait
    // until the ServiceWorkerContainer resolves the promise in 'ready'.
    // When that happens, a service worker is guaranteed to be active.
    await navigator.serviceWorker.ready;

    start_polling(registration);
  } else {
    console.info('no service worker support in browser');
    if (e_status) {
      e_status.innerHTML = 'Sorry, but your browser doesn&rsquo;t support this feature.';
    }
  }
}
swi_oninteractive();

function start_polling(registration) {
  console.info('start_polling()');

  // An oddity of the navigator.serviceWorker.ready promise is that it
  // resolves when a service worker is 'active', but (at least in Chrome),
  // navigator.serviceWorker.controller hasn't been updated yet!
  // To handle that case, get the active service worker from the registration,
  // and use that until navigator.serviceWorker.controller updates.
  temp_controller = registration.active;

  if (e_update) {
    e_update.addEventListener('click', fn_update);
    e_clear.addEventListener('click', fn_clear);

    navigator.serviceWorker.addEventListener('message', fn_receive_status);
  } else {
    navigator.serviceWorker.addEventListener('message', fn_receive_icon);
  }

  // Poll right away, and then at intervals.
  poll_cache(undefined, 'start');
  setInterval(poll_cache, poll_interval);
}

function poll_cache(event, msg='poll') {
  // If we don't get a response from the service worker for too long,
  // let the user know that something went wrong.
  let secs = Math.floor((polls_since_response * poll_interval) / 1000);
  if (secs >= 3) {
    timed_out = true;
    if (e_err_status) {
      e_err_status.innerHTML = 'No response from the service worker for ' + secs + ' seconds.<br>It might recover eventually, or you might need to clear the site data from the browser.';
    }
  }

  post_msg(msg)
}

function post_msg(msg) {
  // post_msg() is only called if there is an active service worker,
  // but navigator.serviceWorker.controller might not be updated yet
  // (as documented above).  Prefer navigator.serviceWorker.controller
  // when it is available so that we keep up with any changes to the
  // service worker, but fall back to temp_controller if necessary.
  if (navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage(msg);
  } else if (temp_controller) {
    temp_controller.postMessage(msg);
  }
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

    if (msg.msg !== old_msg.msg) {
      if (msg.msg) {
        e_status.innerHTML = msg.msg;
      } else {
        // To avoid elements jumping unnecessarily, always allocate at least
        // one line to the status.
        e_status.innerHTML = '&nbsp;'
      }
    }

    if ((msg.err_status !== old_msg.err_status) || timed_out) {
      // If we previously had a 'time out' message, always replace it
      // (or clear it) when we get a new poll response.
      e_err_status.innerHTML = msg.err_status;
    }

    if (msg.usage !== old_msg.usage) {
      e_usage.innerHTML = msg.usage;
    }

    if (msg.top_msg !== old_msg.top_msg) {
      if (old_msg.top_msg in e_top_msg) {
        e_top_msg[old_msg.top_msg].style.display = 'none';
      }
      if (msg.top_msg in e_top_msg) {
        e_top_msg[msg.top_msg].style.display = 'block';
      }
    }

    if (msg.clear_class !== old_msg.clear_class) {
      e_clear.className = msg.clear_class;
    }

    old_msg = msg;

    update_wakelock(msg);
  } catch (e) {
    console.error('polling msg error:', e);
    // sw.js always auto-updates.  If swi.js is cached, communication could
    // break down.  If so, we want to make clear what steps might lead to
    // recovery.
    e_update.className = '';
    e_status.innerHTML = '';
    e_err_status.innerHTML = 'Interface not in sync; try clearing the site data and then refreshing the page.';
    e_usage.innerHTML = '';
    e_top_msg.style.display = 'none';
  }
}

function fn_update(event) {
  if (navigator.serviceWorker) {
    // sw.js always auto-updates.  If swi.js is cached, communication could
    // break down.  So regardless of what we *think* the status is, always
    // send the 'update' message and let the service worker sort it out.
    post_msg('update');
    e_update.className = 'update-disable';
    localStorage.removeItem('yellow_expire');

    init_permissions();
  }
}

function fn_clear(event) {
  if (navigator.serviceWorker) {
    // sw.js always auto-updates.  If swi.js is cached, communication could
    // break down.  So regardless of what we *think* the status is, always
    // send the 'clear' message and let the service worker sort it out.
    post_msg('clear');
    localStorage.clear();
  }
}

/* This function receives service worker messages on all pages except
   the home page.  It's only purpose is to update the icon in the upper
   right corner if the cache is imperfect. */
function fn_receive_icon(event) {
  let msg = event.data;

  let yellow_expire = get_yellow_expire();
  if ((msg.icon == 'yellow') &&
      ((yellow_expire === null) || (Date.now() > yellow_expire))) {
    icon = 'yellow';
  } else {
    icon = undefined;
  }

  console.info(icon);
  if (icon !== old_icon) {
    if (icon === 'yellow') {
      console.info('displaying hazard icon');
      if (!e_icon) {
        console.info('inserting hazard icon');
        e_body.insertAdjacentHTML('afterbegin', '<div id="icon"><img src="../icons/hazard.svg" class="hazard-img"></div>');
        e_icon = document.getElementById('icon');
        e_icon.addEventListener('click', fn_icon_click);
      }
      e_icon.className = 'icon-yellow';
      e_icon.style.display = 'block';
    } else {
      e_icon.style.display = 'none';
    }
  }

  old_icon = icon;

  update_wakelock(msg);
}

/* We get the yellow_expire value from local storage every time we
   need it instead of keeping a local variable.  This ensures that
   multiple windows stay in sync. */
function get_yellow_expire(event) {
  let yellow_expire = localStorage.getItem('yellow_expire');
  if (yellow_expire != null) {
    yellow_expire = parseFloat(yellow_expire);
  }
  return yellow_expire;
}

function fn_icon_click(event) {
  let ms_in_week = 1000*60*60*24*7;
  let yellow_expire = Date.now() + ms_in_week;
  localStorage.setItem('yellow_expire', String(yellow_expire));
  if (event.shiftKey || event.ctrlKey) {
    window.open('../index.html#offline');
  } else {
    window.location.href = '../index.html#offline';
  }
}

/* If the browser supports it, keep the screen awake whenever the 'update'
   button is in the 'update-stop' state (meaning that an update is in
   progress).  Wakelock is currently only supported in Chrome. */
async function update_wakelock(msg) {
  if (msg.update_class == 'update-stop' && !wakelock && navigator.wakeLock) {
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
    }
  } else if (msg.update_class != 'update-stop' && wakelock) {
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
  wakelock = undefined;
}

async function init_permissions() {
  if (navigator.storage) {
    let persistent = await navigator.storage.persist();
    console.info('persistent =', persistent);
  }
}
