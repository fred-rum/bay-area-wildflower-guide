function search_fn(ele, path) {
  if (event.keyCode == 13) {
    v = ele.value;
    p = 0;
    vx = v.toUpperCase().replace(/[^A-Z]/g, "")
    for (i = 0; i < page.length; i++) {
      l = page[i]
      for (j = 0; j < l.length; j++) {
        c = l[j];
        cx = c.toUpperCase().replace(/[^A-Z]/g, "")
        if ((p < 4) && (cx == vx)) {
          p = 4;
          m = l[0]
        }
        if ((p < 3) && (cx.startsWith(vx))) {
          p = 3;
          m = l[0];
        }
        if ((p < 2) && (cx.includes(vx))) {
          p = 2;
          m = l[0];
        }
      }
    }
    if (p) {
      window.location.href = path + m + '.html';
    }
  }
}
