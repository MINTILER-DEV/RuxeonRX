# Development quick start

See [desktop-alpha.md](desktop-alpha.md) for prerequisites, build details,
Windows launch, real guest acceptance and the external tester checklist.

On the Linux server:

```sh
sudo apt-get install qemu-system-x86 qemu-utils xorriso openssh-client python3
cd ~/RuxeonRX
./tools/rx-build bootstrap
./tools/rx-build build
./tools/rx-build test
./tools/rx-build run --vnc
```

For remote display from Windows, forward the server's loopback VNC port:

```powershell
ssh -N -L 5901:127.0.0.1:5901 mntweb@192.168.1.101
```

Connect a VNC viewer to localhost:5901. To run locally on Windows, copy the
single built qcow2 disk and use `tools/run-windows.ps1`.

The desktop image includes its own kernel and bootloader. There is no host
kernel permission workaround or initramfs argument to configure.

Run code tests with:

```sh
python3 -m unittest discover -s tests/unit -v
python3 -m unittest discover -s tests/integration -v
```

In a guest terminal, `tools/rxctl` connects to the session daemon for app and
permission changes. Offline tests use isolated temporary state. App launch in
the graphical session starts a process, not a simulated command log.
