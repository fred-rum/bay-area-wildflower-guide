// This script handles the document end of ServiceWorker interaction (swi).

let e_update;
let e_status;
let e_err_status;

let e_clear;
let e_usage;

let e_top_msg = {};

var temp_controller;

// old_msg is initialized to a dict, so when receive_status() looks for
// changes, every old value appears to be undefined.
var old_msg = {};

/* If the readyState is 'interactive', then the user can (supposedly)
   interact with the page, but it may still be loading HTML, images,
   or the stylesheet.  In fact, the page may not even be rendered yet.
   We use a 0-length timeout to call restore_scroll() as soon as possible
   after pending rendering, if any.

   Hopefully the stylesheet has been loaded and the HTML and CSS are
   sufficiently well designed so that the page isn't still adjusting
   its layout after the call to restore_scroll().
*/
function swi_oninteractive() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', oninteractive);
    return
  }
  console.info('swi_oninteractive()');

  e_update = document.getElementById('update');
  if (!e_update) {
    // Don't poll if we're not on the home page with the update button.
    return;
  }

  e_status = document.getElementById('status');
  e_err_status = document.getElementById('err-status');

  e_clear = document.getElementById('clear');
  e_usage = document.getElementById('usage');

  let top_msg_array = ['green', 'yellow'];
  for (i = 0; i < top_msg_array.length; i++) {
    top_msg = top_msg_array[i];
    e_top_msg[top_msg] = document.getElementById('cache-' + top_msg);
    console.info(top_msg, e_top_msg[top_msg]);
  }

  e_status.innerHTML = 'Waiting for service worker to load';

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js').then(function (registration) {
      // When register() resolves, we're not guaranteed to have an active
      // service worker.  In fact, the service worker might not even be
      // 'installing' yet!  Theoretically, I could set up callbacks on
      // updatestate and statechange, but even easier, I can simply wait
      // until the ServiceWorkerContainer resolves the promise in 'ready'.
      // When that happens, a service worker is guaranteed to be active.
      navigator.serviceWorker.ready.then(start_polling);
    }).catch (function (error) {
      console.info('service worker registration failed');
      e_status.innerHTML = 'No service worker';
    });
  } else {
    console.info('no service worker support in browser');
    e_status.innerHTML = 'Sorry, but your browser doesn&rsquo;t support this feature.';
  }
}
swi_oninteractive();

function start_polling(registration) {
  console.info('start_polling()');
  e_update.addEventListener('click', fn_update);
  e_clear.addEventListener('click', fn_clear);
  navigator.serviceWorker.addEventListener('message', fn_receive_status);

  // An oddity of the navigator.serviceWorker.ready promise is that it
  // resolves when a service worker is 'active', but (at least in Chrome),
  // navigator.serviceWorker.controller hasn't been updated yet!
  // To handle that case, get the active service worker from the registration,
  // and use that until navigator.serviceWorker.controller updates.
  temp_controller = registration.active;

  // sw.js will return the simplified status of ' Checking cache' until it
  // is fully initialized and ready to return real status values.  To avoid
  // flickering while we wait for that first response [...]

  // Poll right away, and then at intervals.
  poll_cache('start');
  setInterval(poll_cache, 500);
}

function poll_cache(msg='poll') {
  // poll_cache() is only called if there is an active controller,
  // but navigator.serviceWorker.controller might not be updated yet
  // (as documented above).  Prefer navigator.serviceWorker.controller
  // when it is available so that we keep up with any changes to the
  // service worker, but fall back to temp_controller if necessary.
  if (navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage(msg);
  } else {
    temp_controller.postMessage(msg);
  }
}

function fn_receive_status(event) {
  try {
    let msg = event.data;

    // Update DOM elements only if they've changed.
    // This might improve performance, but the main advantage is to stop
    // the scrollbar from flickering on Android Chrome.  (I'd guess that
    // the browser can detect unchanged values for textContent and
    // className, but not for innerHTML).
    if (msg.update_button != old_msg.update_button) {
      e_update.textContent = msg.update_button;
    }
    if (msg.update_class != old_msg.update_class) {
      e_update.className = msg.update_class;
    }
    if (msg.status != old_msg.status) {
      e_status.innerHTML = msg.status;
    }
    if (msg.err_status != old_msg.err_status) {
      e_err_status.innerHTML = msg.err_status;
    }
    if (msg.usage != old_msg.usage) {
      e_usage.innerHTML = msg.usage;
    }
    if (msg.top_msg != old_msg.top_msg) {
      if (old_msg.top_msg) {
        e_top_msg[old_msg.top_msg].style.display = 'none';
      }
      if (msg.top_msg) {
        e_top_msg[msg.top_msg].style.display = 'block';
      }
    }
    old_msg = msg;
  } catch (error) {
    console.error(error);
    // sw.js always auto-updates.  If swi.js is cached, communication could
    // break down.  If so, we want to make clear what steps might lead to
    // recovery.
    e_update.className = '';
    e_status.innerHTML = '';
    e_err_status.innerHTML = 'Interface not in sync; try deleting the offline files and then refreshing the page.';
    e_usage.innerHTML = '';
  }
}

function fn_update(event) {
  if (navigator.serviceWorker && navigator.serviceWorker.controller) {
    // sw.js always auto-updates.  If swi.js is cached, communication could
    // break down.  So regardless of what we *think* the status is, always
    // send the 'update' message and let the service worker sort it out.
    navigator.serviceWorker.controller.postMessage('update');
    e_update.className = 'disabled';
  }
}

function fn_clear(event) {
  if (navigator.serviceWorker && navigator.serviceWorker.controller) {
    // sw.js always auto-updates.  If swi.js is cached, communication could
    // break down.  So regardless of what we *think* the status is, always
    // send the 'update' message and let the service worker sort it out.
    navigator.serviceWorker.controller.postMessage('clear');
  }
}
