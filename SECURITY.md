# Security and privacy

FrameCheck runs locally and does not start a server, upload media or use telemetry. It invokes FFmpeg with argument arrays, never a shell. Keep FFmpeg and Python dependencies updated; parsing untrusted media has the risks of the installed decoder.

Reports omit absolute paths but include file names, SHA-256 values and selected frame images. Inspect reports before sharing them. Existing output folders are refused instead of cleared. Cancellation and errors preserve an explicitly incomplete report where possible.

Please use GitHub private vulnerability reporting if it is enabled for this repository. Otherwise open an issue asking for a private contact channel without including exploit details or sensitive media. Do not post secrets in a public issue.
