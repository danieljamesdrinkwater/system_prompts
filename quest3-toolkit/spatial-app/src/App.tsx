import { Canvas } from "@react-three/fiber";
import { XR, createXRStore } from "@react-three/xr";
import { XRScene } from "./components/XRScene";

const xrStore = createXRStore({
  depthSensing: true,
  hand: { model: false }, // We handle hand visuals ourselves
});

export function App() {
  return (
    <>
      <button
        id="enter-xr"
        onClick={() => xrStore.enterAR()}
      >
        Enter Spatial Workspace
      </button>
      <Canvas
        style={{ width: "100vw", height: "100vh" }}
        gl={{ antialias: true, alpha: true }}
        camera={{ position: [0, 1.6, 0], fov: 70 }}
      >
        <XR store={xrStore}>
          <XRScene />
        </XR>
      </Canvas>
    </>
  );
}
