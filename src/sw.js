var url_data = [
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

// url_to_base64 is the mapping of URL to base64 key that we're currently
// using for checking the cache.  It is initialized from the indexedDB,
// but is updated to new_url_to_base64 when the cache is updated.
var url_to_base64 = undefined;

// new_url_to_base64 is the most up-to-date mapping of URL to base64.
// It is used to update the cache when the user is ready.
var new_url_to_base64;

// url_diff indicates whether new_url_to_base64 differs from url_to_base64.
var url_diff;

// base64_to_kb indicates how many KB are required for each file (as
// represented by a base64 hash).  It initially contains all of the 
// base64 keys in new_url_to_base64, but is later adjusted to include
// only those files that aren't yet cached.
var base64_to_kb = {};

// base64_to_delete indicates which base64 keys in the cache are no longer
// in use and can be deleted.
var base64_to_delete = [];

// These values indicate the total calculated size of files that we want
// to be cached and the total size of useful files that already are cached.
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

  if ((!url_to_base64) || (url in url_to_base64)) {
    // There is a race condition between initializing url_to_base64
    // and fetching the first URL.  Fortunately, our fetch
    // response is allowed to be asynchronous.  So if we recognize
    // the URL *or* we don't have url_to_base64 yet, tell the event
    // to wait until we can create a fetch response.
    event.respondWith(fetch_response(event, url));
  } else {
    // I found some documentation that says that performance is
    // better if we simply fail to handle a request when making
    // the default online fetch is fine.  So that's what we do
    // if we have url_to_base64 and it's an unrecognized URL.  In
    // most cases this will be because the user never pressed
    // the shiny green button to cache anything.
    console.info(url + ' not recognized')
    return;
  }
}

async function fetch_response(event, url) {
  // As described in fetch_handler() above, we might be here because
  // we don't have url_to_base64 yet.  Presumably url_to_base64 is
  // already in the process of being read from the indexedDB, but I'm
  // not sure how to wait for that result.  Instead I take the simple
  // path of simply reading it again.
  if (!url_to_base64) {
    await read_db();
  }

  // Now we're guaranteed to have url_to_base64 and can proceed with
  // checking the cache.

  var response = await caches.match(url_to_base64[url]);
  console.info(response);
  if (response) {
    console.info(url + ' found')
    return response;
  } else {
    console.info(url + ' not found')
    return fetch(event.request);
  }
}


/*** Read the old url_to_base64 ***/

// Until the user manually updates the cache again, we want to continue
// using the old url_to_base64 that was used to update the cache last time.
// E.g.
// - the user is online and updates the cache.
// - the user is online and visits the site again and gets a new sw.js,
//   but the user doesn't update the cache.
// - the user goes offline.
// In this case, the registered sw.js has a different URL->base64 map
// than what was used when creating the cache.  Trying to use the new
// url_to_base64 would result in cache misses, which is bad.
//
// The indexedDB stores the url_to_base64 value that was present when
// the cache was last updated.  We use this old url_to_base64 until the
// user updates the cache again.

// Read the cached url_to_base64.
async function read_db() {
  console.info('read_db()');

  let db = await open_db();

  let tx = db.transaction("url_data").objectStore("url_data").get("key");
  let lookup = await async_callbacks(tx);

  console.info('lookup = ');
  console.info(lookup);
  if (lookup){
    url_to_base64 = lookup.value;
    console.info('url_to_base64 = ')
    console.info(url_to_base64);
  }

  // Note that we throw away the db value when we exit.
  // My guess is that this allows the DB connection to close.
}

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

  let db = await async_callbacks(request);

  console.info('open_db() returns ' + db);
  return db;
}

// This function is called when the indexedDB is accessed for the first time.
// (It will also be called if I increment the version number, in which case
// I need to adjust this code to avoid an error.)
async function dbupgradeneeded(event) {
  let db = event.target.result;

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
  // 1. Read the old url_to_base64 from indexedDB.
  // Note that the fetch handler will also call read_db() if it needs
  // it before we're done here.  But we still call it here in order to
  // compare it to the new_url_to_base64.
  //
  // 2. Generate new_url_to_base64 and check how much of it is already
  // cached.
  await Promise.all([read_db(),
                     count_cached()]);

  check_url_diff();

  // Finally, prepare the appropriate info to send to swi.js.
  is_cache_up_to_date();
}

// Check how many KB of the new base64 values already have a file cached.
// Also compute the total KB that will be cached if the cache is updated.
async function count_cached() {
  console.info('count_cached()');

  new_url_to_base64 = {};
  for (let i = 0; i < url_data.length; i++) {
    let url = url_data[i][0];
    let base64 = url_data[i][1];
    let kb = url_data[i][2];
    new_url_to_base64[url] = base64;
    base64_to_kb[base64] = kb;
    kb_total += kb;
  }

  let cache = await caches.open(BASE64_CACHE_NAME);
  let requests = await cache.keys();
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

// Compare the old url_to_base64 with new_url_to_base64.
// This tells us whether we need to update the indexedDB.
// Generally we'd expect to only need to update the indexedDB when
// there are also cache changes to perform, but there are other
// possibilities, e.g.
// - I swap the names (URLs) of two files in the cache, or
// - The user manually deletes indexedDB.
function check_url_diff() {
  console.info('check_url_diff()');
  url_diff = false;

  // Check if any old URLs are missing from new_url_to_base64 or have
  // different base64 values.
  for (let url in url_to_base64) {
    if (!(url in new_url_to_base64) ||
        (url_to_base64[url] != new_url_to_base64[url])) {
      if (!(url in new_url_to_base64)) {
        console.info(url + ' not found in new_url_to_base64');
      } else {
        console.info(url + ' has different data in new_url_to_base64');
      }
      url_diff = true;
      return;
    }
  }

  // Check if any new URLs are missing from the old url_to_base64.
  // We already compared the base64 values for entries that match,
  // so we don't have to do that part again.
  for (let url in new_url_to_base64) {
    if (!(url in url_to_base64)) {
      console.info(url + ' not found in the old url_to_base64');
      url_diff = true;
      return;
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

    // Pretend that we need a bit more data than we actually do.
    // That way, if there's a tiny bit more data to fetch
    // (or only data to delete, or an indexedDB to update),
    // it appears as if there is still 0.1 MB of data to cache.
    let status_total = (kb_total/1024 + 0.1).toFixed(1)

    // If we really are full up to date, then adjust status_cached
    // to match the adjusted status_total.
    if (updating === 'Up to date') {
      status_cached = status_total;
    }

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

  // Update the cache usage estimate.
  // We don't actually wait for its asynchronous operation to finish
  // since that would break this event handler, but hopefully it'll be
  // ready by the next time we poll.
  update_usage();

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

// We don't bother to wait for these calls to finish.  We just fire them
// off and assume that the caches will get cleared eventually.
async function clear_caches(event) {
  // Also discard our local data.
  url_to_base64 = {};
  url_diff = true;

  console.info('clear_caches()');
  let request = indexedDB.deleteDatabase(DB_NAME);
  result = await async_callbacks(request);
  console.info('indexedDB delete result = ' + result);

  request = caches.delete(BASE64_CACHE_NAME);
  result = await async_callbacks(request);
  console.info('cache delete result = ' + result);

  is_cache_up_to_date();
}

// When requested, switch to using the newest url_to_base64
// and update the cache to match.
async function update_cache(event) {
  if (updating) {
    console.info('Update already in progress');
    return;
  }

  // Recording URLs should finish in a flash, but deleting cached files
  // could take finite time, so we just use the 'deleting' message for
  // both steps.
  updating = 'Deleting out-of-date cached files';

  await record_urls();

  cache = await caches.open(BASE64_CACHE_NAME);

  if (base64_to_delete.length) {
    console.info(updating)
  }
  for (let i = 0; i < base64_to_delete.length; i++) {
    let base64 = base64_to_delete[i];
    console.info('Deleting ' + base64);
    await cache.delete(base64);
  }
  base64_to_delete = [];

  // (The old url_to_base64 might not accurately reflect the cache,
  // so ignore that and look at the cache directly.)
  for (let url in url_to_base64) {
    let base64 = url_to_base64[url]
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
  console.info('record_urls()');
  url_to_base64 = new_url_to_base64
  obj = {key: 'key', value: url_to_base64};
  await async_callbacks(db.transaction("url_data", "readwrite").objectStore("url_data").put(obj));
  url_diff = false;
}

function is_cache_up_to_date() {
  let files_to_fetch = (Object.keys(base64_to_kb).length);
  let cached_files_to_delete = Object.keys(base64_to_kb).length;
  if (files_to_fetch || cached_files_to_delete || url_diff) {
    if (files_to_fetch) {
      console.info('files to fetch: ' + files_to_fetch);
    }
    if (cached_files_to_delete) {
      console.info('cached files to delete: ' + cached_files_to_delete);
    }
    if (url_diff) {
      console.info('url_diff');
    }
    updating = false;
  } else {
    updating = 'Up to date';
    console.info(updating);
  }
}

// Update cache usage estimate.
async function update_usage() {
  if (navigator && navigator.storage) {
    let estimate = await navigator.storage.estimate();
    let status_usage = (estimate.usage/1024/1024).toFixed(1)
    let status_quota = (estimate.quota/1024/1024/1024).toFixed(1)

    // The running service worker itself counts as significant usage
    // (e.g. 0.5 MB).  To avoid confusing the user, we treat the cache
    // as 'empty' if usage is low and we don't have any cached files.
    if ((kb_cached == 0) && (status_usage < 10.0)) {
      usage = ' Cache is empty';
    } else {
      usage = ' ' + status_usage + ' MB cached including overhead';
    }
    usage += ' (browser allows up to ' + status_quota + ' GB)';
  }
}
