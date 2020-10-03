var url_to_base64 = [
/* insert code here */
];

var DB_NAME = 'db-v1';
var DB_VERSION = 1;
var BASE64_CACHE_NAME = 'base64-cache-v1';

var updating = 'Checking cache';
var err_status = '';
var kb_total = 0;
var kb_cached = 0;
var new_url_data = {};
var base64_to_kb = {};
var base64_to_delete = [];
var usage = '';


// Some interfaces use callbacks, but we'd rather use Promises.
// async_callbacks() converts a callback interface into a Promise.
//
// The first parameter, 'request', is a request that has been made.
// We assume that it has callbacks 'onsuccess' and 'onerror', and
// async_callbacks() assigns those callbacks.
// - When the 'onsuccess' callback is called, the promise is resolved
//   and returns the request.result.
// - When the 'onerror' callback is called, the promise is rejected.
function async_callbacks(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = (event) => {
      resolve(request.result);
    }

    request.onerror = (event) => {
      return reject(event);
    }
  });
}

// And here's a similar function to async_callbacks, but suitable for
// indexedDB transactions.
// - When the 'oncomplete' callback is called, the promise is resolved.
// - When the 'onerror' or 'onabort' callback is called, the promise is
//   rejected.
function async_tx(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = (event) => {
      resolve(event);
    }

    tx.onerror = (event) => {
      return reject(event);
    }

    tx.onabort = (event) => {
      return reject(event);
    }
  });
}


// Figure out the total size of the data to be cached.
for (let i = 0; i < url_to_base64.length; i++) {
  kb_total += url_to_base64[i][2];
}

console.info('scope = ' + registration.scope);




// Check how many KB of the new base64 values already have a file cached.
async function count_cached() {
  new_url_data = {};
  for (let i = 0; i < url_to_base64.length; i++) {
    let url = url_to_base64[i][0];
    let base64 = url_to_base64[i][1];
    let kb = url_to_base64[i][2];
    new_url_data[url] = {base64: base64,
                         kb: kb};
    base64_to_kb[base64] = kb;
  }

  cache = await caches.open(BASE64_CACHE_NAME);
  requests = await cache.keys();
  console.info('checking cache keys');
  for (let i = 0; i < requests.length; i++) {
    let base64 = remove_scope_from_request(requests[i]);
    if (base64 in base64_to_kb) {
      kb_cached += base64_to_kb[base64];

      // Entries left in base64_to_kb are ones that need to be fetched.
      delete base64_to_kb[base64];
    } else {
      // Entries in base64_to_delete are ones that need to be deleted.
      console.info('Need to delete ' + base64);
      base64_to_delete.push(base64);
    }
  }

  is_update_done();
}
count_cached();

// Get the URL from the request and remove the prepended scope.
// This can be done with a fetch request (which has a real URL)
// or on a cache key (which has a base64 value in place of the
// relative URL).
function remove_scope_from_request(request) {
  return request.url.substr(registration.scope.length);
}

/*** Install the service worker ***/

self.addEventListener('install', fn_install);

async function fn_install(event) {
  // Since the install function requires asynchronous communication to
  // complete, we use event.waitUntil() to keep the process alive until
  // it completes.
  event.waitUntil(fn_install2());
}

async function fn_install2() {
  // Immediately replace any previous service worker.
  await self.skipWaiting();

  // Remove any old caches I might have left lying around from
  // previous versions of the code.
  var cacheNames = await caches.keys();
  await Promise.all(
    cacheNames.map(function(cacheName) {
      if (cacheName !== BASE64_CACHE_NAME) {
        return caches.delete(cacheName);
      }
    })
  );
}


/*** when the service worker is activated ***/

// Once installation of a service worker is finished, it is activated.
// But it won't do anything until the next refresh.  To make it start
// processing fetch requests immediately, we call claim().  We call it
// for all clients, not just the one that registered the service worker,
// because we want all windows to stay in sync.
//
// Note that it's not just that all clients are running the same version
// of the service worker.  All clients are *sharing* the same service worker,
// so we generally don't to worry about changes happening elsewhere and not
// being reflected here.
//
// When we claim the service worker, the browser lets the previous one
// finish what it's doing before killing it.  If it's just fetching
// something from the cache, the transactions are atomic and so safe.
// But if the other worker is in the middle of an update, and then the new
// one also starts updating.  That requires the following sequence:
// - the user starts an update
// - I update sw.js on the server
// - the user hits refresh (or navigates around before returning to index.html)
// - the user starts another update
// This last step isn't ridiculous since as far as the user can tell, the
// previous update just mysteriously stopped.
//
// Even here, the results shouldn't be terrible.  The kb counts could go
// weird, but all the right files should end up in the indexedDB and cache.

self.addEventListener('activate', event => {
  clients.claim();
});


/*** Read the old url_data ***/

// Note that this process is asynchronous, so we might get some requests
// before it's done.  That may cause some files to get fetched online instead
// of from the cache.  TODO: I should probably do this as part of registration
// to be safe when offline.  I could borrow await_tx() to make it fit better
// with promises.

var db;
var url_data = {};

open_db();

async function open_db() {
  if (db) {
    // The indexedDB is already open.
    return
  }

  let request = indexedDB.open(DB_NAME, DB_VERSION);

  // There is no documented provision for the request to wait for the
  // onupgradeneeded callback to complete before calling onsuccess.
  // I see two possibilities:
  // - the request assumes that dbupgradeneeded queued the necessary
  //   transactions, so everything will be fine.
  // - the request waits for all upgrade transactions to complete and
  //   somehow never interrupts between when one transaction completes
  //   and the next starts.  Perhaps this is possible in our single thread.
  //
  // In any case, the onupgradeneeded path doesn't need to be hooked in
  // with the async_callbacks promise.  It just does its own thing when
  // necessary.
  request.onupgradeneeded = dbupgradeneeded;

  db = await async_callbacks(request, dbupgradeneeded);

  let lookup = await db.transaction("url_data").objectStore("url_data").get("key");

  console.info('get_key returned ' + lookup);
  if (lookup){
    url_data = lookup.value;
    console.info(url_data);
  }
}

// This function is called when the indexedDB is accessed for the first time.
// (It will also be called if I increment the version number, in which case
// I need to adjust this code to avoid an error.)
async function dbupgradeneeded(event) {
  db = event.target.result;

  let objectStore = db.createObjectStore("url_data", { keyPath: "key" });

  // We can start using the objectStore handle right away, even if the
  // transaction to the database is still pending.

  // Store an empty value in the newly created objectStore.
  obj = {key: 'key', value: {}};
  objectStore.add(obj);

  // Again, the transaction may still be in flight, but there's no need to
  // wait for it.  Any later read transaction is guaranteed to execute
  // in the proper order.
}


/*** Handle a fetch request ***/

// Handle a fetch request from a client (window/tab).
// Map the URL to a base64 encoding (from the indexedDB), then
// map the base64 encoding to a cache entry.
self.addEventListener('fetch', function(event) {
  // The request is guaranteed to be in scope, so we can simply
  // remove the scope to get the relative URL.
  let url = remove_scope_from_request(event.request);
  console.info('fetching ' + url);
  if (url_data && (url in url_data)) {
    event.respondWith(fetch_response(event, url));
  } else {
    // Allow the default fetch response.
    console.info(url + ' not recognized')
    return;
  }
});

async function fetch_response(event, url) {
  var response = await caches.match(url_data[url].base64);
  console.info(response);
  if (response) {
    console.info(url + ' found')
    return response;
  } else {
    console.info(url + ' not found')
    return fetch(event.request);
  }
}


/*** Handle messages related to user interaction ***/

// Listen for messages from clients and respond with status info.
// The client initiates the message exchange because the status info
// is only needed by index.html, so we don't want to spam any other
// clients that are viewing different pages.
self.addEventListener('message', fn_send_status);

function fn_send_status(event) {
  // Most messages are polling for status.
  // But regardless of the message type, always update the status.
  if (updating === 'Checking cache') {
    var status = ' ' + updating;
  } else {
    let status_cached = (kb_cached/1024).toFixed(1)
    let status_total = (kb_total/1024).toFixed(1)
    status = ' ' + status_cached + ' / ' + status_total + ' MB'
    if (updating !== false) {
      status += ' - ' + updating;
    }
  }
  if (updating === false) {
    var update_class = 'update-update';
  } else if ((updating === 'Up to date') || (updating === 'Checking cache')) {
    update_class = 'update-disable';
  } else {
    update_class = 'update-stop';
  }
  msg = {
    update_class: update_class,
    status: status,
    err_status: err_status,
    usage: usage
  };
  event.source.postMessage(msg);

  if (event.data === 'update') {
    update_cache(event);
  } else if (event.data === 'clear') {
    clear_caches(event);
  }
}

// When requested, switch to using the newest url_data
//  and update the cache to match.
async function update_cache(event) {
  if (updating) {
    console.info('Update already in progress');
    return;
  }

  updating = 'Deleting out-of-date cached files';
  console.info(updating)

  await record_urls();

  cache = await caches.open(BASE64_CACHE_NAME);

  for (let i = 0; i < base64_to_delete.length; i++) {
    let base64 = base64_to_delete[i];
    console.info('Deleting ' + base64);
    await cache.delete(base64);
  }
  base64_to_delete = [];

  // TODO: remove unneeded cache entries
  // (The old url_data might not accurately reflect the cache, so ignore that
  // and look at the cache directly.)
  //
  // TODO: only fetch base64 URLs that aren't already cached.
  for (let url in url_data) {
    let base64 = url_data[url].base64;
    if (base64 in base64_to_kb) {
      let kb = base64_to_kb[base64];
      updating = 'Updating ' + decodeURI(url)
      console.info(updating)
      response = await fetch(url);
      if (response.ok) {
        // Associate the fetched page with the base64 encoding.
        await cache.put(base64, response);

        // Entries left in base64_to_kb are ones that need to be fetched.
        delete base64_to_kb[base64];

        // Update cache usage estimate.
        await update_usage();
  
  // TODO: An error ends fetching, so it should really set updating = false.
  // TODO: An error message would be good, too.
  // error codes:
  // 300-399: The server did something unexpected.
  // 400-499: The file list must have updated.  Refresh the page and try again.
  // (or refresh automatically, then prompt to 'Try again?')
  // 500-599: The server did something unexpected.
      }
      kb_cached += kb;
    }
  }

  is_update_done();
}

async function record_urls() {
  // Initialize a fresh URL DB object.
  url_data = new_url_data
  obj = {key: 'key', value: url_data};
  console.info(obj);
  await async_callbacks(db.transaction("url_data", "readwrite").objectStore("url_data").put(obj));
}

function is_update_done() {
  if (base64_to_delete.length || Object.keys(base64_to_kb).length) {
    updating = false;
  } else {
    updating = 'Up to date';
  }
  update_usage();
}

async function update_usage() {
  if (navigator && navigator.storage) {
    let estimate = await navigator.storage.estimate();
    let status_usage = (estimate.usage/1024/1024).toFixed(1)
    let status_quota = (estimate.quota/1024/1024/1024).toFixed(1)
    usage = (' ' + status_usage + ' MB including overhead' +
             ' (browser allows up to ' + status_quota + ' GB)');
  }
}
