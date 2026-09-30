const state = {
  snapshot: null,
  meta: null,
  profiles: [],
  resolvers: [],
  policies: [],
  redaction: "redacted"
};

function element(id) {
  return document.getElementById(id);
}

function escapeText(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

async function fetchJson(path, options) {
  const response = await fetch(path, options);

  let payload = null;

  try {
    payload = await response.json();
  } catch (error) {
    payload = { error: "the server returned a body that is not JSON", detail: String(error) };
  }

  if (!response.ok) {
    const message = payload && payload.error ? payload.error : "request failed";
    const detail = payload && payload.detail ? payload.detail : "";
    throw new Error(detail ? message + ": " + detail : message);
  }

  return payload;
}

function card(label, value, note, tag, tagClass) {
  const parts = [];
  parts.push('<div class="card">');
  parts.push('<span class="label">' + escapeText(label) + "</span>");
  parts.push('<span class="value">' + escapeText(value) + "</span>");

  if (note) {
    parts.push('<span class="note">' + escapeText(note) + "</span>");
  }

  if (tag) {
    parts.push('<span class="tag ' + (tagClass || "") + '">' + escapeText(tag) + "</span>");
  }

  parts.push("</div>");

  return parts.join("");
}

function renderGrid(target, pieces) {
  target.innerHTML = pieces.join("");
}

function showFailure(target, message) {
  target.innerHTML = '<div class="failure"><div class="title">Resolution failed</div>' + escapeText(message) + "</div>";
}

function sourceTag(source) {
  const mapping = {
    virtual: ["virtual", "ok"],
    physical: ["measured", "warn"],
    automatic: ["automatic", "notice"],
    hybrid: ["hybrid", "notice"],
    disabled: ["disabled", ""]
  };

  return mapping[source] || [source || "unknown", ""];
}

function renderOverview(snapshot) {
  const badge = element("state-badge");
  const known = ["manual", "automatic", "hybrid", "disabled", "error", "conflict", "detected", "detecting", "unknown"];
  const key = String(snapshot.state || "unknown").toLowerCase();

  badge.textContent = snapshot.state;
  badge.className = "state-badge" + (known.indexOf(key) >= 0 ? " state-" + key : "");

  if (snapshot.failed_stage) {
    element("state-detail").textContent = "resolution stopped at " + snapshot.failed_stage;
  } else {
    element("state-detail").textContent = snapshot.stages.length + " stages resolved in " + snapshot.duration_ms + " ms";
  }

  const pieces = [];
  const geo = snapshot.geo;
  const timezone = snapshot.timezone;
  const locale = snapshot.locale;

  if (geo) {
    const tag = sourceTag(geo.source);
    pieces.push(card("Location", geo.latitude.toFixed(4) + ", " + geo.longitude.toFixed(4), "accuracy " + geo.accuracy_m + " m, radius " + geo.radius_m + " m", tag[0], tag[1]));
  } else {
    pieces.push(card("Location", "not resolved", "the geo stage did not produce a position", "failed", "warn"));
  }

  if (timezone) {
    pieces.push(card("Timezone", timezone.identifier, timezone.offset_display + " " + timezone.abbreviation, timezone.source, timezone.confidence === "configured" ? "ok" : ""));
  }

  if (locale) {
    pieces.push(card("Locale", locale.browser_locale, "languages: " + locale.language_pref.join(", "), locale.source, locale.confidence === "configured" ? "ok" : ""));
  }

  if (snapshot.policy) {
    pieces.push(card("Per-site rule", snapshot.policy.pattern, "scope " + snapshot.policy.scope, "active", "notice"));
  } else {
    pieces.push(card("Per-site rule", "none matched", "the profile stands unmodified", "", ""));
  }

  pieces.push(card("Profile", snapshot.profile, snapshot.stages.length + " stages", "", ""));
  pieces.push(card("Resolved at", snapshot.generated_at, "", "", ""));

  renderGrid(element("overview-grid"), pieces);

  element("overview-caveat").textContent =
    "Every value above is browser-scoped. The operating system clock, the system resolver and other applications are untouched, and a coherent environment is not a claim of anonymity.";

  element("brand-sub").textContent = "profile " + snapshot.profile + " | state " + snapshot.state;
}

function renderLocation(snapshot) {
  const geo = snapshot.geo;
  const pieces = [];

  if (!geo) {
    pieces.push(card("Location", "not resolved", "the geo stage failed", "failed", "warn"));
    renderGrid(element("location-grid"), pieces);
    return;
  }

  const tag = sourceTag(geo.source);

  pieces.push(card("Latitude", geo.latitude, "", tag[0], tag[1]));
  pieces.push(card("Longitude", geo.longitude, "", "", ""));
  pieces.push(card("Accuracy", geo.accuracy_m + " m", "reported to the page", "", ""));
  pieces.push(card("Radius", geo.radius_m + " m", geo.radius_m > 0 ? "a coordinate is sampled inside this area" : "a fixed point", "", ""));
  pieces.push(card("Altitude", geo.altitude_m === null ? "not set" : geo.altitude_m + " m", "", "", ""));
  pieces.push(card("Heading", geo.heading_deg === null ? "not set" : geo.heading_deg, "", "", ""));
  pieces.push(card("Speed", geo.speed_mps === null ? "not set" : geo.speed_mps + " m/s", "", "", ""));
  pieces.push(card("Seed", geo.seed === null ? "none" : geo.seed, geo.seed === null ? "no randomization applied" : "reproducible for this input", "", ""));
  pieces.push(card("Provider", geo.provider, geo.detail, "", ""));

  renderGrid(element("location-grid"), pieces);
}

function renderTimezone(snapshot) {
  const block = snapshot.timezone;

  if (!block) {
    renderGrid(element("timezone-grid"), [card("Timezone", "not resolved", "the timezone stage failed", "failed", "warn")]);
    return;
  }

  const pieces = [
    card("Identifier", block.identifier, "", block.source, block.confidence === "configured" ? "ok" : ""),
    card("Offset", block.offset_display, block.offset_minutes + " minutes from UTC", "", ""),
    card("Daylight saving", block.daylight_saving ? "in effect" : "not in effect", "evaluated at the current instant", "", ""),
    card("Abbreviation", block.abbreviation, "reported by the tz database", "", ""),
    card("Mode", block.mode, "", "", ""),
    card("Provenance", block.source, block.detail, "", "")
  ];

  renderGrid(element("timezone-grid"), pieces);
}

function renderLocale(snapshot) {
  const block = snapshot.locale;

  if (!block) {
    renderGrid(element("locale-grid"), [card("Locale", "not resolved", "the locale stage failed", "failed", "warn")]);
    return;
  }

  const pieces = [
    card("Browser locale", block.browser_locale, "the interface language", "", ""),
    card("Language preference", block.language_pref.join(", "), "reported as an ordered list", "", ""),
    card("JavaScript locale", block.js_locale, "the default for Intl and toLocaleString", "", ""),
    card("HTTP language", "see the header below", "sent with every request", "", ""),
    card("System locale", block.system_locale, "what the host reports, not virtualised", "", ""),
    card("Provenance", block.source, block.detail, "", block.confidence === "configured" ? "ok" : "")
  ];

  renderGrid(element("locale-grid"), pieces);

  element("accept-language").textContent = "Accept-Language: " + block.http_language;
}

async function renderNetwork() {
  const host = await fetchJson("/api/host");
  const network = host.network || {};

  const pieces = [
    card("Host timezone", host.timezone, host.timezone_source, "", ""),
    card("Host locale", host.locale, host.locale_source, "", ""),
    card("Platform", host.platform, "release " + host.platform_release, "", ""),
    card("Hostname", network.hostname || "unavailable", "read locally, never transmitted", "", ""),
    card("IPv4 reachable", network.has_ipv4 ? "yes" : "no", "", "", ""),
    card("IPv6 reachable", network.has_ipv6 ? "yes" : "no", "", "", ""),
    card("Interfaces", network.interface_count, "excluding loopback", "", ""),
    card("Proxy variables", network.proxy_configured ? "present" : "absent", "read from the process environment", "", "")
  ];

  renderGrid(element("network-grid"), pieces);

  const detected = state.snapshot && state.snapshot.detected;

  if (!detected) {
    renderGrid(element("detection-grid"), [card("Detection", "no result", "automatic detection produced no proposal", "", "")]);
    return;
  }

  const detectionPieces = [
    card("Proposed centre", Number(detected.latitude).toFixed(2) + ", " + Number(detected.longitude).toFixed(2), detected.reason, "derived", "notice"),
    card("Country", detected.country || "undetermined", "", "", ""),
    card("Radius", detected.radius_m + " m", "a timezone implies a country, not a point", "", ""),
    card("Confidence", detected.confidence, "reported honestly rather than rounded up", "", "")
  ];

  if (detected.signals && detected.signals.length) {
    detectionPieces.push(card("Signals", detected.signals.length, detected.signals.join("; "), "", ""));
  }

  renderGrid(element("detection-grid"), detectionPieces);
}

function renderDns(snapshot) {
  const steps = snapshot.stages.filter((stage) => stage.name === "dns_resolution");
  const block = steps.length ? steps[0].output : null;

  if (!block) {
    renderGrid(element("dns-grid"), [card("DNS", "not resolved", "the DNS stage produced no plan", "failed", "warn")]);
    return;
  }

  const active = block.mode === "doh" ? "DoH active" : block.mode === "dot" ? "DoT active" : block.mode === "custom" ? "custom resolver active" : "system resolver active";

  const pieces = [
    card("Mode", block.mode, block.protocol, "", block.encrypted ? "ok" : "notice"),
    card("Encrypted", block.encrypted ? "yes" : "no", block.certificate_validated ? "certificate validated" : "no certificate validation", block.encrypted ? "ok" : "notice"),
    card("Endpoints", block.endpoints.length ? block.endpoints.join(", ") : "none", "used when the mode is DoH", "", ""),
    card("Servers", block.servers.length ? block.servers.join(", ") : "none", "used when the mode is DoT or custom", "", ""),
    card("Port", block.port, "", "", ""),
    card("Fallback", block.fallback, block.fallback_protocol ? "would continue as: " + block.fallback_protocol : "no fallback, a failure stays a failure", block.fallback === "refuse" ? "ok" : "warn"),
    card("Operating system", block.affects_operating_system ? "modified" : "not modified", "this plan is browser-scoped only", "ok", "ok"),
    card("Status", active, block.detail, "", "")
  ];

  renderGrid(element("dns-grid"), pieces);

  const rows = state.resolvers.map((resolver) => {
    const transport = resolver.mode === "doh" ? "HTTPS" : resolver.mode === "dot" ? "TLS" : resolver.mode === "custom" ? "plaintext" : "system";
    return "<tr><td>" + escapeText(resolver.identifier) + "</td><td>" + escapeText(resolver.mode) + "</td><td>" + escapeText(transport) + "</td><td>" + escapeText(resolver.fallback) + "</td></tr>";
  });

  element("resolver-table").querySelector("tbody").innerHTML = rows.join("");
}

function renderPrivacy(snapshot) {
  const geo = snapshot.geo;
  const timezone = snapshot.timezone;
  const locale = snapshot.locale;
  const dnsStage = snapshot.stages.filter((stage) => stage.name === "dns_resolution")[0];
  const dns = dnsStage ? dnsStage.output : null;
  const privacyStage = snapshot.stages.filter((stage) => stage.name === "privacy_policy")[0];
  const privacy = privacyStage ? privacyStage.output : null;

  const answers = [];

  function answer(question, response, tone) {
    answers.push(
      '<div class="answer"><span class="question">' + escapeText(question) + '</span><span class="response ' + (tone || "") + '">' + escapeText(response) + "</span></div>"
    );
  }

  answer("Which location does the browser expose?", geo ? geo.latitude.toFixed(3) + ", " + geo.longitude.toFixed(3) + " (" + geo.source + ")" : "none, geolocation is refused");
  answer("Which timezone does the browser expose?", timezone ? timezone.identifier + " " + timezone.offset_display : "not resolved");
  answer("Which locale does the browser expose?", locale ? locale.browser_locale : "not resolved");
  answer("Which language header is sent?", locale ? locale.http_language : "not resolved");
  answer("Which DNS resolver is active?", dns ? dns.protocol : "not resolved");
  answer("Is DNS over HTTPS active?", dns ? (dns.mode === "doh" ? "yes" : "no") : "unknown");
  answer("Is DNS over TLS active?", dns ? (dns.mode === "dot" ? "yes" : "no") : "unknown");
  answer("Does DNS configuration touch the operating system?", dns ? (dns.affects_operating_system ? "yes" : "no") : "unknown");
  answer("Is a plaintext DNS fallback permitted?", dns ? (dns.fallback === "refuse" ? "no" : "yes, over " + dns.fallback_protocol) : "unknown", dns && dns.fallback !== "refuse" ? "warn" : "ok");
  answer("Which WebRTC policy is active?", privacy ? privacy.webrtc.policy : "unknown");
  answer("Which profile is active?", snapshot.profile);
  answer("Which profile was displaced by a per-site rule?", snapshot.policy ? "rules for " + snapshot.policy.pattern + " apply to this host" : "none, no rule matched");
  answer("Which hosts have custom rules?", state.policies.length ? state.policies.map((policy) => policy.pattern).join(", ") : "none");

  element("privacy-answers").innerHTML = answers.join("");

  element("privacy-caveat").textContent = privacy
    ? privacy.webrtc.caveat
    : "WebRTC candidate policy shapes connectivity. It does not make a connection anonymous.";
}

function renderProfiles() {
  const active = state.meta.active_profile;

  const pieces = state.profiles.map((profile) => {
    const location = profile.latitude === undefined ? "no fixed position" : profile.latitude.toFixed(3) + ", " + profile.longitude.toFixed(3);
    const tag = profile.identifier === active ? "active" : profile.valid_checksum ? "checksum valid" : "checksum absent";

    return card(
      profile.identifier,
      profile.name,
      "mode " + profile.geolocation_mode + " | radius " + profile.radius_m + " m | " + location + " | DNS " + profile.dns_mode,
      tag,
      profile.identifier === active ? "ok" : profile.valid_checksum ? "ok" : "notice"
    );
  });

  renderGrid(element("profiles-grid"), pieces);

  const options = state.profiles
    .map((profile) => '<option value="' + escapeText(profile.identifier) + '">' + escapeText(profile.name) + "</option>")
    .join("");

  element("activate-select").innerHTML = options;
  element("activate-select").value = active;

  renderStorage();
}

function renderStorage() {
  const storage = state.meta.storage;
  const load = state.meta.last_load;

  const pieces = [
    card("Directory", storage.root, "profile and settings files live here", "", ""),
    card("Persistent", storage.persistent ? "yes" : "no", storage.persistent ? "writes reach the disk" : "this session is memory only", storage.persistent ? "ok" : "warning"),
    card("Profiles on disk", storage.profiles_on_disk, "excluding the index", "", ""),
    card("Saved exports", storage.diagnostics_on_disk, "kept to twenty, oldest pruned", "", ""),
    card("Layout version", storage.layout_version, "", "", "")
  ];

  if (load && load.quarantined && load.quarantined.length) {
    pieces.push(card("Quarantined on load", load.quarantined.length, load.quarantined.map((item) => item.identifier + " (" + item.reason + ")").join("; "), "attention", "warn"));
  }

  if (!storage.persistent && storage.notes && storage.notes.length) {
    pieces.push(card("Reason", storage.notes[0], "", "", ""));
  }

  renderGrid(element("storage-grid"), pieces);
}

function renderPolicies(snapshot) {
  const rows = state.policies.map((policy) => {
    const overrides = [
      policy.profile ? "profile " + policy.profile : "",
      policy.timezone ? "timezone " + policy.timezone : "",
      policy.locale ? "locale " + policy.locale : "",
      policy.dns_mode ? "DNS " + policy.dns_mode : ""
    ].filter(Boolean).join(", ");

    return "<tr><td>" + escapeText(policy.pattern) + "</td><td>" + escapeText(policy.scope) + "</td><td>" + escapeText(policy.profile || "unchanged") + "</td><td>" + escapeText(overrides || "none") + "</td></tr>";
  });

  element("policy-table").querySelector("tbody").innerHTML = rows.join("");

  const matched = snapshot.policy;

  renderGrid(element("policy-test-grid"), [
    card("Looked up host", snapshot.policy ? snapshot.policy.pattern : "no host supplied", "rules are matched against this", "", ""),
    card("Winning rule", matched ? matched.pattern + " (" + matched.scope + ")" : "none", "origin beats subdomain beats domain", matched ? "applied" : "none", matched ? "notice" : ""),
    card("Displaced rules", matched && matched.overshadowed ? matched.overshadowed.length : 0, "matching rules that lost the precedence comparison", "", "")
  ]);
}

async function renderDiagnostics() {
  const report = await fetchJson("/api/diagnostics?level=" + encodeURIComponent(state.redaction));
  const consistency = report.consistency;

  const pieces = [
    card("Consistent", consistency.consistent ? "yes" : "no", consistency.consistent ? "no disagreement found between the examined surfaces" : consistency.finding_count + " disagreement(s) found", consistency.consistent ? "ok" : "notice"),
    card("Export level", report.redaction_level, report.redaction_level === "redacted" ? "coordinates rounded, addresses masked" : report.redaction_level === "minimal" ? "values removed" : "no redaction applied", report.redaction_level === "full" ? "warn" : "ok"),
    card("Environment state", report.environment_state, "", "", ""),
    card("Failed stage", report.failed_stage || "none", "", "", "")
  ];

  renderGrid(element("consistency-grid"), pieces);

  const findings = consistency.findings.map((finding) => {
    return (
      '<div class="finding ' + escapeText(finding.severity) + '">' +
      '<div class="headline">' + escapeText(finding.summary) + "</div>" +
      '<div class="explain">' + escapeText(finding.detail) + "</div>" +
      '<div class="surfaces">surfaces: ' + escapeText(finding.surfaces.join(", ")) + "</div>" +
      "</div>"
    );
  });

  const notExamined =
    '<div class="finding info"><div class="headline">Surfaces this core does not control</div><div class="explain">' +
    escapeText(consistency.not_examined_note) +
    '</div><div class="surfaces">' + escapeText(consistency.surfaces_not_examined.join(", ")) + "</div></div>";

  element("consistency-findings").innerHTML = (findings.length ? findings.join("") : '<div class="finding info"><div class="headline">No disagreements between the examined surfaces</div><div class="explain">' + escapeText(consistency.caveat) + "</div></div>") + notExamined;

  element("diagnostics-report").textContent = JSON.stringify(report, null, 2);
}

async function refresh(snapshotOverride) {
  try {
    const profile = element("profile-select").value || "default";
    const host = element("host-input").value.trim();
    const query = "/api/environment?profile=" + encodeURIComponent(profile) + "&host=" + encodeURIComponent(host) + "&session=interface";

    const snapshot = snapshotOverride || (await fetchJson(query));

    state.snapshot = snapshot;

    renderOverview(snapshot);
    renderLocation(snapshot);
    renderTimezone(snapshot);
    renderLocale(snapshot);
    renderPrivacy(snapshot);
    renderPolicies(snapshot);

    await renderNetwork();
    renderDns(snapshot);
    renderProfiles();
    await renderDiagnostics();
    await loadExports();

    element("footer").textContent =
      "engine " + state.meta.engine_version +
      " | profile schema v" + state.meta.profile_version +
      " | " + state.meta.counts.timezones + " timezones from the local database" +
      " | catalogue of " + state.meta.counts.cities + " cities held offline" +
      " | storage " + (state.meta.storage.persistent ? "persistent at " + state.meta.storage.root : "memory only");
  } catch (error) {
    showFailure(element("overview-grid"), error.message);
    element("state-badge").textContent = "ERROR";
    element("state-badge").className = "state-badge state-error";
    element("state-detail").textContent = error.message;
  }
}

async function sample() {
  const profile = element("profile-select").value || "default";
  const rows = [];

  for (let attempt = 1; attempt <= 10; attempt += 1) {
    const query = "/api/environment?profile=" + encodeURIComponent(profile) + "&session=sampling-" + attempt;
    const snapshot = await fetchJson(query);

    if (!snapshot.geo) {
      rows.push("<tr><td>" + attempt + "</td><td>not resolved</td><td>not resolved</td><td>not resolved</td></tr>");
      continue;
    }

    const centre = snapshot.geo;
    const drift = await distanceFromCentre(profile, centre);

    rows.push(
      "<tr><td>" + attempt + "</td><td>" + centre.latitude + "</td><td>" + centre.longitude + "</td><td>" + drift + "</td></tr>"
    );
  }

  element("sample-table").querySelector("tbody").innerHTML = rows.join("");
}

async function distanceFromCentre(profile, geo) {
  const detail = await fetchJson("/api/profiles/" + encodeURIComponent(profile));

  if (detail.latitude === undefined || detail.latitude === null) {
    return "no centre to compare against";
  }

  const radius = 6371008.8;
  const toRadians = Math.PI / 180;
  const phiA = detail.latitude * toRadians;
  const phiB = geo.latitude * toRadians;
  const deltaPhi = (geo.latitude - detail.latitude) * toRadians;
  const deltaLambda = (geo.longitude - detail.longitude) * toRadians;

  const inner = Math.sin(deltaPhi / 2) ** 2 + Math.cos(phiA) * Math.cos(phiB) * Math.sin(deltaLambda / 2) ** 2;
  const metres = 2 * radius * Math.asin(Math.min(1, Math.sqrt(inner)));

  return metres.toFixed(1) + " m";
}

async function loadProfiles() {
  const payload = await fetchJson("/api/profiles");
  state.profiles = payload.profiles;

  element("profile-select").innerHTML = state.profiles
    .map((profile) => '<option value="' + escapeText(profile.identifier) + '">' + escapeText(profile.name) + "</option>")
    .join("");

  const active = state.profiles.filter((profile) => profile.identifier === state.meta.active_profile)[0];
  const preferred = active || state.profiles.filter((profile) => profile.identifier === "berlin-wide")[0];

  if (preferred) {
    element("profile-select").value = preferred.identifier;
  }
}

async function loadExports() {
  const listing = await fetchJson("/api/diagnostics/list");
  const rows = listing.exports.map((entry) => "<tr><td>" + escapeText(entry.name) + "</td><td>" + entry.bytes + "</td></tr>");
  element("exports-table").querySelector("tbody").innerHTML = rows.join("") || "<tr><td>none yet</td><td>0</td></tr>";
}

async function loadMeta() {
  state.meta = await fetchJson("/api/meta");
}

async function activateProfile(identifier) {
  try {
    const result = await fetchJson("/api/profiles/activate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier: identifier })
    });

    element("activate-result").textContent =
      "Active profile is now " + result.active_profile + (result.persisted ? ", written to disk." : ". This session is memory only, so it will not survive a restart.");

    await loadMeta();
    await refresh();
  } catch (error) {
    element("activate-result").textContent = "Rejected: " + error.message;
  }
}

async function deleteProfile(identifier) {
  try {
    const result = await fetchJson("/api/profiles/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier: identifier })
    });

    element("activate-result").textContent = result.removed ? "Deleted " + identifier + "." : "No profile named " + identifier + ".";

    await loadProfiles();
    await loadMeta();
    await refresh();
  } catch (error) {
    element("activate-result").textContent = "Rejected: " + error.message;
  }
}

async function saveReport() {
  try {
    const report = await fetchJson("/api/diagnostics?level=" + encodeURIComponent(state.redaction) + "&persist=true");
    element("diagnostics-report").textContent = JSON.stringify(report, null, 2);

    const listing = await fetchJson("/api/diagnostics/list");
    const rows = listing.exports.map((entry) => "<tr><td>" + escapeText(entry.name) + "</td><td>" + entry.bytes + "</td></tr>");
    element("exports-table").querySelector("tbody").innerHTML = rows.join("") || "<tr><td>none yet</td><td>0</td></tr>";

    await loadMeta();
    renderStorage();
  } catch (error) {
    element("diagnostics-report").textContent = "Could not write the report: " + error.message;
  }
}

async function validateImport() {
  const raw = element("import-area").value.trim();

  if (!raw) {
    element("import-result").textContent = "Nothing to validate.";
    return;
  }

  try {
    const body = JSON.parse(raw);
    const result = await fetchJson("/api/profiles/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: body })
    });

    element("import-result").textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    element("import-result").textContent = "Rejected: " + error.message;
  }
}

async function performImport() {
  const raw = element("import-area").value.trim();

  if (!raw) {
    element("import-result").textContent = "Nothing to import.";
    return;
  }

  try {
    const body = JSON.parse(raw);
    const result = await fetchJson("/api/profiles/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: body, strict: true })
    });

    element("import-result").textContent = JSON.stringify(result, null, 2);

    await loadProfiles();
    await refresh();
  } catch (error) {
    element("import-result").textContent = "Rejected before activation: " + error.message;
  }
}

function activateTabs() {
  const tabs = Array.from(document.querySelectorAll(".tab"));

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((other) => other.classList.remove("active"));
      tab.classList.add("active");

      document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("active"));
      element("panel-" + tab.dataset.panel).classList.add("active");
    });
  });
}

async function start() {
  activateTabs();

  await loadMeta();
  state.resolvers = (await fetchJson("/api/resolvers")).resolvers;
  state.policies = (await fetchJson("/api/policies")).policies;

  await loadProfiles();

  element("apply-button").addEventListener("click", () => refresh());
  element("sample-button").addEventListener("click", () => sample());
  element("validate-button").addEventListener("click", () => validateImport());
  element("import-button").addEventListener("click", () => performImport());

  element("host-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      refresh();
    }
  });

  element("redaction-select").addEventListener("change", (event) => {
    state.redaction = event.target.value;
    renderDiagnostics();
  });

  element("activate-button").addEventListener("click", () => activateProfile(element("activate-select").value));
  element("delete-button").addEventListener("click", () => deleteProfile(element("activate-select").value));
  element("save-report").addEventListener("click", () => saveReport());

  element("refresh-diagnostics").addEventListener("click", () => renderDiagnostics());

  await refresh();
}

start();
