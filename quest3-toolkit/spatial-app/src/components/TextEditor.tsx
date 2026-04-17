import { useState } from "react";
import { Text } from "@react-three/drei";

interface TextEditorProps {
  width: number;
  height: number;
}

/**
 * Spatial text editor panel — visionOS-style.
 * Displays editable text content on a glass surface.
 * In WebXR, text input is handled through a floating keyboard
 * or voice input. This provides the visual display layer.
 */
export function TextEditor({ width, height }: TextEditorProps) {
  const [content] = useState(
    "Welcome to the Spatial Text Editor.\n\n" +
    "This panel floats in your real environment.\n" +
    "Grab the bottom bar to reposition it.\n\n" +
    "In a full implementation, this would\n" +
    "support keyboard input, voice dictation,\n" +
    "and hand gesture text selection."
  );
  const [cursorVisible, setCursorVisible] = useState(true);

  // Blink cursor
  useState(() => {
    const interval = setInterval(() => setCursorVisible((v) => !v), 530);
    return () => clearInterval(interval);
  });

  const lineCount = content.split("\n").length;

  return (
    <group>
      {/* Title bar */}
      <Text
        position={[0, height / 2 - 0.02, 0.001]}
        fontSize={0.016}
        color="#ffffff"
        anchorX="center"
        anchorY="top"
        font={undefined}
      >
        Text Editor
      </Text>

      {/* Editor background — slightly darker for contrast */}
      <mesh position={[0, -0.01, 0.001]}>
        <planeGeometry args={[width - 0.02, height - 0.06]} />
        <meshPhysicalMaterial
          color="#0d0d1a"
          transparent
          opacity={0.4}
          roughness={0.5}
        />
      </mesh>

      {/* Line numbers */}
      {Array.from({ length: lineCount }, (_, i) => (
        <Text
          key={i}
          position={[-(width / 2) + 0.025, height / 2 - 0.055 - i * 0.018, 0.002]}
          fontSize={0.01}
          color="#666688"
          anchorX="right"
          anchorY="top"
          font={undefined}
        >
          {String(i + 1)}
        </Text>
      ))}

      {/* Line number divider */}
      <mesh position={[-(width / 2) + 0.035, -0.01, 0.002]}>
        <planeGeometry args={[0.001, height - 0.06]} />
        <meshBasicMaterial color="#333355" transparent opacity={0.5} />
      </mesh>

      {/* Text content */}
      <Text
        position={[-(width / 2) + 0.045, height / 2 - 0.05, 0.002]}
        fontSize={0.011}
        color="#e0e0ff"
        anchorX="left"
        anchorY="top"
        maxWidth={width - 0.08}
        lineHeight={1.6}
        font={undefined}
      >
        {content}
      </Text>

      {/* Blinking cursor */}
      {cursorVisible && (
        <mesh position={[-(width / 2) + 0.045, height / 2 - 0.05 - lineCount * 0.018, 0.003]}>
          <planeGeometry args={[0.001, 0.013]} />
          <meshBasicMaterial color="#7777ff" />
        </mesh>
      )}

      {/* Status bar */}
      <group position={[0, -(height / 2) + 0.025, 0.002]}>
        <mesh>
          <planeGeometry args={[width - 0.02, 0.02]} />
          <meshBasicMaterial color="#1a1a2e" transparent opacity={0.5} />
        </mesh>
        <Text
          position={[-(width / 2) + 0.02, 0, 0.001]}
          fontSize={0.008}
          color="#888899"
          anchorX="left"
          anchorY="middle"
          font={undefined}
        >
          {`Ln ${lineCount}  |  UTF-8  |  Spatial Mode`}
        </Text>
      </group>
    </group>
  );
}
