# Godox C100 GHDK

Godox C100 GHDK is a tool that changes the five firmware sounds on a Godox C100.

This kit does not contain Godox firmware. You must add the official firmware file.

**WARNING:** A bad firmware image can stop the camera. The camera can refuse to start. A card with stock firmware does not always repair this.

## Contents

| Path | Description |
|------|-------------|
| `tools/c100.py` | Command-line tool |
| `tools/c100_gui.py` | Desktop window |
| `sounds/meow.wav` | Sample sound |
| `sounds/icanfly.wav` | Sample sound |

## Firmware that you must add

1. Get the official C100 firmware from Godox.
2. Put the file at `firmware/ORIGINAL/gp_cardvr_upgrade.bin`.
3. Do a check of the SHA-256 digest. The digest must be `769733179a81f943c300c4e1a49cec95ff9d2c793618fe037fc8575e95279b64`.

The tool refuses to start if the digest is not this value.

Copy the official file to the card as `RESTORE_ORIGINAL.bin`. Do not overwrite `firmware/ORIGINAL/`.

## Sound slots

All slots are 11.025 kHz mono.

A long file is cut. A short file has silence after the sound.

| Slot | File | Use | Length |
|------|------|-----|--------|
| 1 | `BEEP.WAV` | Menu | 182 ms |
| 2 | `CAMERA.WAV` | Shutter | 301 ms |
| 3 | `CLICK.WAV` | Browse and keys | 255 ms |
| 4 | `POWERON_AUDIO.WAV` | Power on | 719 ms |
| 5 | `TEST.WAV` | Not used in stock | 1.25 s |

Slot 5 is 8-bit. Slots 1 through 4 are 16-bit.

You can point shutter or power on to slot 5.

Then the clip can be 1.06 s at 16-bit.

Volume is a percent. 100 is no change. The range is 25 to 200.

## Start the tool

You must have Python 3.

```
python3 tools/c100.py gui
```

Or use the command line.

```
python3 tools/c100.py status
python3 tools/c100.py sounds --2 sounds/meow.wav --stage
python3 tools/c100.py sounds --test-for poweron --5 sounds/icanfly.wav --volume 70 --stage
python3 tools/c100.py stage stock
```

## Write firmware to the card

The card must be on a card reader. Do not use the camera USB port for this step.

1. Put `RESTORE_ORIGINAL.bin` on the card if it is not there.
2. Write `gp_cardvr_upgrade.bin` with the tool.
3. Eject the card.
4. Remove power from the camera. Set the switch to off.

5. Put the card in the camera.
6. Connect USB-C power.
7. Set the switch to photo. Wait 10 through 15 seconds.
8. Set the switch to off. Disconnect power.
9. Set the switch to photo again.

The camera reads `gp_cardvr_upgrade.bin` and then removes that file.

**CAUTION:** Do not add a write hook or other code change to the firmware extra. That change can stop the camera.

## Reset hole

The hole next to the USB-C port is the reset hole.

If the camera does not respond, push the reset hole with a thin pin.

**NOTE:** A reset does not install firmware.

## License

The tool and the two WAV files are MIT. Godox firmware is not in this kit. Godox owns that firmware.
