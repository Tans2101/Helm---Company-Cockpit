/** Shared QueryClient handle so axios can invalidate useFetch caches after writes. */
let _client = null;

export function setAppQueryClient(client) {
  _client = client;
}

export function getAppQueryClient() {
  return _client;
}
