import React, { useState, useEffect, useRef } from 'react';

export function FlipbookPlayer({ videoUrl, imageUrl, onVideoEnded, className, style }) {
  const [isPlaying, setIsPlaying] = useState(!!videoUrl);
  const videoRef = useRef(null);

  // When a new transition video is received, reset and play it
  useEffect(() => {
    if (videoUrl) {
      setIsPlaying(true);
      if (videoRef.current) {
        videoRef.current.load();
        videoRef.current.play().catch(err => {
          console.warn("Auto-play failed, falling back instantly to static image:", err);
          setIsPlaying(false);
          if (onVideoEnded) onVideoEnded();
        });
      }
    } else {
      setIsPlaying(false);
      if (onVideoEnded) onVideoEnded();
    }
  }, [videoUrl]);

  const handleEnded = () => {
    setIsPlaying(false);
    if (onVideoEnded) {
      onVideoEnded();
    }
  };

  if (!videoUrl || !isPlaying) {
    return (
      <img 
        src={imageUrl} 
        className={className} 
        alt="Drill down visualization" 
        style={{ ...style, display: 'block', width: '100%', aspectRatio: '16/9', borderRadius: '12px' }} 
      />
    );
  }

  return (
    <video
      ref={videoRef}
      src={videoUrl}
      className={className}
      style={{ ...style, display: 'block', width: '100%', aspectRatio: '16/9', borderRadius: '12px', objectFit: 'cover' }}
      autoPlay
      muted
      playsInline
      onEnded={handleEnded}
      onError={(e) => {
        console.error("Video playback error. Falling back to static image:", e);
        setIsPlaying(false);
        if (onVideoEnded) onVideoEnded();
      }}
    />
  );
}

export default FlipbookPlayer;
