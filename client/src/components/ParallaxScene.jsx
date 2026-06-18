import React, { Suspense, useState, useEffect, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { useTexture } from '@react-three/drei';
import * as THREE from 'three';

// Standard static image fallback to use when loading or if WebGL is unavailable
function StaticFallback({ imageUrl, className, style }) {
  return (
    <img 
      src={imageUrl} 
      className={className} 
      alt="Drill down visualization fallback" 
      style={{ ...style, display: 'block', width: '100%', aspectRatio: '16/9', borderRadius: '12px' }} 
    />
  );
}

// Robust Error Boundary to handle WebGL contexts, canvas crashes, or texture loading failures
class CanvasErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error("WebGL Canvas Error Boundary caught an error:", error, errorInfo);
  }

  // Reset error state if the main imageUrl changes (so we can retry rendering WebGL for the new page)
  componentDidUpdate(prevProps) {
    if (prevProps.imageUrl !== this.props.imageUrl && this.state.hasError) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

// Proactive listener for browser WebGL Context Lost events inside R3F
function ContextLostHandler({ onContextLost }) {
  const { gl } = useThree();

  useEffect(() => {
    const canvasEl = gl.domElement;
    if (!canvasEl) return;

    const handleContextLost = (event) => {
      event.preventDefault(); // Stop standard recovery, we will handle it gracefully
      console.warn("WebGL Context Lost caught in 3D Canvas! Falling back to static image.");
      onContextLost();
    };

    canvasEl.addEventListener('webglcontextlost', handleContextLost);
    return () => {
      canvasEl.removeEventListener('webglcontextlost', handleContextLost);
    };
  }, [gl, onContextLost]);

  return null;
}

// Camera controller that wiggles (parallax) and flies into the click target
function CameraController({ zoomTarget, mouseEnabled }) {
  const { camera, mouse } = useThree();
  const currentRotation = useRef(new THREE.Euler(0, 0, 0));

  useFrame((state) => {
    // 1. Zoom and Pan Animation
    if (zoomTarget) {
      // Calculate 3D target coordinate from normalized x, y
      const targetX = (zoomTarget.x - 0.5) * 16;
      const targetY = (0.5 - zoomTarget.y) * 9;
      const targetZ = 1.2; // Deep zoom in distance

      // Smoothly zoom/pan camera into target
      camera.position.x = THREE.MathUtils.lerp(camera.position.x, targetX, 0.08);
      camera.position.y = THREE.MathUtils.lerp(camera.position.y, targetY, 0.08);
      camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetZ, 0.08);

      // Lock rotation during deep zoom
      camera.rotation.x = THREE.MathUtils.lerp(camera.rotation.x, 0, 0.1);
      camera.rotation.y = THREE.MathUtils.lerp(camera.rotation.y, 0, 0.1);
    } else {
      // Smoothly reset camera position to default home
      camera.position.x = THREE.MathUtils.lerp(camera.position.x, 0, 0.05);
      camera.position.y = THREE.MathUtils.lerp(camera.position.y, 0, 0.05);
      camera.position.z = THREE.MathUtils.lerp(camera.position.z, 8.5, 0.05);

      // 2. Parallax Wiggle (only when not deep-zoomed)
      if (mouseEnabled) {
        const targetRotX = mouse.y * 0.12; // Vertical tilt
        const targetRotY = -mouse.x * 0.12; // Horizontal tilt (inverted for correct parallax feel)

        currentRotation.current.x = THREE.MathUtils.lerp(currentRotation.current.x, targetRotX, 0.08);
        currentRotation.current.y = THREE.MathUtils.lerp(currentRotation.current.y, targetRotY, 0.08);

        camera.rotation.x = currentRotation.current.x;
        camera.rotation.y = currentRotation.current.y;
      } else {
        camera.rotation.x = THREE.MathUtils.lerp(camera.rotation.x, 0, 0.05);
        camera.rotation.y = THREE.MathUtils.lerp(camera.rotation.y, 0, 0.05);
      }
    }
  });

  return null;
}

// The core 2.5D displacement mesh
function ParallaxPlane({ imageUrl, depthUrl, onImageClick, onTriggerZoom, displacementScale = 0.3 }) {
  const meshRef = useRef();

  // Load textures
  // We use useTexture which loads textures inside Suspense
  const colorTexture = useTexture(imageUrl);
  const depthTexture = useTexture(depthUrl || imageUrl); // fallback if depthUrl is missing

  // Configure textures for sharp, professional rendering
  useEffect(() => {
    if (colorTexture) {
      colorTexture.minFilter = THREE.LinearFilter;
      colorTexture.generateMipmaps = false;
    }
    if (depthTexture) {
      depthTexture.minFilter = THREE.LinearFilter;
      depthTexture.generateMipmaps = false;
    }
  }, [colorTexture, depthTexture]);

  const handleMeshClick = (e) => {
    e.stopPropagation();
    if (!e.uv) return;
    const x = e.uv.x;
    const y = 1.0 - e.uv.y;

    // Trigger visual zoom animation inside R3F
    if (onTriggerZoom) {
      onTriggerZoom({ x, y });
    }

    // Call parents standard canvas click handler
    if (onImageClick) {
      onImageClick({ clientX: e.nativeEvent.clientX, clientY: e.nativeEvent.clientY, syntheticCoords: { x, y } });
    }
  };

  return (
    <mesh ref={meshRef} onClick={handleMeshClick}>
      {/* 16:9 Aspect Ratio plane with dense vertices for smooth depth deformation */}
      <planeGeometry args={[16, 9, 128, 128]} />
      <meshStandardMaterial
        map={colorTexture}
        displacementMap={depthUrl ? depthTexture : undefined}
        displacementScale={depthUrl ? displacementScale : 0}
        displacementBias={0}
        roughness={0.65}
        metalness={0.05}
      />
    </mesh>
  );
}

export function ParallaxScene({ imageUrl, depthUrl, onImageClick, isStreaming, className, style }) {
  const [hasWebGL, setHasWebGL] = useState(true);
  const [zoomTarget, setZoomTarget] = useState(null);

  // Check if WebGL is supported by the browser
  useEffect(() => {
    try {
      const canvas = document.createElement('canvas');
      const isSupported = !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
      setHasWebGL(isSupported);
    } catch (e) {
      setHasWebGL(false);
    }
  }, []);

  // Reset camera zoom whenever the image changes (i.e. we navigated to a new page)
  useEffect(() => {
    setZoomTarget(null);
  }, [imageUrl]);

  if (!hasWebGL) {
    return <StaticFallback imageUrl={imageUrl} className={className} style={style} />;
  }

  const fallback = <StaticFallback imageUrl={imageUrl} className={className} style={style} />;

  return (
    <div className={className} style={{ ...style, width: '100%', aspectRatio: '16/9', borderRadius: '12px', overflow: 'hidden', position: 'relative', opacity: isStreaming ? 0.6 : 1 }}>
      <CanvasErrorBoundary imageUrl={imageUrl} fallback={fallback}>
        <Suspense fallback={fallback}>
          <Canvas
            camera={{ position: [0, 0, 8.5], fov: 60 }}
            gl={{ antialias: true, alpha: true, toneMapping: THREE.NoToneMapping }}
            style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
          >
            {/* Subtle lighting to reveal the 3D displacement shapes */}
            <ambientLight intensity={1.1} />
            <directionalLight position={[3, 4, 6]} intensity={1.4} />
            <pointLight position={[-4, -3, 3]} intensity={0.4} />
            
            <ContextLostHandler onContextLost={() => setHasWebGL(false)} />
            <CameraController zoomTarget={zoomTarget} mouseEnabled={!isStreaming} />
            
            <ParallaxPlane 
              imageUrl={imageUrl} 
              depthUrl={depthUrl} 
              onImageClick={onImageClick}
              onTriggerZoom={setZoomTarget}
            />
          </Canvas>
        </Suspense>
      </CanvasErrorBoundary>
    </div>
  );
}

export default ParallaxScene;
