'use strict';
var upd_timestamp = '2023-09-01T18:31:49.940907+00:00';
var upd_num_urls = 9113;
var upd_kb_total = 1016575
const DB_NAME = 'db-v1';
const DB_VERSION = 1;
const BASE64_CACHE_NAME = 'base64-cache-v1';
var db;
var activity = 'init';
var msg = 'Checking for local files';
var err_status = '';
var usage_msg = '';
var extra_msg = '';
var stop_activity_flag = false;
var activity_promise;
var db_promise;
var offline_ready = undefined;
var cur_url_to_base64;
var upd_url_to_base64;
var upd_pending = false;
var upd_base64_to_kb;
var cur_timestamp;
var cur_base64;
var all_base64;
var all_num_cached;
var obs_num_files;
var cur_num_files;
var upd_kb_cached;
var red_missing = false;
var red_missed = false;
var validate_flag = false;
self.addEventListener('install', fn_install);
async function fn_install(event) {
  self.skipWaiting();
}
self.addEventListener('activate', event => {
  clients.claim();
});
function db_connection(mode) {
  return db.transaction('url_data', mode).objectStore('url_data');
}
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
    conn.transaction.commit();
  });
}
async function await_connection(conn) {
  conn.transaction.commit();
  await db_connection_promise(conn);
}
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
self.addEventListener('fetch', fetch_handler);
function remove_scope_from_request(request) {
  let url = request.url;
  let scope_end = registration.scope.length
  let search_pos = url.indexOf('?');
  let anchor_pos = url.indexOf('#');
  if (search_pos > -1) {
    return url.substring(scope_end, search_pos);
  } else if (anchor_pos > -1) {
    return url.substring(scope_end, anchor_pos);
  } else {
    return url.substring(scope_end);
  }
}
function fetch_handler(event) {
  let url = remove_scope_from_request(event.request);
  if (offline_ready === false) {
    return;
  } else {
    event.respondWith(fetch_response(event, url));
  }
}
async function fetch_response(event, url) {
  await db_promise;
  if (!offline_ready) {
    return fetch(event.request);
  }
  if (url == '') {
    url = 'index.html';
  }
  if (!(url in cur_url_to_base64)) {
    var home_url = registration.scope + 'index.html';
    return generate_404(url, ' is not part of the current Guide.  Try searching from the <a href="' + home_url + '">home page</a>');
  }
  let response = await caches.match(cur_url_to_base64[url]);
  if (!response) {
    red_missing = true;
    upd_pending = true;
    validate_flag = true;
  }
  if (!response && url.startsWith('photos/')) {
    let alt_url = 'thumbs/' + url.substr('photos/'.length);
    response = await caches.match(cur_url_to_base64[alt_url]);
  } else if (!response && url.startsWith('thumbs/')) {
    let alt_url = 'photos/' + url.substr('thumbs/'.length);
    response = await caches.match(cur_url_to_base64[alt_url]);
  }
  if (response) {
    return response;
  }
  if (url.startsWith('photos/') ||
      url.startsWith('thumbs/') ||
      url.startsWith('figures/') ||
      url.startsWith('favicons/')) {
    return generate_404(url, ' has gone missing from your local copy.  Update your local offline files.');
  } else {
    return fetch(event.request);
  }
}
function generate_404(url, msg) {
  return Promise.resolve(new Response('<html><body>"' + decodeURI(url) + '"' + msg, {'status': 404, headers: {'Content-Type': 'text/html; charset=utf-8'}}));
}
async function read_db() {
  try {
    await open_db();
    let conn = db_connection('readonly');
    let async_cur_data = db_request_promise(conn.get('data'));
    let async_upd_data = db_request_promise(conn.get('upd_base64_to_kb'));
    let cur_data = await async_cur_data;
    if (cur_data && cur_data.url_to_base64) {
      cur_url_to_base64 = cur_data.url_to_base64;
      cur_timestamp = cur_data.timestamp;
      offline_ready = true;
      cur_base64 = {};
      for (let url in cur_url_to_base64) {
        let base64 = cur_url_to_base64[url];
        cur_base64[base64] = true;
      }
    } else {
      cur_url_to_base64 = {};
      cur_base64 = {};
      offline_ready = false;
    }
    let upd_data = await async_upd_data;
    if (upd_data && (upd_data.timestamp === upd_timestamp)) {
      upd_base64_to_kb = upd_data.upd_base64_to_kb;
    }
  } catch (e) {
    cur_url_to_base64 = {};
    cur_base64 = {};
    offline_ready = false;
  }
}
async function open_db() {
  let request = indexedDB.open(DB_NAME, DB_VERSION);
  request.onupgradeneeded = dbupgradeneeded;
  db = await db_request_promise(request);
}
async function dbupgradeneeded(event) {
  let db = event.target.result;
  db.createObjectStore('url_data', {keyPath: 'key'});
}
activity_promise = init_status();
monitor_promise();
async function init_status() {
  db_promise = read_db();
  await db_promise;
  upd_pending = (upd_timestamp !== cur_timestamp);
  activity = 'validate';
  msg = 'Validating local files';
  await check_cached();
}
function validate_cache() {
  activity = 'validate';
  msg = 'Validating local files';
  activity_promise = check_cached();
  monitor_promise();
}
async function check_cached() {
  all_base64 = {};
  let cache = await caches.open(BASE64_CACHE_NAME);
  let requests = await cache.keys();
  all_num_cached = 0;
  for (const request of requests) {
    let base64 = remove_scope_from_request(request);
    all_base64[base64] = true;
    all_num_cached++;
  }
  for (let base64 in cur_base64) {
    if (!(base64 in all_base64)) {
      red_missing = true;
      upd_pending = true;
    }
  }
  count_cached();
  validate_flag = false;
  activity = 'idle';
}
function count_cached() {
  if (!upd_base64_to_kb) return;
  upd_kb_total = 0;
  upd_num_urls = 0;
  for (const base64 in upd_base64_to_kb) {
    upd_kb_total += upd_base64_to_kb[base64];
    upd_num_urls++;
  }
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
}
self.addEventListener('message', fn_send_status);
function fn_send_status(event) {
  if (event.data == 'start') {
    err_status = '';
  }
  if (event.data === 'update') {
    if ((activity === 'init') ||
        (activity === 'validate') ||
        (activity === 'idle') ||
        (activity === 'delete')) {
      if (upd_pending) {
        update_cache_when_ready();
      } else {
      }
    } else if (activity === 'update') {
      pause_update();
    } else {
    }
  } else if (event.data === 'clear') {
    if ((activity === 'validate') ||
        (activity === 'idle') ||
        (activity === 'delete') ||
        (activity === 'update')) {
      clear_caches();
    } else {
    }
  }
  if ((activity === 'idle') && validate_flag) {
    validate_cache();
  } else if ((activity === 'idle') && obs_num_files) {
    activity_promise = idle_delete_obs_files(false);
    monitor_promise();
  }
  if (activity === 'init') {
    var progress = '';
  } else {
    var mb_total = (upd_kb_total/1024 + 0.1).toFixed(1);
    if (all_num_cached == 0) {
      var mb_cached = '0.0';
    } else if (upd_kb_cached === undefined) {
      var mb_cached = '?';
    } else if (upd_pending) {
      var mb_cached = (upd_kb_cached/1024).toFixed(1);
    } else {
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
    var status = progress + msg;
  }
  if (activity !== 'update') {
    if (offline_ready) {
      var update_button = 'Update Local Files';
    } else {
      var update_button = 'Save Files Locally';
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
  } else if (activity === 'update') {
    var update_class = 'update-stop';
    var clear_class = '';
  } else {
    if (upd_pending) {
      var update_class = 'update-update';
    } else {
      var update_class = 'update-disable';
    }
    var clear_class = '';
  }
  var icon = undefined;
  var top_msg = undefined;
  if (activity !== 'init') {
    if (offline_ready) {
      if (!upd_pending) {
        var top_msg = 'green';
      } else {
        var top_msg = 'yellow';
        if (activity !== 'update') {
          var icon = 'yellow';
        }
      }
    } else {
      var top_msg = 'online';
    }
  }
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
    return;
  } else {
    throw 'oops';
  }
  activity = 'busy';
  stop_activity_flag = true;
  await activity_promise;
  activity_promise = undefined;
  stop_activity_flag = false;
}
async function clear_caches() {
  await stop_activity();
  activity = 'busy';
  msg = 'Making all local files obsolete';
  err_status = '';
  try {
    await kill_cur_files();
    activity_promise = idle_delete_obs_files(true);
    monitor_promise();
  } catch (e) {
    if (e) {
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
      activity = 'idle';
      validate_flag = true;
    }
  }
}
async function delete_db() {
  let conn = db_connection('readwrite');
  await db_request_promise(conn.clear());
  await db_connection_promise(conn);
}
async function delete_all_cache_entries() {
  let cache = await caches.open(BASE64_CACHE_NAME);
  let requests = await cache.keys();
  for (let i = 0; i < requests.length; i++) {
    msg = 'Queued deletion of ' + i + ' / ' + requests.length + ' files';
    let request = requests[i]
    await cache.delete(request);
  }
  msg = 'Waiting for browser to process ' + requests.length + ' deleted files.';
}
async function update_cache_when_ready() {
  await stop_activity();
  activity_promise = update_cache();
  monitor_promise();
}
async function monitor_promise() {
  await activity_promise;
}
async function update_cache() {
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
    } else if (is_quota_exceeded(e)) {
      err_status = 'Not enough local storage available.  Sorry.';
    } else {
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
    }
  }
  activity = 'idle';
}
async function read_json() {
  var response = await fetch_and_verify('url_data.json');
  var url_data = await response.json();
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
async function write_upd_base64_to_kb() {
  let obj = {key: 'upd_base64_to_kb',
             upd_base64_to_kb: upd_base64_to_kb,
             timestamp: upd_timestamp
            };
  await write_obj_to_db(obj);
}
async function protect_update(cache) {
  while (true) {
    try {
      await write_margin();
      await protected_update(cache);
      await clear_margin();
      return;
    } catch (e) {
      let quota_exceeded = is_quota_exceeded(e);
      if (quota_exceeded && obs_num_files) {
        err_status = 'Storage limit reached.  Deleting obsolete files before continuing.';
        await clear_margin();
        await delete_obs_files(cache);
        err_status = '';
      } else if (quota_exceeded && cur_num_files) {
        err_status = 'Storage limit reached.  Reverting to online mode so that old files can be deleted.';
        await clear_margin();
        await kill_cur_files();
        await delete_obs_files(cache);
        err_status = 'Storage limit reached.  Reverted to online mode so that old files could be deleted.';
      } else {
        await clear_margin();
        throw e;
      }
    }
  }
}
async function protected_update(cache) {
  await write_upd_base64_to_kb();
  await fetch_all_to_cache_parallel(cache);
  make_cur_files_obsolete();
}
function is_quota_exceeded(e) {
  return (e && ((e.name === 'QuotaExceededError') ||
                (e.name === 'NS_ERROR_FILE_NO_DEVICE_SPACE')));
}
async function write_obj_to_db(obj) {
  let conn = db_connection('readwrite');
  await db_request_promise(conn.put(obj));
  await db_connection_promise(conn);
}
async function write_margin() {
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
  for (let delay of [1, 4, 'end']) {
    try {
      let conn = db_connection('readwrite');
      await db_request_promise(conn.delete('margin'));
      await db_connection_promise(conn);
      return;
    } catch (e) {
      if (is_quota_exceeded(e) && (delay !== 'end')) {
        await sleep(delay * 1000);
      } else {
        return;
      }
    }
  }
}
async function fetch_all_to_cache_parallel(cache) {
  let promises = [fetch_all_to_cache(cache, 0),
                  fetch_all_to_cache(cache, 1),
                  fetch_all_to_cache(cache, 2),
                  fetch_all_to_cache(cache, 3),
                  fetch_all_to_cache(cache, 4),
                  fetch_all_to_cache(cache, 5)];
  var results = await Promise.allSettled(promises);
  if (stop_activity_flag === 'stop_threads') {
    stop_activity_flag = false;
  }
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
}
async function fetch_all_to_cache(cache, id) {
  for (const url in upd_url_to_base64) {
    let base64 = upd_url_to_base64[url]
    if (!(base64 in all_base64)) {
      all_base64[base64] = true;
      try {
        await fetch_to_cache(cache, url, base64);
        upd_kb_cached += upd_base64_to_kb[base64];
        all_num_cached++;
      } catch (e) {
        delete all_base64[base64];
        if (!stop_activity_flag) {
          stop_activity_flag = 'stop_threads';
        }
        throw e;
      }
    }
  }
}
async function fetch_to_cache(cache, url, base64) {
  msg = 'Fetching ' + decodeURI(url)
  var response = await fetch_and_verify(url);
  await check_stop('update (before cache write)');
  await cache.put(base64, response);
}
async function fetch_and_verify(url) {
  for (let retry_sleep = 1; retry_sleep *= 2; true) {
    await check_stop('update (before fetch)');
    try {
      var response = await fetch(url, {cache: "no-cache"});
    } catch (e) {
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
      for (let i = 0; i < retry_sleep; i++) {
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
      return response;
    }
  }
}
async function record_urls() {
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
  err_status = '';
}
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
async function check_stop(from) {
  if (stop_activity_flag) {
    throw null;
  }
}
async function idle_delete_obs_files(del_all_flag) {
  activity = 'delete';
  msg = 'Deleting obsolete offline files';
  try {
    let cache = await caches.open(BASE64_CACHE_NAME);
    await delete_obs_files(cache, del_all_flag);
  } catch (e) {
    if (e) {
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
      validate_flag = true;
    }
  }
  activity = 'idle';
}
async function delete_obs_files(cache, del_all_flag) {
  if (del_all_flag) {
    var total = all_num_cached;
  } else {
    var total = obs_num_files;
  }
  try {
    var count = 0;
    for (const base64 in all_base64) {
      await check_stop('delete_obs_files()');
      if (del_all_flag ||
          (!(base64 in upd_base64_to_kb) && !(base64 in cur_base64))) {
        count++;
        msg = 'Queued deletion of ' + count + ' / ' + total;
        if (del_all_flag) {
          msg += ' local files';
        } else {
          msg += ' obsolete local files';
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
    if (obs_num_files) {
    }
    obs_num_files = 0;
    if (del_all_flag) {
      upd_base64_to_kb = undefined;
    }
  } catch (e) {
    obs_num_files = 0;
    if (!e) {
    } else if (is_quota_exceeded(e)) {
      err_status = 'The browser claims that we can&rsquo;t DELETE local files because we&rsquo;re using too much space.  Yeah, really!  There&rsquo;s nothing more I can do.  You&rsquo;ll need to manually clear the site data from your browser.';
    } else {
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
async function update_usage() {
  if (navigator.storage) {
    let estimate = await navigator.storage.estimate();
    var usage = estimate.usage;
    var quota = estimate.quota;
  } else {
    var usage = 0;
    var quota = undefined;
  }
  var kb_usage = usage / 1024;
  var status_usage = (usage/1024/1024).toFixed(1) + ' MB';
  if (quota < 2*1024*1024*1024) {
    var status_quota = (quota/1024/1024).toFixed(1) + ' MB';
  } else {
    var status_quota = (quota/1024/1024/1024).toFixed(1) + ' GB';
  }
  let cache_empty = (all_num_cached == 0);
  let unsure_if_empty = ((activity === 'init') ||
                         (activity === 'validate') && (!offline_ready));
  if (unsure_if_empty) {
    usage_msg = 'Using ? MB of local storage.';
  } else if (cache_empty) {
    usage_msg = 'Using 0.0 MB of local storage.';
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
  if (!usage && !cache_empty) {
    let kb_per_file = upd_kb_total / upd_num_urls;
    let kb_usage = kb_per_file * all_num_cached;
    status_usage = (kb_usage/1024 + 0.1).toFixed(1) + ' MB'
    if (activity === 'validate') {
      usage_msg = 'Using roughly ? MB of local storage.';
    } else {
      usage_msg = 'Using roughly ' + status_usage + ' of local storage.';
    }
    if (quota === undefined) {
      usage_msg += '<br>Browser limit is unknown.';
    } else {
      usage_msg += '<br>Browser allows at least ' + status_quota + '.';
    }
  }
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
