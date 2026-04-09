import { useState, useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";
import type { Mesh } from "three";

interface TimerProps {
  width: number;
  height: number;
}

/**
 * Spatial timer/clock widget — visionOS-style.
 * Shows current time and a stopwatch with start/stop/reset.
 * Circular progress ring animates around the display.
 */
export function Timer({ width, height }: TimerProps) {
  const [time, setTime] = useState("00:00:00");
  const [clock, setClock] = useState("");
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startTimeRef = useRef(0);
  const ringRef = useRef<Mesh>(null);

  // Update clock display
  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date();
      setClock(
        now.toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: true,
        })
      );
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Stopwatch logic
  useFrame(() => {
    if (running) {
      const now = performance.now();
      const totalMs = elapsed + (now - startTimeRef.current);
      const totalSec = Math.floor(totalMs / 1000);
      const hrs = Math.floor(totalSec / 3600);
      const mins = Math.floor((totalSec % 3600) / 60);
      const secs = totalSec % 60;
      setTime(
        `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
      );

      // Rotate progress ring
      if (ringRef.current) {
        ringRef.current.rotation.z = -((totalMs % 60000) / 60000) * Math.PI * 2;
      }
    }
  });

  const handleStart = () => {
    startTimeRef.current = performance.now();
    setRunning(true);
  };

  const handleStop = () => {
    if (running) {
      setElapsed((prev) => prev + (performance.now() - startTimeRef.current));
      setRunning(false);
    }
  };

  const handleReset = () => {
    setRunning(false);
    setElapsed(0);
    setTime("00:00:00");
  };

  const RING_RADIUS = Math.min(width, height) * 0.3;

  return (
    <group>
      {/* Title */}
      <Text
        position={[0, height / 2 - 0.02, 0.001]}
        fontSize={0.016}
        color="#ffffff"
        anchorX="center"
        anchorY="top"
        font={undefined}
      >
        Timer
      </Text>

      {/* Current clock */}
      <Text
        position={[0, height / 2 - 0.05, 0.001]}
        fontSize={0.012}
        color="#888899"
        anchorX="center"
        anchorY="top"
        font={undefined}
      >
        {clock}
      </Text>

      {/* Progress ring background */}
      <mesh position={[0, 0, 0.001]}>
        <ringGeometry args={[RING_RADIUS - 0.005, RING_RADIUS, 64]} />
        <meshBasicMaterial color="#333355" transparent opacity={0.3} />
      </mesh>

      {/* Progress ring indicator */}
      <mesh ref={ringRef} position={[0, 0, 0.002]}>
        <ringGeometry args={[RING_RADIUS - 0.005, RING_RADIUS, 64, 1, 0, Math.PI * 0.1]} />
        <meshBasicMaterial color="#7777ff" transparent opacity={0.8} />
      </mesh>

      {/* Timer display */}
      <Text
        position={[0, 0.01, 0.002]}
        fontSize={0.028}
        color="#ffffff"
        anchorX="center"
        anchorY="middle"
        font={undefined}
      >
        {time}
      </Text>

      {/* Control buttons */}
      <group position={[0, -(height / 2) + 0.06, 0.002]}>
        {/* Start/Stop */}
        <group
          position={[-0.06, 0, 0]}
          onClick={(e) => {
            e.stopPropagation();
            running ? handleStop() : handleStart();
          }}
        >
          <mesh>
            <circleGeometry args={[0.02, 24]} />
            <meshPhysicalMaterial
              color={running ? "#ff6b6b" : "#4ecdc4"}
              transparent
              opacity={0.8}
              roughness={0.3}
            />
          </mesh>
          <Text position={[0, 0, 0.001]} fontSize={0.009} color="#ffffff" anchorX="center" anchorY="middle" font={undefined}>
            {running ? "Stop" : "Start"}
          </Text>
        </group>

        {/* Reset */}
        <group
          position={[0.06, 0, 0]}
          onClick={(e) => {
            e.stopPropagation();
            handleReset();
          }}
        >
          <mesh>
            <circleGeometry args={[0.02, 24]} />
            <meshPhysicalMaterial
              color="#888899"
              transparent
              opacity={0.5}
              roughness={0.3}
            />
          </mesh>
          <Text position={[0, 0, 0.001]} fontSize={0.009} color="#ffffff" anchorX="center" anchorY="middle" font={undefined}>
            Reset
          </Text>
        </group>
      </group>
    </group>
  );
}
