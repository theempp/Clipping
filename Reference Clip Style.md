# Reference Clip Style

Studied 2026-11-22 from 7 clips zo picked as the target style. All are TikTok reposts of GTA 6 streamer moments. Every file ends with a ~3.5 s TikTok watermark end card; lengths below exclude it.

## The 7 references

| Clip | Streamer | Moment | Length | Layout |
|---|---|---|---|---|
| LUDL0884 | Kai Cenat | Celebrates being first to finish GTA 6 story mode, plane flies off | 8.8 s | Split: cam top, game bottom; ends full-frame face close-up |
| CCGG2854 | Kai Cenat | "I wonder how Kai Cenat is liking GTA 6": shocked face | 8.6 s | Letterboxed 16:9 stream with chat, headline in top black bar |
| WZSF5613 | Lacy | Meets a cat in GTA 6, then reaction-meme cutaways | 8.1 s | Full 16:9 cam+game, then black-and-white meme inserts |
| OHCK2301 | CaseOh | Dives head first into shallow water to lose cops, "wasted" | ~18.5 s | Split cam/game, cuts to full cam facepalm, full "wasted" screen |
| OFRE2718 | Kai Cenat + Rakai | Kai loses it: Rakai still on mission 1 after 5 hours | 16.8 s | Two-streamer split (Kai top, Rakai bottom) |
| XVEA7279 | IShowSpeed | No GTA VI marathon: "I waited 20 damn years! Wait, I'm only 21..." | 27.5 s | Single cam, headline + quote caption mid-frame |
| KZJR9718 | NickEh30 | Gets angry after an NPC swears, chases and fights NPC | 73.2 s | Split cam top, game bottom, whole clip |

## Concept

One clip = one absurd, instantly readable situation. The headline says the whole story before you watch: who, what happened, why it is funny. Video then proves it. No setup, no context needed, no stream knowledge needed.

Recurring angles:
- **Firsts and records**: "OFFICIALLY the FIRST person to ever COMPLETE..."
- **Fails with a punchline**: dive into shallow water, "wasted".
- **Streamer vs streamer**: Kai roasting Rakai being stuck.
- **Quote that contradicts itself**: "waited 20 years... I'm only 21".
- **Wholesome or weird game moment**: Lacy meets a cat.
- **Streamer emotion vs game NPC**: Nick angry at a swearing NPC.

## Emotion

Main notes: **disbelief, hype, second-hand embarrassment, wholesome laugh.** Every clip lands on a big face: wide eyes, mouth open, hand over mouth, facepalm, grin into the camera. The streamer's face is the payoff, the game is the evidence. Tone is playful and teasing, never mean.

## Hook

- Hook is the **text headline**, on screen from frame 1 to the end. 1 to 3 lines, 6 to 18 words.
- Formula: **[Streamer name] + [action/reaction verb] + [specific absurd detail]**, often with a number ("after 5 HOURS", "20 damn years") or a superlative ("FIRST", "STILL").
- CAPS on 1 to 3 power words only (OFFICIALLY, FIRST, COMPLETE, LOSES IT, STILL).
- Ends with one emoji: 😂 😭 👀 ☠️ 😹❤️. Emoji sets the emotion.
- Alt form: a short setup line plus the quote in quotation marks ("I wonder how Kai Cenat is liking GTA 6" 😂).
- Video starts mid-action. No intro, no black frame, no "wait for it". First second already shows the face or the action.

## Captions

- **None of the 7 use word-by-word subtitles.** Text is one static headline only.
- Style A (5 of 7): TikTok native text box: black text in a white rounded box, sans serif medium, centred, sitting on the seam between cam and game (about 40-50% height) or just under the top edge.
- Style B: white text with thin dark outline/shadow, no box (Speed, Kai letterbox).
- Style C: highlighted quote in a red box with white text under the headline (Speed).
- Text width about 80-90% of frame, never covers the face.
- This conflicts with D048/D050 (always-on word captions). See proposal below.

## Framing

- 9:16 vertical. Default = **split screen: face cam top ~40-45%, gameplay bottom ~55-60%.** The headline sits on the seam.
- Cut to **full-frame face close-up** at the reaction peak (Kai grin, CaseOh facepalm). Cut to **full-frame game** for the game payoff ("wasted").
- Two streamers on call: stack both cams (one top, one bottom).
- Lower effort versions (letterboxed 16:9 with chat, or square) exist but read weaker. We do the split.

## Pacing and length

- Sweet spot **8 to 18 s** (5 of 7). Story clips up to ~30 s; a 70 s+ clip only when it is a continuous chain of escalating moments (Nick chase).
- Shape: hook state (0-1 s) → event (1-6 s) → reaction peak → **end within ~1 s after the peak**. No outro, no lingering. Short clips loop cleanly.
- Few cuts. Mostly continuous source footage; cuts only to swap layout at the peak.

## Sound

- Original stream audio, loud and clear (mean about -12 to -20 dB, peaks at 0 dB). Screams/laughs are the peak.
- No added music in 6 of 7. One (Kai first-to-finish) runs dense, constant-loud audio throughout, likely a hype edit.
- Game SFX left in when they are the punchline ("wasted" sting).
- Not transcribed: the cloud box cannot download a Whisper model. Spoken lines are inferred from on-screen text.

## Edits and extras

- Reaction-meme cutaways (black-and-white zoomed faces of other streamers) used once as a punchline (Lacy cat). Fun but optional; needs a meme library.
- No zooms, no progress bars, no emojis floating, no sound effects beyond source.
- Creator watermark (@handle) small near the top-left. Ours goes on as a small handle, never over the face.

## Rules for Clipp

**Detector**
1. Look for: face reaction spike (chat burst + audio peak) tied to a clear game event (death, "wasted", mission fail/complete, NPC interaction, first/record).
2. Also flag streamer-on-streamer banter (call with another roster creator) and self-contradicting quotes.
3. Window: start 0.5-1 s before the event, end 0.5-1.5 s after the reaction peak. Target 8-18 s; allow up to 30 s; >30 s only if chat stays hot across several peaks.

**Judge (Grok)**
1. Must write a headline in the formula above: name + verb + absurd specific detail, 6-18 words, 1-3 CAPS power words, one closing emoji.
2. Drop if the moment needs context to understand, if there is no visible face reaction, or if the payoff is not inside the window.
3. Score up: GTA 6, firsts/records, numbers, streamer-vs-streamer, wholesome-weird, big face.

**Renderer**
1. Default layout: split, cam top ~42%, game bottom ~58%, headline on the seam (white rounded box, black text).
2. Optional layout swap at the peak: full-frame face (or full-frame game if the game is the punchline).
3. Duo layout when two cams are present.
4. Keep source audio, normalise to about -14 LUFS. No music, no SFX by default (fits D052).
5. Hard cut at the end. No outro card.

## Proposal (needs zo)

Make the **static headline the default caption** and turn word-by-word captions (D048/D050) **off by default**, testable per clip. Reason: none of the 7 references use them, and they would cover the face/game seam where the headline lives. If zo agrees this becomes D072.
