## Requirements

- Python 3.12+

## Getting started

Install Poetry globally if it is not already available:
```
python3 -m pip install poetry
```
Install the project dependencies:
```
make install
```

Start telemetry collection and the local API:
```
make start
```

Telemetry is now being recorded, and the API is available on port 8000. The
collector and API deliberately run in one process so the live dashboard can
receive the captured frames.

## Live DDU (second-screen dashboard)

The Live DDU uses the existing UDP collector—there is no second GT7 receiver.
Start the combined collector and API process from the project root (all three
commands below use this same combined process):

```
make live
```

In another terminal, start the React interface:

```
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open [http://localhost:5173/live](http://localhost:5173/live), or use `http://<computer-LAN-IP>:5173/live` from a second device on the same network. The page shows connection state, speed, gear, RPM/shift band, throttle, brake, race position/lap, GT7 lap times, fuel, temperatures, tyre temperatures, and measured tyre slip. `LOCKUP` and `WHEELSPIN` require speed, matching pedal input, and at least 18% measured signed slip; they are measurement alerts, not coaching. GT7's suggested gear is explicitly labelled as a raw game suggestion.

`make live` keeps collection, persistence, the REST API, and `/ws/live` in one process so the in-memory latest-frame hub is shared. The WebSocket sends at most 25 frames per second and drops superseded frames rather than buffering history. It reports `waiting` before the first packet and `stale` after approximately 1.5 seconds without a fresh packet. Override the existing defaults when necessary with `GT7_PS_IP`, `GT7_PS_PORT`, `GT7_API_HOST`, and `GT7_API_PORT`.

This MVP is local-only and has no authentication. It shows raw GT7 data only: no live delta, track inference, AI coaching, or strategy claims. Fuel and mechanical values may be unavailable for some cars or game states.

## Telemetry web interface

First, start the combined local collector and API from the project root:
```
make web
```

In another terminal, start the React interface:
```
cd frontend
npm install
npm run dev
```

Open the address shown by Vite (by default, [http://localhost:5173](http://localhost:5173)).
The interface automatically selects the most recently recorded session. Select Lap A and Lap B to compare speed, throttle, brake, and gear. It displays the recorded car ID and locally catalogued details when available. The collector does not yet record the track reliably, so the interface explicitly shows `Track not recorded` when the session has no real `track_id`. You can manually choose a track layout to overlay lap trajectories; this selection never identifies the session's track.

The delta-time chart aligns laps by normalized physical distance, not sample number. Its convention is **Lap A minus Lap B**: a positive value means Lap A is behind. The chart is intentionally unavailable when telemetry has insufficient or inconsistent distance coverage; it does not infer a delta for those laps.

The trajectory panel also includes a raw-sample playback. It advances both lap markers using each lap's recorded duration and captured sample order, with play/pause, reset, seeking, and 1×/2×/4×/10× speeds. This replay is separate from distance-aligned delta calculation and is intended for inspection of the recorded data, including gaps.

The linked telemetry explorer uses BokehJS. Speed, throttle, brake, gear, and a validated delta share a physical-distance x-range: pan, wheel zoom, box zoom, and reset operate together. Hover inspection shows the recorded distance, metric value, and reconstructed elapsed time for each lap; missing/discontinuous samples are displayed as gaps.

The racing-line overlay is visual evidence only. It uses green for throttle at or above 10%, red for brake at or above 10%, and purple for coasting. Lap A is solid and Lap B is lighter. Sparse labels mark detected braking starts (B), minimum-speed/apex vicinity (A), and throttle resumptions (T), with speed; detailed captured values remain available on hover. Pairwise event-distance claims stay unavailable unless the guarded distance-alignment comparison validates both laps.

## Telemetry charts

After recording at least one lap, create an overview of the most recent session:
```
make graphs
```

The image is saved at `images/<session_id>/telemetry-overview.png`.
To create a chart for a specific session, use `make graphs SESSION=<session_id>`.
