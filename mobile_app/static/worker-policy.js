/* Shared with executable worker isolation tests. No cross-app cache ownership. */
globalThis.BusWorkerPolicy = {
  assets: ['', 'index.html', 'styles.css', 'app.js', 'state.mjs', 'stops.mjs', 'alarm-panel.mjs', 'manifest.webmanifest', 'assets/icon.svg'],
  cacheable(value, scope) {
    const url = new URL(value), root = new URL(scope);
    return url.origin === root.origin && url.pathname.startsWith(root.pathname)
      && this.assets.includes(url.pathname.slice(root.pathname.length)) && !url.search;
  },
  obsolete(name, scope, version) {
    const prefix = `jinju-bus:${new URL(scope).pathname}:`;
    return name.startsWith(prefix) && name !== prefix + version;
  }
};
