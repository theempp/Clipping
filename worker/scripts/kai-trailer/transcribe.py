import whisperx, json, sys
m = whisperx.load_model("large-v3", "cuda", compute_type="float16")
a = whisperx.load_audio("audio.wav")
r = m.transcribe(a, batch_size=16, language="en"); json.dump(r, open("raw.json","w"))
al, md = whisperx.load_align_model(language_code="en", device="cuda")
r = whisperx.align(r["segments"], al, md, a, "cuda")
json.dump(r, open("tx.json","w"))
for s in r["segments"]: print(f'{s["start"]:6.2f}-{s["end"]:6.2f} {s["text"].strip()}')
