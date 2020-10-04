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
var stop_updating = false;

// url_to_base64 is the mapping of URL to base64 key that we're currently
// using for checking the cache.  It is initialized from the indexedDB,
// but is updated to new_url_to_base64 when the cache is updated.
var url_to_base64;

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
// It also removes any trailing #anchor.
//
// This function can be performed on a real fetch request (which has
// a real URL) or on a key from the cache (which the cache has tried
// to format as a URL, but with a base64 value in place of the
// relative URL).
function remove_scope_from_request(request) {
  let url = request.url;
  let scope_end = registration.scope.length
  let anchor_pos = url.indexOf('#');
  if (anchor_pos == -1) {
    return url.substring(scope_end);
  } else {
    return url.substring(scope_end, anchor_pos);
  }
}

// Handle a fetch request from a client (window/tab).
// Map the URL to a base64 encoding (from the indexedDB), then
// map the base64 encoding to a cache entry.

function fetch_handler(event) {
  // The request is guaranteed to be in scope, so we can simply
  // remove the scope to get the relative URL.
  let url = remove_scope_from_request(event.request);
  console.info('fetching', url);

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
    console.info(url, 'not recognized')
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

  let response = await caches.match(url_to_base64[url]);
  console.info(response);
  if (response) {
    console.info(url, 'found')
    return response;
  } else {
    console.info(url, 'not found')
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

  try {
    let tx = db.transaction('url_data').objectStore('url_data').get('data');
    let lookup = await async_callbacks(tx);
    console.info('lookup =', lookup);
    url_to_base64 = lookup.url_to_base64;
    if (url_to_base64 === undefined) {
        url_to_base64 = {};
    }
  } catch {
    console.warn('indexedDB lookup failed');
    url_to_base64 = {};
  }

  console.info('url_to_base64 =', url_to_base64);

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

  console.info('open_db() returns', db);
  return db;
}

// This function is called when the indexedDB is accessed for the first time.
// (It will also be called if I increment the version number, in which case
// I need to adjust this code to avoid an error.)
async function dbupgradeneeded(event) {
  let db = event.target.result;
  db.createObjectStore("url_data", { keyPath: "key" });
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

  // This function might be called a second time after the caches are
  // clear, so be sure to throw away old values before accumulating
  // new data.
  base64_to_kb = {};
  base64_to_delete = [];
  kb_total = 0;
  kb_cached = 0;

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
      console.info('Need to delete', base64);
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
        console.info(url, 'not found in new_url_to_base64');
      } else {
        console.info(url, 'has different data in new_url_to_base64');
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
      console.info(url, 'not found in the old url_to_base64');
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

  // If this is the first poll after the page is refreshed, clear
  // the old err_status.
  if (event.data == 'start') {
    err_status = '';
  }

  if (updating === 'Checking cache') {
    var status = updating;
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

    status = status_cached + ' / ' + status_total + ' MB'

    if (updating !== false) {
      status += ' - ' + updating;
    }
  }
  if (updating === false) {
    var update_class = 'update-update';
  } else if ((updating === 'Up to date') ||
             (updating === 'Checking cache') ||
             (updating === 'Clearing caches')) {
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

  // If we previously told the cache update to stop, then check whether
  // it is now stopped, and clear the flag if so.
  // We do this here to avoid all possible race conditions.
  if ((updating === false) || (update_class === 'update-disable')) {
    stop_updating = false;
  }

  if (event.data === 'update') {
    if (updating === false) {
      // There is no current activity, so start updating the cache.
      update_cache();
    } else if (update_class === 'update-disable') {
      // If we're still checking the cache or if the cache is up to date,
      // ignore the update request.
      console.info('ignore update request');
    } else {
      // If a cache update is in progress, kill it.
      console.info('stop_updating = true');
      stop_updating = true;
    }
  } else if (event.data === 'clear') {
    // If the user clicks the 'Clear Cache' button multiple times in a
    // row, I don't bother to suppress simultaneous calls to clear_caches().
    // Intuition and experimentation indicates that the worst that happens
    // is that the same cache entry is deleted multiple times, and doing
    // so is harmless and safe.
    clear_caches();
  }
}

// We don't bother to wait for these calls to finish.  We just fire them
// off and assume that the caches will get cleared eventually.
async function clear_caches() {
  // stop_updating isn't perfect if a cache update is in progress, but
  // I figure that it should be pretty good and reasonably safe.
  stop_updating = true;

  console.info('clear_caches()');
  updating = 'Clearing caches';

  // For some reason, indexedDB.deleteDatabase() often hangs for me.
  // So I replace the data with an empty set, instead.
  /*
  let request = indexedDB.deleteDatabase(DB_NAME);
  result = await async_callbacks(request);
  console.info('indexedDB delete result =', result);
  */

  let db = await open_db();
  await async_callbacks(db.transaction("url_data", "readwrite").objectStore("url_data").clear());
  url_to_base64 = {};
  url_diff = true;

  // For some reason, caches.delete() often hangs for me.
  // So I delete all of the individual cache entries, instead.
  /*
  request = caches.delete(BASE64_CACHE_NAME);
  result = await async_callbacks(request);
  console.info('cache delete result =', result);
  */

  await delete_all_cache_entries();

  // Reset which files need to be cached.
  await count_cached();

  check_url_diff();

  is_cache_up_to_date();
}

async function delete_all_cache_entries() {
  console.info('delete_all_cache_entries()')
  let cache = await caches.open(BASE64_CACHE_NAME);
  let requests = await cache.keys();

  console.info('num to delete =', requests.length);

  for (let i = 0; i < requests.length; i++) {
    let request = requests[i]
    console.info('Deleting', request);
    await cache.delete(request);
  }
}

// When requested, switch to using the newest url_to_base64
// and update the cache to match.
async function update_cache() {
  console.info('update_cache()');
  err_status = '';

  // Recording URLs should finish in a flash, but deleting cached files
  // could take finite time, so we just use the 'deleting' message for
  // both steps.
  updating = 'Deleting out-of-date cached files';

  await record_urls();

  let cache = await caches.open(BASE64_CACHE_NAME);

  if (base64_to_delete.length) {
    console.info(updating)
  }
  for (let i = 0; i < base64_to_delete.length; i++) {
    // Pay attention to the global stop_updating variable and
    // bail out if it becomes true.
    if (stop_updating){
      return is_cache_up_to_date();
    }

    let base64 = base64_to_delete[i];
    console.info('Deleting', base64);
    await cache.delete(base64);

  }
  base64_to_delete = [];

  // (The old url_to_base64 might not accurately reflect the cache,
  // so ignore that and look at the cache directly.)
  for (let url in url_to_base64) {
    let base64 = url_to_base64[url]
    if (base64 in base64_to_kb) {
      let kb = base64_to_kb[base64];
      updating = 'Fetching ' + decodeURI(url)
      console.info(updating)
      let response;
      try {
        response = await fetch(url);
      } catch {
        console.warn('fetch failed');
        updating = false;
        err_status = '<br>Lost online connectivity.  Try again later.';
        return;
      }

      // Pay attention to the global stop_updating variable and
      // bail out if it becomes true.  We put this check just before
      // the cache.put() so that we don't update the cache after
      // stop_updating becomes true.
      if (stop_updating){
        return is_cache_up_to_date();
      }

      if (response && response.ok) {
        // Associate the fetched page with the base64 encoding.
        await cache.put(base64, response);

        // Entries left in base64_to_kb are ones that need to be fetched.
        delete base64_to_kb[base64];

        kb_cached += kb;
      } else if (response.status == 404) {
        console.warn('fetch missing');
        err_status = '<br>Could not find ' + url + '<br>The Guide must have updated online just now.  Refresh the page and try again.';
        updating = false;
        return;
      } else {
        console.warn('strange server response');
        err_status = '<br>' + response.status + ' ' + response.statusText + '<br>The online server is behaving oddly.  Try again later?';
        updating = false;
        return;
      }
    }
  }

  is_cache_up_to_date();
}

// Record new_url_to_base64 to the indexedDB and begin using it as the current
// url_to_base64.
async function record_urls() {
  console.info('record_urls()');

  let db = await open_db();

  let obj = {key: 'data',
             url_to_base64: new_url_to_base64
            };
  await async_callbacks(db.transaction("url_data", "readwrite").objectStore("url_data").put(obj));

  url_to_base64 = new_url_to_base64;
  url_diff = false;
}

function is_cache_up_to_date() {
  let files_to_fetch = (Object.keys(base64_to_kb).length);
  let cached_files_to_delete = base64_to_delete.length;
  if (files_to_fetch || cached_files_to_delete || url_diff) {
    if (files_to_fetch) {
      console.info('files to fetch:', files_to_fetch);
    }
    if (cached_files_to_delete) {
      console.info('cached files to delete:', cached_files_to_delete);
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
      usage = 'Cache is empty';
    } else if (estimate.usage/1024 >= kb_cached) {
      usage = status_usage + ' MB cached with overhead';
    } else {
      usage = status_usage + ' MB cached with compression';
    }
    usage += ' (browser allows up to ' + status_quota + ' GB)';
  }
}
