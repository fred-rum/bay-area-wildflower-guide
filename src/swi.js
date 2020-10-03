// This script handles the document end of ServiceWorker interaction (swi).

let e_update = document.getElementById('update');
let e_status = document.getElementById('status');
let e_err_status = document.getElementById('err-status');

let e_clear = document.getElementById('clear');
let e_usage = document.getElementById('usage');

var reg;
var intervalID;

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').then(function (registration) {
    var serviceWorker;
    if (registration.installing) {
      serviceWorker = registration.installing;
      console.info('installing');
    } else if (registration.waiting) {
      serviceWorker = registration.waiting;
      console.info('waiting');
    } else if (registration.active) {
      serviceWorker = registration.active;
      console.info('active');
    }
    if (serviceWorker) {
      serviceWorker.addEventListener('statechange', function (e) {
        console.info(e.target.state);
      });
      console.info(serviceWorker.state);
    }
    if (e_status) {
      // TODO: handle the case where e_status isn't ready yet.
      // (Wait for DOM completion as in search.js.)
      // Poll right away, and then at intervals.
      poll_cache();
      intervalID = setInterval(poll_cache, 1000);
    }
    e_status.textContent = ' Checking cache';
  }).catch (function (error) {
    console.info('service worker registration failed');
    e_status.textContent = ' No service worker';
  });
} else {
  console.info('no service worker support in browser');
  e_status.textContent = " Sorry, but your browser doesn't support this feature.";
}

function poll_cache() {
  navigator.serviceWorker.controller.postMessage('polling');
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
