# Deploying PixDoctorV2 flight control

Topology:

- Jetson: PixDoctorV2 GUI, Xbox gamepad over USB.
- Raspberry Pi 4B: `mavlink-router`, Pixhawk USB `/dev/ttyACM0` at 115200.
- UDP 14550 for PixDoctorV2, UDP 14551 for QGroundControl.
- Both GCS links can run at once. Never enable QGroundControl joystick while
  PixDoctorV2 is flying: two `MANUAL_CONTROL` streams fight over the vehicle.

Connection flow: the Pi is the only device with a USB cable to the Pixhawk.
`mavlink-router` opens `/dev/ttyACM0` and serves every GCS that connects to
UDP 14550. PixDoctorV2 uses `udpin:0.0.0.0:14550`, which only listens, so the
GUI never needs the Pi IP. The router learns the Jetson address from the first
packet the GUI sends (its GCS heartbeat) and forwards vehicle telemetry back.

## Two supported wirings

| Wiring | Pixhawk USB goes to | `[link] endpoint` | Setup script |
| :--- | :--- | :--- | :--- |
| With router | Raspberry Pi 4B running `mavlink-router` | `udpin:0.0.0.0:14550` | `deploy/setup_pi.sh` + `deploy/setup_jetson.sh --router` |
| Direct | Jetson (no Pi in the path) | `/dev/ttyACM0` (Linux) or `COMx` (Windows) | `deploy/setup_jetson.sh --direct` |

Only one GCS may own the serial port. Do not plug the Pixhawk into the Jetson
while `mavlink-router` is running on the Pi: two owners of the autopilot's
serial link cause command loss and failsafe trips. Pick one wiring per dive.

## Setup scripts

Both are idempotent; re-run them after changing cables or ports.

```bash
# Raspberry Pi 4B
sudo ./deploy/setup_pi.sh                     # /dev/ttyACM0, 115200
sudo ./deploy/setup_pi.sh --device /dev/ttyACM1

# Jetson
./deploy/setup_jetson.sh --router             # uses the Pi
./deploy/setup_jetson.sh --direct             # Pixhawk on Jetson USB
./deploy/setup_jetson.sh --direct --device /dev/ttyACM0
./deploy/setup_jetson.sh --router --autostart # also install the systemd unit
```

`setup_pi.sh` installs `mavlink-router`, writes
`/etc/mavlink-router/main.conf` with the chosen device, adds the user to
`dialout`, and enables the service. `setup_jetson.sh` installs
`requirements.txt`, adds the user to `input` and `dialout`, sets the link, and
optionally installs `pixdoctor.service` with the real user, path and Python.

Switch wiring later without reinstalling:

```bash
python3 deploy/switch_link.py show
python3 deploy/switch_link.py router
python3 deploy/switch_link.py direct --device /dev/ttyACM0   # or COM5 on Windows
```

`switch_link.py` rewrites only `endpoint` and `auto_connect` inside `[link]`;
comments, `[control]`, `[claw]` and line endings stay untouched.

## Raspberry Pi 4B (MAVLink router)

1. Fresh 64-bit Pi OS. Give the Pi a fixed address (DHCP reservation in the
   router, or a static address in `dhcpcd.conf`). Write it down; the Jetson
   needs it.

2. Install the router package:

   ```bash
   sudo apt update
   sudo apt install mavlink-router
   ```

3. Connect the Pixhawk by USB and confirm the device name:

   ```bash
   ls /dev/ttyACM*
   ```

   `mavlink-router.conf` assumes `/dev/ttyACM0`. If the device appears as
   `/dev/ttyACM1`, change `Device =` in the copied config.

4. Fix USB permissions so the service can open the port:

   ```bash
   sudo usermod -aG dialout "$USER"
   ```

5. Copy the config and unit:

   ```bash
   sudo mkdir -p /etc/mavlink-router
   sudo cp deploy/mavlink-router.conf /etc/mavlink-router/main.conf
   sudo cp deploy/mavlink-router.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now mavlink-router
   ```

6. Verify:

   ```bash
   systemctl status mavlink-router
   ss -lunp | grep 14550
   ```

   `ss` must show the router listening on UDP 14550. Baud 115200 matches the
   Pixhawk USB CDC link used by the ArduSub build.

## Jetson (PixDoctorV2)

1. Install Python 3.11 or newer. `tomllib` is built in; `requirements.txt`
   installs `tomli` automatically on older Python.

2. Copy this repository to `/opt/PixDoctorV2` and install:

   ```bash
   cd /opt/PixDoctorV2
   pip install -r requirements.txt
   ```

3. Check `config.toml`:

   ```toml
   [link]
   endpoint = "udpin:0.0.0.0:14550"
   auto_connect = true
   ```

   Keep `udpin` for the router setup. Use `udpout:<pi-ip>:14550` only if the
   Jetson must push and the router is configured to accept a client.

4. Start the GUI:

   ```bash
   python3 main.py
   ```

   The GUI connects at launch and waits for the router. The top strip shows
   `PIXHAWK: udpin:0.0.0.0:14550` with a non-zero packet rate when the link is
   up.

5. Optional autostart in the desktop session:

   ```bash
   sudo cp deploy/pixdoctor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now pixdoctor
   ```

   Edit `User`, `WorkingDirectory` and `XDG_RUNTIME_DIR` in the unit first.
   The unit runs the GUI on `DISPLAY=:0`; the desktop session must exist.

## Gamepad on Linux

Connect the controller over USB. The GUI picks the pad whose name contains
`Xbox`; it falls back to the first device. Xbox and PlayStation layouts are
recognized. Read access to `/dev/input/event*` needs the `input` group:

```bash
sudo usermod -aG input "$USER"
```

Log out and back in after changing groups. The SDL backend also needs
`SDL_VIDEODRIVER=dummy`, which the GUI sets itself.

## Direct Jetson to Pixhawk (no router)

USB cable from the Pixhawk straight to the Jetson. Nothing else may hold the
port.

1. Find the device:

   ```bash
   ls /dev/ttyACM*
   ```

   Normally `/dev/ttyACM0`. On Windows it is a `COMx` port.

2. Add yourself to `dialout`:

   ```bash
   sudo usermod -aG dialout "$USER"
   ```

   Log out and back in.

3. Point `config.toml` at the port:

   ```toml
   [link]
   endpoint = "/dev/ttyACM0"
   auto_connect = true
   ```

   Serials are opened at 115200, the ArduSub USB CDC rate. The UDP-only
   `[link]` values are ignored for a serial endpoint.

4. Start the GUI with `python3 main.py`. The top strip shows
   `PIXHAWK: /dev/ttyACM0`. The 20 Hz loop, claw bits and failsafes are
   identical; only the transport changes.

5. With `endpoint` left as `udpin:...`, the built-in auto-detector already
   finds `/dev/ttyACM*` on its own. Setting the serial endpoint just skips the
   scan and connects at launch.

The Pi is not used in this wiring. Stop `mavlink-router` on the Pi, or leave
the Pixhawk unplugged from it.

## Link check without the GUI

From the Jetson, confirm the router path before starting the GUI:

```bash
python3 -c "from pymavlink import mavutil; m=mavutil.mavlink_connection('udpin:0.0.0.0:14550'); m.wait_heartbeat(); print('heartbeat', m.target_system, m.target_component)"
```

A printed heartbeat means Pi, serial link and UDP path all work. For the
direct wiring, use `mavutil.mavlink_connection('/dev/ttyACM0', baud=115200)`.

## First-connect checklist

- `FRAME_CONFIG=5` for SimpleROV-4 (reboot required).
- `GRIP_ENABLE=1`, `GRIP_TYPE=3`
- `BTN0_FUNCTION=140` (close), `BTN1_FUNCTION=139` (open),
  `BTN2_FUNCTION=141` (stop)
- The top strip shows `CLAW: --` until the first firmware message. Arming is
  refused while claw parameters are missing or wrong; fix them in the Params
  view or load `deploy/simplerov4.parm`.
- Press `FLY: OFF` once to enable stick control. It stays off after restart.

## Safety

- FLY off: no `MANUAL_CONTROL` is streamed.
- Gamepad lost or silent for `gamepad_timeout_s` (0.25 s): axes go neutral
  immediately, the vehicle disarms after `gamepad_disarm_s` (1 s).
- Link lost (no autopilot heartbeat for `link_timeout_s`): no commands are
  sent; the loop resumes without arming.
- Quit while armed: the GUI asks, then sends neutral axes and disarms.
- The firmware pilot-input and GCS failsafes remain the backstop.