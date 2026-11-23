# Agency Blueprint — Zwoclippe (2026-11-23)

Draft for zo's approval. Nothing built yet. Sources: Nathan Johnson, "How To Build A $1.3m/mo Clipping Agency From Scratch" (youtu.be/PxO1lHJ89L4, 21 min, full transcript read) and zo's Pinterest board "ClipperInterface" (10 of 11 pins read; the 11th did not load).

## 1. What the video actually is
Plain truth: the video has **no AI agents and no software setup**. It is a human business playbook. Nate's agency runs on people (editors, account managers, sales DMs) and Whop for payments and ads. So "how their agents work" maps onto our agents by job, not by copying a system.

His ladder, in order:
1. Content Rewards / Discord campaigns for first money and **case studies** (named campaigns you can quote).
2. **Fan account** for a creator you want. Creators (he names Lacy) shout out fan/edit accounts and hire them later. One student landed a $2.5k/mo client in 30 days this way.
3. **Retainer** instead of pay-per-view: $500-2,000/mo for 1-2 clips a day (their QCP channel: ~1M subs, 1.2k shorts, ad revenue + retainer).
4. Stop editing yourself: hire editors from clipping Discords at **$5-25 per clip**.
5. Sales: cold DMs with case studies, **10% lifetime referral** to big clients (one referral chain built most of the book).
6. **Host campaigns** for clients on Content Rewards instead of joining them.
7. The 7-figure jump: sell **strategy + scripting + weekly account-manager call**, a 1M-view guarantee, to businesses (leads = money). $1,500/mo became $6,000/mo for the same one clip a day.
8. Growth engine: organic content about the agency itself, then **paid ads** showing case studies (claims 8-12x ROAS on recurring billing). Website was one 7-min video plus testimonials.

Edit recipe he gives: take a ~30 s moment, cut it to ~15 s from three beats (setup, skip, payoff), captions, no dead air.

## 2. Adopt / skip — ranked
| # | Idea | Call | Why, for us |
|---|---|---|---|
| 1 | Fan-account route (Lacy first) | **Adopt now** | Exactly our model. Lacy is our first streamer and is named as someone who hires fan accounts. Our channels are the pitch. |
| 2 | Case-study log | **Adopt now** | Every posted clip's views/shares go into a "proof" table; best 3 per streamer become the pitch deck. Costs nothing, feeds #5. |
| 3 | Tight 3-beat edit (30 s to 15 s) | **Adopt now** | Matches D077/D087. Add a "beats" field to the judge so render can stitch setup + payoff and drop the middle. |
| 4 | Consistency over virality | **Adopt (already)** | D088 cadence ramp already does this. Keep. |
| 5 | Retainer pitch to a streamer's team | **Adopt after 30 days of proof** | Needs numbers first. Target: Lacy's team, $500-1,500/mo for daily clips. Outreach agent drafts, zo sends. |
| 6 | Referral 10% | **Adopt with #5** | Only matters once one client signs. |
| 7 | Host campaigns on Content Rewards / Whop | **Later** | Real only when a client pays for reach. |
| 8 | Hire human editors | **Skip for now** | Our render agent is the editor. Revisit only if review time, not render, becomes the limit. |
| 9 | Strategy/scripting upsell to businesses | **Skip** | Different business. Our strategy muscle goes to Zwoclipp long-form narration (D079-D083, D090) instead. |
| 10 | Paid ads | **Skip** | No product to sell yet. |
| 11 | Proxies to post from outside the US | **Skip** | Not needed, and it risks platform flags. |
| 12 | Whop as bank + ads | **Skip** | Not needed until #5. Whop stays for campaign scanning (D070). |

## 3. Agency setup (who does what)
Human: **zo** = owner, approver of every clip (D085), sender of all outreach.

Agents, by the job Nate gives a person:
| Agent | Nate's human equivalent | Does |
|---|---|---|
| Lacy / Jynxzi / Stable Ronaldo agents (D084) | Dedicated editor per client | Watch, detect, judge, render, QA, hand to review, prep post, read stats, learn (D089 brain). |
| Render agent (shared ffmpeg) | Editor | 9:16, captions, zooms (D077), revision memory (D078), 3-beat stitch (new). |
| Publisher | Posting VA | Queues approved clips to YT/X, TikTok manual list (D074), cadence D088. |
| Analyst | Account manager weekly call | Pulls 2 h/24 h/72 h stats, writes a weekly per-streamer report, updates case-study log. |
| Narrator (Zwoclipp long-form) | Strategist/scriptwriter | Grok scripts + TTS for 65-100 s recaps (D079-D083). |
| Scout (campaign-scout) | Campaign hunter | Ranks campaigns by D070 rules. |
| Outreach (new, later) | Sales DM setter | Drafts the retainer DM with case studies; never sends. |

Loop: detect → judge → render → QA → **zo approves** → publish → stats at 2/24/72 h → brain learns → weekly report → proof log → pitch.

## 4. Dashboard look
Base: zo's reference (Dashnect dark mode): charcoal canvas, slightly lighter rounded cards, left sidebar with icon + label nav, top bar with search, help, round accent "+" button, bell, avatar. Fonts and radii sampled from that reference at build time.
Accent: the orange becomes a **lighter navy blue** (starting value #4C78D0, to tune with zo). Secondary chart hues stay muted (violet, teal, cyan from the reference's Timeline pills).
Hosting: Vercel (zo's answer). Build host-ready; deploy only on zo's go. Before deploy: owner-only magic link (D054), sign-ups off, custom domain, signed 1 h clip links (D056).

## 5. Page map
1. **Overview** — today: live streamers, clips waiting, posts out, views 24 h, Wake Up switch (D055), agent activity strip.
2. **Review** — queue with preview, approve / deny / revise note, before-after card (D077), undo (D058). Board view by stage (Tasks-style columns: Detected, Rendering, Review, Scheduled, Posted).
3. **Analytics** — tabs **Growth** (views, followers, share rate, per platform), **Money** (campaign earnings, Content Rewards 30-min countdown D025, Grok/storage spend vs budget), **Pipeline** (clips detected → approved → posted, QA fails, stuck posts).
4. **Streamers** — roster grid, then one page each. **Lacy first**: header card, live state, per-streamer analytics, Reels/Clips gallery, best performers, brain settings, crop box.
5. **Editor** — trim and captions first (zo's answer): preview, timeline with trim handles, crop box, headline/caption text edits, export to Review. Tracks and effects later.
6. **Schedule** — Timeline-style calendar of queued posts per platform (D088 spacing visible).
7. **Campaigns** — scout results, pursue/ask/avoid.
8. **Library** — Files-style: approved clips, downloads to phone (D021), storage meter.
9. **Settings** — edit rules (D078), platforms, worker/GPU status.

## 6. Widgets from zo's board (ranked by use)
| # | Pin | Take | Goes on |
|---|---|---|---|
| 1 | Video editor, purple/cyan tracks (Toronto) | Media bin left, preview centre, text settings right, Media/Audio/Text tracks with playhead | Editor (main layout) |
| 2 | Tablet editor (Behind the scenes) | Bottom tool bar: Split, Detach audio, Duplicate, Trim; filmstrip track with selected-clip handles; "Selected 3.2s" readout | Editor (controls) |
| 3 | Dashnect dark mode (the reference) | Whole shell; Timeline pills with % chips; Tasks columns; Files folders + storage ring | Shell, Schedule, Review board, Library |
| 4 | Chart card (Week/Month/Max) | Segmented range switch, glow line chart, big number + delta | Analytics, streamer pages |
| 5 | Portfolio overview (gradient header) | Wave chart with hover tooltip, KPI row, ring gauge, two action buttons | Analytics Growth tab |
| 6 | CRM worklist (Jessie Caballero) | Left worklist cards + profile header + tabs (Summary, Analytics, Files, History) | Streamer page layout |
| 7 | Project cards (gradient corner, progress, days left) | Streamer cards with corner tint, progress to goal, "next stream" chip | Streamers grid |
| 8 | Dock "+" menu (Image/Video/Audio/Design/New project) | Accent "+" opens: New clip, Import VOD, Upload to Library, New long-form | Global top bar |
| 9 | Edge rings (73% / 21% / 52%) | Small ring gauges for GPU, storage, Grok spend | Sidebar footer / Overview |
| 10 | Profile + alert cards (Cimpean Rares) | Profile hero with content strip; error card style for failed posts | Streamer header, alerts |

Not used: liquid-glass pills and fintech cards appeared under Pinterest's "more ideas", not on zo's board, so they are left out unless zo wants them for the wildcard.

## 7. Three moodboard concepts (for later, after approval)
- **A Classic** (close to reference): Dashnect shell as-is, navy accent, Overview with stat tiles + wave chart + current-streamer card, Timeline as post schedule.
- **B Studio** (close to reference): same shell, editor-first; streamer pages use the CRM worklist layout; Review as Tasks columns with clip thumbnails.
- **C Wildcard**: floating icon dock with glowing navy "+", gradient header band, ring gauges docked on the right edge, big-number glow charts; still charcoal + navy.
All three: same 9 pages, no overlapping UI, phone layout included.

## 8. Next steps
1. zo approves or edits this blueprint.
2. Log decisions (next ID D091): blueprint adopted, accent value, page map, three-beat edit, case-study log.
3. Build the three moodboards, then the chosen one in `dashboard/`.
