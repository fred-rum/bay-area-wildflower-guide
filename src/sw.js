var url_to_base64 = [
/* insert code here */
];

var DB_NAME = 'db-v1';
var DB_VERSION = 1;
var BASE64_CACHE_NAME = 'base64-cache-v1';

var updating = false;
var kb_total = 0;
var kb_cached = 0;
var new_url_data = {};
var base64_to_kb = {};
var base64_to_delete = [];

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
    let key = remove_scope_from_request(requests[i]);
    if (key in base64_to_kb) {
      kb_cached += base64_to_kb[key];

      // Entries left in base64_to_kb are ones that need to be fetched.
      delete base64_to_kb[key];
    } else {
      // Entries in base64_to_delete are ones that need to be deleted.
      console.info('Need to delete ' + key);
      base64_to_delete.push(key);
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
// weird, but all the right files should end up in the indexDB and cache.

self.addEventListener('activate', event => {
  clients.claim();
});


/*** Read the old url_data ***/

// Note that this process is asynchronous, so we might get some requests
// before it's done.  That may cause some files to get fetched online instead
// of from the cache.  TODO: I should probably do this as part of registration
// to be safe when offline.  I could borrow await_tx() to make it fit better
// with promises.

var request = indexedDB.open(DB_NAME, DB_VERSION);
var db;
var url_data = {};

request.onsuccess = function(event) {
  db = event.target.result;
  db.transaction("url_data").objectStore("url_data").get("key").onsuccess = function(event) {
    console.info('get_key returned ' + event.target.result);
    if (event.target.result){
      url_data = event.target.result.value;
      console.info(url_data);
      // TODO: Count the shared kb between the old and new url_data
      // as kb_cached.
    }
  }
};

request.onerror = function(event) {
  console.info('Error while opening indexedDB');
};

// This function is called when the indexDB is created for the first time.
// (It will also be called if I increment the version number, in which case
// I need to adjust it to avoid an error.)
request.onupgradeneeded = function(event) {
  db = event.target.result;

  db.onerror = function(event) {
    // Generic error handler for all errors.
    console.error("Database error: " + event.target.errorCode);
  };

  // Create an objectStore to hold information about our customers. We're
  // going to use "ssn" as our key path because it's guaranteed to be
  // unique - or at least that's what I was told during the kickoff meeting.
  var objectStore = db.createObjectStore("url_data", { keyPath: "key" });

  // Use transaction oncomplete to make sure the objectStore creation is 
  // finished before adding data into it.
  objectStore.transaction.oncomplete = init_db;
};

// This gets called when the database is being freshly created.
function init_db(event) {
  // Store values in the newly created objectStore.
  obj = {key: 'key', value: {}};
  var dataObjectStore = db.transaction("url_data", "readwrite").objectStore("url_data");
  dataObjectStore.add(obj)
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
self.addEventListener('message', function (event) {
  // Most messages are polling for status.
  // But regardless of the message type, always update the status.
  msg_cached = (kb_cached/1024).toFixed(1)
  msg_total = (kb_total/1024).toFixed(1)
  msg = ' ' + msg_cached + ' / ' + msg_total + ' MB'
  if (updating !== false) {
    msg += ' - ' + updating;
  }
  event.source.postMessage(msg);

  if (event.data === 'update') {
    update_cache(event);
  }
});

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
    base64_to_delete = [];
  }

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
        delete base64_to_kb[key];
  
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

// This is awkward because transactions use callbacks, but we want to use
// Promises.
// Call await_tx with a transaction, and it returns a promise that resolves
// or rejects based on which callback gets called.
function await_tx(tx) {
  return new Promise((resolve, reject) => {
    tx.onsuccess = (event) => {
      resolve(event);
    }
    tx.onerror = (event) => {
      return reject(event);
    }
  });
}

async function record_urls() {
  // Initialize a fresh URL DB object.
  url_data = new_url_data
  obj = {key: 'key', value: url_data};
  console.info(obj);
  await await_tx(db.transaction("url_data", "readwrite").objectStore("url_data").put(obj));
}

function is_update_done() {
  if (Object.keys(base64_to_kb).length === 0) {
    updating = 'Up to date';
  } else {
    updating = false;
  }
}
