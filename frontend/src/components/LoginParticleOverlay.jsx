import { useEffect, useRef } from "react";

const PARTICLE_LIMIT = 56;
const PARTICLE_COLORS = ["183, 229, 222", "118, 198, 188", "239, 165, 111"];

export function LoginParticleOverlay() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const host = canvas?.parentElement;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!canvas || !host || reduceMotion.matches) return undefined;

    const context = canvas.getContext("2d");
    const particles = [];
    const pointer = { active: false, x: 0, y: 0 };
    const previousPointer = { x: 0, y: 0 };
    let frame = 0;
    let width = 0;
    let height = 0;
    let previousTime = performance.now();

    function resize() {
      const rect = host.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    }

    function scheduleFrame() {
      if (!frame) frame = window.requestAnimationFrame(drawFrame);
    }

    function spawnParticles(x, y) {
      const count = particles.length < 20 ? 3 : 2;
      for (let index = 0; index < count && particles.length < PARTICLE_LIMIT; index += 1) {
        const angle = Math.random() * Math.PI * 2;
        const speed = 10 + Math.random() * 22;
        particles.push({
          x: x + (Math.random() - 0.5) * 9,
          y: y + (Math.random() - 0.5) * 9,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed - 4,
          radius: 0.9 + Math.random() * 1.6,
          life: 0,
          duration: 0.8 + Math.random() * 0.7,
          color: PARTICLE_COLORS[Math.floor(Math.random() * PARTICLE_COLORS.length)],
        });
      }
    }

    function drawPointerGlow() {
      if (!pointer.active) return;
      const gradient = context.createRadialGradient(pointer.x, pointer.y, 0, pointer.x, pointer.y, 52);
      gradient.addColorStop(0, "rgba(176, 229, 221, 0.16)");
      gradient.addColorStop(0.45, "rgba(122, 205, 194, 0.07)");
      gradient.addColorStop(1, "rgba(122, 205, 194, 0)");
      context.fillStyle = gradient;
      context.beginPath();
      context.arc(pointer.x, pointer.y, 52, 0, Math.PI * 2);
      context.fill();
    }

    function drawFrame(time) {
      frame = 0;
      const delta = Math.min((time - previousTime) / 1000, 0.05);
      previousTime = time;
      context.clearRect(0, 0, width, height);
      drawPointerGlow();

      for (let index = particles.length - 1; index >= 0; index -= 1) {
        const particle = particles[index];
        particle.life += delta;
        if (particle.life >= particle.duration) {
          particles.splice(index, 1);
          continue;
        }
        particle.x += particle.vx * delta;
        particle.y += particle.vy * delta;
        particle.vx *= 0.985;
        particle.vy *= 0.985;
        const opacity = (1 - particle.life / particle.duration) * 0.72;
        context.fillStyle = `rgba(${particle.color}, ${opacity})`;
        context.beginPath();
        context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
        context.fill();
      }

      if (pointer.active || particles.length) scheduleFrame();
    }

    function handlePointerMove(event) {
      const rect = host.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const distance = Math.hypot(x - previousPointer.x, y - previousPointer.y);
      pointer.active = true;
      pointer.x = x;
      pointer.y = y;
      if (distance > 7) {
        spawnParticles(x, y);
        previousPointer.x = x;
        previousPointer.y = y;
      }
      scheduleFrame();
    }

    function handlePointerLeave() {
      pointer.active = false;
      scheduleFrame();
    }

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    host.addEventListener("pointermove", handlePointerMove);
    host.addEventListener("pointerleave", handlePointerLeave);

    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      host.removeEventListener("pointermove", handlePointerMove);
      host.removeEventListener("pointerleave", handlePointerLeave);
    };
  }, []);

  return <canvas className="login-particle-canvas" ref={canvasRef} aria-hidden="true" />;
}
