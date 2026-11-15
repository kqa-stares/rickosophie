"""Put Rick's trained timbre (Applio / RVC model, assets/private/voice/rick.pth + rick.index) on a voice track.

  <Applio's python> tools/rvc.py <input.wav> <output.wav>        (APPLIO = folder of the Applio checkout)

Same settings as the tests the owner validated (pitch 0, index rate 0.5, protect 0.33, rmvpe, contentvec).
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE = ROOT / "assets" / "private" / "voice"


def main(src, dst):
    applio = Path(os.environ.get("APPLIO", ROOT / ".applio"))
    r = subprocess.run([sys.executable, "core.py", "infer", "--pitch", "0", "--index-rate", "0.5", "--volume-envelope", "1",
                        "--protect", "0.33", "--f0-method", "rmvpe", "--input-path", str(Path(src).resolve()),
                        "--output-path", str(Path(dst).resolve()), "--pth-path", str(VOICE / "rick.pth"),
                        "--index-path", str(VOICE / "rick.index"), "--export-format", "WAV", "--embedder-model", "contentvec"],
                       cwd=applio, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not Path(dst).exists():
        sys.exit(f"Rick's voice conversion failed:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    print("Rick's timbre applied ->", dst)


if __name__ == "__main__":
    main(*sys.argv[1:3])
