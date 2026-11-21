# UI/UX DESIGN PLAN: Examination Management Portal (EMP), v2

*Inputs: PDR v2 and TDR v2. Tier labels: **T1** Primary, **T2** Secondary, **T3** Tertiary. T3 screens are designed here so the plan is complete, but they are built only after Gate B (see the Master Blueprint).*

*The course wireframe (`examination-management-wireframe`) only illustrates flow and navigation; replicating it is not mandatory, so this plan defines its own layouts while keeping the same flows.*

---

## 1. Design Principles

1. **Role clarity first.** Each role (Admin, Examiner, Student) gets its own layout, navigation and dashboard. A user never sees a menu item they cannot use.
2. **State is always visible.** Every examination, slot, booking, evaluation (and in T3 attempt and payment) shows a colour-coded status badge with text, so users know what they can do next without guessing.
3. **Prevent errors, then explain them.** Disable actions that are not allowed (for example "Book" when the window is closed) and show the reason in plain words ("Booking opens on 12 Dec, 10:00"). Server rules remain the real guard.
4. **Server-rendered, low-JS.** Core screens are plain Bootstrap pages that work without JavaScript. JS appears only in T2 (charts, validation hints) and T3 (timer, anti-cheat reporting, payment popup).
5. **Calm, distraction-free test mode (T3).** The test screen removes navigation, shows only what the mode allows, and tells the student in advance what is monitored. No dark patterns: rules and consequences are stated before the test starts.
6. **Offline-safe visuals.** Bootstrap, icons and charts are vendored locally; no CDN or web fonts are required for the demo.

---

## 2. Wireframe Reference

| Audience | Layout pattern | Notes |
|---|---|---|
| Public (login, register) | Centered card on a plain background, single column | Role choice on the register screen (Student or Examiner) |
| Admin | **Left sidebar** (collapsible) + top bar with name and logout; content area with page header, filters and tables | Sidebar groups: Overview, Courses, Examinations, Examiners, Students, Slots, Bookings, Search, History. T3 adds: Tests, Proctoring, Payments |
| Examiner | **Top navbar** (Dashboard, Examinations, Slots, Evaluations, Profile) | Card-based dashboard; slot and evaluation tables below |
| Student | **Top navbar** (Dashboard, Examinations, My Bookings, Results, Profile) | Card grid for available examinations; booking confirmations as modals |
| Forms | Bootstrap vertical forms, labels above fields, inline validation messages | Date-time pickers use native `datetime-local` inputs |
| Tables | Responsive table with filter bar above and pagination below; collapses to stacked cards on phones | |
| **Test attempt (T3)** | **Focus layout:** no navbar or sidebar; thin top strip with test title, countdown and "Submit"; question card in the centre | `random_revisitable` and `standard` add a question palette (numbered buttons with answered/unanswered/marked states); `random_forward_only` has **no palette and no Previous button**, only "Save and next" |
| Payment (T3) | Order summary card, then the Razorpay Checkout popup | Result page shows paid / failed / expired with next steps |

---

## 3. Information Architecture (Sitemap)

### 3.1 Public / Shared
- `/login`
- `/register` (choose Student or Examiner)
- `/pending-approval` (examiner awaiting Admin approval)
- `/profile` (any signed-in role)
- Error pages: 403, 404, 500
- *(T2)* `/api/v1/docs` (short API reference page)

### 3.2 Admin
- Dashboard (six totals; T2 adds charts)
- Courses → list, create, edit
- Examinations → list, create, edit, detail (timeline panel with **Open/Close slot creation** and **Open/Close booking** switches), Rubrics, Assigned examiners
- Examiners → list (filter pending/approved/inactive), detail, approve, deactivate
- Students → list, detail
- Slots → list (all), detail, change examiner
- Bookings → list, detail, reschedule, cancel
- Search (students, examiners, examinations, bookings by name or ID)
- History (all historical examination and booking data)
- *(T3)* Tests → list, create/edit, question editor, preview, publish, results
- *(T3)* Proctoring → reports list, attempt violation timeline, CSV export, attempt reset
- *(T3)* Payments → list, reconciliation flags, set examination fee

### 3.3 Staff / Employee (Examiner)
- Dashboard (assigned examinations, created slots, students booked, pending evaluations; T2 charts)
- Examinations → assigned list, detail
- Slots → list, create, edit, delete, booked students
- Evaluations → pending list, evaluation form (rubric scores, marks, remarks), submitted list
- Profile edit
- *(T3)* Tests → list, create/edit for own examinations, question editor, attempt scores

### 3.4 User / Customer (Student)
- Dashboard (available examinations, available slots, upcoming, booked slots, published results; T2 charts)
- Examinations → browse, search and filter, detail with slots
- My Bookings → list, detail, cancel, status
- Schedule (upcoming)
- History (booking and examination history)
- Results → list, detail with feedback (T2: scorecard download)
- Profile edit
- *(T3)* Tests → list of available tests, rules and consent, attempt, result
- *(T3)* Payments → pay for a slot, payment result, my payments

---

## 4. Key User Flows

### 4.1 Registration, Login & Password Reset
**Student**
1. Open `/register`, choose **Student**, enter name, email, password, confirm password.
2. Submit; on success see "Account created" and go to `/login`.
3. Log in; redirected to the Student dashboard.

**Examiner**
1. Open `/register`, choose **Examiner**, fill the form plus department and phone.
2. Submit; account is created as *Pending*.
3. First login shows the **Pending approval** page (no dashboard access).
4. Admin opens Examiners → Pending → **Approve**.
5. Examiner logs in again and lands on the Examiner dashboard.
6. If Admin **deactivates** the examiner, the next request redirects to a "Account inactive" notice.

**Admin**
1. No registration. Log in with the pre-created credentials; redirected to the Admin dashboard. A first-login prompt asks the Admin to change the seeded password.

**Password reset** *(gap flagged: the PDR does not specify one)*: a minimal, admin-assisted flow is used: the user contacts Admin; Admin opens the user detail and sets a temporary password; the user must change it at next login. A self-service email reset is not planned. Confirm this matches the intent.

### 4.2 Core Transaction Flow: Book an Examination Slot
1. Student opens **Examinations**, searches or filters by course and type.
2. Opens an examination card; sees the booking window, deadline and the list of slots (date, time, examiner, seats left, status badge).
3. If booking is closed, the **Book** buttons are disabled with a reason line.
4. Student clicks **Book** on an *Available* slot; a confirmation modal summarises examination, time and examiner.
5. Student confirms. Server checks window, duplicate and capacity in one transaction.
6. Success: flash "Booking confirmed", redirect to My Bookings with a *Booked* badge. (T2: confirmation email.)
7. Errors show specific messages: "This slot is full", "You already have a booking for this examination", "Booking is closed".
8. Before the deadline the student can **Cancel** from My Bookings; the seat is released and the booking shows *Cancelled* in history.
9. Admin may **Reschedule** the booking to another slot of the same examination.
10. *(T3, fee above zero)* Step 4 changes: the button reads **Pay and book**, and flow 4.7 runs instead.

### 4.3 Examiner Evaluation Flow *(substitutes the ticket/support flow; the PDR excludes ticketing)*
1. Examiner opens **Slots** and picks a slot; sees booked students.
2. Opens **Evaluate** for a student; the form lists each rubric criterion with a score field (max shown) and a remarks box.
3. Enters scores; the total updates (server confirms it is within the examination's maximum marks).
4. **Save draft** keeps it private; **Submit** finalises it; **Publish** (or Admin publish) makes it visible to the student.
5. The Pending evaluations counter on the dashboard decreases.
6. Student sees the result and feedback under Results.

### 4.4 Admin Examination Setup Flow
1. Create a **Course**.
2. Create an **Examination** (type, duration, maximum marks, slot-creation window, booking window, deadline).
3. Add **Rubric** criteria until weightages total 100.
4. **Assign examiners** (approved ones only).
5. Use the timeline switches: **Open slot creation** → examiners create slots → **Close slot creation** → **Open booking** → students book → **Close booking**.
6. Monitor Slots and Bookings; Reschedule or change examiner if needed.

### 4.5 T3 Flow: Take an Online Test
1. Student opens **Tests**; sees only tests for examinations with their valid booking (and paid booking when a fee exists) and an open window.
2. Opens the **Rules and consent** screen: duration, delivery mode in plain words ("You cannot go back to earlier questions" or "You can revisit questions"), what is monitored, what happens on leaving the page, and a checkbox "I understand and accept".
3. **Start test**: the server fixes the question set and order for this student.
4. Answering:
   - *Standard:* free navigation with the palette.
   - *Random forward-only:* one question at a time, **Save and next** only; the earlier question is locked.
   - *Random revisitable:* random order per student, free navigation, "mark for review" supported.
5. Countdown is shown; at zero the attempt auto-submits.
6. **Submit** shows a confirmation ("You have N unanswered questions"). Result appears according to the publish mode.

### 4.6 T3 Flow: Anti-Cheat Monitoring
1. During an attempt the page reports tab hidden, window blur (after the grace period), fullscreen exit (when required), and copy/paste/right-click attempts.
2. On a counted violation the server increments the count. When the count reaches the test's limit (default 1) the attempt is **auto-submitted** and the student sees: "Your test was submitted because you left the test page at 10:42:03."
3. Below the limit, the student sees a warning banner: "Warning 1 of 2: leaving the test page again will submit your test."
4. Admin opens **Proctoring → Reports**, filters by test/student/date, opens an attempt to see the timeline (event type, time, seconds away, question number), and can export CSV or **reset** the attempt with a reason (logged).
5. The report states the limit plainly: it shows that and when the student left the page, not which application was opened.

### 4.7 T3 Flow: Pay the Examination Fee and Book
1. Student clicks **Pay and book** on a slot; modal shows examination, slot and amount.
2. Server creates a **seat hold** (10 minutes) and a Razorpay order; a countdown "Seat held for 09:41" appears.
3. Razorpay Checkout opens; the student pays (test mode).
4. On success the server verifies the signature and creates the booking; the student sees **Payment received** with a booking summary and receipt reference.
5. On failure or closing the popup: **Payment failed / not completed**, with "Try again" while the hold is active.
6. If the hold expires, the student sees "Your seat hold expired" and can start again. If a payment completes after expiry or the seat is lost, the money is refunded automatically and the message says so.
7. Cancelling a booking before the deadline shows "Refund initiated".

---

## 5. Screen Inventory

IDs are stable references for the Master Blueprint. Tier in brackets.

### 5.1 Public / Shared
- PUB-01 Login [T1]
- PUB-02 Register (Student / Examiner) [T1]
- PUB-03 Pending approval notice [T1]
- PUB-04 Account inactive notice [T1]
- PUB-05 Change password (first login and temporary password) [T1]
- PUB-06 Profile view and edit [T1]
- PUB-07 Error pages 403, 404, 500 [T1]
- PUB-08 API reference page [T2]

### 5.2 Admin
- ADM-01 Dashboard (six totals) [T1]; charts widget [T2]
- ADM-02 Courses list [T1]
- ADM-03 Course create/edit [T1]
- ADM-04 Examinations list [T1]
- ADM-05 Examination create/edit [T1]
- ADM-06 Examination detail with timeline controls [T1]
- ADM-07 Rubric management [T1]
- ADM-08 Assigned examiners panel [T1]
- ADM-09 Examiners list with filters [T1]
- ADM-10 Examiner detail (approve / deactivate / set temporary password) [T1]
- ADM-11 Students list [T1]
- ADM-12 Student detail with bookings and history [T1]
- ADM-13 Slots list [T1]
- ADM-14 Change slot examiner [T1]
- ADM-15 Bookings list [T1]
- ADM-16 Reschedule booking [T1]
- ADM-17 Search results [T1]
- ADM-18 Historical data view [T1]
- ADM-19 Chart pages (bookings trend, examiner workload, completion) [T2]
- ADM-20 Tests list [T3]
- ADM-21 Test create/edit (mode, duration, window, violation policy) [T3]
- ADM-22 Question editor [T3]
- ADM-23 Test preview and publish [T3]
- ADM-24 Test results and publish scores [T3]
- ADM-25 Proctoring reports list [T3]
- ADM-26 Attempt violation timeline [T3]
- ADM-27 Reset attempt dialog [T3]
- ADM-28 Payments list and reconciliation flags [T3]
- ADM-29 Set examination fee [T3]

### 5.3 Examiner
- EXM-01 Dashboard [T1]; charts [T2]
- EXM-02 Assigned examinations list [T1]
- EXM-03 Examination detail [T1]
- EXM-04 Slots list [T1]
- EXM-05 Slot create/edit [T1]
- EXM-06 Booked students per slot [T1]
- EXM-07 Pending evaluations list [T1]
- EXM-08 Evaluation form [T1]
- EXM-09 Submitted evaluations list [T1]
- EXM-10 Chart page [T2]
- EXM-11 Tests list [T3]
- EXM-12 Test create/edit and question editor [T3]
- EXM-13 Attempt scores [T3]

### 5.4 Student
- STU-01 Dashboard [T1]; charts [T2]
- STU-02 Examinations browse/search/filter [T1]
- STU-03 Examination detail with slots [T1]
- STU-04 Booking confirmation modal [T1]
- STU-05 My bookings [T1]
- STU-06 Booking detail and cancel [T1]
- STU-07 Schedule (upcoming) [T1]
- STU-08 History [T1]
- STU-09 Results list [T1]
- STU-10 Result detail with feedback [T1]; scorecard download [T2]
- STU-11 Chart page [T2]
- STU-12 Tests list [T3]
- STU-13 Rules and consent [T3]
- STU-14 Attempt: standard layout with palette [T3]
- STU-15 Attempt: random forward-only layout (no palette, no Previous) [T3]
- STU-16 Attempt: random revisitable layout with palette and mark for review [T3]
- STU-17 Violation warning banner [T3]
- STU-18 Attempt finished notice (submitted, timeout, or violation) [T3]
- STU-19 Test result and review [T3]
- STU-20 Pay and book modal (order summary and seat-hold countdown) [T3]
- STU-21 Razorpay Checkout popup [T3]
- STU-22 Payment result (paid, failed, expired, refunded) [T3]
- STU-23 My payments [T3]

**Totals:** T1 about 45 screens, T2 about 6, T3 about 26.

---

## 6. Status Badge Convention

Every badge shows text plus colour (colour is never the only signal).

| Domain | State | Colour | Bootstrap class |
|---|---|---|---|
| Generic | Success / Approved / Available / Paid | Green | `text-bg-success` |
| Generic | Pending / Awaiting | Yellow | `text-bg-warning` |
| Generic | Error / Rejected / Failed | Red | `text-bg-danger` |
| Generic | Info / In progress / Submitted | Blue | `text-bg-primary` |
| Generic | Inactive / Draft / Cancelled / Expired | Grey | `text-bg-secondary` |
| Examination | Draft | Grey | secondary |
| Examination | Slot Creation | Blue | primary |
| Examination | Booking Open | Green | success |
| Examination | Closed | Amber outline | `border border-warning text-warning-emphasis` |
| Examination | Completed | Dark | `text-bg-dark` |
| Slot | Available | Green | success |
| Slot | Full | Orange | custom `badge-full` (`#FD7E14`) |
| Slot | Cancelled | Grey | secondary |
| Slot | Completed | Dark | dark |
| Booking | Booked | Green | success |
| Booking | Completed | Dark | dark |
| Booking | Cancelled | Grey | secondary |
| Examiner account | Pending | Yellow | warning |
| Examiner account | Approved | Green | success |
| Examiner account | Deactivated | Red | danger |
| Evaluation | Draft | Grey | secondary |
| Evaluation | Submitted | Blue | primary |
| Evaluation | Published | Green | success |
| Timeline switch | Open | Green | success |
| Timeline switch | Closed | Grey | secondary |
| **T3** Attempt | In progress | Blue | primary |
| **T3** Attempt | Submitted | Green | success |
| **T3** Attempt | Auto-submitted (time up) | Orange | `badge-full` |
| **T3** Attempt | Auto-submitted (violation) | Red | danger |
| **T3** Attempt | Reset | Grey | secondary |
| **T3** Violation count | 0 / below limit / at limit | Green / Yellow / Red | success / warning / danger |
| **T3** Payment | Created | Yellow | warning |
| **T3** Payment | Paid | Green | success |
| **T3** Payment | Failed | Red | danger |
| **T3** Payment | Refunded | Purple | custom `badge-refunded` (`#6F42C1`) |
| **T3** Payment | Expired | Grey | secondary |
| **T3** Seat hold | Active (with countdown) | Yellow | warning |
| **T3** Test | Draft / Published / Closed | Grey / Green / Dark | secondary / success / dark |

---

## 7. Style Guide Basics

*Defaulting to **Bootstrap 5** because the stack is mandated and no other CSS framework is allowed.*

**Colour palette**
| Role | Hex |
|---|---|
| Primary (brand, buttons, links) | `#1F4E79` |
| Primary hover | `#173B5C` |
| Secondary (text muted, neutral buttons) | `#6C757D` |
| Success | `#198754` |
| Warning | `#FFC107` |
| Danger | `#DC3545` |
| Info | `#0DCAF0` |
| Orange (slot full, time-up) | `#FD7E14` |
| Purple (refunded) | `#6F42C1` |
| Page background | `#F5F7FA` |
| Surface / cards | `#FFFFFF` |
| Body text | `#212529` |
| Sidebar background (Admin) | `#14283B` |

Override Bootstrap with CSS variables in `static/css/app.css` (`--bs-primary` and related); do not add another CSS framework.

**Typography**
- Font family: system stack `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` (works offline; no web font download). Monospace for IDs and codes: `ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace`.
- Scale: base 16 px; headings h1 2rem, h2 1.5rem, h3 1.25rem; table text 0.9rem.

**Components**
- Buttons: primary for the single main action; outline for secondary; danger only for destructive actions with a confirm modal.
- Tables: `table table-hover align-middle`; sticky header on long lists.
- Forms: Bootstrap `form-control`, `is-invalid` with `invalid-feedback` text.
- Flash messages: Bootstrap alerts at the top of content, dismissible, `role="alert"`.
- Spacing: Bootstrap spacing scale (multiples of 0.25rem); content max-width 1200 px for non-test pages; test pages max-width 800 px.
- Icons: Bootstrap Icons, vendored as an SVG sprite.

---

## 8. Accessibility & Responsiveness

**Target: WCAG 2.1 Level AA.**
- Colour contrast at least 4.5:1 for text; do not rely on colour alone (badges include text).
- Every form control has a visible `<label>`; errors are linked with `aria-describedby`; focus is moved to the first error after a failed submit.
- Full keyboard operation; visible focus ring; skip-to-content link; modals trap focus and return it on close.
- Semantic landmarks (`header`, `nav`, `main`, `footer`), one `h1` per page, tables with `<th scope>`.
- `aria-live="polite"` for flash messages; `aria-live="assertive"` for the violation warning banner (T3).
- **T3 test pages:** the countdown is announced at 10, 5 and 1 minutes (not every second); question palette buttons have accessible names such as "Question 4, answered, marked for review"; time extensions for students with accommodations are an Admin-handled exception (reset or new attempt), flagged as an open design question.

**Breakpoints (Bootstrap 5 grid)**
| Breakpoint | Width | Behaviour |
|---|---|---|
| xs | under 576 px | Single column; navbar collapses to a hamburger; Admin sidebar becomes an off-canvas drawer; tables stack as cards; booking and payment actions use full-width buttons |
| sm | 576-767 px | Single column with larger touch targets; two-column card grid for examinations |
| md | 768-991 px | Two-column layouts; Admin sidebar collapsible |
| lg | 992-1199 px | Sidebar visible; dashboard cards in a 3-up grid |
| xl and above | 1200 px+ | Full layout with content capped at 1200 px |

Test attempt pages (T3) are optimised for desktop browsers (the monitoring is weaker on mobile); on small screens the palette collapses into a drawer, and a notice explains that desktop is recommended.

---

### Assumptions and gaps flagged
1. Password reset is not in the PDR; an admin-assisted flow is planned (see 4.1). Confirm.
2. Ticketing/support is excluded by the PDR; the evaluation flow is shown in its place (4.3).
3. Accommodations for students needing extra test time are not in the PDR; handled by Admin reset or a future "extra time" field (open question).
4. Screen counts are estimates; the final list follows the TDR routes.
