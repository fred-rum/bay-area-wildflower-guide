var url_to_base64 = [
/* insert code here */
];

console.info('starting from the beginning');

var DB_NAME = 'db-v1';
var DB_VERSION = 1;
var BASE64_CACHE_NAME = 'base64-cache-v1';

// An initial 'updating' message prevents updates until everything
// is initialized.
var updating = 'Checking cache';
var err_status = '';
var usage = '';

var url_data = undefined;
var new_url_data;
var url_diff;

var base64_to_kb = {};
var base64_to_delete = [];

var kb_total = 0;
var kb_cached = 0;


/*** Install the service worker ***/

// If this service worker (sw.js) is already registered, then the
// browser has it in its cache and executes it before fetching
// *anything* from the site it is registered to handle.  In this
// scenario, the service handler registers its fetch handler and
// handles the site fetches either from cache or online.  Eventually
// we fetch swi.js, and when that executes, it tries to register
// sw.js again.  If sw.js can't be found online, then the new
// registration process is tossed out, and we just keep executing
// with the browser's copy of sw.js.  The same thing happens if the
// online sw.js is identical to the browser's copy.  However, if
// the online sw.js is different, then it kicks off the installation
// process.
//
// Now in a normal PWA, the 'install' handler goes off and fetches
// and caches all the URLs that it wants.  Then, when the service
// worker gets activated (e.g. during the next site visit, perhaps
// while offline), it can fetch the cached URLs instead of downloading
// them online.
//
// However, my PWA is different and does essentially nothing when it
// is installed.  Only when there is explicit user interaction will
// it start updating the cache.
//
//
// The above describes what happens when the service worker is already
// registered.  If it is being encountered for the first time, then
// nothing happens until swi.js tries to register it.  The browser
// fetches sw.js and executes it, then calls the 'install' handler.
// In this case, the service worker doesn't process any fetches
// until it is activated.

self.addEventListener('install', fn_install);

async function fn_install(event) {
  console.info('fn_install()');

  // If there was a previous service worker, by default this new one
  // simply waits during this session and becomes the new service worker
  // in the *next* session.  By calling skipWaiting(), we immediately
  // replace the previous service worker to become the active one.
  //
  // We don't care if skipWaiting completes while we're in this handler
  // or if it happens later in the waiting state, so we don't need to
  // wrap it in event.waitUtil().
  self.skipWaiting();
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
// one also starts updating, weird things could happen.  That requires the
//  following sequence:
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
  console.info('activate');
  clients.claim();
});


/*** convert callbacks to promises ***/

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


/*** Handle a fetch request ***/

// The 'fetch' event handler must be added synchronously during the
// first script execution.  We cannot wait until the URL DB has been
// read, because that's asynchronous!  See the fetch_handler() code
// below for how we handle the race of read_db() and fetch_handler().

console.info('adding fetch handler');
self.addEventListener('fetch', fetch_handler);

// Remove the prepended scope from the URL of a request.
// The scope is a string such as 'https://localhost:8000/'.
//
// This function can be performed on a real fetch request (which has
// a real URL) or on a key from the cache (which the cache has tried
// to format as a URL, but with a base64 value in place of the
// relative URL).
function remove_scope_from_request(request) {
  return request.url.substr(registration.scope.length);
}

// Handle a fetch request from a client (window/tab).
// Map the URL to a base64 encoding (from the indexedDB), then
// map the base64 encoding to a cache entry.

function fetch_handler(event) {
  // The request is guaranteed to be in scope, so we can simply
  // remove the scope to get the relative URL.
  let url = remove_scope_from_request(event.request);
  console.info('fetching ' + url);

  if ((!url_data) || (url in url_data)) {
    // There is a race condition between initializing url_data
    // and fetching the first URL.  Fortunately, our fetch
    // response is allowed to be asynchronous.  So if we recognize
    // the URL *or* we don't have url_data yet, tell the event
    // to wait until we can create a fetch response.
    event.respondWith(fetch_response(event, url));
  } else {
    // I found some documentation that says that performance is
    // better if we simply fail to handle a request when making
    // the default online fetch is fine.  So that's what we do
    // if we have url_data and it's an unrecognized URL.  In
    // most cases this will be because the user never pressed
    // the shiny green button to cache anything.
    console.info(url + ' not recognized')
    return;
  }
}

async function fetch_response(event, url) {
  // As described in fetch_handler() above, we might be here because
  // we don't have url_data yet.  Presumably url_data is already in
  // the process of being read from the indexedDB, but I'm not sure
  // how to wait for that result.  Instead I take the simple path of
  // simply reading it again.
  if (!url_data) {
    await read_db();
  }

  // Now we're guaranteed to have url_data and can proceed with
  // checking the cache.

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


/*** Read the old url_data ***/

// Until the user manually updates the cache again, we want to continue
// using the old url_data that was used to update the cache last time.
// E>g.
// - the user is online and updates the cache.
// - the user is online and visits the site again and gets a new sw.js,
//   but the user doesn't update the cache.
// - the user goes offline.
// In this case, the registered sw.js has a different URL->base64 map
// than what was used when creating the cache.  Trying to use the new
// url_data would result in cache misses, which is bad.
//
// The indexedDB stores the url_data value that was present when the
// cache was last updated.  We use this old url_data until the user
// updates the cache again.

async function open_db() {
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

  db = await async_callbacks(request);

  console.info('open_db() returns ' + db);
  return db;
}

// Read the cached url_data.
async function read_db() {
  console.info('read_db()');

  let db = await open_db();

  let tx = db.transaction("url_data").objectStore("url_data").get("key");
  let lookup = await async_callbacks(tx);

  console.info('lookup = ');
  console.info(lookup);
  if (lookup){
    url_data = lookup.value;
    console.info('url_data = ')
    console.info(url_data);
  }

  // Note that we throw away the db value when we exit.
  // My guess is that this allows the DB connection to close.
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


/*** Get the cache status ***/

// This code figure out how much information has been cached and how much
// more would be cached if the user asks for a cache update.

init_status();

async function init_status() {
  console.info('init_status()');

  // Do two things in parallel:
  //
  // 1. Read the old url_data from indexedDB.
  // Note that the fetch handler will also call read_db() if it needs it
  // before we're done here.  But we still call it here in order to
  // compare it to the new_url_data.
  //
  // 2. Generate new_url_data and check how much of it is already cached.
  await Promise.all([read_db(),
                     count_cached()]);

  // Compare the old url_data with new_url_data.
  // This tells us whether we need to update the indexedDB.
  // Generally we'd expect to only need to update the indexedDB when
  // there are also cache changes to perform, but there are other
  // possibilities, e.g.
  // - I swap the names (URLs) of two files in the cache, or
  // - The user manually deletes indexedDB.
  console.info('compare url_data to new_url_data');
  url_diff = false;

  // Check if any old URLs are missing from new_url_data or have
  // different base64 values.
  for (let url in url_data) {
    if (!(url in new_url_data) || (url_data[url] != new_url_data[url])) {
      url_diff = true;
    }
  }

  // Check if any new URLs are missing from the old url_data.
  // We already compared the base64 values for entries that match,
  // so we don't have to do that part again.
  for (let url in new_url_data) {
    if (!(url in url_data)) {
      url_diff = true;
    }
  }

  // Finally, prepare the appropriate info to send to swi.js.
  is_cache_up_to_date();
}

// Check how many KB of the new base64 values already have a file cached.
// Also compute the total KB that will be cached if the cache is updated.
async function count_cached() {
  console.info('count_cached()');

  new_url_data = {};
  for (let i = 0; i < url_to_base64.length; i++) {
    let url = url_to_base64[i][0];
    let base64 = url_to_base64[i][1];
    let kb = url_to_base64[i][2];
    new_url_data[url] = {base64: base64,
                         kb: kb};
    base64_to_kb[base64] = kb;
    kb_total += kb;
  }

  cache = await caches.open(BASE64_CACHE_NAME);
  requests = await cache.keys();
  console.info('checking base64 keys in the cache');
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
}


/*** delete unused caches ***/

// This code is not needed by any other code, so it happens whenever
// it feels like and finishes whenever it wants.

delete_unused_caches();

async function delete_unused_caches() {
  console.info('delete_unused_caches()');

  // Remove any old caches I might have left lying around from
  // previous versions of the code.
  var cacheNames = await caches.keys();

  // I deliberately skip an 'await' on this Promise because I don't need
  // the results for anything.
  Promise.all(
    cacheNames.map(function(cacheName) {
      if (cacheName !== BASE64_CACHE_NAME) {
        return caches.delete(cacheName);
      }
    })
  );
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

function clear_caches(event) {
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

  is_cache_up_to_date();
}

async function record_urls() {
  // Initialize a fresh URL DB object.
  url_data = new_url_data
  obj = {key: 'key', value: url_data};
  console.info(obj);
  await async_callbacks(db.transaction("url_data", "readwrite").objectStore("url_data").put(obj));
}

function is_cache_up_to_date() {
  if (base64_to_delete.length || Object.keys(base64_to_kb).length || url_diff) {
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
