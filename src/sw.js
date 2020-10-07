var url_data = [
/* insert code here */
];

console.info('starting from the beginning');

var DB_NAME = 'db-v1';
var DB_VERSION = 1;
var BASE64_CACHE_NAME = 'base64-cache-v1';

// Activity is 'init', 'busy', 'delete', 'update', or 'idle'.
// An initial 'init' activity prevents updates until everything
// is initialized.
var activity = 'init';
var msg = 'Checking for offline files';
var err_status = '';
var usage_msg = '';

// There are some occasions where I allow an activity to be interrupted.
// For that, we set a flag to tell the activity to stop at the next
// opportunity, and we then await its promise (which otherwise is allowed
// to run and complete asynchronously).
var stop_activity_flag = false;
var activity_promise;

// offline_ready is undefined when we haven't yet checked the indexedDB.
//
// offline_ready is false when we've checked the indexedDB and didn't
// find any URL data, which means that we don't think we have a complete
// copy of all offline files.
//
// offline_ready is true when we've successfully read the URL data from
// the indexedDB, which implies that the offline copy was completely
// fetched some time in the past.  Unfortunate circumstances might have
// corrupted the data, but that's what the offline_ready flag is really
// for; corrupted data is presented very differently to the user than
// no data (or incomplete data).
var offline_ready = undefined;

// url_to_base64 is the mapping of URL to base64 key that we're currently
// using for checking the cache.  It is initialized from the indexedDB,
// but is updated to new_url_to_base64 when the cache is updated.
var url_to_base64;

// new_url_to_base64 is the most up-to-date mapping of URL to base64.
// It is used to update the cache when the user is ready.
var new_url_to_base64;

// url_diff indicates whether new_url_to_base64 differs from url_to_base64.
var url_diff;

// base64_to_kb indicates how many KB are required for each new file
// (as represented by a base64 hash).
// only those files that aren't yet cached.
var base64_to_kb = {};

// base64_wanted indicates which files we need to fetch during an update.
// It is the subset of base64_to_kb that is not already cached.
var base64_wanted = {};

// kb_total is the total KB needed by new_url_to_base64;
var kb_total = 0;

// kb_cached is the total KB needed by new_url_to_base64 and already
// cached (i.e. a subset of kb_total).
var kb_cached = 0;

// obs_base64_to_delete indicates which base64 keys in the cache are not
// needed by url_to_base64 or new_url_to_base64, so they can be deleted
// anytime.
var obs_base64_to_delete = [];

// old_base64_to_delete indicates which base64 keys in the cache are
// needed by url_to_base64 but not by url_to_base64, so they can be
// delete once an update is complete.
var old_base64_to_delete = [];


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
  // wrap it in event.waitUntil().
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
    // We got here because the URL wasn't recognized in url_to_base64,
    // which can happen either because url_to_base64 is empty (and
    // offline_ready is false) or because we're trying to fetch a file
    // that we don't recognize.
    if (offline_ready) {
      console.info(url, 'not recognized')
    }

    // I found some documentation that says that performance is
    // better if we simply fail to handle a request, in which case
    // the browser performs the default online fetch.
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
    if (url_to_base64 === undefined) throw 'oops';
    offline_ready = true;
  } catch (e) {
    console.info('indexedDB lookup failed', e);
    console.info('(This is normal if it was not initialized.)');
    url_to_base64 = {};
    offline_ready = false;
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

  // Read the old url_to_base64 from indexedDB.
  // Note that the fetch handler will also call read_db() if it needs
  // it before we're done here.  But we still call it here in order to
  // compare it to the new_url_to_base64.
  await read_db();

  msg = 'Validating offline files';
  let cache = await caches.open(BASE64_CACHE_NAME);
  await count_cached(cache);
  check_url_diff();

  activity = 'idle';
}

// Check how many KB of the new base64 values already have a file cached.
// Also compute the total KB that will be cached if the cache is updated.
async function count_cached(cache) {
  console.info('count_cached()');

  // This function might be called a second time after the caches are
  // clear, so be sure to throw away old values before accumulating
  // new data.
  base64_to_kb = {};
  obs_base64_to_delete = [];
  old_base64_to_delete = [];
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

  // Generate a temporary dictionary of old base64 keys from the
    // old url_to_base64 data read earlier.
  let old_base64 = {};
  for (let url in url_to_base64) {
    let base64 = url_to_base64[url];
    old_base64[base64] = true;
  }

  // Is this really how you copy a dictionary in Javascript?  Crazy.
  base64_wanted = Object.assign({}, base64_to_kb);

  console.info('checking base64 keys in the cache');
  let requests = await cache.keys();

  for (let i = 0; i < requests.length; i++) {
    let base64 = remove_scope_from_request(requests[i]);
    if (base64 in base64_to_kb) {
      kb_cached += base64_to_kb[base64];

      // Entries left in base64_wanted are ones that need to be fetched.
      delete base64_wanted[base64];
    } else if (base64 in old_base64) {
      old_base64_to_delete.push(base64);
    } else {
      obs_base64_to_delete.push(base64);
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
    if (!(url in new_url_to_base64)) {
      console.info(url, 'not found in new_url_to_base64');
      url_diff = true;
      return;
    }
    if (url_to_base64[url] != new_url_to_base64[url]) {
      console.info(url, 'has different data in new_url_to_base64');
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

  console.info('done with check_url_diff()');
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
  // the old err_status.  I know longer remember why this was useful.
  if (event.data == 'start') {
    err_status = '';
  }


  /////////////////////////////////////////////////////////////////////////////
  // Respond to an activity request.

  if (event.data === 'update') {
    if ((activity === 'idle') || (activity === 'delete')) {
      if (is_cache_up_to_date()) {
        // do nothing
        console.info('cache is up to date: ignore update request');
      } else {
        update_cache_when_ready();
      }
    } else if (activity === 'update') {
      pause_update();
    } else {
      // Ignore the request in other states.
      console.info(activity + ': ignore update request');
    }
  } else if (event.data === 'clear') {
    if ((activity === 'idle') ||
        (activity === 'delete') ||
        (activity === 'update')) {
      clear_caches();
    } else {
      // Ignore the request in other states.
      console.info(activity + ': ignore delete request');
    }
  }

  // If nothing else is going on, delete obsolete files.
  if ((activity === 'idle') && obs_base64_to_delete.length) {
    activity_promise = idle_delete_obs_files();
    monitor_promise();
  }


  /////////////////////////////////////////////////////////////////////////////
  // Respond to the poll with our status.

  // Pretend that we need a bit more data than we actually do.
  // That way, if there's a tiny bit more data to fetch
  // (or only data to delete, or an indexedDB to update),
  // it appears as if there is still 0.1 MB of data to cache.
  var mb_total = (kb_total/1024 + 0.1).toFixed(1);

  if (is_cache_up_to_date()) {
    var mb_cached = mb_total;
  } else {
    var mb_cached = (kb_cached/1024).toFixed(1);
  }

  // Default messages.  Either of these may be modified below
  // if it doesn't make sense for the current activity.
  var progress = mb_cached + ' / ' + mb_total + ' MB';

  // status is used by old copies of swi.js,
  // with progress combined with msg.
  var status = progress + ' &ndash; ' + msg;

  if (activity === 'init') {
    progress = '';
    status = msg;
  } else if (activity === 'idle') {
    msg = '';
    status = progress;
  }

  // This is the default update_button text.
  // We replace it further below for the 'update' activity.
  if (activity !== 'update') {
    if (offline_ready) {
      var update_button = 'Update Offline Files';
    } else {
      var update_button = 'Save Offline Files';
    }
  } else {
    if (offline_ready) {
      var update_button = 'Pause Updating';
    } else {
      var update_button = 'Pause Saving';
    }
  }

  if (activity === 'init') {
    var update_class = 'update-disable';
    var clear_class = 'clear-disable';
  } else if (activity === 'busy') {
    var update_class = 'update-disable';
    var clear_class = 'clear-disable';
  } else if (activity === 'delete') {
    if (is_cache_up_to_date()) {
      var update_class = 'update-disable';
    } else {
      var update_class = 'update-update';
    }
    var clear_class = ''; // enabled
  } else if (activity === 'update') {
    var update_class = 'update-stop';
    var clear_class = ''; // enabled
  } else { // idle
    var clear_class = ''; // enabled
    if (is_cache_up_to_date()) {
      var update_class = 'update-disable';
    } else {
      var update_class = 'update-update';
    }
  }

  // offline_ready is initialized quickly so that we can respond to
  // initial fetches as soon as possible.  But don't set the top_msg
  // until we've checked whether what color it should be.
  var icon = undefined;
  var top_msg = undefined;
  if (offline_ready && (activity !== 'init')) {
    if (is_cache_up_to_date()) {
      var top_msg = 'green';
    } else {
      var top_msg = 'yellow';
      if (activity !== 'update') {
        // The yellow icon is only shown on non-home pages when an update
        // is needed *and* no update is in progress.
        var icon = 'yellow';
      }
    }
  }

  // Update the cache usage estimate.
  // We don't actually wait for its asynchronous operation to finish
  // since that would break this event handler, but hopefully it'll be
  // ready by the next time we poll.
  update_usage();

  var poll_msg = {
    update_button: update_button,
    update_class: update_class,
    progress: progress,
    msg: msg,
    status: status,
    err_status: err_status,
    usage: usage_msg,
    top_msg: top_msg,
    icon: icon,
    clear_class: clear_class,
  };
  event.source.postMessage(poll_msg);
}

async function pause_update() {
  await stop_activity();

  activity = 'idle'
  err_status = '';
}

// If activity is ongoing, tell it to stop, then wait for it to stop.
async function stop_activity() {
  if (activity === 'update') {
    msg = 'Pausing update in progress';
  } else if (activity === 'delete') {
    msg = 'Pausing deletions';
  } else if (activity === 'idle') {
    // No activity to stop.
    return;
  } else {
    // We should never be trying to stop 'init' or 'busy' activity.
    console.error('stop_activity() called when activity is ' + activity);
    throw 'oops';
  }

  activity = 'busy';

  console.log('await activity_promise');
  stop_activity_flag = true;
  await activity_promise;
  activity_promise = undefined;
  stop_activity_flag = false;
  console.info('activity stopped');
}

async function clear_caches() {
  // We allow the delete button to be clicked while the cache is being
  // updated or obsolete files are being deleted.  When that happens,
  // we terminate the other activity progressing to the delete action.
  //
  // (Note that we do *not* allow the delete button to do anything while
  // the same delete is already in progress.)
  await stop_activity();

  console.info('clear_caches()');
  activity = 'busy';
  msg = 'Deleting all offline files';
  err_status = '';

  try {
    url_to_base64 = {};
    url_diff = true;
    offline_ready = false;

    await delete_db();
    await delete_all_cache_entries();

    // Reset which files need to be cached, similar to init_status().
    let cache = await caches.open(BASE64_CACHE_NAME);
    await count_cached(cache);
    check_url_diff();
    is_cache_up_to_date();
  } catch (e) {
    if (e) {
      console.error(e);
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
    }
  }

  activity = 'idle';
}

async function delete_db() {
  // For some reason, indexedDB.deleteDatabase() often hangs for me.
  // So I clear the objectStore, instead.
  let db = await open_db();
  await async_callbacks(db.transaction("url_data", "readwrite").objectStore("url_data").clear());
}

async function delete_all_cache_entries() {
  console.info('delete_all_cache_entries()')

  // For some reason, caches.delete() can really screw up some browsers.
  // E.g. I suspect that Firefox keeps a shadow copy in case there's more
  // activity, but then that shadow copy never goes away, even after a
  // browser restart.  So I delete all of the individual cache entries,
  // instead.
/*
  await caches.delete(BASE64_CACHE_NAME);
  return;
*/

  let cache = await caches.open(BASE64_CACHE_NAME);
  let requests = await cache.keys();

  console.info('num to delete =', requests.length);

  for (let i = 0; i < requests.length; i++) {
    msg = 'Queued deletion of ' + i + ' / ' + requests.length + ' files';
    let request = requests[i]
    cache.delete(request);
  }

  msg = 'Waiting for browser to process ' + requests.length + ' deleted files.';
  console.info('done with delete_all_cache_entries()');
}

async function update_cache_when_ready() {
  // We allow a cache update to be initiated while obsolete files are
  // being deleted.  When that happens, we terminate the deletion before
  // progressing to the cache update.
  await stop_activity();

  // There is no current activity, so start updating the cache.
  // By default, we don't wait for it to finish.
  // But we do record its promise so that clear_cache() can wait for it
  // to halt if necessary.
  activity_promise = update_cache();
  monitor_promise();
}

// Monitor the activity promise so that the console will clearly show if
// the promise ends too soon.  Note that it's perfectly fine for multiple
// entities to wait for a promise to resolve.  All of the callbacks will
// be called (or awaits returned) when the promise is resolved.  And the
// promise remains live for as long as a variable holds its value, so if
// any callback is added (or await started) after the activity is complete,
// the callback is resolved immediately.
async function monitor_promise() {
  await activity_promise;
  console.info('activity_promise complete');
}

// When requested, switch to using the new URL data
// and update the cache to match.
async function update_cache() {
  console.info('update_cache()');
  activity = 'update';
  err_status = '';

  try {
    msg = 'Preparing update';
    let cache = await caches.open(BASE64_CACHE_NAME);
    await protected_write(cache, write_margin);
    await fetch_all_to_cache(cache);
    await record_urls();
    make_old_files_obsolete();
  } catch (e) {
    if (!e) {
      // If we receive a null, then the error has been sufficiently
      // handled already.
    } else if ((e.name === 'QuotaExceededError') ||
               (e.name === 'NS_ERROR_FILE_NO_DEVICE_SPACE')){
      console.warn(e);
      err_status = 'Not enough offline storage available.  Sorry.';
      console.warn(err_status);
    } else {
      console.error(e);
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
    }

    // Clear the margin.
    try {
      await clear_margin();
    } catch (e) {
      console.error(e);
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
    }
  }

  // Whether we completed succesfully or bailed out on an error,
  // we're idle now.
  activity = 'idle';
}

// Wrap a function call in code that reacts appropriately to quota errors.
// If the write fails while there is old or obsolete data that can be deleted,
// delete the old data and try again.  If the write still fails, throw the
// exception back to the caller to handle.
async function protected_write(cache, func) {
  // Keep trying until we run out of options.
  while (true) {
    try {
      // Make sure to wait for func() to asynchronously finish.
      // Otherwise we won't catch its errors.
      return await func();
    } catch (e) {
      // The documented standard is 'QuotaExceededError'.
      // Testing reveals that Firefox throws a different exception, however.
      quota_error = (e && ((e.name === 'QuotaExceededError') ||
                           (e.name === 'NS_ERROR_FILE_NO_DEVICE_SPACE')));
      if (quota_error && obs_base64_to_delete) {
        // Delete obsolete files.
        err_status = 'Storage limit reached.  Deleting obsolete files before continuing.';
        await delete_obs_files(cache);
        err_status = '';
        // now fall through and loop again.
      } else if (quota_error && old_base64_to_delete.length) {
        // Delete old files.
        err_status = 'Storage limit reached.  Reverting to online mode so that old files can be deleted.';
        offline_ready = false;
        make_old_files_obsolete();
        await delete_db();
        await delete_obs_files(cache);
        err_status = 'Storage limit reached.  Reverted to online mode so that old files could be deleted.';
        // now fall through and loop again.
      } else {
        throw e;
      }
    }
  }
}

// Open the DB and write a single object to it.
async function write_obj(obj) {
  let db = await open_db();
  await write_obj_to_db(db, obj);
}

// Write an object to an open DB.
async function write_obj_to_db(db, obj) {
  await async_callbacks(db.transaction("url_data", "readwrite").objectStore("url_data").put(obj));
}

// Store ~4 to 8 MB of junk in the indexedDB.
// If we're able to perform all non-critical writes with this margin in place,
// then after removing the margin we're sure to have space remaining for
// critical resources.
//
// Without this protection I found that I often couldn't register a new
// sw.js.  That's painful during debugging, and it could be disasterous if
// I ever accidentally release a bad sw.js.
async function write_margin() {
  // Because Firefox compresses our data, we need to construct our
  // junk from something non-predictable.
  // generate enough random (assumed 8-byte) numbers to fill 2 MB.
  // list overhead will take some amount more space.
  let junk = [];
  let n = 4*1024*1024/8;
  for (let i = 0; i < n; i++){
    junk.push(Math.random());
  }

  let obj = {key: 'margin',
             junk: junk};
  await write_obj(obj);
}

async function clear_margin() {
  let obj = {key: 'margin',
             junk: ''};
  await write_obj(obj);
}

async function fetch_all_to_cache(cache) {
  for (let url in new_url_to_base64) {
    let base64 = new_url_to_base64[url]
    if (base64 in base64_wanted) {
      await protected_write(cache, async function () {
        await fetch_to_cache(cache, url, base64)
      });

      kb_cached += base64_to_kb[base64];

      // Entries left in base64_to_kb are ones that need to be fetched.
      delete base64_wanted[base64];
    }
  }
}

async function fetch_to_cache(cache, url, base64) {
  await check_stop('update (before fetch)');

  msg = 'Fetching ' + decodeURI(url)
  console.info(msg)
  let response;
  try {
    response = await fetch(url);
  } catch (e) {
    console.warn('fetch failed', e);
    err_status = 'Lost online connectivity.  Try again later.';
    throw null;
  }

  if (!response) {
    err_status = 'Unexpected fetch response.  Try again later?';
    throw null;
  } if (response.status == 404) {
    err_status = 'Could not find ' + decodeURI(url) + '<br>The online Guide must have updated its files just now.  Refresh the page and try again.';
    throw null;
  } else if (!response.ok) {
    err_status = response.status + ' - ' + response.statusText + '<br>The online server is behaving oddly.  Try again later?';
    throw null;
  }

  await check_stop('update (before cache.put)');

  // The fetch was successful.  Now write the result to the cache.
  //
  // Note that we're running within protected_write(),
  // so a quota error in cache.put() will be handled properly.
  await cache.put(base64, response);
}

// Record new_url_to_base64 to the indexedDB and begin using it as the current
// url_to_base64.
async function record_urls() {
  console.info('record_urls()');
  let db = await open_db();

  // Clear margin.  This is a separate transaction since I suspect that
  // combining it with the following write in one atomic transaction would
  // cause more space to be allocated before the margin space is freed.
  let obj = {key: 'margin',
             junk: ''};
  await write_obj_to_db(db, obj);

  // Write data.
  obj = {key: 'data',
         url_to_base64: new_url_to_base64
        };
  await write_obj_to_db(db, obj);

  url_to_base64 = new_url_to_base64;
  url_diff = false;
  offline_ready = true;

  // We might have encountered an issue during processing,
  // but it doesn't matter anymore.
  err_status = '';
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/* check_stop is generally a synchronous function, but for debugging purposes
   I'll occasionally insert a sleep(), which requires an asynchronous function.
*/
async function check_stop(from) {
  if (stop_activity_flag) {
    console.info(from + ' is now stopped');
    /*
    await sleep(1000);
    console.info('sleep is done');
    */
    throw null;
  }
}

async function idle_delete_obs_files() {
  console.info('idle_delete_obs_files()');
  activity = 'delete';
  
  try {
    let cache = await caches.open(BASE64_CACHE_NAME);
    await delete_obs_files(cache);
  } catch (e) {
    if (e) {
      console.error(e);
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
    }
  }

  activity = 'idle';
}

async function delete_obs_files(cache) {
  console.info('delete_obs_files()');

  var total = obs_base64_to_delete.length;
  while (obs_base64_to_delete.length) {
    await check_stop('delete_obs_files()');

    msg = 'Queued deletion of ' + (total - obs_base64_to_delete.length) + ' / ' + total + ' obsolete offline files';
    await cache.delete(obs_base64_to_delete.pop());
  }

  console.info('done with delete_obs_files()');
}

function make_old_files_obsolete() {
  // The old files are now obsolete.
  while (old_base64_to_delete.length) {
    obs_base64_to_delete.push(old_base64_to_delete.pop());
  }
  old_base64_to_delete = [];
}

function is_cache_up_to_date() {
  let files_to_fetch = (Object.keys(base64_wanted).length);
  return !(files_to_fetch || url_diff);
}

// Update cache usage estimate.
async function update_usage() {
  if (navigator.storage) {
    let estimate = await navigator.storage.estimate();
    var usage = estimate.usage;
    var quota = estimate.quota;
  } else {
    var usage = 0; // trigger guesstimate
    var quota = undefined; // limit unknown
  }

  var status_usage = (usage/1024/1024).toFixed(1) + ' MB';

  // The Firefox quota maxes out at 2 GiB.  Since the current file list
  // uses ~650 MB and could temporarily use double that if (somehow)
  // all the files update at once, that seems like a reasonable cutoff
  // for displaying GB vs. MB.
  if (quota < 2*1024*1024*1024) {
    var status_quota = (quota/1024/1024).toFixed(1) + ' MB';
  } else {
    var status_quota = (quota/1024/1024/1024).toFixed(1) + ' GB';
  }

  // The running service worker itself counts as significant usage
  // (0.5 MB to more than 10 MB, depending on activity).
  // Addionally, it can take a long time for the usage to update after
  // clearing the caches (perhaps even forever when idle).
  // Both problems can be fixed by pretending the usage is 0.0 when
  // we don't have any cached files.
  if (!(kb_cached ||
        old_base64_to_delete.length ||
        obs_base64_to_delete.length)) {
    usage_msg = 'Using 0.0 MB of offline storage.';
  } else if (usage/1024 >= kb_cached + 0.1) {
    usage_msg = 'Using ' + status_usage + ' (including overhead).';
  } else {
    usage_msg = 'Using ' + status_usage + ' (with compression).';
  }

  if (quota === undefined) {
    usage_msg += '<br>Browser limit is unknown.';
  } else {
    usage_msg += '<br>Browser allows up to ' + status_quota + '.';
  }

  // When desktop Firefox asks for a receives permission for persistent
  // storage, it effectively removes the storage limit.  But instead of
  // increasing the quota, the browser pretends that there's no usage.
  // Dunno why they thought that was a good idea, but we have to deal
  // with it.
  //
  // The result replaces the normal usage calculation, and is in a
  // completely different format.
  if (!usage &&
      (kb_cached ||
       old_base64_to_delete.length ||
       obs_base64_to_delete.length)) {

    // We don't know the size of old and obsolete files in the cache.
    // Just guess based on how many there are.
    let kb_per_file = kb_total / url_data.length;
    let estimated_files = (old_base64_to_delete.length +
                           obs_base64_to_delete.length);
    let kb_estimate = kb_per_file * estimated_files;

    // The guesstimated total will often be equal to kb_total,
    // modulo floating point discrepencies.  To avoid a disconnect
    // with the progress values, use the same fudge factor.
    if (kb_cached || estimated_files) {
      status_usage = ((kb_cached + kb_estimate)/1024 + 0.1).toFixed(1) + ' MB'
    } else {
      status_usage = '0.0 MB';
    }
    usage_msg = 'Using roughly ' + status_usage + '.';

    if (quota === undefined) {
      usage_msg += '<br>Browser limit is unknown.';
    } else {
      usage_msg += '<br>Browser allows at least ' + status_quota + '.';
    }
  }
}
