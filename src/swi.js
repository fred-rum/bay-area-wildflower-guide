// This script handles the document end of ServiceWorker interaction (swi).

let e_status = document.getElementById('status');
let e_update = document.getElementById('update');

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
      intervalID = setInterval(poll_cache, 200)
    }
  }).catch (function (error) {
    console.info('service worker registration failed');
  });
} else {
  console.info('no service worker support in browser');
}

function poll_cache() {
  navigator.serviceWorker.controller.postMessage('polling');
}

navigator.serviceWorker.addEventListener('message', fn_poll);


function fn_poll(event) {
  e_status.textContent = event.data;
}

if (e_update) {
  e_update.addEventListener('click', fn_update);
}

function fn_update(event) {
  if (navigator.serviceWorker && navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage('update');
  } else {
    e_status.style.color = "red";
    e_status.textContent = "Oops, looks like your browser doesn't support this feature!  Sorry.";
  }
  
  event.preventDefault();
}
