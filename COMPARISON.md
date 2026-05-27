# xcull behaviour comparison

A 99-row sample that shows, at a glance, the kinds of differences a recon
engineer will notice between dedupers (object IDs, content-section
templating, query-keyset merge, bare-folding).

This is **not** the benchmark. It is a side-by-side demo so you can predict
how each tool will treat a URL before you run it on a real target. Full
numbers — peak RSS, throughput, completion time, false merge rate, per-class
PRF — are in [`BENCHMARK.md`](BENCHMARK.md) and the underlying CSVs in
[`raw/`](raw/).

Legend: 🟢 line is kept in the tool's output  ·  🔴 line is merged away or
removed.

| Raw Input URL | uro | urless | urldedupe | uddup | xcull |
|---|---|---|---|---|---|
| `http://example.com/page.php?id=1` | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 |
| `http://example.com/page.php?id=2` | 🔴 | 🔴 | 🔴 | 🟢 | 🔴 |
| `http://example.com/page.php?id=3&page=2` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://example.com/cat/9/details.html` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://example.com/cat/11/details.html` | 🔴 | 🔴 | 🟢 | 🟢 | 🔴 |
| `http://example.com/blog/why-people-suck-a-study` | 🔴 | 🔴 | 🟢 | 🟢 | 🟢 |
| `http://example.com/blog/how-to-lick-your-own-toes` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://example.com/banner.jpg` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://example.com/assets/background.jpg` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `https://target.com/blah/U-61723A/settings` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `https://target.com/blah/U-63352B/settings` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `https://target.com/blah/U-61351A/profile` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `https://target.com/blah/U-61723A/settings` | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| `https://target.com/blah/U-64135C/profile` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `https://google.com` | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 |
| `https://google.com/home?qs=value` | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 |
| `https://google.com/home?qs=secondValue` | 🔴 | 🔴 | 🔴 | 🟢 | 🔴 |
| `https://google.com/home?qs=newValue&secondQs=anotherValue` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `https://google.com/home?qs=asd&secondQs=das` | 🔴 | 🔴 | 🔴 | 🟢 | 🔴 |
| `https://site.com/api/users/123` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `https://site.com/api/users/222` | 🔴 | 🔴 | 🟢 | 🔴 | 🟢 |
| `https://site.com/api/users/412/profile` | 🔴 | 🟢 | 🟢 | 🟢 | 🟢 |
| `https://site.com/users/photos/photo.jpg` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `https://site.com/users/photos/myPhoto.jpg` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `https://site.com/users/photos/photo.png` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `https://www.example.com/product/123` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `https://www.example.com/product/456` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `https://www.example.com/product/123?is_prod=false` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `https://www.example.com/product/222?is_debug=true` | 🔴 | 🔴 | 🟢 | 🟢 | 🟢 |
| `https://www.example.com/` | 🔴 | 🔴 | 🟢 | 🟢 | 🟢 |
| `https://www.example.com/privacy-policy` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `https://www.example.com/product/1` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `https://www.example2.com/product/2` | 🔴 | 🔴 | 🟢 | 🟢 | 🟢 |
| `https://www.example3.com/product/4` | 🔴 | 🔴 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/user/1001/profile` | 🟢 | 🔴 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/user/1002/profile` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/user/1002/profile?view=private` | 🔴 | 🔴 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/user/1002/profile?role=admin` | 🔴 | 🔴 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/user/1002/profile;jsessionid=deadbeef` | 🔴 | 🔴 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/user/1002/profile.json` | 🔴 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/user/1002/profile.bak` | 🔴 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/user/1002/profile.old` | 🔴 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/user/1002/export` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/user/1002/export.csv` | 🔴 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/user/1002/export?format=xml` | 🔴 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/user/1002/reset-password` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/user/1002/reset-password?token=test` | 🔴 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/admin/users/1002` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/admin/users/1002/permissions` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/admin/users/1002/permissions?debug=true` | 🔴 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/admin/users/1002/roles` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/admin/users/1002/roles?impersonate=true` | 🔴 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/org/55/project/77/member/88` | 🟢 | 🔴 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/org/55/project/77/member/89` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/org/55/project/77/member/89?include=secrets` | 🔴 | 🔴 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/org/55/project/77/member/89/billing` | 🔴 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/org/55/project/77/member/89/invoices/pdf` | 🔴 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/org/55/project/77/member/89/activity` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/org/55/project/77/member/89/activity?from=2025-01-01` | 🔴 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/org/55/project/77/member/89/activity?debug=1` | 🔴 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/payment/transfer` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/payment/transfer?currency=usd` | 🟢 | 🟢 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/payment/transfer?currency=usd&debug=true` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/payment/transfer/preview` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/payment/transfer/commit` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/payment/transfer/commit?race=test` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/payment/withdraw` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/payment/withdraw/confirm` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/payment/withdraw/confirm?step=2` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/auth/session` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/auth/session;jsessionid=AAAA1111` | 🔴 | 🔴 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/auth/session;jsessionid=BBBB2222` | 🔴 | 🔴 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v1/auth/session?redirect=/admin` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/v1/auth/token/refresh` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/auth/token/refresh?device=mobile` | 🟢 | 🟢 | 🟢 | 🔴 | 🔴 |
| `http://api.example.com/v1/auth/token/refresh?device=mobile&debug=true` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://example.com/internal/debug` | 🔴 | 🔴 | 🟢 | 🔴 | 🔴 |
| `http://example.com/internal/debug?env=staging` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://example.com/internal/debug?env=production` | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| `http://example.com/internal/health` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://example.com/internal/metrics` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://example.com/internal/prometheus` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://example.com/backup/config.zip` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://example.com/backup/config.tar.gz` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://example.com/backup/.env` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://example.com/backup/.git/config` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://example.com/backup/database.sql` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://example.com/backup/export.phps` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://cdn.example.com/assets/app.js.map` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://cdn.example.com/assets/admin.js.map` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://cdn.example.com/assets/mobile.apk` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://cdn.example.com/assets/mobile.ipa` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/graphql` | 🔴 | 🔴 | 🟢 | 🟢 | 🔴 |
| `http://api.example.com/graphql?query={me{id,email}}` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/graphql?query={users{id,role}}` | 🔴 | 🔴 | 🔴 | 🟢 | 🟢 |
| `http://api.example.com/graphiql` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
| `http://api.example.com/swagger.json` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/openapi.json` | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 |
| `http://api.example.com/v2/swagger.yaml` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 |
