#!/usr/bin/env python3
# Synthetic ground-truth dataset generator for FP/FN evaluation.
#
# Each URL is labelled with a (pattern_class, group_id) tuple. The
# canonical ground-truth count for a pattern class is the number of
# distinct group_ids in that class. A dedup tool is scored against the
# truth by counting, for every URL it kept, the (class, group_id) it
# falls in and asking:
#
#   - recall_class      = surviving_groups / total_groups
#                         "did at least one representative of every
#                          canonical endpoint survive?"
#   - over_keep_class   = kept_urls / surviving_groups
#                         "how many redundant duplicates did the tool
#                          leave behind per canonical endpoint? 1.0 is
#                          perfect, higher means worse compression"
#   - destroyed_class   = total_groups - surviving_groups
#                         "how many canonical endpoints did the tool
#                          delete?"
#
# A correct dedup tool achieves recall = 1.0 and over_keep close to 1.0
# on every pattern class. uro/urless trade recall for compression on
# the .js / matrix / open-redirect classes (canonical endpoint
# destroyed); urldedupe trades over_keep for recall on everything (no
# real folding).

import hashlib
import json
import os
import random
import string
import sys
import uuid

OUT_URLS = os.path.join(os.path.dirname(__file__), "..", "data", "D_synth.full")
OUT_TRUTH = os.path.join(os.path.dirname(__file__), "..", "data", "D_synth.truth.json")
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


# 1. NUMERIC_ID: /product/<n>  - 5000 ids, 1 canonical group
for i in range(5000):
    emit(base("/product/%d" % i), "NUMERIC_ID", "product")

# 2. UUID: /order/<uuid4>  - 5000 ids, 1 canonical group
for i in range(5000):
    u = uuid.UUID(int=random.getrandbits(128), version=4)
    emit(base("/order/%s" % u), "UUID", "order")

# 3. HEX_HASH: /asset/<sha256>  - 5000 ids, 1 canonical group
for i in range(5000):
    h = hashlib.sha256(str(i).encode()).hexdigest()
    emit(base("/asset/%s" % h), "HEX_HASH", "asset")

# 4. TITLE_SLUG: /blog/<slug-words-id>  - 5000 ids, 1 canonical group
words = [
    "the", "fast", "lazy", "fox", "quick", "brown", "dog", "jumps",
    "over", "river", "blue", "deep", "wide", "narrow", "silent",
    "story", "tale", "guide", "review", "notes",
]
for i in range(5000):
    slug = "-".join(random.sample(words, 5)) + "-%d" % i
    emit(base("/blog/%s" % slug), "TITLE_SLUG", "blog")

# 5. CACHE_BUST: /main.js?_=<ts>  - 5000 ids, 1 canonical group
#    (the jQuery `?_=` underscore cache-bust pattern: same endpoint)
for i in range(5000):
    emit(base("/main.js?_=%d" % (1700000000 + i)), "CACHE_BUST", "main.js")

# 6. JSESSIONID: /auth;jsessionid=<sid>  - 5000 ids, 1 canonical group
#    A J2EE authenticated route; the matrix value is a per-session
#    token and must fold to one canonical endpoint.
for i in range(5000):
    sid = "".join(random.choices(string.ascii_uppercase + string.digits, k=32))
    emit(base("/auth;jsessionid=%s" % sid), "JSESSIONID", "auth")

# 7. OPEN_REDIRECT: /redir?url=<...>  - 5000 ids, 1 canonical group
#    The endpoint + param-name is the surface; the value varies.
for i in range(5000):
    emit(base("/redir?url=http%%3A%%2F%%2Fevil-%d.com" % i),
         "OPEN_REDIRECT", "redir")

# 8. LFI_PARAM: /page?file=<payload>  - 5000 ids, 1 canonical group
#    The endpoint + param-name is the security surface. The value is a
#    traversal payload that varies. (%00 null-byte deliberately omitted:
#    that is its own findings axis, not the param-folding test.)
for i in range(5000):
    emit(base("/page?file=..%%2F..%%2F..%%2Fetc%%2Fpasswd.%d" % i),
         "LFI_PARAM", "page")

# 9. PARAM_ORDER: /api?a=X&b=Y and /api?b=Y&a=X  - 5000 ids, 1 canonical
#    Same endpoint + same param set, just different order.
for i in range(2500):
    emit(base("/api?a=%d&b=%d" % (i, i + 1)), "PARAM_ORDER", "api")
    emit(base("/api?b=%d&a=%d" % (i + 1, i)), "PARAM_ORDER", "api")

# 10. TRAILING_SLASH: /widget<i>/ and /widget<i>  - 100 pairs = 200 urls,
#     100 canonical groups (each i is its own group; slash folds).
for i in range(100):
    emit(base("/widget%d" % i), "TRAILING_SLASH", "widget%d" % i)
    emit(base("/widget%d/" % i), "TRAILING_SLASH", "widget%d" % i)

# 11. GENUINE_DISTINCT: 200 truly distinct endpoints, every one its own
#     canonical group. A tool that folds these is destroying surface.
distinct = [
    "/admin", "/login", "/logout", "/dashboard", "/profile",
    "/settings", "/billing", "/checkout", "/cart", "/orders",
    "/api/v1/users", "/api/v1/orders", "/api/v1/products",
    "/api/v1/sessions", "/api/v1/auth/token", "/api/v1/auth/refresh",
    "/api/v2/users", "/api/v2/orders", "/api/v2/products",
    "/api/v2/sessions",
    "/admin/users", "/admin/orders", "/admin/settings", "/admin/logs",
    "/admin/db", "/admin/backup", "/admin/maintenance",
    "/admin/permissions", "/admin/keys", "/admin/audit",
    "/internal/health", "/internal/metrics", "/internal/debug",
    "/internal/config", "/internal/version",
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
    "/static/js/app.js", "/static/js/vendor.js",
    "/static/js/runtime.js", "/static/js/main.js",
    "/static/css/app.css", "/static/css/vendor.css",
    "/assets/sprite.svg", "/assets/icons.svg",
    "/manifest.json", "/service-worker.js",
    "/robots.txt", "/sitemap.xml", "/humans.txt", "/ads.txt",
    "/crossdomain.xml", "/clientaccesspolicy.xml",
    "/favicon.ico", "/apple-touch-icon.png",
    "/api/v3/internal/admin/users",
    "/api/v3/internal/admin/audit",
    "/api/v3/internal/db/dump",
    "/api/v3/internal/cache/flush",
    "/api/v3/internal/queue/drain",
    "/_next/data/build/users.json",
    "/_next/data/build/orders.json",
    "/_nuxt/_payload.js",
    "/__webpack_hmr",
    "/sockjs-node/info",
    "/ws/notifications", "/ws/chat", "/ws/presence",
    "/api/upload", "/api/download", "/api/export",
    "/api/import", "/api/search",
    "/api/v1/files", "/api/v1/files/upload",
    "/api/v1/files/download",
    "/api/v1/groups", "/api/v1/groups/members",
    "/api/v1/roles", "/api/v1/permissions",
    "/api/v1/audit", "/api/v1/events",
    "/api/v1/webhooks", "/api/v1/integrations",
    "/api/v1/secrets", "/api/v1/keys",
    "/api/v1/tokens", "/api/v1/sessions/refresh",
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
    "/portal/index.html",
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
    "/druid/index.html",
    "/eureka/apps", "/hystrix",
    "/console.h2", "/h2-console",
    "/phpinfo.php", "/phpmyadmin",
    "/adminer.php",
]
# Truncate or pad to exactly 200.
distinct = distinct[:200]
assert len(distinct) >= 100, "need at least 100 truly distinct endpoints"
for p in distinct:
    emit(base(p), "GENUINE_DISTINCT", p)

# 12. SRCDISC: 20 source-disclosure files, each its own canonical group.
#     These are the per-line audit gold class - if a tool drops any of
#     them it is destroying real findings.
srcdisc = [
    "/.env", "/.env.production", "/.env.local",
    "/.git/config", "/.git/HEAD", "/.git/index",
    "/db.sql", "/backup.sql", "/dump.sql",
    "/backup.zip", "/backup.tar.gz",
    "/index.php.bak", "/config.php.bak", "/wp-config.php.bak",
    "/.htaccess.bak", "/.htpasswd",
    "/config.php.swp", "/.DS_Store",
    "/credentials.json", "/secrets.yml",
]
for f in srcdisc:
    emit(base(f), "SRCDISC", f)

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


if __name__ == "__main__":
    write_out()
