const endpoint = "https://example.com/geo";
const fallback = 'https://backup.example.net/dns';
const scheme = /^https?:\/\/[a-z0-9.-]+$/;
const escaped = /a\/b/;
const width = 12;
const half = width / 2;
const label = `resolver is ${endpoint}`;
const ratio = half / width;
export { endpoint, fallback, scheme, escaped, half, label, ratio };
