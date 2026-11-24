# Reference Breakdown: Kai Calls Speed

Studied 2026-11-23. Source: YouTube Short `8i6kxJbin3c`, "Kai Cenat Got Donated $300 Just To Call Speed", channel Snickerly. 39.9M views, 763k likes at study time. 14.45 s, 1080x1920, 60 fps.

Local copy, frames, spectrogram: `C:\clip-work\refs\8i6kxJbin3c` (download approved by Zo for analysis only). All timings below are measured (ffmpeg scene detection, per-frame mean colour, RMS per 100 ms, faster-whisper word timestamps), not eyeballed.

Overall grade: about 8/10. See also [[Reference Clip Style]], [[Edit Playbook]], [[Decision Log]].

## Timeline

| Time (s) | Shot | Effect / audio |
|---|---|---|
| 0.00-1.60 | Wide, blur fill | Green tint 0.8-1.1 on "$300" |
| 1.60, 1.97 | Hard cuts, tighter each | Pauses between words removed |
| 3.70 | Close-up, `*SPEECHLESS*` | Scale bump, red-orange flash 3.7-4.2, low boom replaces the silence |
| 4.60 | Close-up, "that was 300 gang" | - |
| 5.83 | Back to wide, phone in hand | - |
| 7.18 | Wide, `*CALLS SPEED*` | Audio drops to about -40 dB RMS; ring around 9.0; 2 s of waiting |
| 9.35 | Voicemail | Band-limited phone voice; captions switch to magenta |
| 11.2-11.8 | Payoff, "oh my god" | Full white flash fading through red, boom, sustained low bed to the end |
| 13.37 | "You wasted 300 bro" | Ends; loops straight back into the opening "$300" |

Cut times: 1.60, 1.97, 3.70, 4.60, 5.83, 7.18, 9.35, 13.37. Average shot about 1.8 s.

## Blurred background

- Used only on wide shots. Sharp layer is a roughly 4:5 crop of the cam, scaled to full width. Top and bottom bands (about 13% each) are a heavily blurred copy of the same frame, moving with it. No dimming beyond what the source already has.
- Close-ups fill the full 9:16 frame, so no blur there.
- Purpose: keeps the subathon countdown and the room in frame without black letterbox bars.

## Face framing

- No smooth tracking. Each cut gets its own fixed crop with the face centred horizontally; zoom level changes on the cut.
- The crop change between shots stands in for camera movement and hides the removed pauses.

## Colour effects

- Green on "$300" (0.8-1.1): a brief colour grade, mostly visible on the white ceiling. Money = green.
- Red-orange on `*SPEECHLESS*` (3.7-4.2): stronger, paired with a scale bump.
- White flash then red fade on the payoff (11.2-11.8): the largest effect, saved for the largest moment.
- Effects escalate across the clip: green, then red, then white flash.

## Captions

- One word at a time, condensed white caps with a black box, placed mid-face (eye/headset level on wides, nose/mouth on close-ups).
- Speaker colour code: white = Kai, magenta box = voicemail voice.
- Asterisk action tags (`*SPEECHLESS*`, `*CALLS SPEED*`) narrate beats with no speech.

## Sound

- Low boom at 3.7 and at 11.3, both on the two biggest beats.
- Phone ring around 9.0.
- Voicemail audio is band-limited (phone sound).
- From 11.4 a sustained low bed runs to the end.
- Loudness swings about 30 dB (RMS -13 to -45).

## What works

- Fast pacing; dead air removed.
- Every silent beat is filled with an effect, a sound or a tag.
- Booms line up with the two peak moments.
- Seamless loop: last line "wasted 300" feeds the first line "$300".

## What is weak

- Captions cover the mouth, which hides the reaction.
- Green tint is faint enough to read as a colour glitch.
- 7.2-9.1 is 2 s of ringing at low volume: drop-off risk.
- Large volume swings.

## Against our decisions

- Punch-ins between crops: conflicts with D112 (no zooms).
- Flash and boom: conflict with D052 / D087 (flash and whoosh off).
- One-word mid-face captions: differ from D048 (3 words per line, bottom margin).

Usable without changing any decision: blur fill on wide shots, a second caption colour for a second speaker, asterisk action tags, removing pauses with hard cuts, loop-friendly endings. None adopted yet; that is Zo's call.
