# Commercial/public OJ product teardown cho JudgeLoom

**Ngày:** 2026-10-30 · **Phạm vi:** sản phẩm OJ công khai/thương mại, bổ sung cho nghiên cứu open-source tại [`open-source-online-judges.md`](./open-source-online-judges.md). Không sửa code/config/test/dependency.

> **Đạo đức & phương pháp.** Chỉ dùng trang public, docs/help/API docs chính thức, public demo và mô tả tính năng công khai. Không login, không vượt paywall/ToS, không scrape dữ liệu riêng, không đọc/dịch ngược JS bundle, app hay private API. **REA không được dùng vì không có artifact được phép**; đây thuần là nghiên cứu sản phẩm công khai. Mọi URL truy cập **2026-10-30**.
>
> **Quy ước.** `[QS]` = quan sát trực tiếp trang/API public. `[QS-GT]` = trang public nhưng chặn automated fetch (403/Cloudflare); dữ kiện lấy từ snippet public/Discuss public, không suy đoán sau login. `[SL]` = suy luận/khuyến nghị. LeetCode, SPOJ, Luogu main, Baekjoon đã chặn hoặc không phục vụ sản phẩm trong ngày khảo sát.

---

## 1. Executive summary

1. **Discovery là faceted search + trạng thái người học.** Codeforces lọc tag/difficulty/rating; Kattis lọc type/objective/author; HackerRank lọc skill/status; Luogu lọc source/algorithm/status. JudgeLoom có `Tag`, `ProblemDifficulty`, `ProblemType` nhưng API list chỉ lọc `difficulty` và `points`.
2. **Problem detail là learning object.** LeetCode có hints/editorial/solutions/discussion; AtCoder có official + user editorial; Luogu có vote solution và tải test sai; Kattis có metadata/downloads/license. JudgeLoom chỉ có `description` + `Solution` tự do.
3. **Submission phải có `run` vs `submit`, contest context, privacy.** Codeforces tách Submit/Custom Invocation/Status; DMOJ API trả case/batch. JudgeLoom thiếu cả ba.
4. **Contest là rule engine.** Codeforces có Div 1–4/ICPC/Team, virtual, hack, clarification; CodeChef 4 division song song; Luogu OI/LeDuo/ICPC/IOI. JudgeLoom có format registry nhưng thiếu đường nộp contest, division/team/clarification, freeze đúng.
5. **Retention đến từ instrumentation.** LeetCode daily/streak/badge/rating graph; solved.ac tier/class/tag rating/streak; HackerRank certification. JudgeLoom chỉ có `rating` và `problem_count`.
6. **API là product surface.** Codeforces API public có ký request; DMOJ token API v2; Luogu Open Platform B2B; HackerRank enterprise API. LeetCode/AtCoder/Baekjoon/CodeChef không có API public chính thức — không scrape.
7. **Tiền nằm ở B2B/education/data.** Luogu premium team/trường/Open Platform; HackerRank/Kattis recruitment; Sphere Engine execution API; AtCoder dataset license.

---

## 2. Product snapshots

### LeetCode
- **Discovery.** Problemset lọc tag qua `?filters=tag%3AJava`, cùng difficulty/status/company; company tag là Premium. `[LEET1][LEET5]` `[QS-GT]`
- **Problem UX.** Statement, examples, constraints, hints, editorial, solutions, discussion; editor + language + Run/Submit + custom input + verdict/per-case. `[LEET2]` `[QS-GT]`
- **Submission/contest.** History theo problem; weekly/special contest, virtual, rating, LeetCoins tối đa 5.000/contest. `[LEET2][LEET7]` `[QS-GT]`
- **Profile/model.** Solved theo difficulty, daily challenge, streak, badge, rating graph; Premium có company questions + 500 AI credit/tháng + 30 solution analysis/ngày. Không có API public chính thức. `[LEET1][LEET6][LEET8][LEET9]` `[QS-GT]`

### Codeforces
- **Discovery.** Problemset lọc difficulty/tag (OR), hiện rating + solved count; contest lọc Div 1–4, Educational, CodeTON, Global, Kotlin, VK Cup, Long, April Fools, Team, ICPC, rated/tried. `[CF2][CF3]` `[QS]`
- **Problem UX.** Statement, examples, note, tag + rating, time/memory, tutorial, Custom test, Status, Standings. `[CF4]` `[QS]`
- **Submission/contest.** Submit/My Submissions/Status/Custom Invocation; API trả verdict + `passedTestCount` + time/memory, không trả output case. Virtual chỉ ICPC mode; hack có verdict thành công/thất bại, xem test; system tests = pretests + hacks; Q&A công khai. `[CF1][CF5][CF6]` `[QS]`
- **API/model.** API anonymous, **1 request/2 giây**; request private cần `apiKey/time/apiSig` SHA-512. Profile có rating/contribution; Polygon cho problem preparation; Gym; EDU. `[CF1][CF8][CF9][CF10]` `[QS/QS-GT]`

### AtCoder
- **Discovery.** Archive lọc Rated Range (ABC ~1999, ARC 1200–2799, AGC 2800+, AHC), category (weekday, unofficial, sponsored, heuristic), search, duration. `[AC1]` `[QS]`
- **Problem UX.** Statement, constraints, examples, score, time/memory, editorial; editorial official + user, đa ngôn ngữ; clarification public. `[AC2][AC3][AC4]` `[QS]`
- **Submission/contest.** Tasks/editorial/clarification public; All Submissions, Standings, Virtual Standings đều chuyển Sign In. ABC/ARC/AGC/AHC; heuristic là loại riêng. `[AC5][AC6]` `[QS]`
- **API/model.** Không có API public chính thức. **AtCoder Datasets** bán license AI: 900+ contest, 5.000+ problem, 30M+ accepted solution, 112 ngôn ngữ, test data/checker/editorial/reference, WA→AC, provenance; ngưỡng ngân sách 100.000 USD+. `[AC7][AC9]` `[QS]`

### HackerRank
- **Discovery.** Domain Algorithms lọc Status/Skills/Difficulty/Subdomains; hiện max score + success rate. `[HR1]` `[QS]`
- **Problem/contest.** Challenge + “Solve Challenge”; hackathon/company contest, upcoming/archived, registration. `[HR1][HR3]` `[QS]`
- **Profile/API.** Certification theo role/skill; mock interview 30–60 phút. HackerRank for Work REST API dùng personal token (tạo một lần, deactivate/delete), quản lý test/user/team/interview/result, ATS. `[HR4][HR6][HR7]` `[QS]`
- **Model.** B2B SaaS Screen/Interview; AI proctoring, plagiarism, identity/multiple-face, AI interviewer; free practice/certification. `[HR2][HR8]` `[QS]`

### CodeChef
- **Discovery/contest.** Practice/Compete/Compiler/Courses. API nội bộ trả Starters, Monday Munch DSA, Placement Prep, skill tests (Python/Java/C/C++/SQL/OS), past contest + `distinct_users`. `[CC1][CC2][CC3]` `[QS]`
- **Division/rating.** Div 1 ≥2000, Div 2 1600–1999, Div 3 1400–1599, Div 4 <1400; 4 parallel contest; user chỉ thi division mình; bài ngoài division là “Non Scorable”; rating tính trong division. `[CC4][CC5]` `[QS]`
- **API/model.** Không có API public chính thức; `/api/list/contests/all` là endpoint nội bộ, không nên phụ thuộc. Free + Pro (đang sale 40%) + courses. `[CC3]` `[QS/SL]`

### CSES
- **Discovery/problem.** Problem set chia category, hiện solved/total; **không** search/difficulty/tag; Statistics cần login. Task có statement, constraints, example, time/memory, “Your submissions”; không editorial. `[CSES1][CSES2]` `[QS]`
- **Contest/model.** Datatähti, HIIT Open (ICPC-style team), NOI Open; course collection; free problem set, sách free PDF + bản in Springer; không API. `[CSES3][CSES4][CSES5]` `[QS]`

### Kattis
- **Discovery.** Filter language/difficulty/order/type (Interactive)/objective (Pass-fail/Scoring)/author/source; cột Fastest/Shortest/Authors/Full Solves/Ratio/Difficulty/Languages. `[KAT1]` `[QS]`
- **Problem UX.** Statement, metadata, CPU/memory, difficulty, statistics, downloads, source & license; “Edit & Submit”, “My Submissions”. `[KAT2]` `[QS]`
- **Contest/profile.** Create/virtual contest, filter Original/Recycled/User created, role Creator/Contestant/Judge, team; ranklist user/country/affiliation/challenge/language. `[KAT3][KAT4]` `[QS]`
- **Model.** Archive free + Kattis Challenge recruitment (~15 phút, dashboard, auto-grade, chống cheat) + job board; package format public spec. `[KAT5][KAT6][KAT7]` `[QS]`

### SPOJ
- **Product.** 20.000+ problem, 315.000+ user, nhiều ngôn ngữ; tag, forum, contest do advanced user tổ chức. `[SPOJ1][SPOJ2]` `[QS-GT]`
- **API/model.** Không API public; cùng công ty **Sphere Engine** bán Compilers/Problems/Containers API v4/v3, widget, JS SDK, webhook, on-prem, 14-day trial, pricing theo scope/submission. SPOJ/Ideone là free service. `[SPOJ3][SPOJ4]` `[QS]`

### Baekjoon (acmicpc.net)
- **Ngày khảo sát.** Toàn site trả thông báo **hoãn mở lại** (2026-10-22): đã chuyển member info, submission, problem, judging data sang Day One Company; mục tiêu 26/10 bị hoãn vì lỗ hổng PHP2Shell và rà soát bảo mật. Không quan sát được UX. `[BOJ1]` `[QS]`
- **Lớp solved.ac.** Tag/difficulty, AC Rating/tier, Class (10 cấp, 36–48 bài/cấp, bonus tối đa 250), Tag Rating (tag ≥500 bài), Over Rating (1.000 bài khó nhất), streak ranking. `[BOJ2][BOJ3][BOJ4][BOJ5][BOJ6]` `[QS]`
- **Model/API.** Free; không API chính thức; chuyển giao chủ sở hữu + downtime dài là rủi ro continuity. `[BOJ1]` `[QS/SL]`

### Luogu
- **Discovery.** Problem list lọc source (Luogu/Codeforces/SPOJ/AtCoder/UVa), difficulty range, algorithm/source/time/status, keyword, search statement. `[LG1]` `[QS-GT]`
- **Problem UX.** Statement Markdown, SPJ, interactive, custom scoring, test-point config; solution vote; tải test sai đầu tiên theo “dynamic level”; user thường tạo tối đa 50 private problem; zip ≤50MB/giải nén ≤100MB. `[LG2]` `[QS]`
- **Contest.** OI (không xem kết quả, lấy submission cuối), **LeDuo** (score × 0.95^(attempts−1), sàn 70%), ICPC (AC mới tính, +20 phút/lần sai), IOI (max score); official/personal/team/invite/internal. `[LG3]` `[QS]`
- **Team/API/model.** Private bank, assignment deadline + leaderboard + export, contest nội bộ, group, batch operation, file; free + premium team. Open Platform B2B: 10.000+ problem, 200.000+ submission/ngày, async `POST /judge/problem`, `GET /judge/result`, WebSocket, quota/credit, cache 1 giờ, subtasks; tích hợp Hydro/UOJ/SYZOJ. `[LG4][LG5][LG6]` `[QS]`

### DMOJ / VNOJ
- **API.** DMOJ API v2: Bearer token 48 ký tự, **90 request/phút**, envelope `api_version/method/fetched/data/error`, pagination. Endpoints contest/participation/problem/user/submission/organization/language/judge; submission detail trả `cases` hoặc `batches`. `[DMOJ1]` `[QS]`
- **VNOJ.** Nav problems/submissions/members/organizations/contests/wiki/tags/judge status/tickets/problem library/contest proposals/magazine; dựa trên DMOJ. Self-host AGPL, không paid tier công khai. `[DMOJ2]` `[QS/SL]`

---

## 3. Feature matrix

| Product | Discovery | Problem detail | Submission | Contest | Profile/retention | Public API | Model |
|---|---|---|---|---|---|---|---|
| **LeetCode** | Tag/difficulty/status/company | Hints/editorial/solutions/discussion | Run/Submit, custom input, per-case | Weekly/special, virtual, rating | Daily/streak/badge/graph | Không official | Premium + AI credits |
| **Codeforces** | Difficulty/tag OR/rating/solved | Statement/tags/tutorial/custom test | Submit/status/custom invocation | Div 1–4/Edu/ICPC/Team; virtual; hack; Q&A | Rating/contribution | Official signed, 1 req/2s | Free; Polygon/Gym/EDU |
| **AtCoder** | Rated range/category/search | Statement/constraints/editorial | Login required | ABC/ARC/AGC/AHC; virtual | Ranking | Không official | Free + dataset license |
| **HackerRank** | Status/skill/difficulty/subdomain | Challenge + “Solve Challenge” | Run/Submit; certification | Hackathon/company; registration | Certification/mock interview | Enterprise REST | B2B SaaS |
| **CodeChef** | Practice/compiler/courses | Statement/editor (SPA) | Verdict/status | Starters + 4 divisions | Rating/division | Không official | Free + Pro + courses |
| **CSES** | Category, no search/tag | Statement/constraints/stats | Login; submissions | Datatähti/HIIT/NOI | Progress only | Không | Free + book/course |
| **Kattis** | Language/difficulty/type/objective | Statement/metadata/downloads/license | Login; pass-fail/scoring | Create/virtual; team; role | Ranklist | Không official | Free + recruitment |
| **SPOJ** | 20k problem/tag | Statement/submit/forum | Verdict/status | User-organized | Solved/rank | Không official | Free + Sphere Engine |
| **Baekjoon** | N/A (offline); solved.ac tag/tier | N/A | N/A | N/A | Tier/Class/streak | Không official | Free; ownership transition |
| **Luogu** | Source/difficulty/algorithm/status | Statement/SPJ/interactive/solution vote | Standard IO/O2/RemoteJudge | OI/LeDuo/ICPC/IOI | Dynamic level/team progress | Open Platform B2B | Free + premium team + B2B |
| **VNOJ/DMOJ** | Problem + organization | Statement/API metadata | API cases/batches | Contest/virtual/org | Rating | Official token API | Self-host AGPL |

> “Không official” trong cột API = không tìm thấy docs public chính thức trong phạm vi khảo sát; không đồng nghĩa không tồn tại endpoint nội bộ. `[SL]`

---

## 4. Patterns

**4.1. Filter taxonomy là domain data.** Codeforces coi tag/difficulty là metadata problem; Kattis coi `problem type` và `objective` là thuộc tính; CodeChef coi division là thuộc tính contest + rating. JudgeLoom đã có model nhưng chưa expose filter/sort. `[CF2][KAT1][CC5]` `[QS]`

**4.2. Problem page phải trả lời “học thế nào”.** LeetCode đặt hints/editorial/solutions/discussion cùng workspace; AtCoder đặt editorial cạnh task; Luogu cho vote solution và tải test sai. Đây là vòng lặp “sai → hiểu → sửa”. `[LEET2][AC3][LG2]` `[QS-GT/QS]`

**4.3. Run khác Submit.** Run dùng input tùy biến, không tính rating/contest, không lưu source vĩnh viễn, rate limit riêng. JudgeLoom chỉ có `Submission`, không có khái niệm run. `[LEET2][CF4][DMOJ1]` `[QS-GT/QS]`

**4.4. Contest cần rule metadata.** Codeforces virtual chỉ ICPC mode; CodeChef division song song; Luogu LeDuo có công thức riêng; Kattis objective pass-fail/scoring. JudgeLoom có registry nhưng chưa enforce `max_submissions`, freeze chỉ ẩn `format_data`, không có đường nộp contest. `[CF5][CC5][LG3][KAT1]` `[QS]`

**4.5. Retention tính từ submission.** Daily/streak/badge/tier/class đều suy ra từ submission + thời gian + problem metadata; cần bảng aggregate có kiểm soát. `[LEET8][BOJ3][BOJ6][HR4]` `[QS-GT/QS]`

**4.6. API maturity không tỉ lệ nổi tiếng.** Codeforces/DMOJ/Luogu/HackerRank có API; LeetCode/AtCoder/Baekjoon/CodeChef không. Cạnh tranh bằng contract + docs + token lifecycle, không scrape. `[CF1][DMOJ1][LG6][HR6][LEET6]` `[QS/QS-GT]`

**4.7. Monetization nghiêng B2B/education/data.** Luogu premium team/trường/Open Platform; HackerRank/Kattis recruitment; Sphere Engine execution; AtCoder dataset. `[LG4][LG5][HR2][KAT5][SPOJ4][AC7]` `[QS]`

**4.8. Trust trước scale.** Codeforces hack/system test/plagiarism `Skipped`; Luogu academic rules/RemoteJudge; HackerRank proctoring/identity. JudgeLoom có `ContestMoss` model nhưng chưa service/API; `Ticket` không thay clarification. `[CF6][CF11][LG2][HR2]` `[QS]`

---

## 5. Gap analysis against JudgeLoom

### 5.1 Hiện trạng

JudgeLoom là Django 5.2 + Ninja + Channels + Celery/Redis/PostgreSQL, AGPL-3.0-or-later; apps `accounts, problems, submissions, contests, judge, ratings, tags, content, tickets, organizations` ([`pyproject.toml`](../../pyproject.toml), [`config/urls.py`](../../config/urls.py)). README quảng cáo “rating graph”, “isolated Judge Worker sandboxing”, “real-time judging”, nhưng `BridgeManager` giữ handler **in-memory**, `JudgeHandler.transport` mặc định `None`, payload dispatch chỉ có source + limits, không test data/checker/package hash ([`apps/judge/bridge/bridge_manager.py`](../../apps/judge/bridge/bridge_manager.py), [`apps/judge/bridge/judge_handler.py`](../../apps/judge/bridge/judge_handler.py)). JudgeLoom **chưa có judge worker hoạt động**; đây là gap P0 lớn nhất.

### 5.2 Bảng gap

| Capability | Hiện tại | Thiếu | Ưu tiên |
|---|---|---|---|
| **Discovery** | `GET /problems/` chỉ filter `difficulty`, `min_points`, `max_points` ([`apps/problems/api/router.py`](../../apps/problems/api/router.py)) | Search/tag/source/author/solved-state/sort | P0 |
| **Problem detail** | `description`, `Solution` tự do; không hint/editorial/discussion | Editorial/hint/official solution/vote/thread | P1 |
| **Problem stats** | `get_problem_statistics()` đếm `Solution`, không đếm `Submission` ([`apps/problems/services/problem_service.py`](../../apps/problems/services/problem_service.py)) | AC rate/attempted/per-tag stats từ submission | P0 |
| **Submission create** | Chỉ `problem_code`, `language_id`, `source_code` ([`apps/submissions/api/schemas.py`](../../apps/submissions/api/schemas.py)) | `contest_key`, `mode`, `client_request_id` | P0 |
| **Submission visibility** | Non-staff chỉ thấy của mình; fallback `problem.author_id` không tồn tại ([`apps/submissions/api/router.py`](../../apps/submissions/api/router.py), [`apps/submissions/services/submission_service.py`](../../apps/submissions/services/submission_service.py)) | Public status, source privacy, share token | P0 |
| **Run/custom** | Không có endpoint/model | `POST /run`, custom input, ephemeral result | P1 |
| **Contest submission** | Không có `POST /contests/{key}/submissions`; create không nhận participation | Gắn contest, enforce `max_submissions` | P0 |
| **Scoring/freeze** | `_is_accepted()` đọc `verdict`/`status` thay vì `result`; `_submission_queryset()` tìm `participation` thay vì `contest_participation`; freeze chỉ ẩn `format_data` ([`apps/contests/formats/base.py`](../../apps/contests/formats/base.py), [`apps/contests/services/ranking_service.py`](../../apps/contests/services/ranking_service.py)) | Freeze theo `created_at`, jury view, snapshot/cache | P0 |
| **Contest modes** | `default/icpc/ioi/atcoder/ecoo`; join/virtual | Division/team/registration/clarification | P1 |
| **Rating** | `Rating` có `performance/volatility`; `get_rating_history` đọc `contests.RatingChange` không tồn tại ([`apps/accounts/services/profile_service.py`](../../apps/accounts/services/profile_service.py)); default 0 | Elo-MMR, history đúng, performance/division | P0/P1 |
| **Profile** | `problem_count`, `points`, `rating` denormalized | Daily/streak/badge/activity/solved-by-tag | P1 |
| **Judge/package** | In-memory bridge, no worker, no package hash/checker | Protocol, outbound worker, manifest, checker | P0 |
| **Anti-cheat/support** | `ContestMoss` model only; `Ticket` không phải clarification | MOSS run/pair review; clarification thread | P1 |
| **Organization** | `admins` M2M; member request | Role/assignment/private bank/report | P1 |
| **API/auth** | JWT HS256; single `User.api_token`; không scope/expiry/revoke; rate limit submission đọc key `SUBMISSION_RATE_LIMIT_PER_MINUTE` trong khi settings có `SUBMISSION_RATE_LIMIT` | Scoped token, refresh, revoke, quota, sửa key | P0 |
| **Ops** | Initial migrations + CI `makemigrations --check` đã có; chưa có metrics/lease timeout/idempotency test | Observability, lease timeout, retry/idempotency | P0 |

**Giữ lại:** service layer, format registry (`register_format`), event bus, WebSocket scaffolding, `SubmissionTestCase`, `ContestParticipation`. Không cần viết lại domain model; cần đóng vòng và thêm contract.

---

## 6. Prioritized backend/API backlog

### P0 — core

| # | Item | API/data-model implication | Pattern |
|---|---|---|---|
| P0.1 | **Judge protocol + worker** | `Judge.protocol_version/last_seen/catalog_hash/capacity`; `Submission.judge_attempt/lease_id/dispatched_at`; `judge.handshake/claim/event`; worker outbound; ack timeout 15–20s; re-queue khi offline | DMOJ/DOMjudge |
| P0.2 | **Problem package/checker** | `ProblemPackage(version, sha256, manifest, source_zip)`, `TestCase(input_sha256, output_sha256, group, points, is_pretest)`, `Checker(type, source_sha256, language)`; `GET /judge/problems/{code}/package?hash=`; cache theo hash | Kattis/DMOJ |
| P0.3 | **Submission contract** | `Submission.mode` (enum, ban đầu `submit`), `contest_participation`, `client_request_id` unique `(user,id)`, `language_key`, `is_public`, `share_token`; `POST /submissions` nhận `contest_key`; `POST /submissions/{id}/rejudge`; `GET /submissions?problem=&contest=&result=&user=` | Codeforces/DMOJ |
| P0.4 | **Contest scoring/freeze** | `POST /contests/{key}/submissions`; enforce `max_submissions`; `ScoreboardSnapshot(contest, freeze_at, payload, version)`; filter `created_at <= freeze_time`; ICPC bỏ CE/IE; sửa `_is_accepted` dùng `result`; jury unfiltered | DOMjudge/DMOJ |
| P0.5 | **Public status/privacy** | `Submission.visibility(private/public/contest)`; `GET /problems/{code}/submissions`; source chỉ owner/staff/author; `POST /submissions/{id}/share` + revoke | Codeforces/DMOJ |
| P0.6 | **Discovery** | `GET /problems?search=&tag=&difficulty=&source=&solved=&ordering=`; Postgres FTS/trigram; `ProblemStat` từ `Submission`; `TagGroup` API | Codeforces/Kattis |
| P0.7 | **Token/API auth** | `ApiToken(user, name, prefix, token_hash, scopes, expires_at, last_used_at, revoked_at)`; `POST/DELETE /auth/tokens`; JWT access/refresh + scopes; rate limit theo token; không session cho judge | DMOJ/HackerRank |
| P0.8 | **Ops** | Idempotency `(user, client_request_id)`; lease timeout/retry; metrics queue/judge/lease; structured log `submission_id/judge_id/attempt`; giữ CI `makemigrations --check` | JudgeLoom |

### P1 — differentiator

| # | Item | API/data-model implication | Pattern |
|---|---|---|---|
| P1.1 | **Run/custom** | `POST /run` (`problem_code`, `language`, `source`, `stdin`, `expected_output?`, limits); `Run` ephemeral TTL 10–30 phút; rate limit riêng; không rating/contest | LeetCode/Codeforces |
| P1.2 | **Editorial/hints** | `Editorial(problem, author, content, is_official, published_at)`, `Hint(problem, order, content, unlock_policy)`; `Solution` thêm `is_official/votes/language`; unlock sau AC/contest end | LeetCode/AtCoder/Luogu |
| P1.3 | **Problem discussion** | `ProblemThread` + `Comment` generic target; moderation/vote/notification | LeetCode/Luogu |
| P1.4 | **Contest extras** | `ContestRegistration`, `ContestDivision`, `ContestTeam`, `Clarification`, `Announcement`; virtual; freeze/unfreeze; scoreboard cache; rating scope | Codeforces/CodeChef/Kattis |
| P1.5 | **Rating** | Elo-MMR (mean/volatility/performance); `Rating` thêm `division/rated_at`; `GET /users/{username}/ratings`; recalc idempotent; fix `RatingChange` | DMOJ |
| P1.6 | **Retention** | `DailyChallenge(date, problem)`, `UserStreak(current, max, last_solved_on)`, `Badge`, `UserBadge`, `ActivityDay`; `GET /users/{username}/activity?year=`; solved-by-tag | LeetCode/solved.ac |
| P1.7 | **Plagiarism/MOSS** | `PlagiarismRun(contest, problem, language, status, provider, result_url)`, `PlagiarismPair(run, a, b, similarity, verdict, reviewed_by)`; async; không public source | Codeforces/MOSS |
| P1.8 | **Notifications** | `Notification(user, type, payload, read_at)`, `NotificationPreference`; email/webhook; publish sau `transaction.on_commit` | Codeforces/Luogu |
| P1.9 | **Org/class** | `OrganizationMember(role)`, `Assignment`, `AssignmentProgress`, `OrganizationContest`; private bank; CSV export | Luogu/HackerRank |
| P1.10 | **Search/docs** | OpenAPI 3.1, `/api/v1`, webhook, idempotency key, cursor pagination, error schema | DMOJ/Luogu |

### P2 — later

| # | Item | API/data-model implication | Pattern |
|---|---|---|---|
| P2.1 | **Remote judge adapter** | `RemoteJudgeProvider`; chỉ API public được phép (Codeforces read-only, Luogu Open Platform B2B); `RemoteSubmission` + provenance; không scrape/proxy trái ToS | Codeforces/Luogu |
| P2.2 | **AI hints/analysis** | `AICreditLedger`, quota subscription; `HintRequest` async; không gửi source khi chưa consent | LeetCode |
| P2.3 | **Dataset licensing/export** | `DatasetExport`, `ConsentRecord`, provenance in/post-contest; chỉ export khi có quyền | AtCoder Datasets |
| P2.4 | **Heuristic/interactive/output-only** | `ProblemType` mở rộng; `ScoreType(sum/group min/max/threshold)`; `Interactor`; output-only prefix | CMS/AHC |
| P2.5 | **Certification/assessment** | `Assessment`, `AssessmentAttempt`, `Certificate`; tách contest rating; proctoring policy | HackerRank |
| P2.6 | **Public product API** | OAuth app/scopes/quota/webhook; read API problem/contest/rating; không lộ source mặc định | DMOJ/Luogu |

---

## 7. What NOT to copy

- **Nội dung problem/test data/editorial/solution/company tags** của LeetCode, AtCoder Datasets, Luogu premium bank, Kattis, HackerRank — tài sản có bản quyền/license riêng.
- **UI, wording, branding, icon, màu sắc, layout** đặc trưng. Học information architecture, không copy trade dress.
- **Paid-only features** (LeetCode company filters/AI credits, HackerRank assessment content, Luogu premium team, AtCoder datasets) khi chưa license.
- **Dữ liệu bị ToS hạn chế/scrape**: LeetCode GraphQL nội bộ, Baekjoon, SPOJ, Luogu main, CodeChef endpoint nội bộ.
- **Thuật toán không công bố**: rating LeetCode, MOSS internals, proctoring/identity model. Chỉ dùng spec công khai (Elo-MMR, Testlib, Kattis package) và tự implement.
- **Source code user mặc định public**. Phải có privacy/share token; không copy mô hình “mọi submission public” sang lớp học/doanh nghiệp.
- **Surveillance** (webcam/face/keystroke) khi chưa có policy/consent/legal review.
- **Remote judge proxy** gửi bài sang OJ khác không phép — rủi ro ToS/pháp lý, không phải feature.

---

## 8. What to build next

**Backend (thứ tự):**
1. Đóng vòng judge: protocol v1 + worker outbound + package hash/checker (P0.1–P0.2).
2. Chuẩn hóa submission: `mode`, `contest_key`, `language_key`, `client_request_id`, visibility/share (P0.3–P0.5).
3. Contest đúng luật: `POST /contests/{key}/submissions`, freeze theo `created_at`, snapshot, ICPC bỏ CE/IE (P0.4).
4. Discovery + stats: FTS/tag/source/solved; `ProblemStat` từ submission (P0.6).
5. Token/API: scoped token, revoke, rate limit, OpenAPI versioned (P0.7).
6. Editorial/discussion + retention + rating graph đúng (P1.2–P1.6).
7. Org/class + notification + plagiarism/clarification (P1.4, P1.7–P1.9).

**Frontend (sau khi API contract chốt):**
1. Problem workspace: editor, language, Run/Submit, custom input, per-case, source privacy.
2. Problem list: facet tag/difficulty/source/status, search, solved-state, acceptance.
3. Problem detail: statement + hints/editorial/solutions/discussion theo tab.
4. Contest: register/join/virtual, division/team, scoreboard freeze/unfreeze, clarification.
5. Profile: rating graph, solved-by-tag/difficulty, streak/daily/badge, activity.
6. Org dashboard: assignment/progress/private bank/export; admin judge fleet.

**Nguyên tắc:** không build UI trước khi API trả đúng semantics `run` vs `submit`, `freeze`, `public/private source`, `contest participation`; nếu không sẽ hard-code lại các giả định sai.

---

## 9. Sources (tất cả truy cập 2026-10-30)

**LeetCode** — trang chính 403; dùng public page/snippet/Discuss public (`[QS-GT]`).
`[LEET1]` https://leetcode.com/problemset/ · `[LEET2]` https://leetcode.com/problems/two-sum/ · `[LEET3]` https://leetcode.com/subscribe/ · `[LEET4]` https://leetcode.com/discuss/ · `[LEET5]` https://leetcode.com/company/google/ · `[LEET6]` https://leetcode.com/discuss/general-discussion/1297705/is-there-public-api-endpoints-available-for-leetcode/ · `[LEET7]` https://leetcode.com/contest/ · `[LEET8]` https://leetcode.com/discuss/post/5736503/feature-release-notes-by-leetcode-9awg/ · `[LEET9]` https://leetcode.com/discuss/post/6104178/All-LeetCode-Badges/

**Codeforces**
`[CF1]` https://codeforces.com/apiHelp · `[CF2]` https://codeforces.com/problemset · `[CF3]` https://codeforces.com/contests · `[CF4]` https://codeforces.com/problemset/problem/4/A · `[CF5]` https://codeforces.com/contest/2261 · `[CF6]` https://codeforces.com/contest/2261/hacks · `[CF7]` https://codeforces.com/api/user.status?handle=tourist&from=1&count=2 · `[CF8]` https://codeforces.com/gyms · `[CF9]` https://codeforces.com/edu/courses · `[CF10]` https://polygon.codeforces.com/ · `[CF11]` https://codeforces.com/blog/entry/155347 · `[CF12]` https://codeforces.com/groups

**AtCoder**
`[AC1]` https://atcoder.jp/contests/archive · `[AC2]` https://atcoder.jp/contests/abc400/tasks/abc400_a · `[AC3]` https://atcoder.jp/contests/abc400/editorial · `[AC4]` https://atcoder.jp/contests/abc400/clarifications · `[AC5]` https://atcoder.jp/contests/abc400/submissions · `[AC6]` https://atcoder.jp/contests/abc400/standings · `[AC7]` https://datasets.atcoder.jp/ · `[AC8]` https://atcoder.jp/company · `[AC9]` https://github.com/qatadaazzeh/atcoder-api

**HackerRank**
`[HR1]` https://www.hackerrank.com/domains/algorithms · `[HR2]` https://www.hackerrank.com/products/screen/ · `[HR3]` https://www.hackerrank.com/contests · `[HR4]` https://www.hackerrank.com/skills-verification · `[HR5]` https://www.hackerrank.com/leaderboard · `[HR6]` https://www.hackerrank.com/work/apidocs · `[HR7]` https://support.hackerrank.com/articles/2067417637-api-overview · `[HR8]` https://www.hackerrank.com/products/interview/

**CodeChef**
`[CC1]` https://www.codechef.com/practice · `[CC2]` https://www.codechef.com/contests · `[CC3]` https://www.codechef.com/api/list/contests/all · `[CC4]` https://www.codechef.com/ratings · `[CC5]` https://www.codechef.com/ratings/divisions

**CSES**
`[CSES1]` https://cses.fi/problemset/ · `[CSES2]` https://cses.fi/problemset/task/1068 · `[CSES3]` https://cses.fi/contests/ · `[CSES4]` https://cses.fi/courses/ · `[CSES5]` https://cses.fi/book/

**Kattis**
`[KAT1]` https://open.kattis.com/problems · `[KAT2]` https://open.kattis.com/problems/hello · `[KAT3]` https://open.kattis.com/contests · `[KAT4]` https://open.kattis.com/ranklist · `[KAT5]` https://www.kattis.com/ · `[KAT6]` https://open.kattis.com/jobs · `[KAT7]` https://www.kattis.com/problem-package-format/spec/2025-09.html

**SPOJ / Sphere Engine** — SPOJ 403; dùng public indexed snippet + docs.
`[SPOJ1]` https://www.spoj.com/ · `[SPOJ2]` https://www.spoj.com/tutorials/ · `[SPOJ3]` https://docs.sphere-engine.com/ · `[SPOJ4]` https://sphere-engine.com/pricing

**Baekjoon / solved.ac**
`[BOJ1]` https://www.acmicpc.net/ (trang thông báo bảo trì) · `[BOJ2]` https://help.solved.ac/en/stats/ac-rating · `[BOJ3]` https://help.solved.ac/en/stats/class · `[BOJ4]` https://help.solved.ac/en/stats/tag-rating · `[BOJ5]` https://help.solved.ac/en/stats/over-rating · `[BOJ6]` https://solved.ac/en/ranking/streak

**Luogu** — main 403; help center/Open Platform public.
`[LG1]` https://www.luogu.com.cn/problem/list · `[LG2]` https://help.luogu.com.cn/manual/luogu/problem · `[LG3]` https://help.luogu.com.cn/manual/luogu/contest · `[LG4]` https://help.luogu.com.cn/manual/luogu/team · `[LG5]` https://docs.lgapi.cn/open/ · `[LG6]` https://docs.lgapi.cn/open/openapi · `[LG7]` https://help.luogu.com.cn/

**DMOJ / VNOJ**
`[DMOJ1]` https://raw.githubusercontent.com/DMOJ/docs/master/docs/site/api.md · `[DMOJ2]` https://oj.vnoi.info/

**Cross-cutting**
`[X1]` https://www.kattis.com/problem-package-format/spec/2025-09.html · `[X2]` https://polygon.codeforces.com/ · `[X3]` https://codeforces.com/blog/entry/155347 · `[X4]` https://leetcode.com/discuss/general-discussion/1297705/is-there-public-api-endpoints-available-for-leetcode/

> `[LEET*]`, `[SPOJ1-2]`, `[LG1]` là trang public nhưng chặn automated fetch ngày khảo sát; dữ kiện tương ứng đánh dấu `[QS-GT]`, chỉ dùng phần công khai/snippet, không suy đoán sau login/paywall. `[BOJ1]` là thông báo bảo trì, không dùng mô tả UX Baekjoon.
