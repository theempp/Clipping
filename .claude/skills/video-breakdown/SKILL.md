---
name: video-breakdown
description: Make a visual study breakdown of a video or pipeline run (stageshow demo). Use only when the user asks for a video breakdown.
---
# Video Breakdown
Purpose: help the user study how the system and clips perform. Built with `stageshow`.
1. Source facts only from stored data (transcript, detector scores, stats). Do not re-watch or re-process the video.
2. Structure: hook > key moments with timestamps and why each worked > metrics > lessons.
3. One concise stageshow scene per section; load stageshow references only for the components used.
4. Styling comes from the project `references/` design intel, never defaults. No references yet = ask first.
5. Save to `breakdowns/<date>-<slug>/`; feed lessons to `learn`.
