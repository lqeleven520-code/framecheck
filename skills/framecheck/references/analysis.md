# Deliver a reusable video breakdown

Read `analysis.json`, `storyboard.json`, `transcript.srt`, the unit start/middle/end images and relevant shot images. Inspect video clips or more frames when action, expression or camera behavior cannot be established from these samples. Merely running the program is not visual understanding; do not describe unseen events, sounds or ranges as observed.

## Evidence

- Delivery units cover the source timeline in 4–15 second ranges, preferring detected cuts and avoiding subtitle boundaries when possible. They are not a claim that original shots last 4–15 seconds. A source shorter than four seconds retains its actual duration.
- Use the recorded display aspect, including rotation and pixel aspect ratio. Never impose 21:9 or a fixed 15-second duration.
- Original shot times remain in `shots`; unit fragments reference them on a relative timeline. A long uncut shot can span units. Do not call that a detected cut.
- Motion is an estimated global 2D transform. Qualify inferred pan, tilt, push or zoom and distinguish moving subjects when evidence permits. Low fit support means uncertain, not static by default.
- Preserve subtitle/ASR provenance and wording. ASR can mishear or omit words and can output traditional Chinese. Correct only against actual audio. Do not invent speakers or dialogue. A cue crossing a unit boundary remains one utterance; do not describe it as repeated performance.

## Output structure

Keep a separate block per unit, using the existing `storyboard.json` text fields and `breakdown.txt` structure:

1. Unit number, source time range, actual aspect and real duration.
2. **整体导演设计** contains **画面风格 only**, based on observable medium, texture and rendering. Do not add film tone, lighting-design, director-intent or sound-restriction sections.
3. **参考对象**: observable setting, visible people and objects. Use neutral labels when names are unknown; do not invent identities, exact ages or asset IDs.
4. **空间与首帧**: visible spatial anchors and main subjects at the actual start.
5. **分镜时间轴**: shot number/time, 景别／视角, 机位／运镜, 摄影参数, 画面内容, 人物动作, 人物神态, 台词／声音 and 场景光影.
6. **本片段结束画面**: the observed last-frame state, without planning another video.

Use only these general observation fields. Do not add video handoff methods, inter-shot continuation instructions, prior-video reference snippets, next-video starting states, production handoffs or private production prompts.

Frame size and FPS are measured. Exact lenses, aperture, equipment, offscreen intent and unseen emotions are not recovered by the engine. Describe visible actions and expressions without inventing motives. Unsupported fields stay explicitly unassessed; do not present the engine's empty notes as a finished visual interpretation.

## Save

The offline report supports local text editing and downloads. An agent can copy `storyboard.json`, update only text fields after inspection, preserve IDs, time ranges and provenance, then run `export-notes` to produce a reusable per-unit text file. Deliver that reviewed text and the evidence report, stating what was viewed, the dialogue source and any incomplete inspection.

The standalone CLI does not automatically fill semantic notes. Agent visual inspection depends on the selected agent's capabilities and privacy settings. Do not include private skills, personal production rules or private examples in public packages.
