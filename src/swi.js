// This script handles the document end of ServiceWorker interaction (swi).

let e_update = document.getElementById('update');
let e_status = document.getElementById('status');
let e_err_status = document.getElementById('err-status');

let e_clear = document.getElementById('clear');
let e_usage = document.getElementById('usage');

var reg;
var intervalID;
var temp_controller;

// TODO: handle the case where e_status isn't ready yet.
// (Wait for DOM completion as in search.js.)
e_status.textContent = ' Waiting for service worker to load';

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
    e_status.textContent = ' No service worker';
  });
} else {
  console.info('no service worker support in browser');
  e_status.textContent = " Sorry, but your browser doesn't support this feature.";
}

function start_polling(registration) {
  console.info('start_polling()');

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
  poll_cache();
  intervalID = setInterval(poll_cache, 1000);
}

function poll_cache() {
  // poll_cache() is only called if there is an active controller,
  // but navigator.serviceWorker.controller might not be updated yet
  // (as documented above).  Prefer navigator.serviceWorker.controller
  // when it is available so that we keep up with any changes to the
  // service worker, but fall back to temp_controller if necessary.
  if (navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage('polling');
  } else {
    temp_controller.postMessage('polling');
  }
}

navigator.serviceWorker.addEventListener('message', fn_receive_status);


function fn_receive_status(event) {
  try {
    let msg = event.data;
    e_update.className = msg.update_class;
    e_status.textContent = msg.status;
    e_err_status.textContent = msg.err_status;
    e_usage.textContent = msg.usage;
  } catch (error) {
    console.error(error);
    // sw.js always auto-updates.  If swi.js is cached, communication could
    // break down.  If so, we want to make clear what steps might lead to
    // recovery.
    e_update.className = '';
    e_status.textContent = '';
    e_err_status.textContent = 'Interface not in sync; try updating the cache and then refreshing the page.';
    e_usage.textContent = '';
  }
}

if (e_update) {
  e_update.addEventListener('click', fn_update);
}

if (e_clear) {
  e_clear.addEventListener('click', fn_clear);
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
