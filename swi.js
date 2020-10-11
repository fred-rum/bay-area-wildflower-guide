
'use strict';
var e_update;
var e_progress;
var e_status;
var e_err_status;
var e_clear;
var e_usage;
var e_extra;
var e_top_msg = {};
var e_body;
var e_icon;
var temp_controller;
var old_msg = {};
var old_icon;
var wakelock;
var poll_interval = 500;
var polls_since_response = 0;
var timed_out = false;
async function swi_oninteractive() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', swi_oninteractive);
    return
  }
  console.info('swi_oninteractive()');
  e_update = document.getElementById('update');
  if (e_update) {
    e_status = document.getElementById('status');
    e_progress = document.getElementById('progress');
    e_err_status = document.getElementById('err-status');
    e_clear = document.getElementById('clear');
    e_usage = document.getElementById('usage');
    e_extra = document.getElementById('extra');
    let top_msg_array = ['green', 'yellow', 'online'];
    for (let i = 0; i < top_msg_array.length; i++) {
      let top_msg = top_msg_array[i];
      e_top_msg[top_msg] = document.getElementById('cache-' + top_msg);
      console.info(top_msg, e_top_msg[top_msg]);
    }
    e_status.innerHTML = 'Waiting for the service worker to load';
    var sw_path = 'sw.js';
  } else {
    e_body = document.getElementById('body');
    var sw_path = '../sw.js';
  }
  if ('serviceWorker' in navigator) {
    try {
      var registration = await navigator.serviceWorker.register(sw_path);
    } catch (e) {
      console.warn('service worker registration failed', e);
      if (e_status) {
        e_status.innerHTML = 'Service worker failed to load.  Manually clearing all site data might help.';
      }
      return;
    }
    await navigator.serviceWorker.ready;
    start_polling(registration);
  } else {
    console.info('no service worker support in browser');
    if (e_status) {
      e_status.innerHTML = 'Sorry, but your browser doesn&rsquo;t support this feature.';
    }
  }
}
swi_oninteractive();
function start_polling(registration) {
  console.info('start_polling()');
  temp_controller = registration.active;
  if (e_update) {
    e_update.addEventListener('click', fn_update);
    e_clear.addEventListener('click', fn_clear);
    e_update.addEventListener('keydown', fn_update_keydown);
    e_clear.addEventListener('keydown', fn_clear_keydown);
    navigator.serviceWorker.addEventListener('message', fn_receive_status);
  } else if (e_body) {
    navigator.serviceWorker.addEventListener('message', fn_receive_icon);
  }
  poll_cache(undefined, 'start');
  setInterval(poll_cache, poll_interval);
}
function poll_cache(event, msg='poll') {
  let secs = Math.floor((polls_since_response * poll_interval) / 1000);
  if (secs >= 3) {
    timed_out = true;
    if (e_err_status) {
      e_err_status.innerHTML = 'No response from the service worker for ' + secs + ' seconds.<br>It might recover eventually, or you might need to clear the site data from the browser.';
    }
  }
  post_msg(msg)
}
function post_msg(msg) {
  if (navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage(msg);
  } else if (temp_controller) {
    temp_controller.postMessage(msg);
  }
  polls_since_response++;
}
function fn_receive_status(event) {
  polls_since_response = 0;
  try {
    let msg = event.data;
    if (msg.update_button !== old_msg.update_button) {
      e_update.textContent = msg.update_button;
    }
    if (msg.update_class !== old_msg.update_class) {
      e_update.className = msg.update_class;
    }
    if (msg.progress !== old_msg.progress) {
      e_progress.innerHTML = msg.progress;
    }
    if ((msg.msg !== old_msg.msg) ||
        (msg.err_status !== old_msg.err_status) ||
        timed_out) {
      if (msg.msg || msg.err_status) {
        e_status.innerHTML = msg.msg;
      } else {
        e_status.innerHTML = '&nbsp;'
      }
      e_err_status.innerHTML = msg.err_status;
    }
    if (msg.usage !== old_msg.usage) {
      e_usage.innerHTML = msg.usage;
    }
    if (msg.extra !== old_msg.extra) {
      e_extra.innerHTML = msg.extra;
    }
    if (msg.top_msg !== old_msg.top_msg) {
      if (old_msg.top_msg in e_top_msg) {
        e_top_msg[old_msg.top_msg].style.display = 'none';
      }
      if (msg.top_msg in e_top_msg) {
        e_top_msg[msg.top_msg].style.display = 'block';
      }
    }
    if (msg.clear_class !== old_msg.clear_class) {
      e_clear.className = msg.clear_class;
    }
    old_msg = msg;
    update_wakelock(msg);
  } catch (e) {
    console.error('polling msg error:', e);
    e_update.className = 'update-update';
    e_clear.className = '';
    e_status.innerHTML = '';
    e_err_status.innerHTML = 'Interface not in sync; try clearing the site data and then refreshing the page.';
    e_usage.innerHTML = '';
    e_extra.innerHTML = '';
    e_top_msg.style.display = 'none';
  }
}
function fn_update(event) {
  if (navigator.serviceWorker) {
    post_msg('update');
    localStorage.removeItem('yellow_expire');
    init_permissions();
  }
}
function fn_clear(event) {
  if (navigator.serviceWorker) {
    post_msg('clear');
    localStorage.clear();
  }
}
function fn_update_keydown(event) {
  if ((event.key == 'Enter') ||
      (event.key == ' ') ||
      (event.key == 'Spacebar')) {
    fn_update(event);
    event.preventDefault();
  }
}
function fn_clear_keydown(event) {
  if ((event.key == 'Enter') ||
      (event.key == ' ') ||
      (event.key == 'Spacebar')) {
    fn_clear(event);
    event.preventDefault();
  }
}
function fn_receive_icon(event) {
  let msg = event.data;
  let yellow_expire = get_yellow_expire();
  if ((msg.icon == 'yellow') &&
      ((yellow_expire === null) || (Date.now() > yellow_expire))) {
    var icon = 'yellow';
  } else {
    var icon = undefined;
  }
  if (icon !== old_icon) {
    if (icon === 'yellow') {
      console.info('displaying hazard icon');
      if (!e_icon) {
        console.info('inserting hazard icon');
        e_body.insertAdjacentHTML('afterbegin', '<div id="icon"><img src="../icons/hazard.svg" class="hazard-img"></div>');
        e_icon = document.getElementById('icon');
        e_icon.addEventListener('click', fn_icon_click);
      }
      e_icon.className = 'icon-yellow';
      e_icon.style.display = 'block';
    } else {
      e_icon.style.display = 'none';
    }
  }
  old_icon = icon;
  update_wakelock(msg);
}
function get_yellow_expire(event) {
  let yellow_expire = localStorage.getItem('yellow_expire');
  if (yellow_expire != null) {
    yellow_expire = parseFloat(yellow_expire);
  }
  return yellow_expire;
}
function fn_icon_click(event) {
  let ms_in_week = 1000*60*60*24*7;
  let yellow_expire = Date.now() + ms_in_week;
  localStorage.setItem('yellow_expire', String(yellow_expire));
  if (event.shiftKey || event.ctrlKey) {
    window.open('../index.html#offline');
  } else {
    window.location.href = '../index.html#offline';
  }
}
async function update_wakelock(msg) {
  if (msg.update_class == 'update-stop' && !wakelock && navigator.wakeLock) {
    try {
      console.info('Requesting wakelock');
      wakelock = await navigator.wakeLock.request('screen');
      console.info('wakelock = ', wakelock);
      wakelock.addEventListener('release', fn_wakelock_released);
    } catch (e) {
      console.warn('wakelock request failed:', e);
      wakelock = undefined;
    }
  } else if (msg.update_class != 'update-stop' && wakelock) {
    try {
      console.info('releasing wakelock');
      wakelock.release();
      wakelock = undefined;
    } catch (e) {
      console.warn('wakelock release failed:', e);
    }
  }
}
function fn_wakelock_released() {
  console.info('fn_wakelock_released()');
}
async function init_permissions() {
  if (navigator.storage) {
    let persistent = await navigator.storage.persist();
    console.info('persistent =', persistent);
   }
}
