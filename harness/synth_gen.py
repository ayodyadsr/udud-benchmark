#!/usr/bin/env python3
# Unified labeled input generator (D_unified.full, ~780k URLs).
#
# This is the single input used by both xcull and xcull-benchmark. It
# replaces the previous mix of D_synth (45k, controlled) + D_example_wb
# (781k, real-but-unlabeled) so every metric in every report comes from
# one input with one ground truth.
#
# Design constraints:
#   - Total size ~780,000 URLs to match the previous Wayback headline
#     scale, so throughput/RAM/completion-time numbers stay comparable
#     to the prior cost/reach measurements.
#   - Every URL carries a (pattern_class, group_id) label, so every
#     dedup tool can be scored against an exact known answer.
#   - Class distribution favours enumeration noise over hand-curated
#     surface, which is what real recon captures look like: ~90% of
#     input URLs are templated (object IDs, cache busts, session
#     tokens, slug listings), and the long tail of genuinely distinct
#     endpoints is what a tester actually has to scan.
#
# Scoring rules (used by synth_eval.py):
#   - For each pattern class, count surviving canonical groups in the
#     tool output. A class is LOSSLESS if every group is represented by
#     at least one keep.
#   - False merge rate = (canonical groups not represented in output) /
#     (total canonical groups). A merge that collapses two distinct
#     groups into one is counted once per destroyed group.
#   - Throughput, peak RSS, and wall time are measured on this same
#     input, so all five headline metrics share an input.

import hashlib
import json
import os
import random
import string
import sys
import uuid

OUT_URLS = os.path.join(os.path.dirname(__file__), "..", "data", "D_unified.full")
OUT_TRUTH = os.path.join(os.path.dirname(__file__), "..", "data", "D_unified.truth.json")
HOST = "syn.example.com"
SCHEME = "https"

random.seed(42)


def base(p):
    return "%s://%s%s" % (SCHEME, HOST, p)


urls = []        # list of (url, pattern_class, group_id)
truth = {}       # pattern_class -> {group_id: count_of_input_lines}


def emit(url, klass, gid):
    urls.append((url, klass, gid))
    truth.setdefault(klass, {}).setdefault(gid, 0)
    truth[klass][gid] += 1


# vocabulary used for both hand-curated GENUINE_DISTINCT and the
# templated-but-distinct REST surface below.
SERVICE_NAMES = [
    "users", "orders", "products", "payments", "invoices", "subscriptions",
    "billing", "carts", "checkouts", "shipping", "refunds", "discounts",
    "coupons", "promotions", "campaigns", "tickets", "messages", "notifications",
    "comments", "reviews", "ratings", "feedback", "reports", "analytics",
    "events", "audit", "logs", "metrics", "stats", "dashboards",
    "files", "uploads", "downloads", "exports", "imports", "archives",
    "media", "images", "videos", "documents", "templates", "themes",
    "settings", "preferences", "profile", "account", "membership", "groups",
    "teams", "organizations", "projects", "tasks", "boards", "lists",
    "tags", "categories", "labels", "topics", "channels", "feeds",
    "posts", "articles", "pages", "stories", "news", "announcements",
    "blogs", "podcasts", "webinars", "courses", "lessons", "quizzes",
    "permissions", "roles", "policies", "rules", "scopes", "claims",
    "tokens", "keys", "secrets", "credentials", "sessions", "devices",
    "apps", "integrations", "connectors", "webhooks", "subscriptions",
    "endpoints", "routes", "domains", "certificates", "dns",
    "queues", "jobs", "workflows", "pipelines", "schedules", "triggers",
    "providers", "vendors", "suppliers", "partners", "contacts", "leads",
]
VERBS = [
    "list", "create", "update", "delete", "search", "export", "import",
    "activate", "deactivate", "approve", "reject", "submit", "cancel",
    "duplicate", "archive", "restore", "publish", "draft", "preview",
    "validate", "verify", "sync", "rebuild", "rotate", "revoke",
]
AREAS = [
    "api", "internal", "admin", "manage", "console", "portal", "staff",
    "operator", "system",
]


# Class proportions chosen to match the shape of a real recon capture:
# the bulk of input is templated noise (query cache-busts, slug listings)
# that any reasonable deduper collapses to a small witness set, plus a
# smaller real attack surface (object enumerations + hand-typed routes)
# that xcull preserves by design. The previous design loaded too much
# raw enumeration (UUID/HEX/JSESSIONID at 230k input) which inflated
# every keep-biased tool's working set artificially; this distribution
# tracks what we measured on a 781k Wayback capture (xcull kept ~129k
# canonical entries from 781k input, ~17% retention).

# 1. NUMERIC_ID: /<base>-<n>/<id>, 30 endpoints x 1000 ids = 30k
#    Real object IDs: xcull preserves under keep-bias because /product/1001
#    and /product/1002 may be distinct IDOR/BOLA targets. uro/urless fold.
NUMERIC_ID_ENDPOINTS = [
    "product", "item", "post", "comment", "order-item", "report",
    "ticket", "issue", "task", "review",
]
# 10 bases x 3 = 30 endpoints
NUMERIC_ID_ENDPOINTS = ["%s-%d" % (n, i) for n in NUMERIC_ID_ENDPOINTS for i in range(3)]
assert len(NUMERIC_ID_ENDPOINTS) == 30
for ep in NUMERIC_ID_ENDPOINTS:
    for i in range(1000):
        emit(base("/%s/%d" % (ep, i)), "NUMERIC_ID", ep)

# 2. UUID: /order-<n>/<uuid4>, 15 endpoints x 1000 uuids = 15k
UUID_ENDPOINTS = ["order-%d" % i for i in range(15)]
for ep in UUID_ENDPOINTS:
    for i in range(1000):
        u = uuid.UUID(int=random.getrandbits(128), version=4)
        emit(base("/%s/%s" % (ep, u)), "UUID", ep)

# 3. HEX_HASH: /asset-<n>/<sha256>, 10 endpoints x 1000 hashes = 10k
HEX_ENDPOINTS = ["asset-%d" % i for i in range(10)]
for ep in HEX_ENDPOINTS:
    for i in range(1000):
        h = hashlib.sha256(("%s-%d" % (ep, i)).encode()).hexdigest()
        emit(base("/%s/%s" % (ep, h)), "HEX_HASH", ep)

# 4. TITLE_SLUG: /blog-<n>/<slug>, 260 patterns x 1000 slugs = 260k
#    Heavy templated bulk: every reasonable deduper folds this to one
#    witness per pattern.
SLUG_WORDS = [
    "the", "fast", "lazy", "fox", "quick", "brown", "dog", "jumps",
    "over", "river", "blue", "deep", "wide", "narrow", "silent",
    "story", "tale", "guide", "review", "notes", "five", "ten", "best",
    "worst", "top", "ultimate", "complete", "real", "true", "simple",
]
SLUG_ENDPOINTS = ["blog-%d" % i for i in range(260)]
for ep in SLUG_ENDPOINTS:
    for i in range(1000):
        slug = "-".join(random.sample(SLUG_WORDS, 5)) + "-%d" % i
        emit(base("/%s/%s" % (ep, slug)), "TITLE_SLUG", ep)

# 5. CACHE_BUST: /<file>-<n>.js?_=<ts>, 250 files x 1000 ts each = 250k
#    Heavy query-noise bulk: xcull folds the `_` cache-bust per file.
CACHE_FILES_BASE = ["main", "app", "vendor", "runtime", "polyfill"]
CACHE_FILES = ["%s-%d.js" % (n, i) for n in CACHE_FILES_BASE for i in range(50)]
assert len(CACHE_FILES) == 250
for f in CACHE_FILES:
    for i in range(1000):
        emit(base("/%s?_=%d" % (f, 1700000000 + i)), "CACHE_BUST", f)

# 6. JSESSIONID: /auth-<n>;jsessionid=<sid>, 5 endpoints x 1000 sids = 5k
JS_ENDPOINTS = ["auth-%d" % i for i in range(5)]
for ep in JS_ENDPOINTS:
    for i in range(1000):
        sid = "".join(random.choices(string.ascii_uppercase + string.digits, k=32))
        emit(base("/%s;jsessionid=%s" % (ep, sid)), "JSESSIONID", ep)

# 7. OPEN_REDIRECT: /redir-<n>?url=<...>, 50 endpoints x 1000 = 50k
REDIR_ENDPOINTS = ["redir-%d" % i for i in range(50)]
for ep in REDIR_ENDPOINTS:
    for i in range(1000):
        emit(base("/%s?url=http%%3A%%2F%%2Fevil-%d.com" % (ep, i)),
             "OPEN_REDIRECT", ep)

# 8. LFI_PARAM: /page-<n>?file=<payload>, 50 endpoints x 1000 = 50k
LFI_ENDPOINTS = ["page-%d" % i for i in range(50)]
for ep in LFI_ENDPOINTS:
    for i in range(1000):
        emit(base("/%s?file=..%%2F..%%2F..%%2Fetc%%2Fpasswd.%d" % (ep, i)),
             "LFI_PARAM", ep)

# 9. PARAM_ORDER: /api-<n>?a=X&b=Y vs /api-<n>?b=Y&a=X, 50 endpoints x
#    500 reorder-pairs = 50k urls
ORDER_ENDPOINTS = ["api-%d" % i for i in range(50)]
for ep in ORDER_ENDPOINTS:
    for i in range(500):
        emit(base("/%s?a=%d&b=%d" % (ep, i, i + 1)), "PARAM_ORDER", ep)
        emit(base("/%s?b=%d&a=%d" % (ep, i + 1, i)), "PARAM_ORDER", ep)

# 10. TRAILING_SLASH: /widget<i>/ and /widget<i>, 5000 pairs = 10k
for i in range(5000):
    emit(base("/widget%d" % i), "TRAILING_SLASH", "widget%d" % i)
    emit(base("/widget%d/" % i), "TRAILING_SLASH", "widget%d" % i)

# 11. GENUINE_DISTINCT: ~50k truly distinct endpoints. Generated as
#     /<area>/v<ver>/<service>/<verb> over hand-picked vocabulary so
#     every component is a token a human would type, never an
#     enumerable id. A deduper that folds these is destroying surface.
distinct = []
# (a) the original hand-curated short list, all clearly distinct
hand_curated = [
    "/admin", "/login", "/logout", "/dashboard", "/profile",
    "/settings", "/billing", "/checkout", "/cart", "/orders",
    "/oauth/authorize", "/oauth/token", "/oauth/revoke",
    "/oauth/userinfo", "/oauth/jwks",
    "/saml/sso", "/saml/slo", "/saml/metadata",
    "/sso/login", "/sso/callback",
    "/graphql", "/graphiql", "/api/graphql",
    "/webhook/github", "/webhook/stripe", "/webhook/twilio",
    "/healthz", "/readyz", "/livez", "/status", "/metrics",
    "/version", "/buildinfo", "/swagger.json", "/openapi.json",
    "/api-docs",
    "/.well-known/security.txt", "/.well-known/openid-configuration",
    "/.well-known/jwks.json", "/.well-known/oauth-authorization-server",
    "/.well-known/host-meta", "/.well-known/webfinger",
    "/.well-known/acme-challenge",
    "/manifest.json", "/service-worker.js",
    "/robots.txt", "/sitemap.xml", "/humans.txt", "/ads.txt",
    "/crossdomain.xml", "/clientaccesspolicy.xml",
    "/_next/data/build/users.json",
    "/_next/data/build/orders.json",
    "/_nuxt/_payload.js",
    "/__webpack_hmr",
    "/sockjs-node/info",
    "/ws/notifications", "/ws/chat", "/ws/presence",
    "/api/upload", "/api/download", "/api/export",
    "/api/import", "/api/search",
    "/console", "/console/login", "/console/dashboard",
    "/manage", "/manage/users", "/manage/billing",
    "/portal", "/portal/login", "/portal/account",
    "/staff", "/staff/login", "/staff/dashboard",
    "/operator", "/operator/dashboard",
    "/superadmin", "/superadmin/dashboard",
    "/dev", "/dev/console", "/dev/api",
    "/staging/admin", "/staging/api",
    "/test/admin", "/test/api",
    "/qa/admin", "/qa/api",
    "/uat/admin", "/uat/api",
    "/preview/admin", "/preview/api",
    "/sandbox/admin", "/sandbox/api",
    "/legacy/admin.php", "/legacy/login.php",
    "/legacy/index.php",
    "/cgi-bin/login.cgi", "/cgi-bin/admin.cgi",
    "/scripts/login.asp", "/scripts/admin.asp",
    "/owa/auth/logon.aspx", "/Citrix/Web/login.aspx",
    "/Pulse/protected/login.cgi",
    "/dana-na/auth/url_default/welcome.cgi",
    "/AWStats", "/awstats/awstats.pl",
    "/server-status", "/server-info",
    "/.svn/entries", "/.hg/store",
    "/_vti_pvt/service.pwd",
    "/aspnet_client", "/App_Data", "/App_Code",
    "/WEB-INF/web.xml", "/WEB-INF/classes",
    "/META-INF/MANIFEST.MF",
    "/jolokia/list", "/jolokia/read",
    "/actuator/health", "/actuator/env", "/actuator/heapdump",
    "/actuator/threaddump", "/actuator/loggers",
    "/druid", "/eureka/apps", "/hystrix",
    "/console.h2", "/h2-console",
    "/phpinfo.php", "/phpmyadmin",
    "/adminer.php",
]
distinct.extend(hand_curated)

# (b) REST surface: /<area>/v<ver>/<service>/<verb>
#     9 areas x 3 versions x 100 services x 24 verbs = 64,800 paths
for area in AREAS:
    for ver in (1, 2, 3):
        for svc in SERVICE_NAMES[:100]:
            for verb in VERBS[:24]:
                distinct.append("/%s/v%d/%s/%s" % (area, ver, svc, verb))

# de-duplicate just in case any hand-curated path collided with the
# programmatic surface, then cap at 50,000 to keep the input near the
# 780k headline. The cap is deterministic because the input list order
# is fixed.
seen = set()
distinct_unique = []
for p in distinct:
    if p not in seen:
        seen.add(p)
        distinct_unique.append(p)
distinct = distinct_unique[:50000]
assert len(distinct) == 50000, "expected exactly 50000 distinct paths, got %d" % len(distinct)
for p in distinct:
    emit(base(p), "GENUINE_DISTINCT", p)

# 12. SRCDISC: 200 source-disclosure files, each its own canonical group.
SRCDISC_BASE = [
    ".env", ".env.production", ".env.local", ".env.staging", ".env.development",
    ".git/config", ".git/HEAD", ".git/index", ".git/logs/HEAD",
    "db.sql", "backup.sql", "dump.sql", "database.sql", "data.sql",
    "backup.zip", "backup.tar.gz", "backup.tar", "backup.7z",
    "index.php.bak", "config.php.bak", "wp-config.php.bak",
    "config.bak", "settings.bak", "app.bak",
    ".htaccess.bak", ".htpasswd",
    "config.php.swp", ".DS_Store",
    "credentials.json", "secrets.yml", "secrets.json", "vault.yml",
    ".aws/credentials", ".ssh/id_rsa", ".ssh/id_ed25519",
    "WEB-INF/web.xml.bak", "META-INF/context.xml.bak",
    "private.pem", "server.key", "ca.crt",
]
# replicate per project name to reach 200 distinct paths (40 x 5 = 200)
SRCDISC_PROJECTS = ["", "/app", "/web", "/site", "/portal"]
srcdisc = []
for proj in SRCDISC_PROJECTS:
    for f in SRCDISC_BASE:
        srcdisc.append("%s/%s" % (proj, f) if proj else "/%s" % f)
srcdisc = srcdisc[:200]
assert len(srcdisc) == 200, "expected 200 srcdisc paths, got %d" % len(srcdisc)
for p in srcdisc:
    emit(base(p), "SRCDISC", p)

# Shuffle so input order does not advantage any tool that depends on
# adjacency.
random.shuffle(urls)


def write_out():
    os.makedirs(os.path.dirname(OUT_URLS), exist_ok=True)
    with open(OUT_URLS, "w") as fh:
        for u, _, _ in urls:
            fh.write(u + "\n")

    canonical_truth = {}
    for klass, groups in truth.items():
        canonical_truth[klass] = {
            "n_input_urls": sum(groups.values()),
            "n_canonical_groups": len(groups),
            "groups": list(groups.keys()),
        }
    with open(OUT_TRUTH, "w") as fh:
        json.dump(canonical_truth, fh, indent=2, sort_keys=True)

    print("wrote %d urls to %s" % (len(urls), OUT_URLS))
    print("wrote ground truth to %s" % OUT_TRUTH)
    total_groups = sum(len(g) for g in truth.values())
    print("classes : %d" % len(truth))
    print("canonical groups : %d" % total_groups)
    print()
    print("per-class breakdown:")
    for klass in sorted(truth):
        groups = truth[klass]
        n_urls = sum(groups.values())
        n_groups = len(groups)
        print("  %-18s urls=%7d  groups=%6d" % (klass, n_urls, n_groups))


if __name__ == "__main__":
    write_out()
