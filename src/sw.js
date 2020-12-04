'use strict';

// The 'insert code here' comment is replaced by cache.py with a few
// variable definitions that summarize information from url_data.json.
// These summary values help us keep the user informed about any pending
// update without needing to read the (large) url_data.json file.
//
// The following variables are defined:
//
// 'upd_timestamp' indicates the date/time that the latest update was
// generated.  If cur_timestamp is different (presumably older), then an
// update is available.
//
// Note that because sw.js is fetched first, and files to cache are fetched
// later, some or all files in the cache may be newer than this timestamp.
// That's OK.  The next time a page is refreshed, it will indicate that an
// update is available, and that update will potentially refetch some files
// that were already new, but that is also OK.
//
// 'upd_num_urls' indicates the number of URLs in the latest update
//
// 'upd_kb_total' indicates the total KB in the latest update

/* insert code here */

console.info('starting from the beginning');

// Admittedly, these are terrible storage names.  But it's hard to change
// them now, and they only need to be unique among sites hosted at
// fred-rum.github.io (i.e. my own sites).
const DB_NAME = 'db-v1';
const DB_VERSION = 1;
const BASE64_CACHE_NAME = 'base64-cache-v1';

// We open the database at the beginning of execution and leave it open
// throughout.  Firefox is then forced to close the database connection
// when clearing the site data, which seems to prevent us from getting
// in stuck with a database but no objectStore.
var db;

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
//
// stop_activity_flag can also be used by an activity on itself.  E.g.
// when fetches are performed in parallel, an error in one thread will
// stop activity in all other threads.
var stop_activity_flag = false;
var activity_promise;

// If a fetch is attempted before the DB is read, the fetch handler
// awaits db_promise so that it can then use the DB values.
var db_promise;

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

// cur_url_to_base64 is the mapping of URL to base64 key that we're currently
// using for checking the cache.  It is initialized from the indexedDB,
// but is updated to upd_url_to_base64 when the cache is updated.
var cur_url_to_base64;

// upd_url_to_base64 is the most up-to-date mapping of URL to base64.
// It is used to update the cache when the user is ready.
var upd_url_to_base64;

// upd_pending indicates whether an update is warranted, i.e. if
// - upd_timestamp differs from cur_timestamp, or
// - any files are missing from the cache (red_missing).
var upd_pending = false;

// upd_base64_to_kb indicates how many KB are required for each file in
// the update (as represented by a base64 key).
var upd_base64_to_kb;

// cur_timestamp indicates the date/time when the cached offline files
// were generated.  If upd_timestamp is different (presumably newer),
// then an update is available.
var cur_timestamp;

// cur_base64 indicates the base64 keys being used by the currently
// cached offline files.  The values are meaningless; only the keys are used.
var cur_base64;

// all_base64 indicates the base64 keys currently in the cache.
// The values are meaningless; only the keys are used.
var all_base64;

// all_num_cached is the length of all_base64 (which is otherwise inefficient
// to compute).
var all_num_cached;

// Keep track of the number of files that are unneeded by either the
// old url_data or the new url_data.  (Obsolete files.)
var obs_num_files;

// Keep track of the number of files that are in cur_base64 but not in
// upd_base64_to_kb.  I.e. it is the count of files that can be deleted
// when the update completes.
var cur_num_files;

// upd_kb_cached is the total KB needed by upd_url_to_base64 and already
// cached (i.e. a subset of upd_kb_total).  It is undefined if upd_base64_to_kb
// is undefined.
var upd_kb_cached;

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

// A 'connection' is a combination of a transaction and the default
// objectStore.  The actual returned object is IDBObjectStore, from which
// the underlying transaction can be retreived.
function db_connection(mode) {
  return db.transaction('url_data', mode).objectStore('url_data');
}

// The db_connection_promise waits for a DB 'connection' (defined above)
// to complete or fail.  E.g. a put() *request* can succeed, but it's
// *transaction* fails due to a quota error.  This promise lets us catch
// that error.
function db_connection_promise(conn) {
  return new Promise((resolve, reject) => {
    conn.transaction.oncomplete = (event) => {
      resolve(undefined);
    };

    conn.transaction.onerror = (event) => {
      reject(conn.transaction.error);
    };

    conn.transaction.onabort = (event) => {
      reject(conn.transaction.error);
    };

    // There was one case where a transaction never reported any status,
    // which implies that it never auto-committed.  Maybe it was a bug on
    // my part, but to be on the safe side, I force the commit here.
    conn.transaction.commit();
  });
}

async function await_connection(conn) {
  conn.transaction.commit();
  await db_connection_promise(conn);
}

// Some interfaces use callbacks, but we'd rather use Promises.
// db_request_promise() converts a callback interface into a Promise.
//
// The first parameter, 'request', is a request that has been made.
// We assume that it has callbacks 'onsuccess' and 'onerror', and
// db_request_promise() assigns those callbacks.
// - When the 'onsuccess' callback is called, the promise is resolved
//   and returns the request.result.
// - When the 'onerror' callback is called, the promise is rejected.
function db_request_promise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = (event) => {
      resolve(request.result);
    };

    request.onerror = (event) => {
      reject(request.error);
    };
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

  if (offline_ready === false) {
    // I found some documentation that says that performance is
    // better if we simply fail to handle a request, in which case
    // the browser performs the default online fetch.
    console.info(url, 'fetched in online mode')
    return;
  } else {
    // There is a race condition between initializing offline_ready
    // and fetching the first URL.  Fortunately, our fetch response
    // is allowed to be asynchronous.  So if we're ready to fetch
    // from the cache (offline_ready === true) *or* if we don't yet
    // know the cache status (offline_ready === undefined), tell the
    // event to wait until we can create a fetch response.
    event.respondWith(fetch_response(event, url));
  }
}

async function fetch_response(event, url) {
  // As described in fetch_handler() above, we might be here because
  // we don't yet know the proper offline_ready value (or the related
  // cur_url_to_base64 value, etc.)  The db_promise is initialized as
  // soon as sw.js starts execution with no asynchronous delay, so we
  // know that it is valid, and we can await it.  In normal cases,
  // the promise will return immediately, but of course its response
  // will be delayed if the DB read is still in progress.
  await db_promise;

  // Now we're guaranteed to have cur_url_to_base64 and can proceed with
  // performing the fetch.

  // fetch_response() is normally only called when offline_ready is true,
  // but it is also called when offline_ready hasn't been initialized yet.
  // So after read_db() is done, check offline_ready again.
  if (!offline_ready) {
    return fetch(event.request);
  }

  if (!(url in cur_url_to_base64)) {
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

  let response = await caches.match(cur_url_to_base64[url]);

  if (!response) {
    // Flag the missing file (even if we can find a fall-back solution below).
    red_missing = true;
    upd_pending = true;

    // We trigger a re-validation of the cache so that an 'update' will know
    // what files to fetch.
    validate_flag = true;
  }

  // If the offline copy of a full-size photo is missing, try falling back
  // to its thumbnail.
  if (!response && url.startsWith('photos/')) {
    console.info('%s not found; falling back to thumbnail', url);
    let alt_url = 'thumbs/' + url.substr('photos/'.length);
    // If cur_url_to_base64[alt_url] is undefined, then no cache will match.
    // I.e. we don't have to explicitly check whether url is valid.
    response = await caches.match(cur_url_to_base64[alt_url]);
  } else if (!response && url.startsWith('thumbs/')) {
    console.info('%s not found; falling back to full-size photo', url);
    let alt_url = 'photos/' + url.substr('thumbs/'.length);
    response = await caches.match(cur_url_to_base64[alt_url]);
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

/*** Read the indexedDB ***/

// The indexedDB stores the cur_url_to_base64 mapping for the currently
// cached files.
//
// The indexedDB also stores a base64_to_kb mapping for the most recent
// update that was started.  If that update failed to complete, then we
// conveniently have full information about the update status without
// needing to check any online files.  Conversely, if the update completed
// and hasn't been superceded by a more recent update, then this information
// simply duplicates the summary variables at the top of this script.

async function read_db() {
  console.info('read_db()');

  try {
    await open_db();
    let conn = db_connection('readonly');
    let async_cur_data = db_request_promise(conn.get('data'));
    let async_upd_data = db_request_promise(conn.get('upd_base64_to_kb'));
    // We don't check the final transaction status because we don't care.

    let cur_data = await async_cur_data;
    console.info('indexedDB data:', cur_data);

    if (cur_data && cur_data.url_to_base64) {
      cur_url_to_base64 = cur_data.url_to_base64;
      cur_timestamp = cur_data.timestamp; // may be undefined
      offline_ready = true;
      console.info('found cur_url_to_base64 in DB');

      // Generate a dictionary of base64 keys from the cur_url_to_base64 data.
      cur_base64 = {};
      for (let url in cur_url_to_base64) {
        let base64 = cur_url_to_base64[url];
        cur_base64[base64] = true;
      }
    } else {
      // Note that we don't initialize these variables until after all
      // asynchronous activity is complete.  Otherwise, a fetch could find
      // that they are initialized (and thus presumed valid), but their
      // values aren't yet filled in.
      cur_url_to_base64 = {};
      cur_base64 = {};
      offline_ready = false;
    }

    // We started this read just after the async_data read, but we don't bother
    // to await its results until now.
    let upd_data = await async_upd_data;

    // The upd_data isn't critical, and if no such data is found,
    // we just continue without it.  We also ignore the upd_data if
    // its timestamp doesn't match the current upd_timestamp.
    if (upd_data && (upd_data.timestamp === upd_timestamp)) {
      upd_base64_to_kb = upd_data.upd_base64_to_kb;
      console.info('found upd_base64_to_kb in DB');
    }

    // Note that we throw away the db and os values when we exit their scope.
    // My guess is that this allows the DB connection to close.
  } catch (e) {
    console.info('indexedDB lookup failed', e);
    console.info('(This is normal if it was not initialized.)');
    cur_url_to_base64 = {};
    cur_base64 = {};
    offline_ready = false;
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
  // with the db_request_promise promise.  It just does its own thing when
  // necessary.
  request.onupgradeneeded = dbupgradeneeded;

  db = await db_request_promise(request);

  console.info('open_db() gets', db);
}

// This function is called when the indexedDB is accessed for the first time.
// (It will also be called if I increment the version number, in which case
// I need to adjust this code to avoid an error.)
async function dbupgradeneeded(event) {
  console.info('dbupgradeneeded()');

  // Since this callback is called *during* the indexedDB.open, the
  // global 'db' variable hasn't been set yet.
  let db = event.target.result;
  db.createObjectStore('url_data', {keyPath: 'key'});
}


/*** Get the cache status ***/

// This code figure out how much information has been cached and how much
// more would be cached if the user asks for a cache update.

activity_promise = init_status();
monitor_promise();

async function init_status() {
  console.info('init_status()');

  // Read the indexedDB.
  // The fetch handler also needs the results of read_db(), so
  // it will also await db_promise if necessary.
  db_promise = read_db();
  await db_promise;

  // This comparison does the right thing even if cur_timestamp is undefined.
  upd_pending = (upd_timestamp !== cur_timestamp);

  activity = 'validate';
  msg = 'Validating offline files';
  await check_cached();
}

function validate_cache() {
  activity = 'validate';
  msg = 'Validating offline files';
  activity_promise = check_cached();
  monitor_promise();
}

// Check which offline files are in the cache, and flag whether any files
// are missing that we expect to be there.
async function check_cached() {
  console.info('check_cached()');

  all_base64 = {};

  // Leave all_num_cached as undefined while waiting for the cache
  // transactions to prevent the progress message from temporarily
  // claiming the cache is empty when it might not be.
  let cache = await caches.open(BASE64_CACHE_NAME);
  let requests = await cache.keys();

  // all_num_cached is cleared here, but the single Javascript thread will
  // update it to a proper value before anyone can read the cleared value.
  all_num_cached = 0;
  for (const request of requests) {
    let base64 = remove_scope_from_request(request);
    all_base64[base64] = true;
    all_num_cached++;
  }

  // Check for files that are supposed to be in the offline copy
  // but have gone missing.
  for (let base64 in cur_base64) {
    if (!(base64 in all_base64)) {
      red_missing = true;
      upd_pending = true;
    }
  }

  count_cached();

  validate_flag = false;

  console.info('check_cached() done');
  activity = 'idle';
}

// Check how many KB of the new base64 values already have a file cached.
// Also compute the total KB that will be cached if the cache is updated.
function count_cached() {
  // If we don't know what files are in the update, then we can't count
  // the cache.
  if (!upd_base64_to_kb) return;

  console.info('count_cached()');

  console.info('upd_base64_to_kb:', upd_base64_to_kb);

  // upd_kb_total was initialized at the top of sw.js, but it's possible that
  // we got newer data from the JSON file.
  upd_kb_total = 0;
  upd_num_urls = 0;
  for (const base64 in upd_base64_to_kb) {
    upd_kb_total += upd_base64_to_kb[base64];
    upd_num_urls++;
  }

  console.info('all_base64:', all_base64);
  console.info('cur_base64:', cur_base64);

  upd_kb_cached = 0;
  cur_num_files = 0;
  obs_num_files = 0;
  for (const base64 in all_base64) {
    if (base64 in upd_base64_to_kb) {
      upd_kb_cached += upd_base64_to_kb[base64];
    } else if (base64 in cur_base64) {
      cur_num_files++;
    } else {
      obs_num_files++;
    }
  }
  console.info('cur_num_files:', cur_num_files);
  console.info('obs_num_files:', obs_num_files);
}


/*** delete unused caches ***/

// I'm not sure if I ever released any code with a different cache name.
// If anyone ever picked up any such code, hopefully it's had a chance to
// run.  Indiscriminately deleting other caches will prove dangerous if I
// ever release any other services linked to the same GitHub account, so
// I've commented out this code.  (I won't actually delete this code yet
// because it might perhaps be useful as a reference at some point.)

/*

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
*/


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
      if (upd_pending) {
        update_cache_when_ready();
      } else {
        // do nothing
        console.info('cache is up to date: ignore update request');
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
  } else if ((activity === 'idle') && obs_num_files) {
    activity_promise = idle_delete_obs_files(false);
    monitor_promise();
  }


  /////////////////////////////////////////////////////////////////////////////
  // Respond to the poll with our status.

  if (activity === 'init') {
    var progress = '';
  } else {
    // The 'progress' message is only displayed when an update is in progress.
    // We never want to look like we're done when there's anything left to do,
    // so we pretend that there's a little more to fetch in total than there
    // really is.  Thus, if there's a delay right at the end, there appears to
    // still be a little bit more to fetch.
    var mb_total = (upd_kb_total/1024 + 0.1).toFixed(1);

    if (all_num_cached == 0) {
      var mb_cached = '0.0';
    } else if (upd_kb_cached === undefined) {
      var mb_cached = '?';
    } else if (upd_pending) {
      var mb_cached = (upd_kb_cached/1024).toFixed(1);
    } else {
      // If we're up to date, make sure mb_cached matches mb_total.
      var mb_cached = (upd_kb_cached/1024 + 0.1).toFixed(1);
    }

    var progress = mb_cached + ' / ' + mb_total + ' MB';
  }

  if (activity === 'idle') {
    msg = '';
  }

  if (progress && msg) {
    var status = progress + ' &ndash; ' + msg;
  } else {
    // At least one of progress or msg is a blank string.
    // Use the non-blank one if there is one.
    // If both are blank, then status is also blank.
    var status = progress + msg;
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
  } else if (activity === 'update') {
    var update_class = 'update-stop';
    var clear_class = ''; // enabled
  } else { // idle, delete, or validate
    if (upd_pending) {
      var update_class = 'update-update';
    } else {
      var update_class = 'update-disable';
    }
    var clear_class = ''; // enabled
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
      if (!upd_pending) {
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
    // We should never be trying to stop 'busy' activity.
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
    await kill_cur_files();

    activity_promise = idle_delete_obs_files(true);
    monitor_promise();
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
  // (This comment was written very early in my indexedDB experimentation.
  // Perhaps I could get it working now, but it's not a priority.)
  let conn = db_connection('readwrite');
  await db_request_promise(conn.clear());
  await db_connection_promise(conn);
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
    await read_json();

    count_cached();

    let cache = await caches.open(BASE64_CACHE_NAME);
    await protect_update(cache);

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
  }

  // Whether we completed succesfully or bailed out on an error,
  // we're idle now.
  activity = 'idle';
}

async function read_json() {
  console.info('read_json()');
  var response = await fetch_and_verify('url_data.json');
  var url_data = await response.json();
  console.info('read OK');

  upd_url_to_base64 = {};
  upd_base64_to_kb = {};
  for (const url_data_item of url_data) {
    let url = url_data_item[0];
    let base64 = url_data_item[1];
    let kb = url_data_item[2];
    upd_url_to_base64[url] = base64;
    upd_base64_to_kb[base64] = kb;
  }
}

// When a cache update is in progress, write the upd_base64_to_kb info
// to indexedDB.  That way, if the update is interrupted and the service
// worker is reloaded, it can immediately display the progress completed
// so far without having to check online.
//
// We don't actually care that much whether the write completes, but
// we *do* care whether it triggers any quota problems.  Therefore, we
// do monitor the transaction and react appropriately to errors.
async function write_upd_base64_to_kb() {
  console.info('write_upd_base64_to_kb()');
  let obj = {key: 'upd_base64_to_kb',
             upd_base64_to_kb: upd_base64_to_kb,
             timestamp: upd_timestamp
            };
  await write_obj_to_db(obj);
}

// Wrap the protected_update() function in code that reacts appropriately
// to quota errors.  If a quota error occurs while there is old or obsolete
// data that can be deleted, delete the old data and try again.  Note that
// the 'try again' part expects the update to pick up where it left off
// despite being called again from scratch.
//
// The protection also includes writing a multi-megabyte chunk of data to
// the indexedDB that serves as a safety margin.  This margin attempts to
// protect against two horrible user experiences:
//
// - If the update succeeds or fails with barely any quota remaining, then
// loading a new service worker can silently fail, which means that the
// user is never told about new updates.
//
// - Firefox occasionally cannot delete a cache entry if the quota is too
// close to full.  WTF?  We delete the margin data prior to deletions (and
// hope that the indexedDB doesn't have the same problem) so that we the
// cache deletions will hopefully work.
async function protect_update(cache) {
  // Keep trying until we run out of options.
  while (true) {
    try {
      await write_margin();
      await protected_update(cache);
      await clear_margin();
      return;
    } catch (e) {
      // The documented standard is 'QuotaExceededError'.
      // Testing reveals that Firefox throws a different exception, however.
      let quota_exceeded = is_quota_exceeded(e);
      if (quota_exceeded && obs_num_files) {
        // Delete obsolete files.
        err_status = 'Storage limit reached.  Deleting obsolete files before continuing.';
        console.warn(err_status);
        await clear_margin();
        await delete_obs_files(cache);
        err_status = '';
        // now fall through and loop again.
      } else if (quota_exceeded && cur_num_files) {
        // Delete old files.
        err_status = 'Storage limit reached.  Reverting to online mode so that old files can be deleted.';
        console.warn(err_status);
        await clear_margin();
        await kill_cur_files();
        await delete_obs_files(cache);
        err_status = 'Storage limit reached.  Reverted to online mode so that old files could be deleted.';
        // now fall through and loop again.
      } else {
        // There's nothing to delete, so permanently fail the write.
        await clear_margin();
        throw e;
      }
    }
  }
}

async function protected_update(cache) {
  await write_upd_base64_to_kb();

  await fetch_all_to_cache_parallel(cache);

  // The old files are now obsolete.
  make_cur_files_obsolete();
}

function is_quota_exceeded(e) {
  return (e && ((e.name === 'QuotaExceededError') ||
                (e.name === 'NS_ERROR_FILE_NO_DEVICE_SPACE')));
}

// Write an object to the indexedDB.
async function write_obj_to_db(obj) {
  let conn = db_connection('readwrite');
  await db_request_promise(conn.put(obj));
  await db_connection_promise(conn);
}

// Store ~4 to 8 MB of junk in the indexedDB.
// If we're able to perform various large writes with this margin in place,
// then after removing the margin we're sure to have space remaining for
// small writes which would fail terribly on a quota error.
async function write_margin() {
  // Because Firefox compresses our data, we need to construct our
  // junk from something non-predictable.
  // generate enough random (assumed 8-byte) numbers to fill 2 MB.
  // list overhead will take some amount more space.
  console.info('write_margin()');
  let junk = [];
  let n = 4*1024*1024/8;
  for (let i = 0; i < n; i++){
    junk.push(Math.random());
  }

  let obj = {key: 'margin',
             junk: junk};
  await write_obj_to_db(obj);
}

async function clear_margin() {
  console.info('clear_margin()');

  // I've noticed that the delete sometimes fails in Firefox, but retrying
  // it shortly later seems to always succeed.  Grn.
  //
  // Oddly, overwriting the margin works more often than deleting it.
  // However, the overwrite does not always succeed, but a delete after
  // 1 second delay seems to always succeed.  Therefore, I've removed the
  // experimental code to attempt an overwrite.
  for (let delay of [1, 4, 'end']) {
    try {
      let conn = db_connection('readwrite');
      await db_request_promise(conn.delete('margin'));
      await db_connection_promise(conn);
      console.info('clear_margin() managed to delete');
      return; // break out of the delay loop
    } catch (e) {
      console.warn('clear_margin() failed to delete:', e);
      if (is_quota_exceeded(e) && (delay !== 'end')) {
        console.info('sleeping', delay, 'seconds before trying again');
        await sleep(delay * 1000);
      } else {
        // Delaying longer is not expected to work.  Continue on with
        // real work, and if errors persist, they'll be caught there.
        return;
      }
    }
  }
}

// Dispatch multiple asynchronous threads, each fetching URLs to the cache.
// If any thread encounters an exception, it stops all threads, then throws
// the exception up the chain.  If there are multiple exceptions, priority
// is given to a non-null exception.  A null exception is often a response
// to another exception (e.g. by a parallel thread), and we don't want it to
// suppress the original exception information.
async function fetch_all_to_cache_parallel(cache) {
  let promises = [fetch_all_to_cache(cache, 0),
                  fetch_all_to_cache(cache, 1),
                  fetch_all_to_cache(cache, 2),
                  fetch_all_to_cache(cache, 3),
                  fetch_all_to_cache(cache, 4),
                  fetch_all_to_cache(cache, 5)];
  var results = await Promise.allSettled(promises);

  // If stop_activity_flag was set in order to stop the parallel threads,
  // clear it.  But don't clear it if it was set by a pending user action.
  if (stop_activity_flag === 'stop_threads') {
    stop_activity_flag = false;
  }

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
  for (const url in upd_url_to_base64) {
    let base64 = upd_url_to_base64[url]
    if (!(base64 in all_base64)) {
      // Update all_base64 immediately so that parallel threads don't
      // pick the same URL/base64 to fetch.  We'll revert this later
      // if the fetch/put fail.
      all_base64[base64] = true;

      try {
        await fetch_to_cache(cache, url, base64);
        upd_kb_cached += upd_base64_to_kb[base64];
        all_num_cached++;
      } catch (e) {
        // Remove the aborted base64 value from all_base64.
        delete all_base64[base64];

        // If stop_activity_flag is already set by a pending user input,
        // don't touch it.  Otherwise, set stop_activity_flag to a special
        // value that causes the parallel threads to stop, after which we
        // clear the stop_activity_flag in order to resume normal operation
        // (which may be an error or a response to a full quota).
        if (!stop_activity_flag) {
          stop_activity_flag = 'stop_threads';
        }

        console.warn('stopping because of', e);
        throw e;
      }
    }
  }
}

async function fetch_to_cache(cache, url, base64) {
  msg = 'Fetching ' + decodeURI(url)
  console.info(msg)
  var response = await fetch_and_verify(url);

  await check_stop('update (before cache write)');

  // The fetch was successful.  Now write the result to the cache.
  //
  // Note that we're running within protected_write(),
  // so a quota error in cache.put() will be handled properly.
  await cache.put(base64, response);
}

// Fetch a URL, check for errors, and retry a few times for a 503 response.
async function fetch_and_verify(url) {
  // There is no 'normal' end condition for this loop.
  // Instead the loop is only exited with a return or throw:
  // - an 'OK' response returns the response.
  // - an error throws an exception.
  // - a 503 response loops a few times, then throws an exception if the
  //   problem doesn't clear up.
  for (let retry_sleep = 1; retry_sleep *= 2; true) {
    await check_stop('update (before fetch)');

    try {
      var response = await fetch(url, {cache: "no-cache"});
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

        await check_stop('update (before fetch)');
        await sleep(1000);
      }
      continue;
    } else if (!response.ok) {
      err_status = response.status + ': ' + response.statusText + '<br>The online server is behaving oddly.  Try again later?';
      throw null;
    } else {
      // response.ok
      return response;
    }
  }
}

// Record upd_url_to_base64 to the indexedDB and begin using it as
// cur_url_to_base64.
async function record_urls() {
  console.info('record_urls()');

  // Write data.
  let obj = {key: 'data',
             url_to_base64: upd_url_to_base64,
             timestamp: upd_timestamp
            };
  await write_obj_to_db(obj);

  cur_url_to_base64 = upd_url_to_base64;
  cur_base64 = upd_base64_to_kb;
  upd_pending = false;
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

async function idle_delete_obs_files(del_all_flag) {
  console.info('idle_delete_obs_files()');
  activity = 'delete';
  msg = 'Deleting obsolete offline files';
  
  try {
    let cache = await caches.open(BASE64_CACHE_NAME);
    await delete_obs_files(cache, del_all_flag);
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
//    This case calls the function with del_all_flag=true.
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
async function delete_obs_files(cache, del_all_flag) {
  console.info('delete_obs_files()');

  if (del_all_flag) {
    var total = all_num_cached;
  } else {
    var total = obs_num_files;
  }

  console.info('all_base64:', all_base64);
  console.info('cur_base64:', cur_base64);
  console.info('upd_base64_to_kb:', upd_base64_to_kb);

  try {
    var count = 0;
    for (const base64 in all_base64) {
      await check_stop('delete_obs_files()');

      if (del_all_flag ||
          (!(base64 in upd_base64_to_kb) && !(base64 in cur_base64))) {
        count++;

        msg = 'Queued deletion of ' + count + ' / ' + total;
        if (del_all_flag) {
          msg += ' offline files';
        } else {
          msg += ' obsolete offline files';
        }

        await cache.delete(base64);

        delete all_base64[base64];
        all_num_cached--;

        if (upd_base64_to_kb && (base64 in upd_base64_to_kb)) {
          upd_kb_cached -= upd_base64_to_kb[base64];
        } else {
          obs_num_files--;
        }
      }
    }

    console.info('done with delete_obs_files()');
    if (obs_num_files) {
      console.error('obs_num_files:', obs_num_files);
    }
    obs_num_files = 0;

    // We deleted upd_base64_to_kb from indexedDB, so to be consistent, we
    // also remove it from our internal variable.  (Actually, we deleted it
    // earlier in the delete process, but it's nice to temporarily keep the
    // variable around to help display the delete progress.  If the deletion
    // is interrupted by an update, then upd_base64_to_kb will normally be
    // re-read, so it doesn't matter that we kept the value around a bit
    // longer.)
    if (del_all_flag) {
      upd_base64_to_kb = undefined;
    }
  } catch (e) {
    // Prevent idle_delete_obs_files() from being repeatedly called and
    // hitting the same error every time.
    obs_num_files = 0;

    if (!e) {
      // If we receive a null, then the error has been sufficiently
      // handled already.
    } else if (is_quota_exceeded(e)) {
      console.error(e);
      err_status = 'The browser claims that we can&rsquo;t DELETE offline files because we&rsquo;re using too much space.  Yeah, really!  There&rsquo;s nothing more I can do.  You&rsquo;ll need to manually clear the site data from the browser.';
    } else {
      console.error(e);
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
    }
    throw null;
  }
}

async function kill_cur_files() {
  offline_ready = false;
  cur_timestamp = undefined;
  upd_pending = true;
  red_missing = false;
  make_cur_files_obsolete();
  await delete_db();
}

function make_cur_files_obsolete() {
  obs_num_files += cur_num_files;
  cur_num_files = 0;
  cur_base64 = {};
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
  let cache_empty = (all_num_cached == 0);

  // Sometimes we're not sure whether the cache is empty.
  let unsure_if_empty = ((activity === 'init') ||
                         (activity === 'validate') && (!offline_ready));

  if (unsure_if_empty) {
    usage_msg = 'Using ? MB of offline storage.';
  } else if (cache_empty) {
    usage_msg = 'Using 0.0 MB of offline storage.';
  } else if (usage/1024 >= upd_kb_cached + 0.1) {
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
    let kb_per_file = upd_kb_total / upd_num_urls;
    let kb_usage = kb_per_file * all_num_cached;

    // The guesstimated total will often be equal to upd_kb_total,
    // modulo floating point discrepencies.  To avoid a disconnect
    // with the progress values, use the same fudge factor.
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
    var kb_needed = kb_usage + ((upd_kb_total - upd_kb_cached) * 1.25) + (16 * 1024);
  } else {
    var kb_needed = kb_usage + ((upd_kb_total - upd_kb_cached) * 1.2) + (10 * 1024);
  }

  if (upd_pending &&
      (cur_num_files || obs_num_files) &&
      quota &&
      (kb_needed > quota/1024)) {
    extra_msg = 'The Guide will delete old files if necessary to make space for the update.'
  } else {
    extra_msg = '';
  }
}
