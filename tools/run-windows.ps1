param(
    [string]$Disk = "$PSScriptRoot\..\out\desktop\ruxeonrx-1.0.qcow2",
    [ValidateSet('tcg','whpx')][string]$Acceleration = 'tcg',
    [switch]$SafeMode,
    [ValidateSet('dsound','sdl','none')][string]$Audio = 'dsound'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Disk)) { throw "Desktop disk missing: $Disk" }
$diskPath = (Resolve-Path -LiteralPath $Disk).Path
$qemu = (Get-Command qemu-system-x86_64 -ErrorAction Stop).Source
$extra = @()
if ($SafeMode) { $extra += @('-fw_cfg', 'name=opt/ruxeonrx/safe,string=1') }
& $qemu -accel $Acceleration -m 3072 -smp 2 -drive "file=$diskPath,format=qcow2,if=virtio" -vga std -device ich9-intel-hda -device hda-duplex,audiodev=audio0 -audiodev "$Audio,id=audio0" -display gtk -nic user -serial "file:$PSScriptRoot\..\out\desktop\windows-serial.log" -monitor none @extra
exit $LASTEXITCODE
