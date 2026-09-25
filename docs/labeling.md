# Labeling the sample videos (our dev set)

Without labels we would be tuning blind, so every sample video is annotated by hand with
[`tools/label_tool.html`](../tools/label_tool.html) and scored with the official `evaluate.py`.

## Workflow

1. Open `tools/label_tool.html` in Chrome, Edge or Safari (no server needed).
2. Load a video; check that the FPS box matches the video (25 for this camera).
3. Pick a class (hotkeys `1`–`0`, `q`, `w`, `t`, `y`), go to the start frame, press `[`; go to the
   end frame, press `]`. Arrow keys step one frame, `Shift`+arrow one second.
4. Select a row and press `s` / `e` to move its start / end to the current time; `Del` removes it.
5. Export JSON. Load the file again to continue, or to add the next video to the same file.
6. Save the merged file as `labels/dev_labels.json` and commit it.

Labels are auto-saved in the browser per video name, but export often.

## Conventions (from the task — follow them exactly)

| Class | Start | End |
|---|---|---|
| accident | first frame contact is visible | all involved objects stop moving or leave the frame |
| near_miss | onset of the evasive action (braking / swerving starts) | road users are clear of each other |
| red_light | front of the vehicle crosses the stop line on red | vehicle leaves the junction or the frame |
| wrong_way | vehicle enters the opposing lane | returns to a correct lane or leaves the frame |
| illegal_u_turn | vehicle starts turning | completes the turn |
| stopped_vehicle | vehicle stops (only if it then stays ≥ 10 s, not queueing at a signal) | moves again or is removed |
| jaywalking | pedestrian steps onto the road outside a crossing | pedestrian leaves the road |
| failure_to_yield | vehicle enters the crossing while a pedestrian is on / stepping onto it | vehicle leaves the crossing |
| illegal_turn | vehicle starts turning | completes the turn |
| solid_line_crossing | a wheel crosses the solid line | vehicle is fully in the new lane |
| stop_line | vehicle stops past the stop line on red (not in the junction) | signal turns green |
| congestion | queue stops moving (all lanes of one direction) | queue clears |
| road_obstacle | obstacle appears | obstacle is removed |
| fire_smoke | first visible smoke | smoke clears or the video ends |

Rules that matter for the score:

- **Two events of the same class at the same time are one segment** covering both (the tool warns
  about same-class overlaps).
- Events of different classes may overlap (a wrong-way car that crashes = `wrong_way` + `accident`).
- If an event is still going on when the video ends, the end is the video duration.
- Boundaries are matched at IoU 0.3, 0.5 and 0.7, so a second too early or late on a 5-second event
  already costs the 0.7 threshold. Step frame by frame around start and end.

## Quality control

- Two people label each video independently; a third resolves differences over 1 s.
- Keep a short note of every doubtful case in `labels/notes.md` (time, what happened, decision), so
  the rules and the labels follow the same interpretation.
- Never label from the model's output; look at the video.
