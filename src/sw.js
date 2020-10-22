'use strict';

var url_data = [
/* insert code here */
];

console.info('starting from the beginning');

// Admittedly, these are terrible storage names.  But it's hard to change
// them now, and they only need to be unique among sites hosted at
// fred-rum.github.io (i.e. my own sites).
const DB_NAME = 'db-v1';
const DB_VERSION = 1;
const BASE64_CACHE_NAME = 'base64-cache-v1';

// Activity is 'init', 'busy', 'delete', 'update', or 'idle'.
// An initial 'init' activity prevents updates until everything
// is initialized.
var activity = 'init';
var msg = 'Checking for offline files';
var err_status = '';
var usage_msg = '';
var extra_msg = '';

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
// (as represented by a base64 key).  It is also used to determine
// whether a cached base64 key is needed by the new url_data.
var base64_to_kb;

// old_base64 indicates the base64 keys being used by the old url_data.
// The values are meaningless; only the keys are used.
var old_base64;

// all_base64 indicates the base64 keys currently in the cache.
// The values are meaningless; only the keys are used.
var all_base64;

// Keep track of the number of files that are unneeded by either the
// old url_data or the new url_data.  (Obsolete files.)
var num_obs_files;

// Keep track of the number of files that are used by old url_data but
// aren't needed by the new url_data.  (Old files.)
var num_old_files;

// kb_total is the total KB needed by new_url_to_base64;
var kb_total = 0;

// kb_cached is the total KB needed by new_url_to_base64 and already
// cached (i.e. a subset of kb_total).
var kb_cached = 0;

// Indicate cache errors.
var red_missing = false; // someone deleted files from the cache
var red_missed = false;  // we forgot to put files in the cache

// When validate_flag is true, the cache will be revalidated at the
// next opportunity.
var validate_flag = false;


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

  if (!url_to_base64 || offline_ready) {
    // There is a race condition between initializing url_to_base64
    // and fetching the first URL.  Fortunately, our fetch
    // response is allowed to be asynchronous.  So if we recognize
    // the URL *or* we don't have url_to_base64 yet, tell the event
    // to wait until we can create a fetch response.
    event.respondWith(fetch_response(event, url));
  } else {
    console.info(url, ' fetched in online mode')

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

  // fetch_response() is normally only called when offline_ready is true,
  // but it is also called when offline_ready hasn't been initialized yet.
  // So after read_db() is done, check offline_ready again.
  if (!offline_ready) {
    return fetch(event.request);
  }

  if (!(url in url_to_base64)) {
    // If we're offline and a fetch is attempted of an unrecognized file,
    // generate a 404 without attempting an online fetch.  This can happen
    // when the browser speculatively fetches a file such as favicon.ico.
    // Or the user could type in a URL by hand or use an old URL.  2Or
    // url_data could be incomplete, but given the other failure types,
    // it seems unwise to panic the user when there's nothing the user can
    // do about it.
    console.info('%s not recognized; generating a 404', url)
    return generate_404(url, ' is not part of the current Guide.  Try the search bar.');
  }

  let response = await caches.match(url_to_base64[url]);

  if (!response) {
    // Flag the missing file (even if we can find a fall-back solution below).
    red_missing = true;
    url_diff = true;

    // We trigger a re-validation of the cache so that an 'update' will know
    // what files to fetch.
    validate_flag = true;
  }

  // If the offline copy of a full-size photo is missing, try falling back
  // to its thumbnail.
  if (!response && url.startsWith('photos/')) {
    console.info('%s not found; falling back to thumbnail', url);
    let alt_url = 'thumbs/' + url.substr('photos/'.length);
    // If url_to_base64[alt_url] is undefined, then no cache will match.
    // I.e. we don't have to explicitly check whether url is valid.
    response = await caches.match(url_to_base64[alt_url]);
  } else if (!response && url.startsWith('thumbs/')) {
    console.info('%s not found; falling back to full-size photo', url);
    let alt_url = 'photos/' + url.substr('thumbs/'.length);
    response = await caches.match(url_to_base64[alt_url]);
  }

  if (response) {
    console.info('%s found', url)
    return response;
  }

  if (url.startsWith('photos/') ||
      url.startsWith('thumbs/') ||
      url.startsWith('figures/') ||
      url.startsWith('favicons/')) {
    // Generate a 404 for non-essential files.
    console.info('%s not found; generating a 404', url)
    return generate_404(url, ' has gone missing from your offline copy.  Update your offline files.');
  } else {
    // For small files and essential files (particularly those needed to
    // run the service worker interface), get them from the internet.
    console.info('%s not found; fetching from the internet', url)
    return fetch(event.request);
  }
}

function generate_404(url, msg) {
  return Promise.resolve(new Response('<html>' + decodeURI(url) + msg, {'status': 404, headers: {'Content-Type': 'text/html; charset=utf-8'}}));
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

  try {
    let db = await open_db();
    let tx = db.transaction('url_data').objectStore('url_data').get('data');
    let lookup = await async_callbacks(tx);
    console.info('lookup =', lookup);
    url_to_base64 = lookup.url_to_base64;
    if (url_to_base64 === undefined) throw 'oops';
    offline_ready = true;

    // Note that we throw away the db value when we exit its scope.
    // My guess is that this allows the DB connection to close.
  } catch (e) {
    console.info('indexedDB lookup failed', e);
    console.info('(This is normal if it was not initialized.)');
    url_to_base64 = {};
    offline_ready = false;
  }

  // Generate a dictionary of old base64 keys from the url_to_base64 data.
  old_base64 = {};
  for (let url in url_to_base64) {
    let base64 = url_to_base64[url];
    old_base64[base64] = true;
  }
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

activity_promise = init_status();

async function init_status() {
  console.info('init_status()');

  // Read the old url_to_base64 from indexedDB.
  // Note that the fetch handler will also call read_db() if it needs
  // it before we're done here.  But we still call it here in order to
  // compare it to the new_url_to_base64.
  await read_db();

  check_url_diff();

  activity = 'validate';
  msg = 'Validating offline files';
  await count_cached();
}

function validate_cache() {
  activity = 'validate';
  msg = 'Validating offline files';
  activity_promise = count_cached();
}

// Check how many KB of the new base64 values already have a file cached.
// Also compute the total KB that will be cached if the cache is updated.
async function count_cached() {
  console.info('count_cached()');

  all_base64 = {};
  kb_cached = 0;
  num_old_files = 0;
  num_obs_files = 0;

  let cache = await caches.open(BASE64_CACHE_NAME);
  let requests = await cache.keys();

  for (let i = 0; i < requests.length; i++) {
    let base64 = remove_scope_from_request(requests[i]);
    all_base64[base64] = true;

    if (base64 in base64_to_kb) {
      kb_cached += base64_to_kb[base64];
    } else if (base64 in old_base64) {
      num_old_files++;
    } else {
      num_obs_files++;
    }
  }

  // Check for files that are supposed to be in the offline copy
  // but have gone missing.
  for (let base64 in old_base64) {
    if (!(base64 in all_base64)) {
      red_missing = true;
      url_diff = true;
    }
  }

  validate_flag = false;

  console.info('init done');
  activity = 'idle';
}

// Compare the old url_to_base64 with new_url_to_base64.
// This tells us whether we need to update the indexedDB.
// Generally we'd expect to only need to update the indexedDB when
// there are also cache changes to perform, but there are other
// possibilities, e.g.
// - I swap the names (URLs) of two files in the cache, or
// - The user manually deleted the indexedDB, but the cached files remain
//   up to date.
function check_url_diff() {
  console.info('check_url_diff()');
  url_diff = false;

  // This function might be called a second time after the caches are
  // clear, so be sure to throw away old values before accumulating
  // new data.
  base64_to_kb = {};
  kb_total = 0;

  new_url_to_base64 = {};
  for (let i = 0; i < url_data.length; i++) {
    let url = url_data[i][0];
    let base64 = url_data[i][1];
    let kb = url_data[i][2];
    new_url_to_base64[url] = base64;
    base64_to_kb[base64] = kb;
    kb_total += kb;
  }

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
  // the old err_status.  I no longer remember why this was useful.
  if (event.data == 'start') {
    err_status = '';
  }


  /////////////////////////////////////////////////////////////////////////////
  // Respond to an activity request.

  if (event.data === 'update') {
    if ((activity === 'init') ||
        (activity === 'validate') ||
        (activity === 'idle') ||
        (activity === 'delete')) {
      if (is_cache_up_to_date() && (activity !== 'init')) {
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
    if ((activity === 'validate') ||
        (activity === 'idle') ||
        (activity === 'delete') ||
        (activity === 'update')) {
      clear_caches();
    } else {
      // Ignore the request in other states.
      console.info(activity + ': ignore delete request');
    }
  }

  // If nothing else is going on, validate the cache or delete obsolete files.
  if ((activity === 'idle') && validate_flag) {
    validate_cache();
  } else if ((activity === 'idle') && num_obs_files) {
    activity_promise = idle_delete_obs_files(false);
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

  if (activity === 'init') {
    var progress = '';
  } else if (activity === 'validate') {
    var progress = '? / ' + mb_total + ' MB';
  } else {
    var progress = mb_cached + ' / ' + mb_total + ' MB';
  }

  // status is used by old copies of swi.js,
  // with progress combined with msg.
  if (activity === 'init') {
    var status = msg;
  } else if (activity === 'idle') {
    msg = '';
    var status = progress;
  } else {
    var status = progress + ' &ndash; ' + msg;
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
    // init can queue a user action, but it doesn't yet know whether
    // there is anything to do.
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
  } else { // idle or validate
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
  //
  // icon is no longer used in the latest swi.js, but it is supported
  // for a potentially cached copy of swi.js.
  var icon = undefined;
  var top_msg = undefined;
  if (activity !== 'init') {
    if (offline_ready) {
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
    } else {
      var top_msg = 'online';
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
    extra: extra_msg,
    top_msg: top_msg,
    red_missing: red_missing,
    red_missed: red_missed,
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
  } else if (activity === 'validate') {
    msg = 'Waiting for validation to complete'
  } else if (activity === 'init') {
    msg = 'Waiting for service worker to initalize'
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
  // we terminate the other activity before progressing to the delete
  // clear_caches action.
  //
  // (Note that we do *not* allow the delete button to do anything while
  // the same delete is already in progress.)
  await stop_activity();

  console.info('clear_caches()');
  activity = 'busy';
  msg = 'Making all offline files obsolete';
  err_status = '';

  try {
    await kill_old_files();

    activity_promise = idle_delete_obs_files(true);
  } catch (e) {
    if (e) {
      console.error(e);
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
      activity = 'idle';
      validate_flag = true;
    }
  }
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
  // In particular, Firefox just fails to free the space, even if I let
  // everything settle before deleting, and even if I quit the browser
  // and restart.
  // 
  // So I delete all of the individual cache entries, instead.
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
    await cache.delete(request);
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

    let func = async function() {
      await fetch_all_to_cache_parallel(cache);
    };

    await protected_write(cache, func);

    // The old files are now obsolete.
    make_old_files_obsolete();

    // The new files are now official.
    await record_urls();
  } catch (e) {
    if (!e) {
      // If we receive a null, then the error has been sufficiently
      // handled already.
    } else if (is_quota_exceeded(e)) {
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

  validate_flag = true;
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
      let quota_exceeded = is_quota_exceeded(e);
      if (quota_exceeded && num_obs_files) {
        // Delete obsolete files.
        err_status = 'Storage limit reached.  Deleting obsolete files before continuing.';
        await delete_obs_files(cache);
        err_status = '';
        // now fall through and loop again.
      } else if (quota_exceeded && num_old_files) {
        // Delete old files.
        err_status = 'Storage limit reached.  Reverting to online mode so that old files can be deleted.';
        await kill_old_files();
        await delete_obs_files(cache);
        err_status = 'Storage limit reached.  Reverted to online mode so that old files could be deleted.';
        // now fall through and loop again.
      } else {
        throw e;
      }
    }
  }
}

function is_quota_exceeded(e) {
  return (e && ((e.name === 'QuotaExceededError') ||
                (e.name === 'NS_ERROR_FILE_NO_DEVICE_SPACE')));
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

// Dispatch multiple asynchronous threads, each fetching URLs to the cache.
// If any thread encounters an exception, it stops all threads, then throws
// the exception up the chain.  A thread that is stopped in this manner
// simply returns.  It does not throw anything, as that would just confuse
// the issue.
var stop_parallel_threads;
async function fetch_all_to_cache_parallel(cache) {
  stop_parallel_threads = false;

  let promises = [fetch_all_to_cache(cache, 0),
                  fetch_all_to_cache(cache, 1),
                  fetch_all_to_cache(cache, 2),
                  fetch_all_to_cache(cache, 3),
                  fetch_all_to_cache(cache, 4),
                  fetch_all_to_cache(cache, 5)];
  var results = await Promise.allSettled(promises);

  // If any thread has an exception, throw it up the chain.
  // If there are multiple exceptions, give priority to a non-null exception.
  // A null exception either has already been handled or requires no handling.
  let e_null = false;
  for (let i = 0; i < results.length; i++){
    if (results[i].status === 'rejected') {
      let e = results[i].reason;
      if (e) {
        throw e;
      } else {
        e_null = true;
      }
    }
  }
  if (e_null) throw null;

  console.info(results);
}

async function fetch_all_to_cache(cache, id) {
  for (let url in new_url_to_base64) {
    let base64 = new_url_to_base64[url]
    if (!(base64 in all_base64)) {
      // Update all_base64 immediately so that parallel threads don't
      // pick the same URL/base64 to fetch.  We'll revert this later
      // if the fetch/put fail.
      all_base64[base64] = true;

      try {
        await fetch_to_cache(cache, url, base64);
      } catch (e) {
        // Remove the aborted base64 value from all_base64.
        delete all_base64[base64];

        stop_parallel_threads = true;

        throw e;
      }

      kb_cached += base64_to_kb[base64];
    }
  }
}

async function fetch_to_cache(cache, url, base64) {
  msg = 'Fetching ' + decodeURI(url)
  console.info(msg)
  let response;

  // Normally this loop does nothing since by default it ends with a break
  // statement.  But a 503 response can cause it to continue looping.
  for (let retry_sleep = 1; retry_sleep *= 2; true) {
    await check_stop_or_pause('update (before fetch)');

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
      err_status = '404: Could not find ' + decodeURI(url) + '<br>The online Guide must have updated its files just now.  Refresh the page and try again.';
      throw null;
    } if ((response.status == 503) && (retry_sleep <= 8)) {
      // Take N discrete one-second sleeps to make it easier to interrupt.
      // This also re-iterates the retry message in case this is the last
      // thread left running, and it would otherwise look silent.
      for (let i = 0; i < retry_sleep; i++) {
        // Use msg instead of err_status because it's a huge pain to clean up
        // err_status on both success and failure when some other process might
        // have generated a higher priority error message.
        let secs = retry_sleep - i;
        if (secs == 1) {
          secs = '1 second';
        } else {
          secs = secs + ' seconds';
        }
        msg = '503: server busy; retrying in ' + secs;

        await check_stop_or_pause('update (before fetch)');
        await sleep(1000);
      }
      continue;
    } else if (!response.ok) {
      err_status = response.status + ': ' + response.statusText + '<br>The online server is behaving oddly.  Try again later?';
      throw null;
    }

    break;
  }

  await check_stop_or_pause('update (before cache write)');

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
  old_base64 = base64_to_kb;
  url_diff = false;
  red_missing = false;
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

async function check_stop_or_pause(from) {
  await check_stop(from);

  if (stop_parallel_threads) {
    console.info('stopping parallel thread during ' + from);
    throw null;
  }
}

async function idle_delete_obs_files(and_new_files) {
  console.info('idle_delete_obs_files()');
  activity = 'delete';
  msg = 'Deleting obsolete offline files';
  
  try {
    let cache = await caches.open(BASE64_CACHE_NAME);
    await delete_obs_files(cache, and_new_files);
  } catch (e) {
    if (e) {
      console.error(e);
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
      validate_flag = true;
    }
  }

  activity = 'idle';
}

// delete_obs_files() can be called in three circumstances:
// 1. when 'idle': deletes obsolete files
// 2. from 'update': deletes obsolete files
//    (old files may have just been made obsolete)
// 3. when the 'delete' button is pushed: deletes all files
//    (old files are made obsolete before calling this)
//    This case calls the function with and_new_files=true.
//
// In 1 & 3, the activity is 'delete', and it can be interrupted for
// an update or to delete files.  And yes, that's redundant from 3,
// but whatever.
//
// In 2, the activity is 'update', and it can be interrupted to pause
// the update or to delete all files (scenario 3 above).  Also related
// to 2, if a previous update added files to all_base64, they become
// last to be deleted.  (This may also be true of keys read from the
// cache.  I haven't checked.)  This is surprisingly, but convenient
// if the user cancels the delete with another update.
async function delete_obs_files(cache, and_new_files) {
  console.info('delete_obs_files()');

  if (and_new_files) {
    var total = Object.keys(all_base64).length;
  } else {
    var total = num_obs_files;
  }

  var count = 0;
  for (let base64 in all_base64) {
    await check_stop('delete_obs_files()');

    if ((!(base64 in base64_to_kb) && !(base64 in old_base64)) ||
        and_new_files) {
      count++;

      msg = 'Queued deletion of ' + count + ' / ' + total;
      if (and_new_files) {
          msg += ' offline files';
      } else {
          msg += ' obsolete offline files';
      }

      await cache.delete(base64);

      delete all_base64[base64];

      if (base64 in base64_to_kb) {
        kb_cached -= base64_to_kb[base64];
      } else {
        num_obs_files--;
      }
    }
  }

  console.info('done with delete_obs_files()');
  if (num_obs_files) {
    console.error('num_obs_files:', num_obs_files);
  }
}

async function kill_old_files() {
  offline_ready = false;
  url_diff = true;
  red_missing = false;
  make_old_files_obsolete();
  await delete_db();
}

function make_old_files_obsolete() {
  old_base64 = {};
  num_obs_files += num_old_files;
  num_old_files = 0;
}

function is_cache_up_to_date() {
  return !url_diff;
}

// Update cache usage estimate.
async function update_usage() {
  // In the service worker, 'navigator' is a WorkerNavigator,
  // which provides a subset of the Navigator interface.
  if (navigator.storage) {
    let estimate = await navigator.storage.estimate();
    var usage = estimate.usage;
    var quota = estimate.quota;
  } else {
    var usage = 0; // trigger guesstimate
    var quota = undefined; // limit unknown
  }

  var kb_usage = usage / 1024;
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
  // To avoid confusion, pretend that the usage is 0.0 MB if we
  // think the cache is empty.
  let cache_empty = !(kb_cached || offline_ready || num_obs_files);

  // Sometimes we're not sure whether the cache is empty.
  let unsure_if_empty = ((activity === 'init') ||
                         (activity === 'validate') && (!offline_ready));

  if (unsure_if_empty) {
    usage_msg = 'Using ? MB of offline storage.';
  } else if (cache_empty) {
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
  // I dunno why they thought that was a good idea, but we have to deal
  // with it.
  //
  // The result replaces the normal usage calculation, and is in a
  // completely different format.
  if (!usage && !cache_empty) {
    // We don't know the size of old and obsolete files in the cache.
    // Just guess based on how many there are.
    let kb_per_file = kb_total / url_data.length;
    let kb_estimate = kb_per_file * (num_old_files + num_obs_files);

    // The guesstimated total will often be equal to kb_total,
    // modulo floating point discrepencies.  To avoid a disconnect
    // with the progress values, use the same fudge factor.
    var kb_usage = kb_cached + kb_estimate;
    status_usage = (kb_usage/1024 + 0.1).toFixed(1) + ' MB'
    if (activity === 'validate') {
      usage_msg = 'Using roughly ? MB of offline storage.';
    } else {
      usage_msg = 'Using roughly ' + status_usage + ' of offline storage.';
    }

    if (quota === undefined) {
      usage_msg += '<br>Browser limit is unknown.';
    } else {
      usage_msg += '<br>Browser allows at least ' + status_quota + '.';
    }
  }

  // kb_needed is the estimated worst case usage when update completes
  // and before old/obsolete files are deleted.  Include hysteresis:
  // the kb_needed calculation is a bit more pessimistic when the extra
  // message is visible than when it is clear.
  if (extra_msg) {
    var kb_needed = kb_usage + ((kb_total - kb_cached) * 1.25) + (16 * 1024);
  } else {
    var kb_needed = kb_usage + ((kb_total - kb_cached) * 1.2) + (10 * 1024);
  }

  if (!is_cache_up_to_date() &&
      (num_old_files + num_obs_files) &&
      quota &&
      (kb_needed > quota/1024)) {
    extra_msg = 'The Guide will delete old files if necessary to make space for the update.'
  } else {
    extra_msg = '';
  }
}
