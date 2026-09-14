"use client";

import { useRef, type ReactNode } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { useReducedMotionPreference } from "@/components/accessibility-provider";

gsap.registerPlugin(useGSAP);

export function CampusMotion({
  children,
  route,
}: {
  children: ReactNode;
  route: string;
}) {
  const surface = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotionPreference();

  useGSAP(
    () => {
      if (reducedMotion) return;
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.fromTo(
          surface.current,
          { opacity: 0.65 },
          { opacity: 1, duration: 0.3, ease: "power1.out", clearProps: "opacity" },
        );
      });
      return () => media.revert();
    },
    { scope: surface, dependencies: [route, reducedMotion], revertOnUpdate: true },
  );

  return <div ref={surface} className="min-w-0">{children}</div>;
}
