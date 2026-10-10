# Contributing

Read `docs/development/desktop-alpha.md` and the architecture decisions before
changing public contracts. Use Python 3 standard-library-first code, explicit
errors, structured IPC, atomic state replacement, and no shell interpolation of
app commands. Keep generated images, caches, keys and proprietary installers out
of git. Public manifests and IPC use versioned contracts.

Run `python3 -m compileall -q services shell sdk tools tests`, unit and integration
discovery, and the real guest acceptance for image/session changes. Keep failures
and screenshots available for review. Test security boundaries with malicious
inputs and actual executable behavior rather than only emitted success strings.

Use issues labeled `bug`, `security`, `accessibility`, `build`, `desktop`, or
`alpha-feedback`; releases follow capability gates rather than calendar dates.
Version `0.5.0-alpha` denotes the QEMU native desktop alpha.
