/** Honeypot: auto-login as System Admin after SPA boot (no live PLC). */
(function () {
  var USER = "Admin";
  var PASS = "Admin123!"; // >=8 chars — SPA rejects shorter passwords after Login
  var MAX_TRIES = 60;
  var INTERVAL_MS = 400;

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function findPinia(app) {
    if (!app) return null;
    var gp = app.config && app.config.globalProperties;
    if (gp && gp.$pinia) return gp.$pinia;
    var provides = app._context && app._context.provides;
    if (!provides) return null;
    var keys = Object.keys(provides);
    for (var i = 0; i < keys.length; i++) {
      var v = provides[keys[i]];
      if (v && v._s) return v;
    }
    // Symbol keys
    var syms = Object.getOwnPropertySymbols(provides);
    for (var j = 0; j < syms.length; j++) {
      var sv = provides[syms[j]];
      if (sv && sv._s) return sv;
    }
    return null;
  }

  function findLoginStore(pinia) {
    if (!pinia || !pinia._s) return null;
    var found = null;
    pinia._s.forEach(function (store, id) {
      if (found) return;
      if ((String(id).indexOf("login") !== -1) && typeof store.login === "function") {
        found = store;
      }
    });
    return found;
  }

  async function run() {
    var app = null;
    var store = null;
    for (var i = 0; i < MAX_TRIES; i++) {
      await sleep(INTERVAL_MS);
      var el = document.querySelector("#app");
      app = el && el.__vue_app__;
      if (!app) continue;
      var pinia = findPinia(app);
      store = findLoginStore(pinia);
      if (store) break;
    }
    if (!store) {
      console.warn("[honeypot] login store not found — UI stays as guest");
      return;
    }
    if (store.isLoggedIn && store.isAdministrator) return;
    try {
      await store.login(USER, PASS, false);
      console.info("[honeypot] auto-login as " + USER + " (System Admin)");
    } catch (e) {
      console.warn("[honeypot] auto-login failed", e);
    }
  }

  if (document.readyState === "complete") run();
  else window.addEventListener("load", run);
})();
