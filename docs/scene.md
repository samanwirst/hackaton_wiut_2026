# Scene layout (`configs/scene_tashkent.json`)

The task describes a fixed camera, but the supplied clips show small framing differences and
brief camera settling. The road layout is a fixed fact of the scene. We draw it once on a
full-resolution frame with `tools/annotation/scene_editor.html` (open the file in a browser, load a frame or a
sample video, draw, export) and save the result as `configs/scene_tashkent.json`. All coordinates
are video pixels; if a video has a different size, coordinates are rescaled from `frame_size`.

There is one layout per camera. `scene.cameras` in `configs/pipeline.yaml` lists them; a video
gets the layout annotated at exactly its size, else one with the same aspect ratio, else the
default `scene.config` (empty: a video from an unknown camera gets no geometry, so only the rules
that need none can fire). `configs/scene_tashkent.json` is the official camera (3840×2160, drawn on
C3905).

For Part A, the annotated layout is registered to the middle frame of each clip with SIFT
features and a RANSAC similarity transform (translation, rotation and uniform scale).
The middle frame avoids the initial settling observed in C3896; random access is permitted
for Part A. The match must have at least 40 inliers, 45% inlier support, broad image coverage,
median residual at most 1.5 thumbnail pixels, scale within 5%, rotation within 3 degrees and
translation within 8% of image dimensions. Weak matches do not inherit this camera's geometry.
This is a single static correction, not continuous camera stabilisation: residual motion or
occlusion can still make a lamp unreadable.

`configs/scene_reference_tashkent.png` is the original C3905 frame 0, resized to 960×540 and
converted to grayscale. It is shipped in the package and never downloaded at inference.
Reproduce it into a new path (the tool refuses overwrites):

```bash
python tools/build_scene_reference.py --video data/samples/C3905.MP4 --out /tmp/scene-reference.png
```

The source original SHA-256 is
`e99072464be42627d7cc83b5a7f6c5149352326e95503338ac289fbb6b537aad`.
No filename-dependent predictions or other same-camera footage are used. The feature matcher
follows the [OpenCV SIFT matching documentation](https://docs.opencv.org/4.13.0/dc/dc3/tutorial_py_matcher.html).
The independently learned direction field stays in its training coordinates: it is **not**
warped as though it were hand-drawn geometry. Part B never calls `load_video_scene`, never
opens a video, and does not consume the registered Part A scene or trajectories.

Every key is optional. A rule whose geometry is missing does not fire.

| Key | Geometry | Used by |
|---|---|---|
| `frame_size` | `[width, height]` of the annotated frame | rescaling |
| `registration` | `{reference: path}` to the shipped reference thumbnail | Part A image-based layout alignment |
| `road` | list of polygons: the carriageway (where vehicles drive; not pavements, not parking bays) | jaywalking, stopped vehicle, congestion, obstacles |
| `road_exclude` | polygons cut out of `road`: medians, traffic islands | same as `road` |
| `crosswalks` | `[{id, polygon, signal?}]` pedestrian crossings; `signal` can colour the visualisation | jaywalking (excluded area), failure to yield (regardless of pedestrian signal) |
| `intersection` | polygon of the junction box | red light (end), stop line, wrong way (ignored inside) |
| `traffic_lights` | `[{id, roi: [x1, y1, x2, y2], kind?, lamps?}]` box around the lamp housing; `kind` is `vehicle` or `pedestrian`; each calibrated `lamps` box must contain its expected hue, not merely a bright background reflection | signal state |
| `signals` | derived signals for heads that face away from the camera (see below) | red light, stop line, jaywalking |
| `stop_lines` | `[{id, line: [[x, y], [x, y]], forward: [dx, dy], light}]` — `forward` is the direction of travel over the line, `light` the id of the light or derived signal that controls it; draw it where vehicles must stop, just before the crossing | red light, stop line, queues at a red signal (not stopped vehicle, not congestion) |
| `solid_lines` | `[{id, polyline}]` continuous markings that must not be crossed | solid line crossing |
| `lanes` | `[{id, polygon, direction: [dx, dy], allowed_turns: ["straight", "left", "right"]}]` | wrong way (overrides the learned field), illegal turn |
| `zones` | `[{id, polygon}]` entry / exit areas at the edges of the junction | illegal turn |
| `prohibited_movements` | `[["zoneA", "zoneB"], ...]` entry → exit pairs that are not allowed | illegal turn |
| `u_turn_prohibited` | polygons where signs or markings explicitly prohibit U-turns; missing means unknown | illegal U-turn |
| `u_turn_allowed` | allowed areas that override a prohibited polygon | illegal U-turn |
| `direction_groups` | `[{id, polygon}]` one region per direction of travel | congestion |
| `parking` | polygons of parking bays / lay-bys | stopped vehicle (excluded) |
| `ignore` | polygons to ignore completely (timestamp overlay, far background) | all |

Headings are in image coordinates (x to the right, y down). A clockwise change of heading on
screen is a right turn for the driver.

## Signals that cannot be seen (`signals`)

Calibrated lamp boxes require saturation ≥80, brightness ≥70 and the expected red/amber/green
hue, with at least 4% supporting pixels. The old brightness-only threshold of 150 missed dim
daylight signals. The lower threshold is paired with a hue check to reject white headlights
and differently coloured objects behind an unlit lamp. Unknown stays unknown; it is not green.
The scoped development review is reproduced with `tools/review_signals.py` and documented in
`reports/scene_review/`. It does not establish event accuracy or full-cycle phase timing.

The camera sees a signal head only from the front. The heads that govern traffic driving towards
the camera face away from it, so their state is derived from heads that can be seen, by the usual
phase logic of a junction:

- vehicles and the pedestrians who cross the perpendicular road walk in the same phase: the vehicle
  signal is green while that pedestrian signal is green, and turns red a fixed clearance after the
  pedestrian signal turned red (flashing green + amber);
- the pedestrians who cross the road of those vehicles are in the conflicting phase: their signal
  is red while the vehicles have green or amber.

```json
"signals": [
  {"id": "avenue", "sources": [{"light": "ped_diag", "red_delay_s": 6.0, "amber_s": 3.0}, {"light": "veh_island"}]},
  {"id": "avenue_crossing", "inverse_of": "avenue", "green_after_s": 2.0, "red_before_s": 4.0}
]
```

`sources` are tried in order at every moment; the first one whose state is known wins (here the
vehicle head on the island, which shows the same phase, covers moments when the pedestrian head is
hidden). `invert: true` on a source swaps red and green. `inverse_of` gives the conflicting phase;
`green_after_s` / `red_before_s` leave the clearance times at both ends as unknown, and no rule
decides anything on an unknown signal. On C3905 the derived `avenue` signal matches the island head
to the frame: green 34.5–72.4 s, amber 72.6–75.4 s, red 75.6–114.4 s.

## What is learned instead (`configs/scene_model_tashkent.npz`)

`python tools/learn_scene.py --videos data/samples/` runs detection and tracking on the sample videos
and stores:

- `road_mask` — the pixels that moving vehicles' wheels covered (used when `road` is not drawn),
- `counts` — per image cell, a histogram of vehicle headings in 12 bins (the direction field used
  for wrong-way detection, congestion grouping and the Part B wrong-way signal),
- `footprints` — the raw coverage counts, for the EDA page.

It also writes `docs/scene_model_tashkent_preview.jpg` (road mask in green, dominant direction
arrows) so the result can be checked by eye.

## Example

```json
{
  "frame_size": [1920, 1080],
  "road": [[[0, 520], [1920, 480], [1920, 1080], [0, 1080]]],
  "crosswalks": [{"id": "cw_north", "polygon": [[700, 540], [1250, 530], [1270, 600], [690, 612]]}],
  "intersection": [[600, 600], [1400, 590], [1500, 900], [500, 920]],
  "traffic_lights": [{"id": "tl_main", "roi": [1502, 188, 1522, 240]}],
  "stop_lines": [{"id": "sl_south", "line": [[640, 930], [1450, 915]], "forward": [0, -1], "light": "tl_main"}],
  "solid_lines": [{"id": "centre", "polyline": [[960, 1080], [975, 700]]}],
  "u_turn_allowed": [],
  "prohibited_movements": [["south", "west"]]
}
```
