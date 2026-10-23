# Third-party components

The FrameCheck application code is MIT licensed. It uses these separately licensed components:

- [Python](https://www.python.org/): Python Software Foundation License. A Windows bundle includes the Python runtime and its license.
- [NumPy](https://numpy.org/): BSD-3-Clause, with additional notices for bundled numerical libraries. The dependency's complete license notices are included with a bundled distribution.
- [Pillow](https://python-pillow.github.io/): MIT-CMU (HPND) and notices for bundled libraries. Complete installed dependency license files are included with a bundled distribution.
- [Tcl/Tk](https://www.tcl.tk/): Tcl/Tk license. Runtime license files are included with a bundled distribution.
- [PyInstaller](https://pyinstaller.org/): GPL with its bootloader distribution exception. Used only to build the optional executable; its relevant notices are retained.
- [FFmpeg command-line tools](https://ffmpeg.org/legal.html): LGPL/GPL depending on the user's selected build. The external `ffmpeg` and `ffprobe` executables are not redistributed by this project; the separate PyAV library case is described below.
- [OpenCV](https://opencv.org/): its installed wheel's main and third-party notices are included in the Windows bundle.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and [CTranslate2](https://github.com/OpenNMT/CTranslate2): local speech inference. The speech model is downloaded separately; no model weights are included in the release.
- [Hugging Face tokenizers](https://github.com/huggingface/tokenizers), Hub client and Xet client, [ONNX Runtime](https://github.com/microsoft/onnxruntime), and their installed dependencies retain the license files collected with each build.
- [PyAV](https://github.com/PyAV-Org/PyAV): the wheel includes FFmpeg shared libraries. The tested 19.0.2 Windows wheel reports FFmpeg 9.0.2, LGPLv3 or later. These library binaries are included for the speech dependency; the standalone `ffmpeg.exe`/`ffprobe.exe` command-line tools remain external. Relevant library license texts and upstream source references accompany the bundle. Users may replace compatible shared libraries.

Dependency versions and the actual collected license files accompany each binary release. This summary does not replace the complete notices. Dependency installation and first-use speech models require downloads; video comparison itself performs no network requests. Optional agent-based visual interpretation follows the selected provider's privacy terms.
