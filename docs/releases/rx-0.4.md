# RX 0.4: Session integration and hardening

The roadmap has no named RX 0.4 milestone, so this release is the integration
bridge between native app management and the RX 0.5 usable alpha.

It adds `rx-sessiond` service health, crash accounting, automatic safe-mode
selection after three failures, explicit recovery, validated settings, and
unprivileged device inventory. Accessibility-safe defaults include keyboard-
friendly focus, high-contrast selection, and text scaling from 0.75 to 3.0.
Telemetry remains disabled unless explicitly enabled.

Acceptance is covered by `test_rx04_session_hardening.py`.
