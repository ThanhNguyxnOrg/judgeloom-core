# Open-source online judge landscape cho JudgeLoom

**Ngày:** 2026-10-30 · **Phạm vi:** nghiên cứu upstream để tìm thứ JudgeLoom có thể kế thừa, học pattern hoặc tích hợp external service. **Không** sửa code/config/test/dependency. **Phương pháp:** GitHub API để lấy license/stars/pushed_at/release; đọc raw `LICENSE`, `README`, docs/source trên default branch; không clone repo lớn. Stars là snapshot, không phải tăng trưởng. DMOJ docs bị Cloudflare chặn nên claim DMOJ lấy từ repo `DMOJ/docs` và code chính.

> **Quy ước bằng chứng.** `[xác minh]` = đọc trực tiếp LICENSE/docs/code primary source có link. `[đề xuất]` = suy luận/khuyến nghị cho JudgeLoom, không phải tuyên bố upstream. License là **tóm tắt kỹ thuật, không phải tư vấn pháp lý**; trước khi copy phải rà soát LICENSE và nghĩa vụ phân phối.

JudgeLoom hiện là Django 6 / Django Ninja / Channels / Celery / PostgreSQL / Redis, license `AGPL-3.0-or-later` ([pyproject.toml](../../pyproject.toml)). Báo cáo tập trung vào các gap đã biết: bridge/worker/sandbox, test data/checker sync, contest scoring/freeze, rating, scheduling, auth, event bus và migration.

---

## 1. Executive summary — 5 khuyến nghị

1. **Copy semantics của DMOJ judge protocol, không copy transport cũ.** DMOJ dùng TCP + zlib + JSON packet, handshake `name`/`key`, judge gửi problem catalog kèm mtime, site gửi `submission-request`, judge trả `ack`, `grading-begin`, `test-case-status` (batch 0,25 s), `grading-end`, `ping-response` ([packet.py](https://raw.githubusercontent.com/DMOJ/judge-server/master/dmoj/packet.py), [judge_handler.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/bridge/judge_handler.py)). JudgeLoom nên giữ state machine/payload semantics nhưng chạy trên WebSocket/Channels có version, và cho worker **kết nối ra** bridge.
2. **Không tự viết sandbox.** Dùng `isolate` cho quick win (CMS và Judge0 đều dùng: [CMS Sandbox.py](https://raw.githubusercontent.com/cms-dev/cms/main/cms/grading/Sandbox.py), [Judge0 isolate_job.rb](https://raw.githubusercontent.com/judge0/judge0/master/app/jobs/isolate_job.rb)); dùng `go-judge` khi cần HTTP/WS API, file cache và scale ngang (Hydro: [client.ts](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrojudge/src/sandbox/client.ts)).
3. **Chuẩn hóa test data/checker theo Kattis Problem Package + Testlib.** Package format cho `problem.yaml`, `data/`, `output_validators/`, `submissions/` ([spec](https://www.kattis.com/problem-package-format/)); Testlib cho exit code `0/1/2/3/5` và `quitp(points)` ([testlib.h](https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/testlib.h)). Lưu package + manifest hash + checksum từng case; worker tải theo hash và cache.
4. **Sửa contest trước khi mở rộng.** `_is_accepted()` đọc `verdict`/`status` thay vì `result`; `_submission_queryset()` tìm field `participation` thay vì `contest_participation`; freeze chỉ ẩn `format_data`. Học DOMjudge freeze theo **thời điểm submission** ([config-basic.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/config-basic.rst)), DMOJ ICPC penalty ([icpc.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/contest_format/icpc.py)), CMS subtask score types ([Score types.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Score%20types.rst)).
5. **Đóng vòng vận hành:** rating mặc định 1500 + `rate_all`/`rate_exclude`/floor/ceiling như DMOJ ([ratings.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/ratings.py)); schedule contest start/end/recalc; publish sau `transaction.on_commit`; commit migration và CI `makemigrations --check --dry-run`.

---

## 2. Landscape comparison

| Project | Role | Stack | License (verified) | Maturity (2026-10-30) | Best thing to learn | Inheritance verdict |
|---|---|---|---|---|---|---|
| **DMOJ online-judge** | Contest platform + judge bridge | Django, Python, PostgreSQL/MySQL, Redis | AGPL-3.0 ([LICENSE](https://raw.githubusercontent.com/DMOJ/online-judge/master/LICENSE)) | 1.197★; push 2026-10-25; v4.0.0 (2023) | Protocol, format registry, Elo-MMR | **Copy/fork** (AGPL) |
| **DMOJ judge-server** | Remote judge worker | Python, cptbox, C++ helper | AGPL-3.0 ([LICENSE](https://raw.githubusercontent.com/DMOJ/judge-server/master/LICENSE)) | 980★; push 2026-10-12; v5.0.0 (2026) | Outbound worker, batching | **Reimplement protocol** |
| **VNOJ** | DMOJ-based VN deployment | DMOJ + Docker | AGPL-3.0 ([repo](https://github.com/VNOI-Admin/OJ)) | 230★; push 2026-10-30 | VN-scale deployment | **Copy/deploy** (AGPL) |
| **CMS** | IOI-style contest system | Python/Tornado/SQLAlchemy/PostgreSQL, isolate | AGPL-3.0-or-later ([setup.py](https://raw.githubusercontent.com/cms-dev/cms/main/setup.py)) | 1.043★; push 2026-10-29; v1.5.1 (2025) | Task/score types, datasets, tokens | **Copy pattern/code** |
| **DOMjudge** | ICPC contest control | PHP/Symfony/Doctrine, MySQL, C++ runguard | GPL-2.0-or-later ([README](https://raw.githubusercontent.com/DOMjudge/domjudge/main/README.md)) | 922★; push 2026-10-30; 10.0.0DEV | Freeze, scorecache, pull API | **Study/selective copy** |
| **HydroOJ** | Platform + plugin ecosystem | Node/TS, MongoDB, Koa/cordis, go-judge | AGPL-3.0-or-later + §7 ([README](https://raw.githubusercontent.com/hydro-dev/Hydro/master/README-EN.md)) | 7.177★; push 2026-10-28; 5.0.7 | Plugins, test-data cache, `lockAt` | **Study only** |
| **Judge0** | Execution microservice | Rails, PostgreSQL, Redis/Resque, isolate | GPL-3.0 ([LICENSE](https://raw.githubusercontent.com/judge0/judge0/master/LICENSE)) | 4.499★; push 2026-10-26; v1.13.1 (2024) | HTTP execution API | **Integrate service** |
| **UOJ** | Full OJ (legacy) | PHP, MySQL, C++ judger | MIT ([LICENSE](https://raw.githubusercontent.com/UniversalOJ/UOJ-System/master/LICENSE)) | 513★; push 2026-03-19 | DB queue, Extra Tests/Hack | **Study only** |
| **QDUOJ** | Full OJ (Django/Vue) | Django/DRF, Vue, dramatiq, HTTP judge | MIT backend ([LICENSE](https://raw.githubusercontent.com/QingdaoU/OnlineJudge/master/LICENSE)); Judger SATA | 6.557★; push 2024-10-23; v1.6.1 (2024) | Django dispatcher, server load | **Study; avoid Judger** |
| **HustOJ** | Full OJ (legacy) | PHP, MySQL, C++ judge_client | GPL-2.0 (mixed headers) ([LICENSE](https://raw.githubusercontent.com/zhblue/hustoj/master/LICENSE)) | 3.819★; push 2026-10-30; 26.08.19 | FPS import, lightweight deploy | **Avoid copying** |
| **Themis** | Windows grading (VN) | Closed binary | **No license/repo** ([page](https://dsapblog.wordpress.com/2013/12/24/themis/)) | No OSS activity | Folder workflow | **Workflow only** |
| **isolate** | Sandbox CLI | C, namespaces/cgroups/seccomp | GPL-2.0-or-later ([LICENSE](https://raw.githubusercontent.com/ioi/isolate/master/LICENSE)) | 1.500★; push 2026-10-26; v2.7 | Minimal sandbox + metadata | **Integrate binary** |
| **nsjail** | Sandbox CLI | C++, namespaces, Kafel seccomp | Apache-2.0 ([LICENSE](https://raw.githubusercontent.com/google/nsjail/master/LICENSE)) | 4.179★; push 2026-10-28; 3.6 | Rich policy | **Integrate if needed** |
| **go-judge** | Sandbox service | Go, REST/WS/gRPC | MIT ([LICENSE](https://raw.githubusercontent.com/criyle/go-judge/master/LICENSE)) | 633★; push 2026-10-13; v1.13.3 | HTTP/WS, file cache | **Integrate service** |
| **Testlib** | Checker library | C++ header | MIT ([LICENSE](https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/LICENSE)) | 1.755★; push 2026-10-28; 0.9.41 | Checker exit codes | **Vendor header** |

---

## 3. Per-project deep dives

### 3.1 DMOJ + VNOJ — closest Django/Python analogue

**Vai trò và license.** DMOJ gồm site Django (`online-judge`) và judge worker Python (`judge-server`), cả hai AGPL-3.0 ([site LICENSE](https://raw.githubusercontent.com/DMOJ/online-judge/master/LICENSE), [judge LICENSE](https://raw.githubusercontent.com/DMOJ/judge-server/master/LICENSE)). Đây là cặp gần JudgeLoom nhất về ngôn ngữ và mô hình triển khai. VNOJ là deployment dựa trên DMOJ: site tự mô tả "dựa trên nền tảng DMOJ" ([oj.vnoi.info](https://oj.vnoi.info/)); repo `VNOI-Admin/OJ` là fork AGPL-3.0, vẫn push 2026-10-30 ([repo](https://github.com/VNOI-Admin/OJ)). `vnoj-docker` chỉ là Docker setup, **không có license** ([repo](https://github.com/VNOI-Admin/vnoj-docker)) nên không copy file.

**Kiến trúc và protocol.** Site không gọi HTTP tới judge; judge mở TCP tới site và hai bên nói packet JSON nén zlib, prefix 4 byte big-endian, tối đa 8 MiB ([base_handler.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/bridge/base_handler.py)). Handshake gửi `id`, `key`, `problems` (kèm mtime) và `executors`; site trả `handshake-success` ([judge_handler.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/bridge/judge_handler.py)). Judge gửi `ping-response` kèm `time`/sysinfo; site cập nhật `ping`/`load`. Khi chấm, site gửi `submission-request` với source, limits, `short-circuit`, `meta`; judge trả `submission-acknowledged`, site có timer 20 s và đóng connection nếu không ack ([judge_handler.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/bridge/judge_handler.py)). Judge trả `grading-begin`, `test-case-status`, `grading-end`, `compile-error`, `internal-error`, `submission-terminated`; test case gom trong queue và flush mỗi 0,25 s ([packet.py](https://raw.githubusercontent.com/DMOJ/judge-server/master/dmoj/packet.py)). Đây là **protocol spec trên thực tế**; DMOJ không có tài liệu protocol độc lập.

**Sandbox và contest format.** Judge-server dùng `cptbox` — ptrace + seccomp + filesystem policy, không phải `isolate` ([cptbox/__init__.py](https://raw.githubusercontent.com/DMOJ/judge-server/master/dmoj/cptbox/__init__.py), [graders/standard.py](https://raw.githubusercontent.com/DMOJ/judge-server/master/dmoj/graders/standard.py)). Contest format dùng registry `register_contest_format(name)` và interface `update_participation`/`display_user_problem`/`get_label_for_problem` ([base.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/contest_format/base.py), [registry.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/contest_format/registry.py)). ICPC tính penalty = AC time + 20 phút × số lần sai, bỏ `IE`/`CE`, tiebreak bằng AC cuối ([icpc.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/contest_format/icpc.py)).

**Rating/API.** DMOJ dùng **Elo-MMR**: `MEAN_INIT=1500`, `RATING_INIT=1200`, variance tăng theo số contest, tie tính nửa trận, có performance ceiling ([ratings.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/ratings.py)). `rate_contest()` loại `rate_exclude`, chỉ lấy `virtual=0`, nếu `rate_all=False` chỉ lấy người có submission, lọc floor/ceiling ([ratings.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/ratings.py)). API v2 dùng token `Authorization: Bearer`, rate limit 90 req/phút ([API docs](https://docs.dmoj.ca/#/site/api), [raw docs](https://raw.githubusercontent.com/DMOJ/docs/master/docs/site/api.md)); web dùng session/OAuth, judge bridge dùng shared secret HMAC riêng.

**Takeaway cho JudgeLoom.** Copy state machine/payload semantics, ICPC formula và Elo-MMR; giữ judge auth là shared secret riêng. Có thể tái dùng DMOJ judge-server như external worker nếu viết adapter packet, nhưng sẽ ràng buộc AGPL và protocol cũ.

### 3.2 CMS — chuẩn mực cho IOI-style contest

**Vai trò và license.** CMS là hệ thống quản lý contest kiểu IOI, không phải OJ self-service; docs nói nó chỉ cung cấp công cụ hạn chế để phát triển test data ([Introduction.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Introduction.rst)). License **AGPL-3.0-or-later**, xác minh từ header `setup.py`: "either version 3 of the License, or (at your option) any later version" ([setup.py](https://raw.githubusercontent.com/cms-dev/cms/main/setup.py)).

**Stack/kiến trúc.** Python 3.11+, Tornado 4.5.3, SQLAlchemy 1.3, psycopg2, PostgreSQL bắt buộc vì dùng Large Object ([pyproject.toml](https://raw.githubusercontent.com/cms-dev/cms/main/pyproject.toml), [Introduction.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Introduction.rst)). Các service tách rời (Evaluation, Worker, Scoring, Proxy, Contest/Admin/Ranking Web) và giao tiếp bằng TCP + JSON newline-delimited với `__method`/`__data`/`__id` ([Introduction.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Introduction.rst), [Internals.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Internals.rst)). **Không có auth giữa các service**; docs yêu cầu mạng riêng/firewall ([Introduction.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Introduction.rst)) — bài học ngược với JudgeLoom: không được tin bridge nội bộ mù quáng.

**Sandbox/scoring.** Worker gọi `isolate` qua `Sandbox.py` với `--box-id`, `--cg`, `--init` ([Sandbox.py](https://raw.githubusercontent.com/cms-dev/cms/main/cms/grading/Sandbox.py)); installation yêu cầu isolate >= 2.0 và cgroup v2 ([Installation.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Installation.rst)). `Task` chứa statement/config; `Dataset` chứa compile/evaluate/score, có nhiều version và chỉ một active ([Data model.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Data%20model.rst)). Task types: Batch, OutputOnly, Communication, Interactive, TwoSteps; score types: Sum, GroupMin, GroupMul, GroupThreshold ([Task types.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Task%20types.rst), [Score types.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Score%20types.rst)). Score mode theo IOI 2010-2012, 2013-2016, 2017+ (sum of best per subtask) ([Configuring a contest.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Configuring%20a%20contest.rst)).

**Freeze/ranking/API.** CMS không dùng time-based freeze; nó dùng **tokens** để mở khóa kết quả private, với contest-token/task-token và `token_mode`, `token_gen_*` ([Configuring a contest.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Configuring%20a%20contest.rst)). RankingWebServer tách hoàn toàn khỏi DB, nhận dữ liệu qua ProxyService bằng HTTP Basic Auth, lưu JSON files ([RankingWebServer.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/RankingWebServer.rst)). Không có REST API cho contestant; CWS dùng username/password hoặc IP autologin ([Configuring a contest.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Configuring%20a%20contest.rst)).

**Takeaway cho JudgeLoom.** Copy **data model tinh thần**: dataset versioning, subtask score types, tokens; tách scoreboard read model. Không copy RPC không auth. CMS là nguồn tốt nhất cho IOI/partial scoring và rejudge theo dataset.

### 3.3 DOMjudge — chuẩn mực cho freeze và vận hành ICPC

**Vai trò/license/stack.** DOMjudge là hệ thống thi ICPC (domserver + judgehost), PHP 8.2/Symfony 7.4/Doctrine ORM 3, MySQL/MariaDB, judgehost C++ `runguard` ([composer.json](https://raw.githubusercontent.com/DOMjudge/domjudge/main/webapp/composer.json), [overview.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/overview.rst)). License **GPL-2.0-or-later**: README ghi "either version 2, or (at your option) any later version" ([README](https://raw.githubusercontent.com/DOMjudge/domjudge/main/README.md)).

**Kiến trúc judge.** Judgehost là daemon PHP **pull** công việc từ REST API: `POST judgehosts/fetch-work`, nhận `judgetask`, tải source/testcase qua `get_files`, chạy `runguard`, upload `update-judging`/`add-judging-run` ([judgedaemon.main.php](https://raw.githubusercontent.com/DOMjudge/domjudge/main/judge/judgedaemon.main.php)). Đây là mô hình ngược DMOJ: judgehost chủ động poll, dễ qua NAT/firewall hơn nhưng cần API server mạnh. `runguard` dùng process group, rlimit, chroot, cgroup; không phải isolate ([runguard.cc](https://raw.githubusercontent.com/DOMjudge/domjudge/main/judge/runguard.cc)).

**Scoring/freeze.** DOMjudge hỗ trợ pass-fail (ICPC) và score (IOI partial); pass-fail sort theo `sortorder`, tổng điểm, penalty, rồi AC cuối, còn score mode dùng testcase groups với accept score + aggregation sum/min/max/avg ([scoring.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/scoring.rst)). Freeze dùng milestone `freezetime`: scoreboard public/team **không update** sau freeze, nhưng submission trước freeze được judge sau freeze vẫn có thể cập nhật; jury luôn thấy scoreboard thật; unfreeze bằng `unfreezetime` hoặc nút "unfreeze now" ([config-basic.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/config-basic.rst)). Đây là semantics JudgeLoom phải copy: freeze là **filter theo `submitted_at`**, không phải ẩn `format_data`.

**Hiệu năng/rejudge/API.** DOMjudge dùng `scorecache` (từng team/problem) và `rankcache` (aggregate) để tránh tính lại toàn bộ scoreboard ([scoring.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/scoring.rst)). Rejudge giữ judging cũ nhưng mark invalid; submittime giữ nguyên ([judging.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/judging.rst)). Problem package theo ICPC/Kattis format, có `domjudge-problem.ini`, `special_run`, `special_compare`, `points` ([problem-format.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/problem-format.rst)). REST API v4 theo CCS Contest API; scoreboard lọc theo public/roles; judgehost dùng `restapi.secret` riêng ([ScoreboardController.php](https://raw.githubusercontent.com/DOMjudge/domjudge/main/webapp/src/Controller/API/ScoreboardController.php), [judgedaemon.main.php](https://raw.githubusercontent.com/DOMjudge/domjudge/main/judge/judgedaemon.main.php)).

**Takeaway cho JudgeLoom.** Copy freeze algorithm, scorecache/rankcache, rejudge-invalid semantics và judgehost pull model nếu muốn worker không cần inbound. Không copy PHP/runguard; dùng isolate/go-judge.

### 3.4 HydroOJ — plugin hoá và test-data cache

**Vai trò/license/stack.** Hydro là platform Node.js/TypeScript, MongoDB, Koa + cordis, chia package `hydrooj`, `hydrojudge`, `ui-default`, `vjudge` ([packages](https://github.com/hydro-dev/Hydro/tree/master/packages)). License phức tạp: LICENSE là AGPLv3, README nói "AGPLv3 with additional terms" — không được xoá copyright, phải đổi tên/version khi distribute modified version, không dùng trademark ([README-EN](https://raw.githubusercontent.com/hydro-dev/Hydro/master/README-EN.md)); `packages/hydrooj/package.json` ghi `AGPL-3.0-or-later OR Proprietary`, còn `hydrojudge` ghi `AGPL-3.0-or-later` ([hydrooj package](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrooj/package.json), [hydrojudge package](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrojudge/package.json)). Vì §7 additional terms, **không nên copy code**; chỉ học pattern.

**Kiến trúc/contest/rating.** `hydrojudge` gọi go-judge qua HTTP `POST /run`, `/file` cache, `/stream` WebSocket ([sandbox/client.ts](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrojudge/src/sandbox/client.ts)). README nhấn mạnh stateless, scale ngang và **quản lý test-data cache giữa các judge server, pull theo nhu cầu** ([README](https://raw.githubusercontent.com/hydro-dev/Hydro/master/README.md)). Contest rule là object có `scoreboard`, `scoreboardRow`, `scoreboardHeader`, `stat`, `applyProjection` ([model/contest.ts](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrooj/src/model/contest.ts)). Freeze dùng `lockAt` + `unlocked`: submission sau `lockAt` bị loại khỏi scoreboard public, jury có perm thấy scoreboard thật ([model/contest.ts](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrooj/src/model/contest.ts), [handler/contest.ts](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrooj/src/handler/contest.ts)). Rating dùng Codeforces-style ([lib/rating.ts](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrooj/src/lib/rating.ts)); `plugin-api.ts` export model/service/framework cho plugin ([plugin-api.ts](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrooj/src/plugin-api.ts)).

**Takeaway cho JudgeLoom.** Học plugin registry + test-data cache + `lockAt` freeze + CF rating; **không copy code** vì additional §7 terms. Nếu muốn dùng Hydro làm external service, dùng HTTP API thay vì nhúng.

### 3.5 Judge0 — execution service, không phải contest platform

**Vai trò/license/stack.** Judge0 là "online code execution system", không có contest/ranking; phù hợp làm execution backend. Rails 6.1, PostgreSQL, Redis/Resque, Puma; license **GPL-3.0** ([Gemfile](https://raw.githubusercontent.com/judge0/judge0/master/Gemfile), [docker-compose.yml](https://raw.githubusercontent.com/judge0/judge0/master/docker-compose.yml), [LICENSE](https://raw.githubusercontent.com/judge0/judge0/master/LICENSE)). `IsolateJob` chạy `isolate --cg -b <id> --init`, copy source/stdin, compile, run, đọc metadata, cleanup ([isolate_job.rb](https://raw.githubusercontent.com/judge0/judge0/master/app/jobs/isolate_job.rb)). API JSON HTTP: `POST /submissions?wait=true`, batch, languages; auth bằng header token cấu hình và IP allow/deny ([sessions_controller.rb](https://raw.githubusercontent.com/judge0/judge0/master/app/controllers/sessions_controller.rb), [routes.rb](https://raw.githubusercontent.com/judge0/judge0/master/config/routes.rb), [ce.judge0.com](https://ce.judge0.com)).

**Takeaway cho JudgeLoom.** Dùng Judge0 như **external execution service** cho MVP/đa ngôn ngữ; không dùng làm contest layer. Tích hợp HTTP đơn giản hơn copy `IsolateJob` (GPL-3.0).

### 3.6 UOJ — legacy nhưng đáng đọc về queue và hack

**Vai trò/license/stack.** UOJ Community Edition là full OJ PHP 7 + MySQL + C++ judger, license MIT ([README](https://raw.githubusercontent.com/UniversalOJ/UOJ-System/master/README.md), [LICENSE](https://raw.githubusercontent.com/UniversalOJ/UOJ-System/master/LICENSE)). Judger C++ `main_judger.cpp` nhận config qua DB/file và chạy sandbox tự viết dùng seccomp + ptrace + rlimit ([main_judger.cpp](https://raw.githubusercontent.com/UniversalOJ/UOJ-System/master/judger/uoj_judger/main_judger.cpp), [run_program_sandbox.h](https://raw.githubusercontent.com/UniversalOJ/UOJ-System/master/judger/uoj_judger/run/run_program_sandbox.h)). UOJ có Extra Tests/Hack ([README](https://raw.githubusercontent.com/UniversalOJ/UOJ-System/master/README.md)) — pattern tốt cho test bổ sung sau contest; kiến trúc DB queue + PHP + C++ sandbox là legacy.

**Takeaway cho JudgeLoom.** Học Extra Tests/Hack; không copy code hay sandbox. MIT cho phép copy nhưng lợi ích không tương xứng chi phí.

### 3.7 QDUOJ — Django tham khảo, Judger thì không

**Vai trò/license/stack.** QDUOJ là OJ Django + DRF + Vue, backend MIT ([LICENSE](https://raw.githubusercontent.com/QingdaoU/OnlineJudge/master/LICENSE)); judge dùng `dramatiq`, `JudgeDispatcher` gọi HTTP tới JudgeServer với `X-Judge-Server-Token`, chọn server theo `task_number`/`cpu_core` ([tasks.py](https://raw.githubusercontent.com/QingdaoU/OnlineJudge/master/judge/tasks.py), [dispatcher.py](https://raw.githubusercontent.com/QingdaoU/OnlineJudge/master/judge/dispatcher.py)). Judger sandbox riêng license **SATA**, không phải MIT ([Judger LICENSE](https://raw.githubusercontent.com/QingdaoU/Judger/master/LICENSE)). 6.557★ nhưng push cuối 2024-10-23, release v1.6.1 2024-04-07 — không nên chọn làm nền cho alpha 2026.

**Takeaway cho JudgeLoom.** Học Django dispatch + per-server load; **tránh** copy Judger SATA và stack Django 3.2 cũ. Đây là ví dụ "stars cao ≠ còn maintain".

### 3.8 HustOJ — legacy, license không phù hợp để copy

**Vai trò/license/stack.** HustOJ là OJ PHP + MySQL + C++ `judge_client`, phổ biến ở các trường; license GPL-2.0 theo README và `gpl-2.0.txt` ([README](https://raw.githubusercontent.com/zhblue/hustoj/master/README.md), [LICENSE](https://raw.githubusercontent.com/zhblue/hustoj/master/LICENSE)). Một số header như `okcalls64.h` ghi "either version 2 ... or any later version" ([okcalls64.h](https://raw.githubusercontent.com/zhblue/hustoj/master/trunk/core/judge_client/okcalls64.h)), tạo **inconsistency**: không thể coi cả repo là GPL-2.0-or-later chắc chắn. `judge_client` dùng ptrace + chroot + setrlimit + seccomp whitelist ([judge_client.cc](https://raw.githubusercontent.com/zhblue/hustoj/master/trunk/core/judge_client/judge_client.cc)).

**Takeaway cho JudgeLoom.** Chỉ học format import FPS và mô hình triển khai nhẹ; **không copy code** vì rủi ro GPL-2.0-only và chất lượng sandbox.

### 3.9 Themis — không phải open source đã xác minh

**Vai trò.** Themis là phần mềm chấm thi Windows phổ biến ở Việt Nam, do Lê Minh Hoàng và Đỗ Đức Đông phát triển; trang tác giả chỉ phân phối binary, không công bố source/license ([author page](https://dsapblog.wordpress.com/2013/12/24/themis/)). Các wrapper web như `themis-web-interface` (MIT) hay `themis-web` (không license) chỉ là UI, không phải core ([themis-web-interface](https://github.com/natsukagami/themis-web-interface), [themis-web](https://github.com/khoakomlem/themis-web)). Workflow folder-based (mỗi contest/thí sinh một thư mục, test `.INP/.OUT`, chấm offline) quen thuộc với giáo viên VN, nhưng **không thể kế thừa code**; chỉ có thể viết importer từ format thư mục (suy luận từ workflow, không có spec chính thức).

**Takeaway cho JudgeLoom.** Không dùng Themis làm nguồn code/license; chỉ dùng làm tham chiếu workflow và có thể viết importer nếu cộng đồng cần.

### 3.10 Sandbox stack: isolate, nsjail, go-judge

**isolate** là CLI sandbox nhỏ, dùng Linux namespaces + cgroups, chạy `--init`, `--run`, `--cleanup`, xuất metadata (time/memory/status) ([README](https://raw.githubusercontent.com/ioi/isolate/master/README.md)); license **GPL-2.0-or-later** ([LICENSE](https://raw.githubusercontent.com/ioi/isolate/master/LICENSE)). CMS và Judge0 đều dùng ([CMS Sandbox.py](https://raw.githubusercontent.com/cms-dev/cms/main/cms/grading/Sandbox.py), [Judge0 isolate_job.rb](https://raw.githubusercontent.com/judge0/judge0/master/app/jobs/isolate_job.rb)). Nhược điểm: mỗi lần chạy là process CLI, cần quản lý box id, ít streaming.

**nsjail** là process isolation của Google, namespaces + cgroups + seccomp-BPF qua Kafel, config protobuf, network isolation; license **Apache-2.0** ([README](https://raw.githubusercontent.com/google/nsjail/master/README.md), [LICENSE](https://raw.githubusercontent.com/google/nsjail/master/LICENSE), [nsjail.dev](https://nsjail.dev/)). Mạnh nhưng cấu hình phức tạp; phù hợp nếu cần policy tùy biến/network sandbox.

**go-judge** là sandbox service Go, REST `POST /run`, `/file` cache, `/ws`, `/stream`, gRPC tùy chọn; license **MIT** ([README](https://raw.githubusercontent.com/criyle/go-judge/master/README.md), [LICENSE](https://raw.githubusercontent.com/criyle/go-judge/master/LICENSE), [docs.goj.ac](https://docs.goj.ac/)). Hydro dùng đúng mô hình này ([client.ts](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrojudge/src/sandbox/client.ts)).

**Takeaway cho JudgeLoom.** Quick win: wrapper isolate + metadata parser. Next: go-judge sidecar để có HTTP/WS, file cache, streaming, scale ngang. Chỉ chọn nsjail nếu cần tự kiểm soát seccomp policy. **Không tự viết ptrace/chroot sandbox** như DMOJ/HustOJ/UOJ.

### 3.11 Testlib + Kattis package + CCS API

**Testlib** là C++ header MIT cho checker/validator/generator/interactor ([README](https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/README.md), [LICENSE](https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/LICENSE)). Checker protocol trả exit code: `_ok=0`, `_wa=1`, `_pe=2`, `_fail=3`, `_dirt=4`, `_points=5`, `_unexpected_eof=8`, `_partially=16` ([testlib.h](https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/testlib.h)); `quitp(points, message)` in điểm trong message và exit `_points` ([testlib.h](https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/testlib.h)). Đây là contract đơn giản, ổn định, nên dùng thay vì tự định nghĩa checker.

**Kattis Problem Package Format** chuẩn hóa `problem.yaml`, `data/`, `output_validators/`, `submissions/`; DOMjudge hỗ trợ ([spec](https://www.kattis.com/problem-package-format/), [problem-format.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/problem-format.rst)). `problemtools` là reference validator MIT ([repo](https://github.com/Kattis/problemtools), [LICENSE](https://raw.githubusercontent.com/Kattis/problemtools/master/LICENSE)).

**CCS Contest API** là spec liên thông REST của ICPC, dùng bởi DOMjudge; phù hợp nếu JudgeLoom muốn expose scoreboard/submissions cho tooling ngoài ([CCS specs](https://ccs-specs.icpc.io/), [repo](https://github.com/icpc/ccs-specs)). Spec repo không có LICENSE file; **implement interface** an toàn hơn copy text.

**Takeaway cho JudgeLoom.** Vendor `testlib.h` kèm notice MIT; dùng Kattis package làm format import/export chuẩn; chỉ dùng CCS API như adapter ngoài, không làm core data model.

---

## 4. Ma trận license tương thích với AGPL-3.0-or-later

> Tóm tắt kỹ thuật, **không phải tư vấn pháp lý**. Khi copy code phải giữ copyright/license notice, cung cấp source theo AGPL/GPL, và không dùng trademark của upstream. Với GPLv2-only, không có đường nâng cấp lên GPLv3/AGPLv3; với GPLv2-or-later thì có thể chọn GPLv3 rồi kết hợp (tham khảo [GNU license list](https://www.gnu.org/licenses/license-list.html), [GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html)).

| Project / component | License đã xác minh | Copy code | Study pattern | Integrate service | Avoid | Caveat |
|---|---|---|---|---|---|---|
| DMOJ site + judge-server | AGPL-3.0 | ✅ | ✅ | ✅ (adapter) | — | Phải công bố source khi chạy network; protocol không có spec độc lập |
| VNOJ OJ | AGPL-3.0 | ✅ | ✅ | ✅ | — | Là fork DMOJ; `vnoj-docker` không license, đừng copy |
| CMS | AGPL-3.0-or-later | ✅ | ✅ | ✅ | — | RPC nội bộ không auth; đừng copy nguyên security model |
| DOMjudge | GPL-2.0-or-later | ✅ (chọn GPLv3) | ✅ | ✅ | — | Phải giữ GPL notice; `runguard` là GPL |
| HydroOJ | AGPL-3.0-or-later + §7 terms | ⚠️ chỉ nếu chấp nhận §7 | ✅ | ✅ (HTTP) | Copy nếu không muốn rename/attribution | Package còn ghi "OR Proprietary"; rủi ro pháp lý cao |
| Judge0 | GPL-3.0-only | ✅ (combined AGPLv3) | ✅ | ✅ | — | Không có "or later"; copy làm combined work chỉ AGPLv3 |
| UOJ | MIT | ✅ | ✅ | ✅ | — | Legacy; không nên copy sandbox |
| QDUOJ backend | MIT | ✅ | ✅ | — | Copy Judger | Judger là SATA, không phải MIT |
| HustOJ | GPL-2.0 (mixed headers) | ❌ | ✅ | — | Copy code | GPL-2.0-only không tương thích AGPLv3; header không nhất quán |
| Themis | Không có license/repo | ❌ | ✅ (workflow) | — | Mọi copy binary/code | All rights reserved; chỉ dùng importer tự viết |
| isolate | GPL-2.0-or-later | ✅ | ✅ | ✅ (process) | — | Binary distribution phải kèm source/GPL |
| nsjail | Apache-2.0 | ✅ | ✅ | ✅ | — | Giữ NOTICE; patent grant |
| go-judge | MIT | ✅ | ✅ | ✅ | — | Giữ copyright notice |
| Testlib | MIT | ✅ (vendor header) | ✅ | ✅ | — | Giữ notice trong file/third-party |
| Kattis problemtools | MIT | ✅ | ✅ | ✅ | — | Spec repo không license; đừng copy text spec |
| CCS API spec | Không có LICENSE file | — | ✅ | ✅ (implement) | Copy spec text | Implement interface, không copy tài liệu |

**Cách đọc bảng:** "Copy code" = có thể đưa code vào JudgeLoom và tuân thủ license tương ứng; "Study pattern" = có thể đọc để thiết kế lại, không copy biểu thức code; "Integrate service" = chạy như process/HTTP service riêng, giảm rủi ro derivative work; "Avoid" = không nên copy vì license hoặc chất lượng.

---

## 5. Mapping vào gap cụ thể của JudgeLoom

### 5.1 Judge bridge + worker + sandbox

**Hiện trạng.** `BridgeManager` là singleton in-memory giữ handler; `dispatch_submission()` chỉ gọi `handler.send_submission(payload)`, payload chỉ có source + limits, không có test data/checker ([bridge_manager.py](../../apps/judge/bridge/bridge_manager.py)). `JudgeHandler.transport` là callback tùy chọn; nếu `None` thì trả `False` ([judge_handler.py](../../apps/judge/bridge/judge_handler.py)). Không có server/worker client/reconnect/ack timeout. `Judge` có `ping`, `load`, `problems`, `runtimes` nhưng không có protocol version, `last_seen`, catalog hash ([judge.py](../../apps/judge/models/judge.py)).

**Nên làm.** Định nghĩa `judge-protocol-v1` theo DMOJ semantics: `hello` (name/key, executors, problems + mtime/hash), `submission` (id, problem, language, source, limits, meta), `ack`, `started`, `case` (batch), `finished`, `compile_error`, `internal_error`, `ping/pong`, `cancel`. Lưu `protocol_version`, `last_seen`, `catalog_hash` trên `Judge`. Worker kết nối outbound; bridge giữ registry + dispatch; Redis/Celery chỉ queue submission, không chứa trạng thái judge. Ack timeout 15–20 s; timeout thì đánh dấu judge offline và re-queue (DMOJ đóng connection và set IE nếu judge chết giữa chừng: [judge_handler.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/bridge/judge_handler.py)). Sandbox: isolate trước (`--box-id ... --cg --init`, copy source, compile, run từng case, parse metadata, cleanup trong `finally`); sau đó go-judge khi cần throughput/streaming. Worker là service riêng, user riêng, không root.

### 5.2 Test data/checker sync

**Hiện trạng.** `ProblemTestData` có `zipfile`, `generator`, `checker`, `checker_source`, `interactive_judge`; `ProblemTestCase` có `order`, `input_file`, `output_file`, `points`, `is_pretest`, `batch_number` ([problem_data.py](../../apps/problems/models/problem_data.py), [problem_data_case.py](../../apps/problems/models/problem_data_case.py)). Không có package version, manifest hash, per-case checksum hay sync API. `get_available_judge()` chỉ kiểm tra `judge.problems` tồn tại, không kiểm tra đúng version test data ([bridge_manager.py](../../apps/judge/bridge/bridge_manager.py)).

**Nên làm.** Lưu `ProblemPackage` (version, sha256, source zip, manifest JSON) + `TestCase` (input_sha256, output_sha256, points, group). Worker gửi catalog `problem_id -> package_hash`; bridge chỉ dispatch khi hash khớp hoặc cho phép tải. API `GET /judge/problems/{id}/package?hash=...` trả zip/manifest; worker cache theo hash, xóa cache cũ. Checker chạy theo Testlib contract; lưu `checker_type` + `checker_source_hash`. Với interactive, dùng `runpipe`/go-judge stream thay vì file tĩnh. Nguồn học: DMOJ gửi `problems` kèm mtime và cập nhật `supported-problems` ([packet.py](https://raw.githubusercontent.com/DMOJ/judge-server/master/dmoj/packet.py)); Hydro cache test data giữa các judge ([README](https://raw.githubusercontent.com/hydro-dev/Hydro/master/README.md)); DOMjudge tải testcase qua `get_files` ([judgedaemon.main.php](https://raw.githubusercontent.com/DOMjudge/domjudge/main/judge/judgedaemon.main.php)); layout theo Kattis package ([spec](https://www.kattis.com/problem-package-format/)).

### 5.3 Contest scoring/ranking/freeze

**Bug hiện tại.** `_is_accepted()` đọc `getattr(submission, "verdict", "")` và `status`, nhưng `Submission` dùng `result` cho AC/WA/TLE ([base.py](../../apps/contests/formats/base.py), [submission.py](../../apps/submissions/models/submission.py)). `_submission_queryset()` kiểm tra field `"participation"`, trong khi FK là `contest_participation`; fallback lọc `user_id` + `problem_id` nên có thể gộp submission ngoài contest ([base.py](../../apps/contests/formats/base.py)). `_subtask_scores()` đọc `submission.result` như dict, nhưng `result` là CharField. `get_frozen_ranking()` chỉ thay `format_data` bằng `{"frozen": True}`, không tính lại score/rank theo freeze time ([ranking_service.py](../../apps/contests/services/ranking_service.py)).

**Nên làm.** Sửa field names trước; test với `result=AC` và `contest_participation` thật. Freeze theo DOMjudge: `freeze_time = start + scoreboard_frozen_after`; public ranking chỉ dùng submission `created_at <= freeze_time`; jury không filter; unfreeze sau `end_time`. ICPC dùng công thức DMOJ: chỉ tính attempt trước AC, bỏ CE/IE, penalty = AC time + 20 × wrong, tiebreak = last AC. IOI dùng score types CMS (Sum/GroupMin/GroupMul/GroupThreshold) thay vì chỉ cộng points. Cache ranking theo `(contest_id, freeze_time, version)`.

### 5.4 Rating

**Hiện trạng.** `User.rating` và `max_rating` default `0` ([user.py](../../apps/accounts/models/user.py)); `calculate_ratings()` dùng `getattr(user, "rating", 1500)`, nên user mới nhận 0 ([rating_service.py](../../apps/ratings/services/rating_service.py)). Hàm lấy toàn bộ ranking, không lọc `rate_exclude`, không tôn trọng `rate_all`, `rating_floor`, `rating_ceiling` dù model có ([contest.py](../../apps/contests/models/contest.py)). Elo hiện tại K=32, `volatility_before=0`, `volatility_after=abs(delta)` là giả.

**Nên làm.** Quick fix: default 1500 + data migration; `rating_before` lấy từ `Rating` gần nhất, fallback 1500; lọc `rate_exclude`, `virtual=0`, `rate_all`, floor/ceiling như DMOJ ([ratings.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/ratings.py)). Sau đó port Elo-MMR: `mean`, `volatility`, `times_ranked`, `performance`, `historical_p`; viết command recalc toàn bộ. Không dùng Hydro CF rating vì license §7; có thể học công thức nhưng tự implement.

### 5.5 Task scheduling

**Hiện trạng.** `CELERY_BEAT_SCHEDULE` chỉ có `judge.monitor_judges` và `judge.cleanup_stale_sessions` ([base.py](../../config/settings/base.py)); `contests.tasks` định nghĩa `schedule_contest_start`, `schedule_contest_end`, `recalculate_contest_rankings` nhưng không có chỗ nào gọi ([contests/tasks.py](../../apps/contests/tasks.py)). `end_contest()` gọi rating nếu `is_rated`, nhưng task không được trigger ([contest_lifecycle_service.py](../../apps/contests/services/contest_lifecycle_service.py)).

**Nên làm.** Thêm beat task `contests.tick` mỗi phút: quét contest có `start_time`/`end_time` trong khoảng, dùng `select_for_update(skip_locked=True)` + cột `started_at`/`ended_at` để idempotent; enqueue start/end qua `apply_async(eta=...)` hoặc tick. Recalc ranking sau mỗi submission judged (debounce 5–10 s) và tại freeze/end. Rating chạy sau end, trong transaction, có lock. Học DOMjudge milestones và CMS timing ([config-basic.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/config-basic.rst), [Configuring a contest.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Configuring%20a%20contest.rst)).

### 5.6 API/auth

**Hiện trạng.** `JudgeLoomAuth(HttpBearer)` chỉ decode JWT HS256 bằng `SECRET_KEY`, không session fallback, không scope/revoke ([permissions.py](../../core/permissions.py)). Web dùng Django session (`SESSION_ENGINE=cache`), API dùng JWT; endpoint `auth=JudgeLoomAuth()` từ chối session ([base.py](../../config/settings/base.py), [accounts/router.py](../../apps/accounts/api/router.py)). Judge bridge dùng `auth_key` shared secret, tách biệt, nhưng không rotation/TLS ([judge_handler.py](../../apps/judge/bridge/judge_handler.py)).

**Nên làm.** Chọn canonical API auth: JWT access/refresh + scopes, hoặc token cá nhân như DMOJ ([API docs](https://docs.dmoj.ca/#/site/api)); viết `AuthBase` kết hợp JWT + session cho web/API, nhưng không dùng session cho judge. Judge auth giữ shared secret + `hmac.compare_digest`, thêm key rotation (`auth_key_id`), TLS, IP allowlist tùy chọn. Không dùng JWT user cho worker.

### 5.7 Event bus/WebSocket

**Hiện trạng.** `_derive_channel()` lấy namespace trước dấu chấm và pluralize: `submission.judged` → `submissions`; `contest.ranking.updated` → `contests` ([events.py](../../core/events.py)). `publish()` gửi group event `{"type": "event.broadcast", "data": event.serialize()}` ([events.py](../../core/events.py)). Nhưng `SubmissionConsumer` join group `submission_{id}` và handler `broadcast()` đọc `event["payload"]`; `ContestConsumer` join `contest_{key}` và handler `ranking_update`/`contest_event` ([submissions/consumers.py](../../apps/submissions/consumers.py), [contests/consumers.py](../../apps/contests/consumers.py)). Không có group/type nào khớp, nên realtime gần như chắc chắn không hoạt động.

**Nên làm.** Chốt contract: group `submission_{id}`/`contest_{key}`; event type `submission.update`, `contest.ranking`, `contest.lifecycle`; payload có `type`, `payload`, `timestamp`, `source`. Sửa `publish()` nhận explicit `group` + `event_type`; publish sau `transaction.on_commit`; test bằng `InMemoryChannelLayer`. DMOJ dùng per-submission secret channel `sub_<secret>` ([judge_handler.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/bridge/judge_handler.py)); JudgeLoom giữ id + permission check, nhưng đúng contract.

### 5.8 Migrations/testing

**Hiện trạng.** Không có thư mục `migrations/` trong `apps/*`; `makemigrations --check` sẽ fail. Test hiện có nhưng thiếu protocol/freeze/rating-exclusion.

**Nên làm.** Commit initial migration cho từng app; CI thêm `python manage.py makemigrations --check --dry-run`. Test: (a) fake judge transport theo protocol, (b) contest format với fixture `result=AC`/`contest_participation`, (c) freeze snapshot trước/sau `freeze_time`, (d) rating exclusion/floor/ceiling, (e) event bus group/type contract, (f) integration isolate/go-judge chỉ chạy Linux. DMOJ có `echo_test_client.py`/`echo_test_server.py` trong bridge để test protocol ([bridge](https://github.com/DMOJ/online-judge/tree/master/judge/bridge)); có thể học cách mock.

---

## 6. Roadmap ưu tiên

### Quick wins (1–3 tuần)

| Việc | Nguồn | Adopt chính xác |
|---|---|---|
| Sửa scoring field names | JudgeLoom local | `result`, `contest_participation`; test AC/WA/CE |
| Freeze đúng | DOMjudge | Filter `created_at <= freeze_time`; jury view unfiltered; unfreeze sau end ([config-basic.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/config-basic.rst)) |
| ICPC penalty | DMOJ | AC time + 20 × wrong; bỏ CE/IE; tiebreak last AC ([icpc.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/contest_format/icpc.py)) |
| Rating default + exclusion | DMOJ | 1500; `rate_exclude`, `rate_all`, floor/ceiling ([ratings.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/ratings.py)) |
| Event bus contract | DMOJ/Channels | Group `submission_{id}`/`contest_{key}`; type khớp handler; test InMemory layer |
| Schedule contest tasks | DOMjudge | `contests.tick` mỗi phút + idempotent start/end/recalc |
| Commit migrations | Django | `makemigrations` + CI check |

### Next (4–8 tuần)

| Việc | Nguồn | Adopt chính xác |
|---|---|---|
| Judge protocol v1 | DMOJ | Hello/auth, problem catalog + hash, submission/ack, case batch, grading-end, ping/load ([packet.py](https://raw.githubusercontent.com/DMOJ/judge-server/master/dmoj/packet.py)) |
| Worker outbound + reconnect | DMOJ | Worker nối ra bridge; exponential backoff; ack timeout; re-queue |
| isolate sandbox | CMS/Judge0 | `isolate --cg --init/--run/--cleanup`; parse metadata; chạy user riêng ([Sandbox.py](https://raw.githubusercontent.com/cms-dev/cms/main/cms/grading/Sandbox.py)) |
| Test data package + hash sync | Kattis/Hydro | Package + manifest; worker cache theo hash; API tải package ([spec](https://www.kattis.com/problem-package-format/)) |
| Testlib checker runner | Testlib | Exit code 0/1/2/3/5; `quitp` points; timeout/cleanup ([testlib.h](https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/testlib.h)) |
| Per-case batching | DMOJ | Flush mỗi 0,25 s; tránh DB write từng case ([packet.py](https://raw.githubusercontent.com/DMOJ/judge-server/master/dmoj/packet.py)) |

### Later (8–16 tuần)

| Việc | Nguồn | Adopt chính xác |
|---|---|---|
| go-judge sidecar | Hydro/go-judge | HTTP `/run`, `/file` cache, `/stream`; scale ngang ([client.ts](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrojudge/src/sandbox/client.ts)) |
| Elo-MMR | DMOJ | Mean/variance, tie nửa trận, performance history, `times_ranked` ([ratings.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/ratings.py)) |
| scorecache/rankcache | DOMjudge | Cache cell + aggregate; invalidate theo contest/submission ([scoring.rst](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/scoring.rst)) |
| Dataset versioning | CMS | Nhiều dataset, active dataset, rejudge theo dataset ([Data model.rst](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Data%20model.rst)) |
| CCS API adapter | DOMjudge/CCS | `/api/v4` scoreboard/submissions cho tooling ngoài ([CCS](https://ccs-specs.icpc.io/)) |
| Plugin rule registry | DMOJ/Hydro | `register_format`, rule object; hot-plug không sửa core ([registry.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/contest_format/registry.py)) |

---

## 7. Nguồn (truy cập 2026-10-30)

**DMOJ / VNOJ**
- Repos: https://github.com/DMOJ/online-judge · https://github.com/DMOJ/judge-server · https://github.com/VNOI-Admin/OJ · https://oj.vnoi.info/
- Primary files: [LICENSE site](https://raw.githubusercontent.com/DMOJ/online-judge/master/LICENSE) · [LICENSE judge](https://raw.githubusercontent.com/DMOJ/judge-server/master/LICENSE) · [packet.py](https://raw.githubusercontent.com/DMOJ/judge-server/master/dmoj/packet.py) · [judge_handler.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/bridge/judge_handler.py) · [ratings.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/ratings.py) · [icpc.py](https://raw.githubusercontent.com/DMOJ/online-judge/master/judge/contest_format/icpc.py) · [API docs](https://raw.githubusercontent.com/DMOJ/docs/master/docs/site/api.md)

**CMS**
- Repo/docs: https://github.com/cms-dev/cms · https://cms.readthedocs.io/en/latest/
- Primary files: [LICENSE](https://raw.githubusercontent.com/cms-dev/cms/main/LICENSE.txt) · [setup.py](https://raw.githubusercontent.com/cms-dev/cms/main/setup.py) · [Introduction](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Introduction.rst) · [Data model](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Data%20model.rst) · [Score types](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Score%20types.rst) · [Configuring](https://raw.githubusercontent.com/cms-dev/cms/main/docs/Configuring%20a%20contest.rst) · [Sandbox.py](https://raw.githubusercontent.com/cms-dev/cms/main/cms/grading/Sandbox.py)

**DOMjudge**
- Repo/docs: https://github.com/DOMjudge/domjudge · https://www.domjudge.org/documentation · https://ccs-specs.icpc.io/
- Primary files: [README](https://raw.githubusercontent.com/DOMjudge/domjudge/main/README.md) · [COPYING](https://raw.githubusercontent.com/DOMjudge/domjudge/main/COPYING) · [config-basic](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/config-basic.rst) · [scoring](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/scoring.rst) · [judging](https://raw.githubusercontent.com/DOMjudge/domjudge/main/doc/manual/judging.rst) · [judgedaemon](https://raw.githubusercontent.com/DOMjudge/domjudge/main/judge/judgedaemon.main.php)
- https://ccs-specs.icpc.io/ · https://github.com/icpc/ccs-specs

**HydroOJ**
- Repo/docs: https://github.com/hydro-dev/Hydro · https://docs.hydro.ac/
- Primary files: [LICENSE](https://raw.githubusercontent.com/hydro-dev/Hydro/master/LICENSE) · [README](https://raw.githubusercontent.com/hydro-dev/Hydro/master/README-EN.md) · [package.json](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrooj/package.json) · [sandbox client](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrojudge/src/sandbox/client.ts) · [contest model](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrooj/src/model/contest.ts) · [rating](https://raw.githubusercontent.com/hydro-dev/Hydro/master/packages/hydrooj/src/lib/rating.ts)

**Judge0**
- Repo/docs: https://github.com/judge0/judge0 · https://ce.judge0.com
- Primary files: [LICENSE](https://raw.githubusercontent.com/judge0/judge0/master/LICENSE) · [isolate_job](https://raw.githubusercontent.com/judge0/judge0/master/app/jobs/isolate_job.rb) · [auth](https://raw.githubusercontent.com/judge0/judge0/master/app/controllers/sessions_controller.rb) · [compose](https://raw.githubusercontent.com/judge0/judge0/master/docker-compose.yml)

**UOJ / QDUOJ / HustOJ / Themis**
- https://github.com/UniversalOJ/UOJ-System · https://universaloj.github.io/ · https://github.com/QingdaoU/OnlineJudge · http://opensource.qduoj.com/ · https://github.com/zhblue/hustoj · http://www.hustoj.com/
- https://raw.githubusercontent.com/UniversalOJ/UOJ-System/master/LICENSE · https://raw.githubusercontent.com/QingdaoU/OnlineJudge/master/LICENSE · https://raw.githubusercontent.com/QingdaoU/Judger/master/LICENSE · https://raw.githubusercontent.com/zhblue/hustoj/master/LICENSE
- https://dsapblog.wordpress.com/2013/12/24/themis/ · https://github.com/natsukagami/themis-web-interface

**Sandbox / Testlib / specs**
- https://github.com/ioi/isolate · https://github.com/google/nsjail · https://github.com/criyle/go-judge · https://docs.goj.ac/ · https://nsjail.dev/
- https://github.com/MikeMirzayanov/testlib · https://www.kattis.com/problem-package-format/ · https://github.com/Kattis/problemtools · https://ccs-specs.icpc.io/
- License references: https://raw.githubusercontent.com/ioi/isolate/master/LICENSE · https://raw.githubusercontent.com/google/nsjail/master/LICENSE · https://raw.githubusercontent.com/criyle/go-judge/master/LICENSE · https://raw.githubusercontent.com/MikeMirzayanov/testlib/master/LICENSE · https://raw.githubusercontent.com/Kattis/problemtools/master/LICENSE
- GNU compatibility: https://www.gnu.org/licenses/license-list.html · https://www.gnu.org/licenses/gpl-faq.html
