'use strict';
var sw_timestamp = '2020-10-28T18:40:51.832458+00:00';
var num_urls = 5030;
var kb_total = 660739
console.info('starting from the beginning');
const DB_NAME = 'db-v1';
const DB_VERSION = 1;
const BASE64_CACHE_NAME = 'base64-cache-v1';
var activity = 'init';
var msg = 'Checking for offline files';
var err_status = '';
var usage_msg = '';
var extra_msg = '';
var stop_activity_flag = false;
var activity_promise;
var offline_ready = undefined;
var url_to_base64;
var new_url_to_base64;
var url_diff = false;
var base64_to_kb;
var old_timestamp;
var old_base64;
var all_base64;
var num_cached;
var num_obs_files;
var num_old_files;
var kb_cached;
var red_missing = false;
var red_missed = false;
var validate_flag = false;
self.addEventListener('install', fn_install);
async function fn_install(event) {
  console.info('fn_install()');
  self.skipWaiting();
}
self.addEventListener('activate', event => {
  console.info('activate');
  clients.claim();
});
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
console.info('adding fetch handler');
self.addEventListener('fetch', fetch_handler);
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
function fetch_handler(event) {
  let url = remove_scope_from_request(event.request);
  console.info('fetching', url);
  if (!url_to_base64 || offline_ready) {
    event.respondWith(fetch_response(event, url));
  } else {
    console.info(url, ' fetched in online mode')
    return;
  }
}
async function fetch_response(event, url) {
  if (!url_to_base64) {
    await read_db();
  }
  if (!offline_ready) {
    return fetch(event.request);
  }
  if (!(url in url_to_base64)) {
    console.info('%s not recognized; generating a 404', url)
    return generate_404(url, ' is not part of the current Guide.  Try the search bar.');
  }
  let response = await caches.match(url_to_base64[url]);
  if (!response) {
    red_missing = true;
    url_diff = true;
    validate_flag = true;
  }
  if (!response && url.startsWith('photos/')) {
    console.info('%s not found; falling back to thumbnail', url);
    let alt_url = 'thumbs/' + url.substr('photos/'.length);
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
    console.info('%s not found; generating a 404', url)
    return generate_404(url, ' has gone missing from your offline copy.  Update your offline files.');
  } else {
    console.info('%s not found; fetching from the internet', url)
    return fetch(event.request);
  }
}
function generate_404(url, msg) {
  return Promise.resolve(new Response('<html>' + decodeURI(url) + msg, {'status': 404, headers: {'Content-Type': 'text/html; charset=utf-8'}}));
}
async function read_db() {
  console.info('read_db()');
  try {
    url_to_base64 = {};
    old_base64 = {};
    offline_ready = false;
    let db = await open_db();
    let os = db.transaction('url_data', 'readonly').objectStore('url_data');
    let rx_data = os.get('data');
    let rx_new_data = os.get('base64_to_kb');
    let data = await async_callbacks(rx_data);
    console.info('indexedDB data:', data);
    if (data && data.url_to_base64) {
      url_to_base64 = data.url_to_base64;
      old_timestamp = data.timestamp;
      offline_ready = true;
      console.info('found url_to_base64 in DB');
      for (let url in url_to_base64) {
        let base64 = url_to_base64[url];
        old_base64[base64] = true;
      }
    }
    let new_data = await async_callbacks(rx_new_data);
    if (new_data && (new_data.timestamp === sw_timestamp)) {
      base64_to_kb = new_data.base64_to_kb;
      console.info('found latest base64_to_kb in DB');
    }
  } catch (e) {
    console.info('indexedDB lookup failed', e);
    console.info('(This is normal if it was not initialized.)');
  }
}
async function open_db() {
  let request = indexedDB.open(DB_NAME, DB_VERSION);
  request.onupgradeneeded = dbupgradeneeded;
  let db = await async_callbacks(request);
  console.info('open_db() returns', db);
  return db;
}
async function dbupgradeneeded(event) {
  let db = event.target.result;
  db.createObjectStore("url_data", { keyPath: "key" });
}
activity_promise = init_status();
monitor_promise();
async function init_status() {
  console.info('init_status()');
  await read_db();
  url_diff = (sw_timestamp !== old_timestamp);
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
async function check_cached() {
  console.info('check_cached()');
  all_base64 = {};
  let cache = await caches.open(BASE64_CACHE_NAME);
  let requests = await cache.keys();
  num_cached = 0;
  for (const request of requests) {
    let base64 = remove_scope_from_request(request);
    all_base64[base64] = true;
    num_cached++;
  }
  for (let base64 in old_base64) {
    if (!(base64 in all_base64)) {
      red_missing = true;
      url_diff = true;
    }
  }
  count_cached();
  validate_flag = false;
  console.info('check_cached() done');
  activity = 'idle';
}
function count_cached() {
  if (!base64_to_kb) return;
  console.info('count_cached()');
  console.info('base64_to_kb:', base64_to_kb);
  kb_total = 0;
  num_urls = 0;
  for (const base64 in base64_to_kb) {
    kb_total += base64_to_kb[base64];
    num_urls++;
  }
  console.info('all_base64:', all_base64);
  console.info('old_base64:', old_base64);
  kb_cached = 0;
  num_old_files = 0;
  num_obs_files = 0;
  for (const base64 in all_base64) {
    if (base64 in base64_to_kb) {
      kb_cached += base64_to_kb[base64];
    } else if (base64 in old_base64) {
      num_old_files++;
    } else {
      num_obs_files++;
    }
  }
  console.info('num_old_files:', num_old_files);
  console.info('num_obs_files:', num_obs_files);
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
      if (url_diff) {
        update_cache_when_ready();
      } else {
        console.info('cache is up to date: ignore update request');
      }
    } else if (activity === 'update') {
      pause_update();
    } else {
      console.info(activity + ': ignore update request');
    }
  } else if (event.data === 'clear') {
    if ((activity === 'validate') ||
        (activity === 'idle') ||
        (activity === 'delete') ||
        (activity === 'update')) {
      clear_caches();
    } else {
      console.info(activity + ': ignore delete request');
    }
  }
  if ((activity === 'idle') && validate_flag) {
    validate_cache();
  } else if ((activity === 'idle') && num_obs_files) {
    activity_promise = idle_delete_obs_files(false);
    monitor_promise();
  }
  if (activity === 'init') {
    var progress = '';
  } else {
    var mb_total = (kb_total/1024 + 0.1).toFixed(1);
    if (num_cached == 0) {
      var mb_cached = '0.0';
    } else if (kb_cached === undefined) {
      var mb_cached = '?';
    } else if (url_diff) {
      var mb_cached = (kb_cached/1024).toFixed(1);
    } else {
      var mb_cached = (kb_cached/1024 + 0.1).toFixed(1);
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
  } else if (activity === 'update') {
    var update_class = 'update-stop';
    var clear_class = '';
  } else {
    if (url_diff) {
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
      if (!url_diff) {
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
  await stop_activity();
  console.info('clear_caches()');
  activity = 'busy';
  msg = 'Making all offline files obsolete';
  err_status = '';
  try {
    await kill_old_files();
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
  let db = await open_db();
  await async_callbacks(db.transaction("url_data", "readwrite").objectStore("url_data").clear());
}
async function delete_all_cache_entries() {
  console.info('delete_all_cache_entries()')
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
  await stop_activity();
  activity_promise = update_cache();
  monitor_promise();
}
async function monitor_promise() {
  await activity_promise;
  console.info('activity_promise complete');
}
async function update_cache() {
  console.info('update_cache()');
  activity = 'update';
  err_status = '';
  try {
    msg = 'Preparing update';
    await read_json();
    write_new_base64();
    count_cached();
    let cache = await caches.open(BASE64_CACHE_NAME);
    await protected_write(cache, write_margin);
    let func = async function() {
      await fetch_all_to_cache_parallel(cache);
    };
    await protected_write(cache, func);
    make_old_files_obsolete();
    await record_urls();
  } catch (e) {
    if (!e) {
    } else if (is_quota_exceeded(e)) {
      console.warn(e);
      err_status = 'Not enough offline storage available.  Sorry.';
      console.warn(err_status);
    } else {
      console.error(e);
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
    }
    try {
      await clear_margin();
    } catch (e) {
      console.error(e);
      err_status = e.name + '<br>Something went wrong.  Refresh and try again?';
    }
  }
  activity = 'idle';
}
async function read_json() {
  console.info('read_json()');
  var response = await fetch_and_verify('url_data.json');
  var url_data = await response.json();
  console.info('read OK');
  new_url_to_base64 = {};
  base64_to_kb = {};
  for (const url_data_item of url_data) {
    let url = url_data_item[0];
    let base64 = url_data_item[1];
    let kb = url_data_item[2];
    new_url_to_base64[url] = base64;
    base64_to_kb[base64] = kb;
  }
}
function write_new_base64() {
  let obj = {key: 'base64_to_kb',
             base64_to_kb: base64_to_kb,
             timestamp: sw_timestamp
            };
  write_obj(obj);
}
async function protected_write(cache, func) {
  while (true) {
    try {
      return await func();
    } catch (e) {
      let quota_exceeded = is_quota_exceeded(e);
      if (quota_exceeded && num_obs_files) {
        err_status = 'Storage limit reached.  Deleting obsolete files before continuing.';
        await delete_obs_files(cache);
        err_status = '';
      } else if (quota_exceeded && num_old_files) {
        err_status = 'Storage limit reached.  Reverting to online mode so that old files can be deleted.';
        await kill_old_files();
        await delete_obs_files(cache);
        err_status = 'Storage limit reached.  Reverted to online mode so that old files could be deleted.';
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
async function write_obj(obj) {
  let db = await open_db();
  await write_obj_to_db(db, obj);
}
async function write_obj_to_db(db, obj) {
  await async_callbacks(db.transaction('url_data', 'readwrite').objectStore('url_data').put(obj));
}
async function write_margin() {
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
  console.info(results);
}
async function fetch_all_to_cache(cache, id) {
  for (const url in new_url_to_base64) {
    let base64 = new_url_to_base64[url]
    if (!(base64 in all_base64)) {
      all_base64[base64] = true;
      try {
        await fetch_to_cache(cache, url, base64);
        kb_cached += base64_to_kb[base64];
        num_cached++;
      } catch (e) {
        delete all_base64[base64];
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
  await cache.put(base64, response);
}
async function fetch_and_verify(url) {
  for (let retry_sleep = 1; retry_sleep *= 2; true) {
    await check_stop('update (before fetch)');
    try {
      var response = await fetch(url);
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
  console.info('record_urls()');
  let db = await open_db();
  let obj = {key: 'margin',
             junk: ''};
  await write_obj_to_db(db, obj);
  obj = {key: 'data',
         url_to_base64: new_url_to_base64,
         timestamp: sw_timestamp
        };
  await write_obj_to_db(db, obj);
  url_to_base64 = new_url_to_base64;
  old_base64 = base64_to_kb;
  url_diff = false;
  red_missing = false;
  offline_ready = true;
  err_status = '';
}
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
async function check_stop(from) {
  if (stop_activity_flag) {
    console.info(from + ' is now stopped');
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
async function delete_obs_files(cache, and_new_files) {
  console.info('delete_obs_files()');
  if (and_new_files) {
    var total = num_cached;
  } else {
    var total = num_obs_files;
  }
  console.info('all_base64:', all_base64);
  console.info('old_base64:', old_base64);
  console.info('base64_to_kb:', base64_to_kb);
  var count = 0;
  for (const base64 in all_base64) {
    await check_stop('delete_obs_files()');
    if (and_new_files ||
        (!(base64 in base64_to_kb) && !(base64 in old_base64))) {
      count++;
      msg = 'Queued deletion of ' + count + ' / ' + total;
      if (and_new_files) {
          msg += ' offline files';
      } else {
          msg += ' obsolete offline files';
      }
      await cache.delete(base64);
      delete all_base64[base64];
      num_cached--;
      if (base64_to_kb && (base64 in base64_to_kb)) {
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
  num_obs_files = 0;
  if (and_new_files) {
    base64_to_kb = undefined;
  }
}
async function kill_old_files() {
  offline_ready = false;
  old_timestamp = undefined;
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
  let cache_empty = (num_cached == 0);
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
  if (!usage && !cache_empty) {
    let kb_per_file = kb_total / num_urls;
    let kb_usage = kb_per_file * num_cached;
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
  if (extra_msg) {
    var kb_needed = kb_usage + ((kb_total - kb_cached) * 1.25) + (16 * 1024);
  } else {
    var kb_needed = kb_usage + ((kb_total - kb_cached) * 1.2) + (10 * 1024);
  }
  if (url_diff &&
      (num_old_files || num_obs_files) &&
      quota &&
      (kb_needed > quota/1024)) {
    extra_msg = 'The Guide will delete old files if necessary to make space for the update.'
  } else {
    extra_msg = '';
  }
}
