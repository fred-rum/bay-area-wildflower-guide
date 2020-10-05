
let e_update;
let e_status;
let e_err_status;
let e_clear;
let e_usage;
let e_top_msg = {};
var temp_controller;
var old_msg = {};
var old_icon;
var wakelock;
function swi_oninteractive() {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', oninteractive);
    return
  }
  console.info('swi_oninteractive()');
  e_update = document.getElementById('update');
  if (e_update) {
    e_status = document.getElementById('status');
    e_err_status = document.getElementById('err-status');
    e_clear = document.getElementById('clear');
    e_usage = document.getElementById('usage');
    let top_msg_array = ['green', 'yellow'];
    for (i = 0; i < top_msg_array.length; i++) {
      top_msg = top_msg_array[i];
      e_top_msg[top_msg] = document.getElementById('cache-' + top_msg);
      console.info(top_msg, e_top_msg[top_msg]);
    }
    e_status.innerHTML = 'Waiting for service worker to load';
    var sw_path = 'sw.js';
  } else {
    e_icon = document.getElementById('icon');
    var sw_path = '../sw.js';
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register(sw_path).then(function (registration) {
      navigator.serviceWorker.ready.then(start_polling);
    }).catch (function (error) {
      console.info('service worker registration failed');
      if (e_status) {
        e_status.innerHTML = 'No service worker';
      }
    });
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
    navigator.serviceWorker.addEventListener('message', fn_receive_status);
  } else if (e_icon) {
    e_icon.addEventListener('click', fn_icon_click);
    navigator.serviceWorker.addEventListener('message', fn_receive_icon);
  }
  poll_cache(undefined, 'start');
  setInterval(poll_cache, 500);
}
function poll_cache(event, msg='poll') {
  if (navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage(msg);
  } else {
    temp_controller.postMessage(msg);
  }
}
function fn_receive_status(event) {
  try {
    let msg = event.data;
    if (msg.update_button != old_msg.update_button) {
      e_update.textContent = msg.update_button;
    }
    if (msg.update_class != old_msg.update_class) {
      e_update.className = msg.update_class;
    }
    if (msg.status != old_msg.status) {
      e_status.innerHTML = msg.status;
    }
    if (msg.err_status != old_msg.err_status) {
      e_err_status.innerHTML = msg.err_status;
    }
    if (msg.usage != old_msg.usage) {
      e_usage.innerHTML = msg.usage;
    }
    if (msg.top_msg != old_msg.top_msg) {
      if (old_msg.top_msg) {
        e_top_msg[old_msg.top_msg].style.display = 'none';
      }
      if (msg.top_msg) {
        e_top_msg[msg.top_msg].style.display = 'block';
      }
    }
    old_msg = msg;
    update_wakelock(msg);
  } catch (error) {
    console.error(error);
    e_update.className = '';
    e_status.innerHTML = '';
    e_err_status.innerHTML = 'Interface not in sync; try deleting the offline files and then refreshing the page.';
    e_usage.innerHTML = '';
    e_top_msg.style.display = 'none';
  }
}
function fn_update(event) {
  if (navigator.serviceWorker && navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage('update');
    e_update.className = 'disabled';
    localStorage.removeItem('yellow_expire');
  }
}
function fn_clear(event) {
  if (navigator.serviceWorker && navigator.serviceWorker.controller) {
    navigator.serviceWorker.controller.postMessage('clear');
    localStorage.clear();
  }
}
function fn_receive_icon(event) {
  let msg = event.data;
  let yellow_expire = get_yellow_expire();
  if ((msg.icon == 'yellow') &&
      ((yellow_expire === null) || (Date.now() > yellow_expire))) {
    icon = 'yellow';
  } else {
    icon = undefined;
  }
  if (icon !== old_icon) {
    if (icon === 'yellow') {
      e_icon.className = 'icon-yellow';
    } else {
      e_icon.className = '';
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
    } catch {
      console.warn('wakelock request failed');
    }
  } else if (msg.update_class != 'update-stop' && wakelock) {
    try {
      console.info('releasing wakelock');
      wakelock.release();
      wakelock = undefined;
    } catch {
      console.warn('wakelock release failed');
    }
  }
}
function fn_wakelock_released() {
  console.info('fn_wakelock_released()');
  wakelock = undefined;
}
