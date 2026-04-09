# Spatial Workspace — Quest 3

A mixed-reality spatial productivity app for Meta Quest 3, styled after Apple Vision Pro's visionOS interface. Floating glass panels in your real environment for notes, text editing, and timers.

## Design

The UI follows Apple Vision Pro's design language:
- **Glassmorphism** -- translucent frosted-glass panels with depth
- **Window bar** at the bottom of each panel for grab/move
- **Hand pinch gestures** for selection and interaction
- **Hover highlights** on interactive elements
- **Smooth spring animations** for open/close/resize
- **Spatial snapping** for organized window layouts

## Stack

- **React Three Fiber** + **@react-three/xr** -- React-based 3D/XR rendering
- **Three.js** -- 3D engine
- **@react-spring/three** -- Physics-based animations
- **Vite** -- Dev server with HTTPS (required for WebXR)
- **TypeScript** -- Type safety

## Prerequisites

- **Node.js 18+** on your Mac
- **Quest 3** and Mac on the same Wi-Fi network
- **Quest 3 browser** (supports WebXR with passthrough)

## Getting Started

```bash
# 1. Generate HTTPS certificates (required for WebXR)
npm run generate-cert

# 2. Install dependencies
npm install

# 3. Start dev server
npm run dev
# or: bash scripts/dev-serve.sh

# 4. Open in Quest 3 browser
# Navigate to https://<your-mac-ip>:5173
# Accept the self-signed certificate warning
# Tap "Enter AR" to launch the spatial workspace
```

## Development Workflow

1. Edit code on your Mac -- Vite hot-reloads in the Quest browser
2. The app enters `immersive-ar` mode with passthrough enabled
3. Panels float in your real environment, controlled by hand tracking
4. Use the hand menu (palm up) to spawn new panels

## Production Build

```bash
npm run build
npx vite preview --host
```
