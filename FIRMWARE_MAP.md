# Godox C100 firmware map

This file is a map of C100 firmware V1.0.0. It records hardware, flash rules, image layout, addresses, and dump results.

This kit does not contain official stock firmware. Get the official file from the Godox site. See README.md. This kit includes `firmware/gp_cardvr_upgrade.BAYER.bin`.

**CAUTION:** A change to the firmware extra can stop the camera. A card with stock firmware does not always repair this.

## Hardware

| Piece | What it is |
|---|---|
| Product | Godox C100 |
| SoC | GeneralPlus car-DVR (USB MSDC VID `0x1B3F` PID `0x8301`) |
| Sensor | GalaxyCore GC2083 (live SCCB chip id `0x2083`) |
| Sensor out | RAW Bayer 8/10 only (datasheet). The chip has no YUV mode. |
| Live config | Window 1936×1088. Out 1920×1080. First pixel R (RGGB). Line 1833 (30 fps table). `0x023e=0x98`. |
| Still path | GC2083 MIPI → CSI `0xD0000000` → CDSP `0xD0800000` (demosaic) → encoder YUV `0x321800` → JPEG through `write()` |

Bayer is on this board. It lives on MIPI/CSI. It is not in the encoder buffer.

Proof build: `firmware/gp_cardvr_upgrade.BAYER.bin` (SIDECAR6T). SHA-256 starts with `4423e89e0b7da538`. That file is in this kit.

## Flash rules

- Official updater name: `gp_cardvr_upgrade.bin`. The camera removes the file after a good flash.
- Locked stock vault: `firmware/ORIGINAL/`. SHA-256 `769733179a81f943c300c4e1a49cec95ff9d2c793618fe037fc8575e95279b64`. Do not overwrite this file.
- Card restore copy: `RESTORE_ORIGINAL.bin` (same hash). Leave that file on the card.
- Card volume on this host: `/Volumes/Untitled 2`. Write the image. Run `sync`. Do a hash check. Eject the card.

Flash cycle:

1. Remove power from the camera.
2. Set the switch to off.
3. Set the switch to photo. Wait about 10 s.
4. Set the switch to off.
5. Set the switch to photo again.

If preview stops, USB does not mount. Use a card reader. Write stock firmware as `gp_cardvr_upgrade.bin`.

## Image layout

- File size: 1 841 152 bytes.
- APP links at VA `0`. File offset = VA + `0x10200`.
- ARM little-endian.
- Unused `OutputFormatNoSupport` cave at VA `0x1390` to `0x15e8`. That cave is the write-hook home.
- `get_capture_buf` is at VA `0x15a78`. That address is not the cave end `0x15e8`. Do not overlay it.

## Sound slots

Resource pack at `0x170000`. Cluster size is 512 bytes. All slots are 11.025 kHz mono.

| Slot | File | Offset | Bits | Length | Use |
|---|---|---|---|---|---|
| 1 | `BEEP.WAV` | `0x170E00` | 16 | 182 ms | Menu |
| 2 | `CAMERA.WAV` | `0x171E00` | 16 | 301 ms | Shutter |
| 3 | `CLICK.WAV` | `0x173A00` | 16 | 255 ms | Browse and keys |
| 4 | `POWERON_AUDIO.WAV` | `0x1B0400` | 16 | 719 ms | Power on |
| 5 | `TEST.WAV` | `0x1B7000` | 8 | 1.25 s | Not used in stock |

Clusters: BEEP=7, CAMERA=`0xf`, CLICK=`0x1d`, POWERON=`0x202`, TEST=`0x238`.

You can point shutter or power on to slot 5. Then the clip can be 1.06 s at 16-bit.

## Way in

**CAUTION:** Do not add a write hook or other code change to the firmware extra. That change can stop the camera.

The stable hook is `write()` at VA `0x98448`. JPEG stills go out as 128 KB chunks. The first write of 4 KB or more is the still.

Start from `SIDECAR6B`. Hex-edit extras after `0x1518`. Branch from `0x1484` (just before `close`).

Do not assemble the hook again. SIDECAR7 and SIDECAR8 opened a 32 KB zero file and dropped the JPEG.

| API | VA |
|---|---|
| `open` | `0x980d4` (flags `0x601`. Does not replace an existing dump. Use a new name.) |
| `close` | `0x97748` |
| `write` | `0x98448` |
| `unlink` | `0x983ec` |
| `malloc` | `0x4d218` → `0x56520` |
| `sccb_read` | `0x4b720(reg16, &u8)`. Fail stores `0xFF`. |
| `sccb_write` | `0x4ac5c` |
| SCCB handle | `*[0x12416c]` (live: `0x208f00`) |

Rules that caused crashes:

- Extra must return to `0x1490` (`pop {r0-r3}`), not `0x1494`. 6Q and 6R skipped that pop and died (32 KB zeros).
- Marker at `0x14b4` must be exactly 8 bytes. A 7-byte marker cuts the image by one byte and shifts `stream_on`.
- Nested `write()` is safe. One-shot flag at ctx `0x14d8+0x1c` skips the sidecar.
- Do not read CDSP MMIO (`0xD0800000`) inside `write()`.
- Do not read CSI MMIO (`0xD0000000`) from stream-on (6U: preview brick). Recover with a card reader.
- Do not call unused raw helpers `0x89440` / `0x890f4` from stream-on.

YUVDUMP extra skeleton (change literals only):

```
0x1484  b 0x1518
0x1518  write N bytes from a checked DRAM pointer
        close sidecar fd
        b 0x1490
```

To write a fixed address (BSS or a known buffer): nop the `ldr r3,[r3]` at `0x1520` (`mov r3,r3`) and set the src literal at `0x1568`.

## Address book

### Sensor (GC2083, SCCB)

| Addr | Role | Live |
|---|---|---|
| `0x03f0` / `0x03f1` | Chip id | `0x20` `0x83` |
| `0x0015` / `0x0d15` | Mirror / first pixel | `0x00` → R (RGGB) |
| `0x0d0d` / `0x0d0e` | win height | `0x0440` = 1088 |
| `0x000f` / `0x0010` | win width | `0x0790` = 1936 |
| `0x0195` to `0x0198` | out window | 1920×1080 (8-aligned, RAW10-legal) |
| `0x0d05` / `0x0d06` | line length | `0x0729` = 1833 (30 fps table) |
| `0x023e` | last init write | `0x98` |
| `0x03fe` | page | `0x00` |

Init tables: 25 fps `0xd527c`, 30 fps `0xd6c00` (`{u16 reg, u8 val, pad}`, end `0xffff/0xff`).

### SoC / pipeline

| Addr | Role |
|---|---|
| `0xD0000000` | SYSTEM/CSI. `0x88fc0` rawFmt mux (`+8`, `+0x1c`) |
| `0xD0800000` | CDSP. `+0x240` / `+0x228` bits. `+0x304` packed 1920×1080 (`0x438780`). `+0x310` raw DMA (`0x50000000` unused). |
| `0x128130` | `CaptureRaw_Mode` |
| `0x1314b0` | Capture object (`get_capture_buf` `r0`). `+0x8c` → slots `0x20e600`, `+0x90=4`, `+0x94=3`, `+0xe0=0` |
| `0x12416c` | SCCB handle pointer → `0x208f00` |
| `0x12824c` | Small CSI-ish object → `0x316b40` (tiny. `+0x15b0` walk = abort) |
| `0x1317b4` | Encoder object |
| `0x1317c8` | Encoder `+0x14` = YUV pointer `0x321800` (not the pixels) |
| `0x131fcc` | Display / OSD object (192×128) |
| `0x14d8` | Sidecar ctx (fd at `+0x14`, one-shot at `+0x1c`) |
| `0x4bde4` | `stream_on` (`bl 0x8d498`). Do not hang CSI copies here |
| `0x15a78` | `get_capture_buf`. Returns slot`+8` or `0x50000000` if no raw. |
| `0x15b2c` | Success tail: `ldr r0,[r2,#8]` then pop. 73 hooks this |

### Encoder object (`0x1317b4`) live

| Off | Value | Meaning |
|---|---|---|
| `+0x04` / `+0x0c` | 1920 | width |
| `+0x08` / `+0x10` | 1080 | height |
| `+0x14` | `0x321800` | YUV frame (Y 1920×1080 then chroma, 4 147 200 bytes) |
| `+0x18` | `0x618e40` | 64 bytes past NV12-sized YUV. End or next. Not a second frame. |
| `+0x38` / `+0x48` | `0x218600` / `0x20c600` | heap node headers, not pixels |

YUV dump size `0x3f4800` = 1920×1080×2. First 2 073 600 bytes = Y (matches the still).

### Other RAM (not Bayer)

| Where | What |
|---|---|
| `0x19c200` + 10 × `0x8000` | SD exFAT cluster cache (VBR `EB 76 90` `EXFAT   ` in first slot) |
| `0x20e630` | Capture slot (48 B, stable at shutter). `+8=0x68b6d0` (in YUV arena), `+0x10=0x25800` (153600 = 1920×80), `+0x18=0x7050b030` (not low DRAM) |
| `0x316b40` | Tiny header: zeros, then `0x0007800a` (1920 / 10-bit-ish), `0x00000c3c` |

## Builds

Hashes are SHA-256 prefixes (16 hex) unless noted. All files are 1 841 152 bytes.

This kit includes `firmware/gp_cardvr_upgrade.BAYER.bin`. Other research builds are not in this kit. Official stock firmware is not in this kit.

### Keep / products

| File | Hash prefix | Notes |
|---|---|---|
| `ORIGINAL/gp_cardvr_upgrade.bin` | `769733179a81f943…79b64` full | Stock vault. Not in this kit. |
| `firmware/gp_cardvr_upgrade.BAYER.bin` | `4423e89e0b7da538` | In this kit. Same as 6T. Chip id `0x2083`. |
| `YUVDUMP.bin` | `63ce133ba003056f` | Same as 6I. Full YUV `DUMPE.BIN` |
| `SIDECAR6B.bin` | `a1955c5733a0417d` | Proven JPEG sidecar base |
| `MEOW.bin` / `MUTED.bin` | `8ee20cf8…` / `dcb0f1cc…` | WAV experiments |

### Working RAM / SCCB peeks (6B extra, return `0x1490`)

| Build | Hash prefix | Dump | Result |
|---|---|---|---|
| 6S | `513f4c660a5c03be` | `DUMPO` | Handle `0x208f00` |
| 6T / BAYER | `4423e89e0b7da538` | `DUMPQ` | Chip id `0x2083` |
| 6V | `82a845759214b6c3` | `DUMPV` | Live Bayer window / RGGB / 30 fps |
| 6X | `e19e75b530673199` | `DUMPP` | `*[0x12824c]=0x316b40` |
| 6Y | `0e3b7419b0551f5d` | `DUMP2` | 32 B at `0x316b40` (tiny object) |
| 6Z | `6d87925e4e1702f3` | `DUMP3` | 256 B BSS: 10×32 KB FS pool |
| 70 | `18f0428a4f0e16f4` | `DUMP4` | `0x19c200` = exFAT VBR, not mosaic |
| 71 | `047b3ab7ea199faf` | `DUMP5` | Encoder object. YUV ptr `0x321800`. |
| 72 | `3b9695c1cc2a6a4e` | `DUMP8` | `0x20c600`/`0x218600` heap headers |
| 73 | `53317a10a31eecfe` | `DUMP9` | JPEG-start slot snap (`+8` inside YUV) |
| 74 | `214433816029899a` | `DUMP0` | 48 B at `0x20e630`: `+8` still `0x68b6d0`, `+0x18` still `0x7050b030`, `+0x10=0x25800` (153600 = 1920×80) |
| 75 | `43ffa9b0c8e012f0` | `DUMP1` | `get_capture_buf` entry: obj `0x1314b0`, slots `0x20e600`, mode `4`, count `3`, raw queue `+0xe0=0` |

### Dead / do not restage as-is

| Build | Why |
|---|---|
| SIDECAR1 | WAV cave = prefetch abort |
| SIDECAR2 to 5 | open/close/pop mistakes |
| SIDECAR7/8 | Reassembled hook → 32 KB zeros, no JPEG |
| PURERAW2/3 | No JPEG |
| 6L | Alloc `+0x310`, CDSP never writes (`A5`) |
| 6M to 6P | Stream-on CDSP kicks. Stream dies. |
| 6Q | SCCB + second file + `b 0x1494` (stack smash) |
| 6R | Handle-only extra, same `b 0x1494` |
| 6U | CSI copy at stream-on. First image NULL-deref. Flashed copy bricked preview. |
| 6W | Walked `obj+0x15b0` off a small block. Shutter abort. |

6C to 6K / PURERAW1 / DUMPX lineage: JPEG sidecar variants and CDSP peeks. Useful dumps stay under `card/`. Do not treat them as Bayer.

## Bayer

1. The sensor is a GC2083. The live program is 1080p30 RAW Bayer (RGGB, RAW10-legal width).
2. CDSP demosaics before the encoder. `CaptureRaw_Mode=1` does not switch `0x321800` to mosaic.
3. CDSP raw DMA `+0x310` stays `0x50000000` (not programmed). Our buffer never filled.
4. `get_capture_buf` treats `0x50000000` as no raw. JPEG pick (`+8`) landed inside the YUV arena.
5. No RAW10-sized (2 592 000) pointer sits next to the encoder object.
6. SIDECAR75 / `DUMP1`: capture obj `0x1314b0` (304 bytes before encoder `0x1317b4`), slot array `0x20e600`, mode `4`, 3 YUV slots, `+0xe0` raw queue = 0. This product does not set up a raw frame list. JPEG cannot see Bayer unless you create that path.

## Still open (Bayer pixels)

1. Earlier than JPEG pick, not stream-on. CDSP frame-done or CSI completion into DRAM. 73 is JPEG-start. Still YUV.
2. `0x88fc0` rawFmt mux. Hardware write. Last.
3. CSI register snapshot from a context that is not `stream_on` and is not `write()`.

Do not: more CDSP kicks, CSI MMIO at `0x4bde4`, hook rebuilds, `b 0x1494`.

## Sidecar dump index

These files are research dumps. They are not in this kit.

| File | Bytes | Content |
|---|---|---|
| `DUMP6` / `DUMPX` | 4160 | JPEG peek + `C100SID6` |
| `DUMPB` | 24 KB | 192×128 OSD plane |
| `DUMPD` / `DUMPE` | 4 151 360 | Full YUV (`YUVDUMP`) |
| `DUMPQ` | 4176 | BAYER proof `CID1` + `0x2083` |
| `DUMPV` | 4184 | Live format regs |
| `DUMPO` / `DUMPP` / `DUMP2` / `DUMP3` | peeks | Handle / CSI obj / BSS window |
| `DUMP4` | 36 928 | exFAT cache |
| `DUMP5` | 4416 | Encoder object |
| `DUMP8` | 4288 | Heap headers |
| `DUMP9` | 4176 | JPEG-start slot |
| `DUMP0` | 4208 | Slot `0x20e630` (74). `+8=0x68b6d0`, `+0x10=0x25800`, `+0x18=0x7050b030` |
| `DUMP1` | 4192 | Queue snapshot (75). obj `0x1314b0`, slots `0x20e600`, mode 4, count 3, e0=0 |

YUV dump (`DUMPE.BIN`): 64-byte header + 4 KB JPEG + 4 147 200 bytes from `0x1317c8`. First 2 073 600 bytes = 1920×1080 Y. Next 2 073 600 bytes = chroma (4:2:2-sized). Mode=1 does not turn this buffer into mosaic.

Decode YUV: `python3 tools/decode_yuv_dump.py card/DUMPE.BIN`

Decode SCCB: `python3 tools/decode_sccb_dump.py card/DUMPQ.BIN`

Those decode scripts are not in this kit.

## Official firmware

Godox publishes C100 firmware V1.0.0 here:

https://www.godox.com/firmware-Cameras-Printers/
