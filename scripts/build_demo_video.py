"""Assemble a narrated demo video from captured frames and synthesised speech.

No screen recorder and no ffmpeg on this machine: the frames come from the
browser tool, the voice from libespeak-ng, and GStreamer muxes them. The result
is a slideshow with a synthetic voice - a draft to re-voice, not a final cut.
"""
import ctypes, glob, os, shutil, struct, subprocess, sys

FRAMES = sorted(glob.glob("/tmp/claude-chrome-screenshots-dsVgcN/screenshot-*.jpg"),
                key=lambda p: int(p.rsplit("-", 1)[1].split(".")[0]))
assert len(FRAMES) >= 10, f"expected 10 frames, found {len(FRAMES)}"

# (frame index, narration)
BEATS = [
 (0, "A part drops below its reorder level at a locomotive works, and an alert fires. "
     "The stores officer has to answer a question the alert cannot: is this real? "
     "The evidence lives in three systems that do not talk to each other, and he gets "
     "twenty of these a day. "
     "Raise a duplicate indent against stock already in transit, and the works pays "
     "expedite rates on stock it already owns. Miss a real shortage, and a locomotive "
     "sits idle. "
     "These two alerts are the same problem from the outside. Nine days of stock against "
     "nine and a half. One is real. One is not."),
 (1, "This is the agent working. Every line is a real tool call against a real Postgres, "
     "through M C P."),
 (2, "Four subagents, dispatched at once. Not four subtasks: four competing explanations "
     "for why this shortage might be on paper only. A consumption spike. Stock already "
     "inbound. A duplicate indent someone raised last week. A part being superseded. "
     "Every one of them is trying to prove the shortage is not real. Ruling all four out "
     "is what makes it real."),
 (3, "The arithmetic happens in a sandbox. Tested Python fits the draw rate, builds a "
     "lead time distribution from what the vendor actually did, and solves the stockout "
     "date. No number in this system comes from the model."),
 (4, "Now the important part. The header has gone amber: blocked on you. "
     "Four and a half units a day, runs dry in nine days, and the vendor takes thirty one. "
     "That shaded stretch is three weeks with an empty bin before the vendor turns up. "
     "The card carries the exact mail that will go out, not a summary of it, and one line "
     "saying what would change its mind: if that unconfirmed consignment is confirmed and "
     "lands in time, do not raise this indent. "
     "The agent never asks for permission bare. An approval is only worth something if a "
     "person can check it in five seconds."),
 (5, "Approve, and the indent is raised. Then it stops again, separately, for the vendor "
     "mail. Approving the order did not pre-approve the letter."),
 (6, "Indent raised, vendor mailed, run logged."),
 (7, "Second alert. Same shape, same shortfall, same nine days."),
 (8, "But this time two hypotheses come back positive. There is already an open indent, "
     "and a consignment in transit that lands before the stock runs out. "
     "So the agent does nothing. "
     "There is no amber anywhere, and no approve button. Nothing to approve, because "
     "nothing should happen. The run log records no action as an outcome, not an error. "
     "Most agents cannot do this: they are built to act, so declining looks like failure. "
     "Being confidently right that nothing should happen is the harder half of the "
     "problem, and the half that saves the money."),
 (9, "It is trustworthy because it is not the model's opinion. Adjudication is ordinary "
     "Python with unit tests, and this exact case passes with no model involved at all. "
     "True Forge ran the agent loop, the M C P calls, the sandbox, the parallel subagents "
     "and the approval pause. What I brought is the tool server over Postgres, the skill, "
     "the analysis code, and the adjudication: the part that decides. "
     "You can drive both of these yourself, in a browser, in about a minute."),
]

VOICE = os.environ.get("PIPER_VOICE", "en_GB-alba-medium")
PIPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tts/bin/piper")
VOICES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices")


def synth(text: str) -> tuple[list[int], int]:
    """One beat of narration through piper, returned as samples.

    espeak-ng was the first draft and sounded like it. A neural voice is the
    difference between a demo that reads as finished and one that reads as a
    placeholder, and presentation is a sixth of the score.
    """
    out = "/tmp/_beat.wav"
    subprocess.run([PIPER, "-m", VOICE, "--data-dir", VOICES, "-f", out],
                   input=text.encode(), check=True, capture_output=True)
    import wave
    with wave.open(out) as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    return list(struct.unpack("<%dh" % (len(raw) // 2), raw)), rate


FPS = 2
os.makedirs("seq", exist_ok=True)
for f in glob.glob("seq/*.jpg"):
    os.remove(f)

all_samples, idx, timeline, rate = [], 0, [], 22050
for frame_i, text in BEATS:
    seg, rate = synth(text)
    seg += [0] * int(rate * 0.6)          # a beat of silence between sections
    all_samples.extend(seg)
    secs = len(seg) / rate
    for _ in range(max(1, round(secs * FPS))):
        shutil.copy(FRAMES[frame_i], f"seq/f{idx:05d}.jpg")
        idx += 1
    timeline.append((frame_i, round(secs, 1)))

data = struct.pack("<%dh" % len(all_samples), *all_samples)
with open("narration.wav", "wb") as f:
    f.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt ")
    f.write(struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16))
    f.write(b"data" + struct.pack("<I", len(data)) + data)

total = len(all_samples) / rate
print(f"narration {total//60:.0f}m {total%60:04.1f}s   frames {idx} at {FPS}fps")
for i, (fr, s) in enumerate(timeline):
    print(f"  beat {i+1}: frame {fr}  {s}s")
