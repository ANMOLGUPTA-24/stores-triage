"""Assemble a narrated demo video from captured frames and synthesised speech.

How the draft cut was made, kept so it can be remade.

There is no screen recorder and no ffmpeg on this machine, and the console runs
as a native Wayland window, so X11 capture (ximagesrc) returns black. The frames
therefore come from browser screenshots, the voice from libespeak-ng through
ctypes, and GStreamer muxes the two into WebM.

The result is a slideshow with a synthetic voice. It is a stand-in: the
narration text is the same one in notes/video-script.md, so re-recording it in a
human voice and swapping narration.wav gives the same cut without the robot.

    python3 scripts/build_demo_video.py     # writes narration.wav and seq/
    gst-launch-1.0 -q -e \
      multifilesrc location=seq/f%05d.jpg index=0 caps="image/jpeg,framerate=2/1" \
        ! jpegdec ! videoconvert ! vp8enc deadline=1 cpu-used=8 ! queue \
        ! webmmux name=mux ! filesink location=demo.webm \
      filesrc location=narration.wav ! wavparse ! audioconvert ! audioresample \
        ! vorbisenc ! queue ! mux.
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

lib = ctypes.CDLL("libespeak-ng.so.1")
SYNTH_CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
buf = []
def cb(wav, n, ev):
    if wav and n > 0:
        buf.extend(wav[i] for i in range(n))
    return 0
c_cb = SYNTH_CB(cb)
rate = lib.espeak_Initialize(2, 0, None, 0)
lib.espeak_SetSynthCallback(c_cb)
lib.espeak_SetVoiceByName(b"en-gb")
lib.espeak_SetParameter(1, 168, 0)   # rate, words per minute
lib.espeak_SetParameter(2, 100, 0)   # volume

FPS = 2
os.makedirs("seq", exist_ok=True)
for f in glob.glob("seq/*.jpg"):
    os.remove(f)

all_samples, idx, timeline = [], 0, []
for frame_i, text in BEATS:
    buf.clear()
    b = text.encode()
    lib.espeak_Synth(b, len(b) + 1, 0, 0, 0, 0x1000, None, None)
    lib.espeak_Synchronize()
    seg = list(buf)
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
