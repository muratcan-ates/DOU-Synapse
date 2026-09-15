import Image from "next/image";
import styles from "./synapse-illustration.module.css";

const ART = {
  neuron: {
    light: "/brand/art/neuron-light.svg",
    dark: "/brand/art/neuron-dark.svg",
    sizes: "(min-width: 1536px) 720px, (min-width: 1024px) 52vw, 100vw",
  },
  hands: {
    light: "/brand/art/hands-light.png",
    dark: "/brand/art/hands-dark.png",
    sizes: "(min-width: 1800px) 1480px, (min-width: 1024px) calc(100vw - 320px), calc(100vw - 32px)",
  },
} as const;

/** Sanat dekoratiftir; tema ve boyut değişirken işlevsel içerik resme taşınmaz. */
export function SynapseIllustration({
  variant,
  className = "",
  prominent = false,
}: {
  variant: keyof typeof ART;
  className?: string;
  prominent?: boolean;
}) {
  const art = ART[variant];
  return (
    <div aria-hidden="true" className={`${styles.frame} ${styles[variant]} ${className}`}>
      {/* Lazy yükleme, CSS ile gizli olan diğer tema görselini indirmeyi önler. */}
      <Image src={art.light} alt="" fill sizes={art.sizes} fetchPriority={prominent ? "high" : undefined} className={`${styles.image} ${styles.light}`} />
      <Image src={art.dark} alt="" fill sizes={art.sizes} fetchPriority={prominent ? "high" : undefined} className={`${styles.image} ${styles.dark}`} />
    </div>
  );
}
